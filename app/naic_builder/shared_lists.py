"""Reusable dropdown choices. Record answers remain stored text snapshots."""
from __future__ import annotations

from copy import deepcopy
import re
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .models import FormDefinition, SharedChoiceItem, SharedChoiceList, utc_now


class SharedListConflict(ValueError):
    pass


def clean_name(value: str, limit: int = 200) -> str:
    name = re.sub(r"\s+", " ", value or "").strip()
    if not name or len(name) > limit:
        raise ValueError(f"Enter a name between 1 and {limit} characters.")
    return name


def get_shared_list(session: Session, list_id: int, *, include_deleted: bool = False) -> SharedChoiceList | None:
    query = select(SharedChoiceList).where(SharedChoiceList.id == list_id)
    if not include_deleted:
        query = query.where(SharedChoiceList.deleted.is_(False))
    return session.scalar(query.options(selectinload(SharedChoiceList.items)))


def list_shared_lists(session: Session) -> list[dict]:
    lists = session.scalars(select(SharedChoiceList).where(SharedChoiceList.deleted.is_(False)).options(selectinload(SharedChoiceList.items))).all()
    return [serialize_shared_list(item) for item in sorted(lists, key=lambda row: row.name.casefold())]


def serialize_shared_list(item: SharedChoiceList) -> dict:
    choices = [{"id": row.id, "name": row.name, "active": row.active}
               for row in sorted(item.items, key=lambda row: (row.name.casefold(), row.id))]
    return {"id": item.id, "name": item.name, "revision": item.revision, "seed_key": item.seed_key, "items": choices,
            "active_count": sum(row["active"] for row in choices)}


def create_shared_list(session: Session, name: str) -> SharedChoiceList:
    name = clean_name(name, 160)
    item = SharedChoiceList(name=name, name_key=name.casefold())
    session.add(item)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError("A list with this name already exists.") from exc
    return get_shared_list(session, item.id)


def change_shared_list(session: Session, list_id: int, revision: int, action: str, *, name: str = "", item_id: int = 0) -> None:
    choice_list = get_shared_list(session, list_id)
    if choice_list is None:
        raise KeyError(list_id)
    item = next((row for row in choice_list.items if row.id == item_id), None)
    if action not in {"rename_list", "add", "rename", "deactivate", "reactivate", "delete_choice", "delete_list"}:
        raise ValueError("Choose a valid list action.")
    if action in {"rename", "deactivate", "reactivate", "delete_choice"} and item is None:
        raise ValueError("This choice is no longer available. Reload the list.")
    if action in {"rename_list", "add", "rename"}:
        name = clean_name(name, 160 if action == "rename_list" else 200)
    changed = session.execute(update(SharedChoiceList).where(
        SharedChoiceList.id == list_id, SharedChoiceList.revision == revision, SharedChoiceList.deleted.is_(False)
    ).values(revision=SharedChoiceList.revision + 1, updated_at=utc_now()))
    if changed.rowcount != 1:
        session.rollback()
        raise SharedListConflict("This list was updated elsewhere. Reload it before saving your change.")
    if action == "rename_list":
        choice_list.name, choice_list.name_key = name, name.casefold()
    elif action == "delete_list":
        if shared_list_usage(session, list_id):
            session.rollback()
            raise ValueError("This list is still connected to a form. Switch those fields to own choices or another shared list before deleting it.")
        # Keep only its identity/seed marker: historical references cannot be
        # reassigned to a new list, and startup must not recreate a deleted list.
        choice_list.items.clear()
        choice_list.name = ""
        choice_list.name_key = f"deleted:{uuid4().hex}"
        choice_list.deleted = True
    elif action == "delete_choice":
        session.delete(item)
    elif action == "add":
        session.add(SharedChoiceItem(list_id=list_id, name=name, name_key=name.casefold()))
    elif action == "rename":
        item.name, item.name_key = name, name.casefold()
    else:
        item.active = action == "reactivate"
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError("This name already exists. Check the inactive choices too.") from exc


def field_blocks(schema: dict):
    def walk(nodes):
        for node in nodes or []:
            if not isinstance(node, dict):
                continue
            if node.get("kind") == "field":
                yield node
            yield from walk(node.get("children"))
    yield from walk(schema.get("blocks"))


def resolve_shared_choices(session: Session, schema: dict, *, validate: bool = False, fallback_schema: dict | None = None) -> dict:
    """Return an editor copy; never change the frozen form or the record's values."""
    resolved = deepcopy(schema)
    # Older records can use a newly connected list by stable field ID. This
    # affects only the editor copy, never their original form or printed report.
    current_fields = {field.get("id"): field for field in field_blocks(fallback_schema or {})}
    cache = {}
    for field in field_blocks(resolved):
        props = field.get("props") or {}
        if "shared_list_id" not in props and props.get("control") == "select":
            current_props = (current_fields.get(field.get("id"), {}).get("props") or {})
            if current_props.get("control") == "select" and current_props.get("shared_list_id"):
                props["shared_list_id"] = current_props["shared_list_id"]
        list_id = props.get("shared_list_id")
        if list_id is None:
            continue
        if type(list_id) is not int or list_id < 1 or props.get("control") != "select":
            if validate:
                raise ValueError("Shared lists can only be used with dropdown fields. Choose a valid list.")
            continue
        if list_id not in cache:
            if validate:
                # SQLite serializes writers. Hold the list until the form save
                # commits, so deleting a list cannot race a new field binding.
                session.execute(update(SharedChoiceList).where(
                    SharedChoiceList.id == list_id, SharedChoiceList.deleted.is_(False)
                ).values(revision=SharedChoiceList.revision))
            cache[list_id] = get_shared_list(session, list_id, include_deleted=True)
        choice_list = cache[list_id]
        if choice_list is None or choice_list.deleted:
            if validate:
                raise ValueError("A selected shared list could not be found. Choose another list or use own choices.")
            if choice_list is not None and choice_list.deleted:
                props["options"] = []
            continue
        normal_names = {option.get("name") for option in props.get("options", []) if isinstance(option, dict) and option.get("is_normal")}
        props["options"] = [{"name": row.name, "key": f"shared_{row.id}", "order": index,
                             "is_normal": row.name in normal_names}
                            for index, row in enumerate(sorted(choice_list.items, key=lambda row: row.name.casefold()), 1) if row.active]
    return resolved


def shared_list_usage(session: Session, list_id: int) -> list[dict]:
    from .services import current_version, load_block_storage_document
    result = []
    for form in session.scalars(select(FormDefinition).options(selectinload(FormDefinition.versions)).order_by(FormDefinition.name)).all():
        version = current_version(form)
        if not version:
            continue
        schema, _ = load_block_storage_document(version)
        fields = [field["name"] for field in field_blocks(schema) if (field.get("props") or {}).get("shared_list_id") == list_id]
        if fields:
            result.append({"slug": form.slug, "name": form.name, "fields": fields})
    return result


def ensure_standard_shared_lists(session: Session) -> int:
    """Connect only recognizable standard patient fields, once, using new versions.

    Import the union of existing choices without touching records or old versions.
    Custom fields retain their own choices until explicitly connected in the builder.
    """
    from .services import current_version, load_block_storage_document, build_form_version_record
    definitions = session.scalars(select(FormDefinition).options(selectinload(FormDefinition.versions))).all()
    documents = {}
    for form in definitions:
        version = current_version(form)
        if version:
            documents[form.id] = (form, version, load_block_storage_document(version)[0])
    changed_forms = set()
    for key, name in [("requesting_physician", "Requesting physicians"), ("room", "Rooms")]:
        seed_key = f"standard_patient_{key}_v1"
        if session.scalar(select(SharedChoiceList.id).where(SharedChoiceList.seed_key == seed_key)):
            continue
        matches = []
        names = {}
        for form_id, (_, _, schema) in documents.items():
            for field in field_blocks(schema):
                props = field.get("props") or {}
                if (str(field.get("id", "")).endswith(f".patient_information.{key}")
                        and props.get("control") == "select" and not props.get("shared_list_id")):
                    matches.append((form_id, props))
                    for option in props.get("options", []):
                        if isinstance(option, dict) and str(option.get("name", "")).strip():
                            label = clean_name(option["name"], max(200, len(option["name"])))
                            names.setdefault(label.casefold(), label)
        if not matches:
            continue
        # A user-created list with the same name is not silently repurposed.
        list_name = name
        suffix = 1
        while session.scalar(select(SharedChoiceList.id).where(SharedChoiceList.name_key == list_name.casefold())):
            list_name = f"{name} (existing forms {suffix})"
            suffix += 1
        choice_list = SharedChoiceList(name=list_name, name_key=list_name.casefold(), seed_key=seed_key)
        session.add(choice_list)
        session.flush()
        for label in names.values():
            session.add(SharedChoiceItem(list_id=choice_list.id, name=label, name_key=label.casefold()))
        for form_id, props in matches:
            props["shared_list_id"] = choice_list.id
            changed_forms.add(form_id)
    for form_id in changed_forms:
        form, previous, schema = documents[form_id]
        previous.is_current = False
        session.add(build_form_version_record(form_id=form.id, version_number=previous.version_number + 1,
                    summary="Connected standard dropdowns to shared lists; historical records retained.",
                    block_storage_schema=schema, source="builder", is_current=True))
        form.updated_at = utc_now()
    if changed_forms:
        session.commit()
        session.expire_all()
    return len(changed_forms)
