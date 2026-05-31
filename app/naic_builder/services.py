from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
from pathlib import Path
from datetime import timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .config import (
    CLINIC_UPLOADS_DIR,
    ORGANIZATION_SHORT_NAME,
    RECORD_UPLOADS_DIR,
    REFERENCE_SCHEMA_PATH,
    SIGNATORY_UPLOADS_DIR,
    USER_UPLOADS_DIR,
)
from .database import Base, engine
from .models import ClinicProfile, FormDefinition, FormVersion, LibraryNode, Record, RecordAsset, User, utc_now
from .schemas import (
    AccountRequestPayload,
    ClinicProfilePayload,
    FormSavePayload,
    LoginPayload,
    PasswordChangePayload,
    RecordCreatePayload,
    RecordUpdatePayload,
    SetupAdminPayload,
    UserCreatePayload,
)

ACTIVE_BLOCK_SCHEMA_SOURCE = "builder_blocks_v1"
LEGACY_BLOCK_SCHEMA_SOURCE = "compat_legacy_fields_sections"
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_RECORD_IMAGE_BYTES = 10 * 1024 * 1024
MAX_CLINIC_LOGO_BYTES = 5 * 1024 * 1024
MAX_USER_AVATAR_BYTES = 2 * 1024 * 1024
MAX_SIGNATORY_STAMP_BYTES = 5 * 1024 * 1024
DEFAULT_PRINT_ACCENT_COLOR = "#1e5d52"
DEFAULT_PRINT_ACCENT_MIGRATED_META_KEY = "print_accent_default_migrated"
DEFAULT_PRINT_ACCENT_COLORS_BY_FORM_KEY = {
    "abg": "#8064a2",
    "blood_bank": "#cc3399",
    "blood_gas_analysis": "#8064a2",
    "cardiac": "#f79646",
    "cardiaci": "#f79646",
    "coag": "#c0504d",
    "covid_19_antigen_rapid_test": "#f79646",
    "fecalysis": "#4bacc6",
    "female": "#9bbb59",
    "hba1c": "#9bbb59",
    "hba1ci": "#9bbb59",
    "hematology": "#c0504d",
    "hiv_1_and_2_testing": "#f79646",
    "hscrp": "#f79646",
    "male": "#9bbb59",
    "microbiology": "#000000",
    "ogtt": "#9bbb59",
    "pro_time_aptt": "#c0504d",
    "semen": "#00b0f0",
    "serology": "#f79646",
    "serologyi": "#f79646",
    "urinalysis": "#ffff66",
    "urine": "#ffff66",
}
PRINT_SUMMARY_SOURCES = {
    "field",
    "primary_identity",
    "secondary_identity",
    "record_key",
    "issued_at",
    "form_version",
}
PRINT_SIGNATURE_SOURCES = {"blank", "prepared_by", "manual", "field"}
PRINT_FONT_FAMILIES = {
    "arial",
    "arial_narrow",
    "aptos",
    "segoe_ui",
    "cambria_title",
    "georgia_title",
    "times_new_roman",
    "bahnschrift_title",
}
DEFAULT_PRINT_SUMMARY_ITEMS = [
    {"id": "summary_primary", "label": "Record", "source": "primary_identity", "field_id": ""},
    {"id": "summary_secondary", "label": "Detail", "source": "secondary_identity", "field_id": ""},
    {"id": "summary_issued", "label": "Issued", "source": "issued_at", "field_id": ""},
    {"id": "summary_version", "label": "Form version", "source": "form_version", "field_id": ""},
]
DEFAULT_LAB_REQUEST_FIELD_SET_ID = "default_lab_request"
DEFAULT_PATIENT_INFO_MATERIALIZED_META_KEY = "default_patient_info_materialized"
PATIENT_INFO_GROUP_KEY = "patient_information"
PATIENT_INFO_GROUP_NAME = "Patient Information"
PATIENT_INFO_PRIMARY_KEY = "name"
PATIENT_INFO_SECONDARY_KEY = "case_number"
PATIENT_INFO_REQUIRED_KEYS = {PATIENT_INFO_PRIMARY_KEY, PATIENT_INFO_SECONDARY_KEY}
SIGNATORY_FIELD_KEYS = {"medical_technologist", "pathologist"}
SIGNATORY_INPUT_TYPES = {"person_dropdown", "manual", "fixed", "blank", "stamp_image"}
DEFAULT_MEDTECH_SIGNATORY_PEOPLE = [
    {"id": "imelda_a_elemia", "name": "Imelda A. Elemia, RMT", "license": "0036643"},
    {"id": "crystel_c_tesoro", "name": "Crystel C. Tesoro, RMT", "license": "0103760"},
    {"id": "ma_jesusa_b_vite", "name": "Ma. Jesusa B. Vite, RMT", "license": "0118710"},
    {"id": "andrea_coleen_a_avellones", "name": "Andrea Coleen A. Avellones, RMT", "license": "0119501"},
    {"id": "julie_kyle_a_ronato", "name": "Julie Kyle A. Ronato, RMT", "license": "0119616"},
    {"id": "shiela_mae_d_libradilla", "name": "Shiela Mae D. Libradilla, RMT", "license": "0135995"},
]
DEFAULT_PATHOLOGIST_SIGNATORY_PEOPLE = [
    {
        "id": "bernardita_mojica_figueroa",
        "name": "Bernardita Mojica Figueroa, MD, DPSP",
        "license": "068053",
    },
]


def load_reference_schema() -> dict[str, Any]:
    return json.loads(REFERENCE_SCHEMA_PATH.read_text(encoding="utf-8"))




def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or "item"


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_email(value: Any) -> str:
    return compact_text(value).lower()


def normalize_login_id(value: Any) -> str:
    return slugify(compact_text(value))


def validate_email_format(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def validate_role(value: Any) -> str:
    role = compact_text(value).lower()
    return role if role in {"admin", "medtech"} else "medtech"


def validate_user_status(value: Any) -> str:
    status = compact_text(value).lower()
    return status if status in {"pending", "active", "disabled"} else "pending"


def normalize_print_accent_color(value: Any) -> str:
    text = compact_text(value)
    return text.lower() if re.fullmatch(r"#[0-9a-fA-F]{6}", text) else DEFAULT_PRINT_ACCENT_COLOR


def form_key_from_meta(meta: dict[str, Any]) -> str:
    raw_key = compact_text(meta.get("form_key")) or compact_text(meta.get("form_id"))
    if raw_key.startswith("form."):
        raw_key = raw_key[5:]
    return slugify(raw_key)


def default_print_accent_color_for_form_key(form_key: Any) -> str:
    return DEFAULT_PRINT_ACCENT_COLORS_BY_FORM_KEY.get(slugify(compact_text(form_key)), DEFAULT_PRINT_ACCENT_COLOR)


def print_accent_text_color(value: Any) -> str:
    color = normalize_print_accent_color(value).lstrip("#")
    red = int(color[0:2], 16)
    green = int(color[2:4], 16)
    blue = int(color[4:6], 16)

    def linear_channel(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    luminance = (
        0.2126 * linear_channel(red)
        + 0.7152 * linear_channel(green)
        + 0.0722 * linear_channel(blue)
    )
    contrast_with_dark = (luminance + 0.05) / 0.05
    contrast_with_light = 1.05 / (luminance + 0.05)
    return "#171512" if contrast_with_dark >= contrast_with_light else "#ffffff"


def ensure_form_default_print_accent(meta: dict[str, Any]) -> bool:
    form_key = form_key_from_meta(meta)
    default_accent = default_print_accent_color_for_form_key(form_key)
    if default_accent == DEFAULT_PRINT_ACCENT_COLOR:
        return False

    raw_config = meta.get("print_config") if isinstance(meta.get("print_config"), dict) else {}
    print_config = normalize_print_config(raw_config)
    changed = print_config != raw_config
    already_migrated = bool(meta.get(DEFAULT_PRINT_ACCENT_MIGRATED_META_KEY))

    if not already_migrated and print_config.get("accent_color") == DEFAULT_PRINT_ACCENT_COLOR:
        print_config["accent_color"] = default_accent
        meta[DEFAULT_PRINT_ACCENT_MIGRATED_META_KEY] = True
        changed = True
    elif not already_migrated and print_config.get("accent_color") != DEFAULT_PRINT_ACCENT_COLOR:
        meta[DEFAULT_PRINT_ACCENT_MIGRATED_META_KEY] = True
        changed = True

    if changed:
        meta["print_config"] = print_config
    return changed


def normalize_print_density(value: Any) -> str:
    density = compact_text(value).lower()
    return density if density in {"compact", "comfortable"} else "compact"


def normalize_print_image_size(value: Any) -> str:
    size = compact_text(value).lower()
    return size if size in {"small", "medium", "large"} else "medium"


def normalize_print_table_density(value: Any) -> str:
    density = compact_text(value).lower()
    return density if density in {"compact", "comfortable"} else "compact"


def normalize_print_result_layout(value: Any) -> str:
    layout = compact_text(value).lower()
    return layout if layout in {"rows", "compact_grid"} else "compact_grid"


def normalize_print_font_family(value: Any) -> str:
    font_family = compact_text(value).lower().replace("-", "_").replace(" ", "_")
    return font_family if font_family in PRINT_FONT_FAMILIES else "arial_narrow"


def normalize_print_signature_source(value: Any, *, default: str = "blank") -> str:
    source = compact_text(value).lower()
    fallback = default if default in PRINT_SIGNATURE_SOURCES else "blank"
    return source if source in PRINT_SIGNATURE_SOURCES else fallback


def normalize_boolean_setting(value: Any, *, default: bool = True) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, str):
        return compact_text(value).lower() not in {"0", "false", "no", "off"}
    return bool(value)


def default_print_summary_label(source: str) -> str:
    return {
        "primary_identity": "Record",
        "secondary_identity": "Detail",
        "record_key": "Record key",
        "issued_at": "Issued",
        "form_version": "Form version",
        "field": "Field",
    }.get(source, "Field")


def normalize_print_summary_item(item: Any, index: int) -> dict[str, str]:
    raw_item = item if isinstance(item, dict) else {}
    source = compact_text(raw_item.get("source")).lower()
    if source not in PRINT_SUMMARY_SOURCES:
        source = "field"
    field_id = compact_text(raw_item.get("field_id")) if source == "field" else ""
    label = compact_text(raw_item.get("label")) or default_print_summary_label(source)
    return {
        "id": compact_text(raw_item.get("id")) or f"summary_{index + 1}",
        "label": label,
        "source": source,
        "field_id": field_id,
    }


def normalize_print_config(raw_config: Any) -> dict[str, Any]:
    config = raw_config if isinstance(raw_config, dict) else {}
    summary_items = [
        normalize_print_summary_item(item, index)
        for index, item in enumerate(normalize_items(config.get("summary_items")))
    ]
    if not summary_items:
        summary_items = [dict(item) for item in DEFAULT_PRINT_SUMMARY_ITEMS]

    return {
        "accent_color": normalize_print_accent_color(config.get("accent_color")),
        "density": normalize_print_density(config.get("density")),
        "font_family": normalize_print_font_family(config.get("font_family")),
        "show_logo": normalize_boolean_setting(config.get("show_logo"), default=True),
        "show_clinic_info": normalize_boolean_setting(config.get("show_clinic_info"), default=True),
        "show_status": normalize_boolean_setting(config.get("show_status"), default=True),
        "show_summary": normalize_boolean_setting(config.get("show_summary"), default=False),
        "show_signatures": normalize_boolean_setting(config.get("show_signatures"), default=True),
        "hide_empty_fields": normalize_boolean_setting(config.get("hide_empty_fields"), default=False),
        "show_section_titles": normalize_boolean_setting(config.get("show_section_titles"), default=True),
        "show_group_titles": normalize_boolean_setting(config.get("show_group_titles"), default=True),
        "image_size": normalize_print_image_size(config.get("image_size")),
        "table_density": normalize_print_table_density(config.get("table_density")),
        "result_layout": normalize_print_result_layout(config.get("result_layout")),
        "signature_left_label": compact_text(config.get("signature_left_label")) or "Medical Technologist",
        "signature_left_source": normalize_print_signature_source(config.get("signature_left_source"), default="prepared_by"),
        "signature_left_name": compact_text(config.get("signature_left_name")),
        "signature_left_field_id": compact_text(config.get("signature_left_field_id")),
        "signature_right_label": compact_text(config.get("signature_right_label")) or "Pathologist",
        "signature_right_source": normalize_print_signature_source(config.get("signature_right_source"), default="blank"),
        "signature_right_name": compact_text(config.get("signature_right_name")),
        "signature_right_field_id": compact_text(config.get("signature_right_field_id")),
        "summary_items": summary_items,
    }


def password_hash_value(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 120_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${iterations}${salt}${digest}".format(
        iterations=iterations,
        salt=base64.b64encode(salt).decode("ascii"),
        digest=base64.b64encode(digest).decode("ascii"),
    )


def verify_password_hash(password_hash: str | None, password: str) -> bool:
    stored = compact_text(password_hash)
    if not stored:
        return False
    try:
        algorithm, iterations_text, salt_text, digest_text = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = base64.b64decode(salt_text.encode("ascii"))
        expected = base64.b64decode(digest_text.encode("ascii"))
    except (TypeError, ValueError, base64.binascii.Error):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def validate_password_strength(password: str) -> None:
    if len(password or "") < 8:
        raise ValueError("Use at least 8 characters for the password.")


def derive_login_id(*, full_name: str, email: str, requested_login_id: str = "") -> str:
    requested = normalize_login_id(requested_login_id)
    if requested:
        return requested
    email_local = normalize_email(email).split("@", 1)[0]
    email_candidate = normalize_login_id(email_local)
    if email_candidate:
        return email_candidate
    return normalize_login_id(full_name) or "user"


def next_available_login_id(session: Session, base_login_id: str) -> str:
    base = normalize_login_id(base_login_id) or "user"
    candidate = base
    suffix = 2
    while session.scalar(select(User.id).where(User.login_id == candidate)) is not None:
        candidate = f"{base}{suffix}"
        suffix += 1
    return candidate


def has_any_users(session: Session) -> bool:
    return session.scalar(select(User.id).limit(1)) is not None


def has_any_admin_users(session: Session) -> bool:
    return session.scalar(
        select(User.id).where(User.role == "admin", User.status == "active").limit(1)
    ) is not None


def count_active_admin_users(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count(User.id)).where(User.role == "admin", User.status == "active")
        )
        or 0
    )


def get_user_or_none(session: Session, user_id: int) -> User | None:
    return session.scalar(select(User).where(User.id == user_id))


def get_user_by_identifier(session: Session, identifier: str) -> User | None:
    normalized = compact_text(identifier).lower()
    if not normalized:
        return None
    return session.scalar(
        select(User).where(
            or_(
                func.lower(User.login_id) == normalized,
                func.lower(User.email) == normalized,
            )
        )
    )


def serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "login_id": user.login_id,
        "full_name": user.full_name,
        "role": user.role,
        "status": user.status,
        "must_change_password": bool(user.must_change_password),
        "avatar_path": user.avatar_path,
        "avatar_original_filename": compact_text(user.avatar_original_filename),
        "avatar_mime_type": compact_text(user.avatar_mime_type),
        "has_avatar": bool(compact_text(user.avatar_path)),
        "created_at": user.created_at.astimezone(timezone.utc).isoformat(),
        "updated_at": user.updated_at.astimezone(timezone.utc).isoformat(),
    }


def get_or_create_clinic_profile(session: Session) -> ClinicProfile:
    profile = session.scalar(select(ClinicProfile).limit(1))
    if profile is not None:
        return profile
    profile = ClinicProfile(clinic_name="")
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def serialize_clinic_profile(profile: ClinicProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "clinic_name": compact_text(profile.clinic_name),
        "address": compact_text(profile.address),
        "contact_number": compact_text(profile.contact_number),
        "contact_email": compact_text(profile.contact_email),
        "logo_path": profile.logo_path,
        "logo_original_filename": compact_text(profile.logo_original_filename),
        "logo_mime_type": compact_text(profile.logo_mime_type),
        "has_logo": bool(compact_text(profile.logo_path)),
        "created_at": profile.created_at.astimezone(timezone.utc).isoformat(),
        "updated_at": profile.updated_at.astimezone(timezone.utc).isoformat(),
    }


def get_clinic_profile(session: Session) -> dict[str, Any]:
    return serialize_clinic_profile(get_or_create_clinic_profile(session))


def list_users(session: Session, *, status: str | None = None) -> list[dict[str, Any]]:
    query = select(User).order_by(User.created_at.desc(), User.id.desc())
    normalized_status = validate_user_status(status) if compact_text(status) else ""
    if normalized_status:
        query = query.where(User.status == normalized_status)
    users = session.scalars(query).all()
    return [serialize_user(user) for user in users]


def count_users(session: Session, *, status: str | None = None) -> int:
    query = select(func.count(User.id))
    normalized_status = validate_user_status(status) if compact_text(status) else ""
    if normalized_status:
        query = query.where(User.status == normalized_status)
    return int(session.scalar(query) or 0)


def save_user(session: Session, user: User) -> User:
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError("This email or login ID is already in use.") from exc
    session.refresh(user)
    return user


def request_account(session: Session, payload: AccountRequestPayload) -> dict[str, Any]:
    full_name = compact_text(payload.full_name)
    email = normalize_email(payload.email)
    validate_password_strength(payload.password)
    if not full_name:
        raise ValueError("Enter the staff member's full name.")
    if not validate_email_format(email):
        raise ValueError("Enter a valid email address.")
    login_id = next_available_login_id(
        session,
        derive_login_id(full_name=full_name, email=email, requested_login_id=payload.login_id or ""),
    )
    user = User(
        email=email,
        login_id=login_id,
        full_name=full_name,
        role="medtech",
        status="pending",
        password_hash=password_hash_value(payload.password),
        must_change_password=False,
    )
    return serialize_user(save_user(session, user))


def create_initial_admin(session: Session, payload: SetupAdminPayload) -> dict[str, Any]:
    if has_any_users(session):
        raise ValueError("Initial setup is already complete.")
    full_name = compact_text(payload.full_name)
    email = normalize_email(payload.email)
    validate_password_strength(payload.password)
    if not full_name:
        raise ValueError("Enter the admin's full name.")
    if not validate_email_format(email):
        raise ValueError("Enter a valid email address.")
    login_id = next_available_login_id(
        session,
        derive_login_id(full_name=full_name, email=email, requested_login_id=payload.login_id or ""),
    )
    user = User(
        email=email,
        login_id=login_id,
        full_name=full_name,
        role="admin",
        status="active",
        password_hash=password_hash_value(payload.password),
        must_change_password=False,
    )
    return serialize_user(save_user(session, user))


def create_user_account(session: Session, payload: UserCreatePayload) -> dict[str, Any]:
    full_name = compact_text(payload.full_name)
    email = normalize_email(payload.email)
    validate_password_strength(payload.password)
    if not full_name:
        raise ValueError("Enter the staff member's full name.")
    if not validate_email_format(email):
        raise ValueError("Enter a valid email address.")
    login_id = next_available_login_id(
        session,
        derive_login_id(full_name=full_name, email=email, requested_login_id=payload.login_id or ""),
    )
    user = User(
        email=email,
        login_id=login_id,
        full_name=full_name,
        role=validate_role(payload.role),
        status="active",
        password_hash=password_hash_value(payload.password),
        must_change_password=True,
    )
    return serialize_user(save_user(session, user))


def approve_user_account(session: Session, user_id: int, *, role: str) -> dict[str, Any]:
    user = get_user_or_none(session, user_id)
    if user is None:
        raise KeyError(user_id)
    user.role = validate_role(role)
    user.status = "active"
    return serialize_user(save_user(session, user))


def update_user_status(session: Session, user_id: int, *, status: str) -> dict[str, Any]:
    user = get_user_or_none(session, user_id)
    if user is None:
        raise KeyError(user_id)
    next_status = validate_user_status(status)
    if next_status == "disabled" and user.role == "admin" and user.status == "active" and count_active_admin_users(session) <= 1:
        raise ValueError("Keep at least one active admin account.")
    user.status = next_status
    return serialize_user(save_user(session, user))


def update_user_admin_details(
    session: Session,
    user_id: int,
    *,
    full_name: str,
    role: str,
) -> dict[str, Any]:
    user = get_user_or_none(session, user_id)
    if user is None:
        raise KeyError(user_id)
    resolved_name = compact_text(full_name)
    if not resolved_name:
        raise ValueError("Enter the staff member's full name.")
    next_role = validate_role(role)
    if (
        user.role == "admin"
        and user.status == "active"
        and next_role != "admin"
        and count_active_admin_users(session) <= 1
    ):
        raise ValueError("Keep at least one active admin account.")
    user.full_name = resolved_name
    user.role = next_role
    return serialize_user(save_user(session, user))


def reset_user_password_by_admin(
    session: Session,
    user_id: int,
    *,
    temporary_password: str,
) -> dict[str, Any]:
    user = get_user_or_none(session, user_id)
    if user is None:
        raise KeyError(user_id)
    validate_password_strength(temporary_password)
    user.password_hash = password_hash_value(temporary_password)
    user.must_change_password = True
    return serialize_user(save_user(session, user))


def authenticate_user(session: Session, payload: LoginPayload) -> dict[str, Any]:
    user = get_user_by_identifier(session, payload.identifier)
    if user is None:
        raise ValueError("The email or login ID and password do not match.")
    if not verify_password_hash(user.password_hash, payload.password):
        raise ValueError("The email or login ID and password do not match.")
    if user.status == "pending":
        raise ValueError("This account is still waiting for admin approval.")
    if user.status == "disabled":
        raise ValueError("This account is currently disabled. Ask an admin for access.")
    if user.status != "active":
        raise ValueError("This account is not active yet.")
    return serialize_user(user)


def change_user_password(
    session: Session,
    user_id: int,
    payload: PasswordChangePayload,
    *,
    require_current_password: bool = True,
) -> dict[str, Any]:
    user = get_user_or_none(session, user_id)
    if user is None:
        raise KeyError(user_id)
    if require_current_password and not verify_password_hash(user.password_hash, payload.current_password):
        raise ValueError("The current password is incorrect.")
    validate_password_strength(payload.new_password)
    user.password_hash = password_hash_value(payload.new_password)
    user.must_change_password = False
    return serialize_user(save_user(session, user))


def normalize_items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_notes(raw_notes: Any) -> list[str]:
    notes: list[str] = []
    for note in raw_notes or []:
        text = compact_text(note)
        if text and text not in notes:
            notes.append(text)
    return notes


def unique_key(base: str, used: set[str]) -> str:
    key = slugify(base)
    candidate = key
    suffix = 2
    while candidate in used:
        candidate = f"{key}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def normalize_options(raw_options: Any, field_id: str) -> list[dict[str, Any]]:
    options = raw_options or []
    normalized: list[dict[str, Any]] = []
    used: set[str] = set()

    for index, option in enumerate(options, start=1):
        if isinstance(option, dict):
            name = compact_text(option.get("name"))
            key_source = compact_text(option.get("key")) or name
        else:
            name = compact_text(option)
            key_source = name
        if not name:
            continue
        key = unique_key(key_source, used)
        normalized.append(
            {
                "id": f"{field_id}.{key}",
                "key": key,
                "name": name,
                "order": index,
                "is_normal": bool(option.get("is_normal")) if isinstance(option, dict) else False,
            }
        )

    return normalized


def normalize_field(field: dict[str, Any], parent_id: str, order: int, used_keys: set[str]) -> dict[str, Any]:
    name = compact_text(field.get("name")) or f"Untitled Field {order}"
    key = unique_key(compact_text(field.get("key")) or name, used_keys)
    field_id = f"{parent_id}.{key}"
    kind = "field_group" if compact_text(field.get("kind")) == "field_group" else "field"

    normalized: dict[str, Any] = {
        "id": field_id,
        "key": key,
        "name": name,
        "kind": kind,
        "order": order,
    }

    notes = normalize_notes(field.get("notes"))
    if notes:
        normalized["notes"] = notes

    source = field.get("source")
    if isinstance(source, dict) and source:
        normalized["source"] = source

    if kind == "field_group":
        child_used: set[str] = set()
        normalized["fields"] = [
            normalize_field(child, field_id, child_order, child_used)
            for child_order, child in enumerate(field.get("fields") or [], start=1)
            if isinstance(child, dict)
        ]
        return normalized

    options = normalize_options(field.get("options"), field_id)
    control = compact_text(field.get("control")) or ("select" if options else "input")
    data_type = compact_text(field.get("data_type")) or ("enum" if control == "select" else "text")

    normalized["control"] = control
    normalized["data_type"] = data_type
    if bool(field.get("required")):
        normalized["required"] = True

    unit_hint = compact_text(field.get("unit_hint"))
    if unit_hint:
        normalized["unit_hint"] = unit_hint

    reference_text = compact_text(field.get("reference_text") or field.get("normal_value"))
    if reference_text:
        normalized["reference_text"] = reference_text
        normalized["normal_value"] = reference_text

    normal_min = compact_text(field.get("normal_min"))
    if normal_min:
        normalized["normal_min"] = normal_min

    normal_max = compact_text(field.get("normal_max"))
    if normal_max:
        normalized["normal_max"] = normal_max

    if options:
        normalized["options"] = options

    return normalized


def normalize_section(section: dict[str, Any], form_id: str, order: int, used_keys: set[str]) -> dict[str, Any]:
    name = compact_text(section.get("name")) or f"Untitled Section {order}"
    key = unique_key(compact_text(section.get("key")) or name, used_keys)
    section_id = f"{form_id}.{key}"
    field_used: set[str] = set()

    normalized: dict[str, Any] = {
        "id": section_id,
        "key": key,
        "name": name,
        "order": order,
        "fields": [
            normalize_field(field, section_id, field_order, field_used)
            for field_order, field in enumerate(section.get("fields") or [], start=1)
            if isinstance(field, dict)
        ],
    }

    notes = normalize_notes(section.get("notes"))
    if notes:
        normalized["notes"] = notes

    source = section.get("source")
    if isinstance(source, dict) and source:
        normalized["source"] = source

    return normalized


def normalize_signatory_option(raw_option: Any, index: int, slot_id: str) -> dict[str, Any] | None:
    option = raw_option if isinstance(raw_option, dict) else {"name": raw_option}
    name = compact_text(option.get("name"))
    if not name:
        return None
    key = slugify(compact_text(option.get("key")) or compact_text(option.get("id")) or name)
    option_id = compact_text(option.get("id")) or f"{slot_id}.{key}"
    license_text = compact_text(option.get("license") or option.get("license_no") or option.get("license_number"))
    if license_text.lower().startswith("lic. no:"):
        license_text = compact_text(license_text.split(":", 1)[1])
    return {
        "id": option_id,
        "key": key,
        "name": name,
        "title": compact_text(option.get("title")),
        "license": license_text,
        "order": int(option.get("order") or index),
    }


def default_signatory_options(slot_id: str, people: list[dict[str, str]]) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for index, person in enumerate(people, start=1):
        option = normalize_signatory_option(person, index, slot_id)
        if option is not None:
            options.append(option)
    return options


def default_signatory_slots() -> list[dict[str, Any]]:
    medtech_1_options = default_signatory_options("medical_technologist_1", DEFAULT_MEDTECH_SIGNATORY_PEOPLE)
    medtech_2_options = default_signatory_options("medical_technologist_2", DEFAULT_MEDTECH_SIGNATORY_PEOPLE)
    pathologist_options = default_signatory_options("pathologist", DEFAULT_PATHOLOGIST_SIGNATORY_PEOPLE)
    pathologist_default = compact_text(pathologist_options[0]["id"]) if pathologist_options else ""
    return [
        {
            "id": "medical_technologist_1",
            "label": "Medical Technologist",
            "input_type": "person_dropdown",
            "required": True,
            "show_on_print": True,
            "show_license": True,
            "signature_line": True,
            "default_option_id": "",
            "options": medtech_1_options,
        },
        {
            "id": "medical_technologist_2",
            "label": "Medical Technologist",
            "input_type": "person_dropdown",
            "required": False,
            "show_on_print": True,
            "show_license": True,
            "signature_line": True,
            "default_option_id": "",
            "options": medtech_2_options,
        },
        {
            "id": "pathologist",
            "label": "Pathologist",
            "input_type": "fixed",
            "required": False,
            "show_on_print": True,
            "show_license": True,
            "signature_line": True,
            "default_option_id": pathologist_default,
            "options": pathologist_options,
        },
    ]


def normalize_signatory_slot(raw_slot: Any, index: int) -> dict[str, Any] | None:
    slot = raw_slot if isinstance(raw_slot, dict) else {}
    label = compact_text(slot.get("label")) or f"Signatory {index}"
    slot_id = slugify(compact_text(slot.get("id")) or compact_text(slot.get("key")) or label)
    input_type = compact_text(slot.get("input_type")).lower()
    if input_type not in SIGNATORY_INPUT_TYPES:
        input_type = "person_dropdown"
    options = [
        option
        for option in (
            normalize_signatory_option(option, option_index, slot_id)
            for option_index, option in enumerate(normalize_items(slot.get("options")), start=1)
        )
        if option is not None
    ]
    default_option_id = compact_text(slot.get("default_option_id"))
    if default_option_id and all(compact_text(option.get("id")) != default_option_id for option in options):
        default_option_id = ""
    if input_type == "fixed" and not default_option_id and options:
        default_option_id = compact_text(options[0].get("id"))
    return {
        "id": slot_id,
        "label": label,
        "input_type": input_type,
        "required": normalize_boolean_setting(slot.get("required"), default=False),
        "show_on_print": normalize_boolean_setting(slot.get("show_on_print"), default=True),
        "show_license": normalize_boolean_setting(slot.get("show_license"), default=True),
        "signature_line": normalize_boolean_setting(slot.get("signature_line"), default=True),
        "default_option_id": default_option_id,
        "manual_name": compact_text(slot.get("manual_name")),
        "manual_title": compact_text(slot.get("manual_title")),
        "manual_license": compact_text(slot.get("manual_license")),
        "stamp_image_url": compact_text(slot.get("stamp_image_url")),
        "stamp_image_filename": compact_text(slot.get("stamp_image_filename")),
        "stamp_image_mime_type": compact_text(slot.get("stamp_image_mime_type")),
        "options": options,
    }


def normalize_signatory_slots(raw_slots: Any, *, use_defaults: bool = False) -> list[dict[str, Any]]:
    if not isinstance(raw_slots, list):
        return default_signatory_slots() if use_defaults else []
    slots = [
        slot
        for slot in (
            normalize_signatory_slot(slot, index)
            for index, slot in enumerate(raw_slots, start=1)
        )
        if slot is not None
    ]
    return slots


def signatory_option_by_id(slot: dict[str, Any], option_id: str) -> dict[str, Any] | None:
    target_id = compact_text(option_id)
    for option in normalize_items(slot.get("options")):
        if isinstance(option, dict) and compact_text(option.get("id")) == target_id:
            return option
    return None


def build_signatory_snapshot(slot: dict[str, Any], raw_value: Any = None) -> dict[str, Any]:
    value = raw_value if isinstance(raw_value, dict) else {}
    input_type = compact_text(slot.get("input_type")).lower()
    option_id = compact_text(value.get("option_id"))
    if not option_id and input_type == "fixed":
        option_id = compact_text(slot.get("default_option_id"))
    option = signatory_option_by_id(slot, option_id) if option_id else None

    name = compact_text(value.get("name"))
    title = compact_text(value.get("title"))
    license_text = compact_text(value.get("license"))
    if option is not None:
        name = compact_text(option.get("name"))
        title = compact_text(option.get("title"))
        license_text = compact_text(option.get("license"))
        option_id = compact_text(option.get("id"))
    elif input_type in {"fixed", "manual"}:
        name = compact_text(slot.get("manual_name"))
        title = compact_text(slot.get("manual_title"))
        license_text = compact_text(slot.get("manual_license"))

    return {
        "slot_id": compact_text(slot.get("id")),
        "label": compact_text(slot.get("label")) or "Signatory",
        "input_type": input_type if input_type in SIGNATORY_INPUT_TYPES else "person_dropdown",
        "option_id": option_id,
        "name": name,
        "title": title,
        "license": license_text,
        "required": normalize_boolean_setting(slot.get("required"), default=False),
        "show_on_print": normalize_boolean_setting(slot.get("show_on_print"), default=True),
        "show_license": normalize_boolean_setting(slot.get("show_license"), default=True),
        "signature_line": normalize_boolean_setting(slot.get("signature_line"), default=True),
        "stamp_image_url": compact_text(slot.get("stamp_image_url")),
        "stamp_image_filename": compact_text(slot.get("stamp_image_filename")),
        "stamp_image_mime_type": compact_text(slot.get("stamp_image_mime_type")),
    }


def normalize_record_signatory_snapshots(raw_signatories: Any, slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_map: dict[str, Any] = {}
    if isinstance(raw_signatories, dict):
        raw_map = raw_signatories
    elif isinstance(raw_signatories, list):
        raw_map = {
            compact_text(item.get("slot_id")): item
            for item in raw_signatories
            if isinstance(item, dict) and compact_text(item.get("slot_id"))
        }

    snapshots: list[dict[str, Any]] = []
    for slot in slots:
        slot_id = compact_text(slot.get("id"))
        if not slot_id:
            continue
        snapshots.append(build_signatory_snapshot(slot, raw_map.get(slot_id)))
    return snapshots


def signatory_snapshots_for_print(snapshots: list[dict[str, Any]]) -> list[dict[str, str]]:
    printable: list[dict[str, str]] = []
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        if not normalize_boolean_setting(snapshot.get("show_on_print"), default=True):
            continue
        input_type = compact_text(snapshot.get("input_type")).lower()
        required = normalize_boolean_setting(snapshot.get("required"), default=False)
        name = compact_text(snapshot.get("name"))
        license_text = compact_text(snapshot.get("license"))
        stamp_image_url = compact_text(snapshot.get("stamp_image_url"))
        if input_type == "stamp_image":
            if not stamp_image_url:
                continue
            printable.append(
                {
                    "label": compact_text(snapshot.get("label")) or "Signatory",
                    "name": "",
                    "title": "",
                    "license": "",
                    "image_url": stamp_image_url,
                    "image_alt": compact_text(snapshot.get("stamp_image_filename"))
                    or compact_text(snapshot.get("label"))
                    or "Signatory stamp",
                }
            )
            continue
        if not name and not normalize_boolean_setting(snapshot.get("signature_line"), default=True):
            continue
        if not name and not license_text and input_type != "blank" and not required:
            continue
        printable.append(
            {
                "label": compact_text(snapshot.get("label")) or "Signatory",
                "name": name,
                "title": compact_text(snapshot.get("title")),
                "license": license_text if normalize_boolean_setting(snapshot.get("show_license"), default=True) else "",
                "image_url": "",
                "image_alt": "",
            }
        )
    return printable


def reference_common_field_set(field_set_id: str) -> dict[str, Any]:
    target_id = compact_text(field_set_id)
    for field_set in normalize_items(load_reference_schema().get("common_field_sets")):
        if isinstance(field_set, dict) and compact_text(field_set.get("id")) == target_id:
            return field_set
    return {}


def default_patient_info_legacy_group() -> dict[str, Any]:
    field_set = reference_common_field_set(DEFAULT_LAB_REQUEST_FIELD_SET_ID)
    fields: list[dict[str, Any]] = []

    for raw_field in normalize_items(field_set.get("fields")):
        if not isinstance(raw_field, dict):
            continue
        key = compact_text(raw_field.get("key"))
        name = compact_text(raw_field.get("name"))
        if not key or not name:
            continue
        if key in SIGNATORY_FIELD_KEYS:
            continue

        data_type = compact_text(raw_field.get("data_type")) or "text"
        if key == "date_or_datetime":
            data_type = "datetime"

        field: dict[str, Any] = {
            "key": key,
            "name": name,
            "kind": "field",
            "control": compact_text(raw_field.get("control")) or "input",
            "data_type": data_type,
            "source": {
                "common_field_set_id": DEFAULT_LAB_REQUEST_FIELD_SET_ID,
                "common_field_id": compact_text(raw_field.get("id")),
            },
        }
        options = normalize_options(raw_field.get("options"), f"{PATIENT_INFO_GROUP_KEY}.{key}")
        if options:
            field["options"] = options
        if key in PATIENT_INFO_REQUIRED_KEYS:
            field["required"] = True
        fields.append(field)

    return {
        "key": PATIENT_INFO_GROUP_KEY,
        "name": PATIENT_INFO_GROUP_NAME,
        "kind": "field_group",
        "source": {"common_field_set_id": DEFAULT_LAB_REQUEST_FIELD_SET_ID},
        "fields": fields,
    }


def legacy_schema_has_default_patient_info(raw_schema: dict[str, Any]) -> bool:
    for field in normalize_items(raw_schema.get("fields")):
        if not isinstance(field, dict):
            continue
        if compact_text(field.get("key")) == PATIENT_INFO_GROUP_KEY:
            return True
        if compact_text(field.get("name")).lower() == PATIENT_INFO_GROUP_NAME.lower():
            return True
    return False


def materialize_default_patient_info_fields(raw_schema: dict[str, Any]) -> dict[str, Any]:
    schema = raw_schema if isinstance(raw_schema, dict) else {}
    if compact_text(schema.get("common_field_set_id")) != DEFAULT_LAB_REQUEST_FIELD_SET_ID:
        return schema
    if legacy_schema_has_default_patient_info(schema):
        return schema

    materialized = json.loads(json.dumps(schema))
    materialized["fields"] = [
        default_patient_info_legacy_group(),
        *normalize_items(materialized.get("fields")),
    ]
    return materialized


def legacy_field_to_block(field: dict[str, Any]) -> dict[str, Any]:
    field_id = compact_text(field.get("id")) or f"blk_{slugify(field.get('name') or 'field')}"
    kind = "field_group" if compact_text(field.get("kind")) == "field_group" else "field"
    props: dict[str, Any] = {
        "key": compact_text(field.get("key")) or slugify(field.get("name") or field_id),
        "order": int(field.get("order") or 1),
    }

    notes = normalize_notes(field.get("notes"))
    if notes:
        props["notes"] = notes

    source = field.get("source")
    if isinstance(source, dict) and source:
        props["source"] = source

    if kind == "field_group":
        return {
            "id": field_id,
            "kind": "field_group",
            "name": compact_text(field.get("name")) or "Untitled Group",
            "props": props,
            "children": [
                legacy_field_to_block(child)
                for child in normalize_items(field.get("fields"))
                if isinstance(child, dict)
            ],
        }

    props["control"] = compact_text(field.get("control")) or "input"
    props["data_type"] = compact_text(field.get("data_type")) or "text"
    props["required"] = bool(field.get("required") or False)

    unit_hint = compact_text(field.get("unit_hint"))
    if unit_hint:
        props["unit_hint"] = unit_hint

    reference_text = compact_text(field.get("reference_text") or field.get("normal_value"))
    if reference_text:
        props["reference_text"] = reference_text

    normal_min = compact_text(field.get("normal_min"))
    if normal_min:
        props["normal_min"] = normal_min

    normal_max = compact_text(field.get("normal_max"))
    if normal_max:
        props["normal_max"] = normal_max

    options = []
    for option in normalize_items(field.get("options")):
        if not isinstance(option, dict):
            continue
        name = compact_text(option.get("name"))
        if not name:
            continue
        options.append(
            {
                "id": compact_text(option.get("id")) or f"{field_id}.{slugify(name)}",
                "key": compact_text(option.get("key")) or slugify(name),
                "name": name,
                "order": int(option.get("order") or len(options) + 1),
                "is_normal": bool(option.get("is_normal")),
            }
        )
    if options:
        props["options"] = options

    return {
        "id": field_id,
        "kind": "field",
        "name": compact_text(field.get("name")) or "Untitled Field",
        "props": props,
        "children": [],
    }


def legacy_section_to_block(section: dict[str, Any]) -> dict[str, Any]:
    section_id = compact_text(section.get("id")) or f"blk_{slugify(section.get('name') or 'section')}"
    props: dict[str, Any] = {
        "key": compact_text(section.get("key")) or slugify(section.get("name") or section_id),
        "order": int(section.get("order") or 1),
    }

    notes = normalize_notes(section.get("notes"))
    if notes:
        props["notes"] = notes

    source = section.get("source")
    if isinstance(source, dict) and source:
        props["source"] = source

    return {
        "id": section_id,
        "kind": "section",
        "name": compact_text(section.get("name")) or "Untitled Section",
        "props": props,
        "children": [
            legacy_field_to_block(field)
            for field in normalize_items(section.get("fields"))
            if isinstance(field, dict)
        ],
    }


def build_block_schema_from_legacy_storage(raw_schema: dict[str, Any]) -> dict[str, Any]:
    raw_schema = materialize_default_patient_info_fields(raw_schema)
    meta: dict[str, Any] = {
        "form_id": compact_text(raw_schema.get("id")),
        "form_key": compact_text(raw_schema.get("key")),
        "form_order": int(raw_schema.get("order") or 1),
    }

    notes = normalize_notes(raw_schema.get("notes"))
    if notes:
        meta["notes"] = notes

    source = raw_schema.get("source")
    if isinstance(source, dict) and source:
        meta["source"] = source

    blocks = [
        *[
            legacy_field_to_block(field)
            for field in normalize_items(raw_schema.get("fields"))
            if isinstance(field, dict)
        ],
        *[
            legacy_section_to_block(section)
            for section in normalize_items(raw_schema.get("sections"))
            if isinstance(section, dict)
        ],
    ]

    block_schema = {
        "schema_version": 1,
        "source_kind": LEGACY_BLOCK_SCHEMA_SOURCE,
        "meta": meta,
        "blocks": blocks,
    }
    if block_schema_has_default_patient_info(block_schema):
        meta[DEFAULT_PATIENT_INFO_MATERIALIZED_META_KEY] = True
        block_schema["meta"] = meta
    ensure_default_patient_info_identity(block_schema)
    return block_schema


def default_patient_info_field_id(form_id: str, field_key: str) -> str:
    return f"{compact_text(form_id)}.{PATIENT_INFO_GROUP_KEY}.{field_key}"


def block_schema_has_default_patient_info(block_schema: dict[str, Any]) -> bool:
    for block in normalize_items(block_schema.get("blocks")):
        if not isinstance(block, dict):
            continue
        props = block.get("props") if isinstance(block.get("props"), dict) else {}
        if compact_text(props.get("key")) == PATIENT_INFO_GROUP_KEY:
            return True
        if compact_text(block.get("name")).lower() == PATIENT_INFO_GROUP_NAME.lower():
            return True
    return False


def build_default_patient_info_block(form_id: str) -> dict[str, Any]:
    field_group = normalize_field(default_patient_info_legacy_group(), form_id, 1, set())
    return legacy_field_to_block(field_group)


def resequence_top_level_block_orders(blocks: list[dict[str, Any]]) -> None:
    for index, block in enumerate(blocks, start=1):
        if not isinstance(block, dict):
            continue
        props = block.get("props") if isinstance(block.get("props"), dict) else {}
        props["order"] = index
        block["props"] = props


def ensure_default_patient_info_identity(block_schema: dict[str, Any]) -> bool:
    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    form_id = compact_text(meta.get("form_id"))
    if not form_id or not block_schema_has_default_patient_info(block_schema):
        return False

    name_field_id = default_patient_info_field_id(form_id, PATIENT_INFO_PRIMARY_KEY)
    case_field_id = default_patient_info_field_id(form_id, PATIENT_INFO_SECONDARY_KEY)
    identity = normalize_record_identity_config(meta.get("record_identity"))
    changed = False

    if not identity["primary_field_id"]:
        identity["primary_field_id"] = name_field_id
        changed = True
    if not identity["secondary_field_id"]:
        identity["secondary_field_id"] = case_field_id
        changed = True

    searchable_ids = list(identity["searchable_field_ids"])
    for field_id in [name_field_id, case_field_id]:
        if field_id and field_id not in searchable_ids:
            searchable_ids.append(field_id)
            changed = True
    if searchable_ids != identity["searchable_field_ids"]:
        identity["searchable_field_ids"] = searchable_ids
        changed = True

    if changed or meta.get("record_identity") != identity:
        meta["record_identity"] = identity
        block_schema["meta"] = meta
        return True
    return False


def ensure_default_patient_info_block_schema(block_schema: dict[str, Any]) -> bool:
    if not isinstance(block_schema, dict):
        return False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    form_id = compact_text(meta.get("form_id"))
    if not form_id:
        return False

    changed = False
    blocks = normalize_items(block_schema.get("blocks"))
    has_patient_info = block_schema_has_default_patient_info(block_schema)
    was_materialized = bool(meta.get(DEFAULT_PATIENT_INFO_MATERIALIZED_META_KEY))

    if not has_patient_info and was_materialized:
        return False

    if not has_patient_info:
        blocks = [build_default_patient_info_block(form_id), *blocks]
        block_schema["blocks"] = blocks
        has_patient_info = True
        changed = True

    if has_patient_info and meta.get(DEFAULT_PATIENT_INFO_MATERIALIZED_META_KEY) is not True:
        meta[DEFAULT_PATIENT_INFO_MATERIALIZED_META_KEY] = True
        block_schema["meta"] = meta
        changed = True

    if has_patient_info:
        resequence_top_level_block_orders(blocks)
        changed = ensure_default_patient_info_identity(block_schema) or changed
    return changed


def block_field_to_legacy_field(block: dict[str, Any], parent_id: str, order: int, used_keys: set[str]) -> dict[str, Any]:
    kind = compact_text(block.get("kind"))
    if kind not in {"field", "field_group"}:
        raise ValueError(f"Unsupported block kind for legacy field bridge: {kind or 'unknown'}")

    props = block.get("props") if isinstance(block.get("props"), dict) else {}
    raw_field: dict[str, Any] = {
        "id": compact_text(block.get("id")) or "",
        "key": compact_text(props.get("key")) or compact_text(block.get("name")),
        "name": compact_text(block.get("name")) or "Untitled Field",
        "kind": "field_group" if kind == "field_group" else "field",
        "order": int(props.get("order") or order),
    }

    notes = normalize_notes(props.get("notes"))
    if notes:
        raw_field["notes"] = notes

    source = props.get("source")
    if isinstance(source, dict) and source:
        raw_field["source"] = source

    if kind == "field_group":
        child_used: set[str] = set()
        raw_field["fields"] = [
            block_field_to_legacy_field(child, raw_field.get("id") or parent_id, child_order, child_used)
            for child_order, child in enumerate(normalize_items(block.get("children")), start=1)
            if isinstance(child, dict) and compact_text(child.get("kind")) in {"field", "field_group"}
        ]
        return normalize_field(raw_field, parent_id, order, used_keys)

    control = compact_text(props.get("control")) or "input"
    data_type = compact_text(props.get("data_type")) or "text"
    if control == "select" or data_type == "enum":
        control = "select"
        data_type = "enum"
    else:
        control = "input"
        data_type = data_type or "text"

    raw_field["control"] = control
    raw_field["data_type"] = data_type
    if bool(props.get("required")):
        raw_field["required"] = True

    unit_hint = compact_text(props.get("unit_hint"))
    if unit_hint:
        raw_field["unit_hint"] = unit_hint

    reference_text = compact_text(props.get("reference_text") or props.get("normal_value"))
    if reference_text:
        raw_field["reference_text"] = reference_text
        raw_field["normal_value"] = reference_text

    normal_min = compact_text(props.get("normal_min"))
    if normal_min:
        raw_field["normal_min"] = normal_min

    normal_max = compact_text(props.get("normal_max"))
    if normal_max:
        raw_field["normal_max"] = normal_max

    options = []
    for option in normalize_items(props.get("options")):
        if not isinstance(option, dict):
            continue
        name = compact_text(option.get("name"))
        if not name:
            continue
        options.append(
            {
                "id": compact_text(option.get("id")) or "",
                "key": compact_text(option.get("key")) or slugify(name),
                "name": name,
                "order": int(option.get("order") or len(options) + 1),
                "is_normal": bool(option.get("is_normal")),
            }
        )
    if options:
        raw_field["options"] = options

    return normalize_field(raw_field, parent_id, order, used_keys)


def block_section_to_legacy_section(block: dict[str, Any], form_id: str, order: int, used_keys: set[str]) -> dict[str, Any]:
    if compact_text(block.get("kind")) != "section":
        raise ValueError("Only section blocks can be bridged into legacy sections.")

    props = block.get("props") if isinstance(block.get("props"), dict) else {}
    raw_section: dict[str, Any] = {
        "id": compact_text(block.get("id")) or "",
        "key": compact_text(props.get("key")) or compact_text(block.get("name")),
        "name": compact_text(block.get("name")) or "Untitled Section",
        "order": int(props.get("order") or order),
        "fields": [],
    }

    notes = normalize_notes(props.get("notes"))
    if notes:
        raw_section["notes"] = notes

    source = props.get("source")
    if isinstance(source, dict) and source:
        raw_section["source"] = source

    field_used: set[str] = set()
    raw_section["fields"] = [
        block_field_to_legacy_field(child, compact_text(raw_section.get("id")) or form_id, child_order, field_used)
        for child_order, child in enumerate(normalize_items(block.get("children")), start=1)
        if isinstance(child, dict) and compact_text(child.get("kind")) in {"field", "field_group"}
    ]

    return normalize_section(raw_section, form_id, order, used_keys)


def build_legacy_storage_schema_from_blocks(raw_schema: dict[str, Any]) -> dict[str, Any]:
    blocks = normalize_items(raw_schema.get("blocks"))
    meta = raw_schema.get("meta") if isinstance(raw_schema.get("meta"), dict) else {}
    form_id = compact_text(meta.get("form_id")) or "form.compat"
    used_field_keys: set[str] = set()
    used_section_keys: set[str] = set()

    fields: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    for order, block in enumerate(blocks, start=1):
        if not isinstance(block, dict):
            continue
        kind = compact_text(block.get("kind"))
        if kind in {"field", "field_group"}:
            fields.append(block_field_to_legacy_field(block, form_id, order, used_field_keys))
            continue
        if kind == "section":
            sections.append(block_section_to_legacy_section(block, form_id, len(sections) + 1, used_section_keys))
            continue
        if kind in {"note", "divider", "table", "repeater", "columns"}:
            continue
        raise ValueError(f"Unsupported block kind for current compatibility bridge: {kind or 'unknown'}")

    legacy: dict[str, Any] = {
        "fields": fields,
        "sections": sections,
    }

    notes = normalize_notes(meta.get("notes"))
    if notes:
        legacy["notes"] = notes

    source = meta.get("source")
    if isinstance(source, dict) and source:
        legacy["source"] = source

    return legacy


def normalize_block_option_props(raw_options: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    for index, option in enumerate(normalize_items(raw_options), start=1):
        if isinstance(option, dict):
            normalized_option = dict(option)
            name = compact_text(normalized_option.get("name") or normalized_option.get("label"))
            if not name:
                continue
            normalized_option["name"] = name
            normalized_option.pop("label", None)
            normalized_option["key"] = compact_text(normalized_option.get("key")) or slugify(name) or f"option_{index}"
            normalized_option["order"] = int(normalized_option.get("order") or index)
            normalized_option["is_normal"] = bool(normalized_option.get("is_normal"))
            normalized.append(normalized_option)
            continue

        name = compact_text(option)
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "key": slugify(name) or f"option_{index}",
                "order": index,
                "is_normal": False,
            }
        )

    return normalized


def normalize_active_block_storage_node(node: dict[str, Any]) -> bool:
    if not isinstance(node, dict):
        return False

    changed = False
    props = node.get("props") if isinstance(node.get("props"), dict) else None
    if isinstance(props, dict):
        if "field_type" in props:
            props.pop("field_type", None)
            changed = True

        if compact_text(node.get("kind")) == "field":
            required = bool(props.get("required"))
            if required:
                if props.get("required") is not True:
                    props["required"] = True
                    changed = True
            elif "required" in props:
                props.pop("required", None)
                changed = True

        reference_text = compact_text(props.get("reference_text") or props.get("normal_value"))
        if reference_text:
            if props.get("reference_text") != reference_text:
                props["reference_text"] = reference_text
                changed = True
        elif "reference_text" in props:
            props.pop("reference_text", None)
            changed = True

        if "normal_value" in props:
            props.pop("normal_value", None)
            changed = True

        normal_min = compact_text(props.get("normal_min"))
        if normal_min:
            if props.get("normal_min") != normal_min:
                props["normal_min"] = normal_min
                changed = True
        elif "normal_min" in props:
            props.pop("normal_min", None)
            changed = True

        normal_max = compact_text(props.get("normal_max"))
        if normal_max:
            if props.get("normal_max") != normal_max:
                props["normal_max"] = normal_max
                changed = True
        elif "normal_max" in props:
            props.pop("normal_max", None)
            changed = True

        if "options" in props:
            normalized_options = normalize_block_option_props(props.get("options"))
            if normalized_options:
                if normalized_options != props.get("options"):
                    props["options"] = normalized_options
                    changed = True
            else:
                props.pop("options", None)
                changed = True

    for child in normalize_items(node.get("children")):
        if normalize_active_block_storage_node(child):
            changed = True

    return changed


def normalize_active_block_storage_schema(block_schema: dict[str, Any]) -> bool:
    if not isinstance(block_schema, dict):
        return False

    changed = False
    blocks = normalize_items(block_schema.get("blocks"))
    if block_schema.get("blocks") != blocks:
        block_schema["blocks"] = blocks
        changed = True

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    normalized_identity = normalize_record_identity_config(meta.get("record_identity"))
    if any(
        [
            normalized_identity["primary_field_id"],
            normalized_identity["secondary_field_id"],
            normalized_identity["searchable_field_ids"],
        ]
    ):
        if meta.get("record_identity") != normalized_identity:
            meta["record_identity"] = normalized_identity
            block_schema["meta"] = meta
            changed = True
    elif "record_identity" in meta:
        meta.pop("record_identity", None)
        block_schema["meta"] = meta
        changed = True

    normalized_print_config = normalize_print_config(meta.get("print_config"))
    if meta.get("print_config") != normalized_print_config:
        meta["print_config"] = normalized_print_config
        block_schema["meta"] = meta
        changed = True
    if ensure_form_default_print_accent(meta):
        block_schema["meta"] = meta
        changed = True

    normalized_signatories = normalize_signatory_slots(
        meta.get("signatories"),
        use_defaults="signatories" not in meta,
    )
    if meta.get("signatories") != normalized_signatories:
        meta["signatories"] = normalized_signatories
        block_schema["meta"] = meta
        changed = True

    for block in blocks:
        if normalize_active_block_storage_node(block):
            changed = True

    return changed


def build_block_storage_payload(
    raw_schema: dict[str, Any],
    *,
    legacy_storage_schema: dict[str, Any],
) -> dict[str, Any]:
    if isinstance(raw_schema, dict) and "blocks" in raw_schema and "fields" not in raw_schema and "sections" not in raw_schema:
        block_schema = json.loads(json.dumps(raw_schema))
        source_kind = ACTIVE_BLOCK_SCHEMA_SOURCE
    else:
        block_schema = build_block_schema_from_legacy_storage(legacy_storage_schema)
        source_kind = LEGACY_BLOCK_SCHEMA_SOURCE

    block_schema["schema_version"] = int(block_schema.get("schema_version") or 1)
    block_schema["source_kind"] = source_kind
    block_schema["blocks"] = normalize_items(block_schema.get("blocks"))
    normalize_active_block_storage_schema(block_schema)

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    meta.pop("common_field_set_id", None)
    meta["form_id"] = compact_text(legacy_storage_schema.get("id"))
    meta["form_key"] = compact_text(legacy_storage_schema.get("key"))
    meta["form_order"] = int(legacy_storage_schema.get("order") or 1)
    meta.pop("legacy_form_id", None)
    meta.pop("legacy_form_key", None)
    meta.pop("legacy_order", None)

    notes = normalize_notes(legacy_storage_schema.get("notes"))
    if notes:
        meta["notes"] = notes
    else:
        meta.pop("notes", None)

    source = legacy_storage_schema.get("source")
    if isinstance(source, dict) and source:
        meta["source"] = source
    else:
        meta.pop("source", None)

    ensure_form_default_print_accent(meta)
    block_schema["meta"] = meta
    return block_schema


def build_block_storage_document_from_legacy_storage(
    legacy_storage_schema: dict[str, Any],
) -> dict[str, Any]:
    return build_block_storage_payload(
        legacy_storage_schema,
        legacy_storage_schema=legacy_storage_schema,
    )


def build_form_version_storage_documents(
    raw_block_schema: dict[str, Any],
    *,
    slug: str,
    name: str,
    form_order: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_block_schema = json.loads(json.dumps(raw_block_schema))
    normalize_active_block_storage_schema(normalized_block_schema)
    legacy_storage_source = build_legacy_storage_schema_from_blocks(normalized_block_schema)
    legacy_storage_schema = build_legacy_storage_payload(
        legacy_storage_source,
        slug=slug,
        name=name,
        form_order=form_order,
    )
    stored_block_schema = build_block_storage_payload(
        normalized_block_schema,
        legacy_storage_schema=legacy_storage_schema,
    )
    return legacy_storage_schema, stored_block_schema


def block_payload_form_key(raw_block_schema: dict[str, Any]) -> str:
    if not isinstance(raw_block_schema, dict):
        return ""
    meta = raw_block_schema.get("meta") if isinstance(raw_block_schema.get("meta"), dict) else {}
    return compact_text(meta.get("form_key"))


def stable_form_schema_id(slug: str) -> str:
    return f"form.{slugify(slug or 'compat')}"


def build_legacy_storage_payload(
    raw_schema: dict[str, Any],
    *,
    slug: str,
    name: str,
    form_order: int,
) -> dict[str, Any]:
    raw_schema = materialize_default_patient_info_fields(raw_schema if isinstance(raw_schema, dict) else {})
    form_id = stable_form_schema_id(slug)
    field_used: set[str] = set()
    section_used: set[str] = set()

    normalized: dict[str, Any] = {
        "id": form_id,
        "key": slug,
        "name": compact_text(name) or "Untitled Form",
        "order": form_order,
        "fields": [
            normalize_field(field, form_id, field_order, field_used)
            for field_order, field in enumerate(raw_schema.get("fields") or [], start=1)
            if isinstance(field, dict)
        ],
        "sections": [
            normalize_section(section, form_id, section_order, section_used)
            for section_order, section in enumerate(raw_schema.get("sections") or [], start=1)
            if isinstance(section, dict)
        ],
    }

    notes = normalize_notes(raw_schema.get("notes"))
    if notes:
        normalized["notes"] = notes

    source = raw_schema.get("source")
    if isinstance(source, dict) and source:
        normalized["source"] = source

    return normalized


def build_form_version_record(
    *,
    form_id: int,
    version_number: int,
    summary: str,
    legacy_storage_schema: dict[str, Any],
    block_storage_schema: dict[str, Any],
    source: str,
    is_current: bool,
) -> FormVersion:
    return FormVersion(
        form_id=form_id,
        version_number=version_number,
        summary=summary,
        schema_json=json.dumps(legacy_storage_schema, ensure_ascii=False),
        block_schema_json=json.dumps(block_storage_schema, ensure_ascii=False),
        source=source,
        is_current=is_current,
    )


def current_version(definition: FormDefinition) -> FormVersion | None:
    for version in definition.versions:
        if version.is_current:
            return version
    return definition.versions[-1] if definition.versions else None


def load_legacy_storage_document(version: FormVersion) -> dict[str, Any]:
    raw_schema = compact_text(version.schema_json)
    if not raw_schema:
        return {}
    try:
        parsed = json.loads(raw_schema)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def load_block_storage_document(
    version: FormVersion,
    *,
    legacy_storage_schema: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    raw_block_storage = compact_text(version.block_schema_json)
    if raw_block_storage:
        try:
            parsed = json.loads(raw_block_storage)
            if isinstance(parsed, dict):
                return parsed, False
        except json.JSONDecodeError:
            pass
    fallback_legacy_storage = legacy_storage_schema if isinstance(legacy_storage_schema, dict) else load_legacy_storage_document(version)
    return build_block_storage_document_from_legacy_storage(fallback_legacy_storage), True


def load_json_object(raw_value: str | None) -> dict[str, Any]:
    payload = compact_text(raw_value)
    if not payload:
        return {}
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def normalize_record_values(raw_values: Any) -> dict[str, Any]:
    if not isinstance(raw_values, dict):
        return {}

    normalized: dict[str, Any] = {}
    for raw_key, raw_value in raw_values.items():
        field_id = compact_text(raw_key)
        if not field_id:
            continue

        if isinstance(raw_value, dict):
            asset_payload: dict[str, Any] = {}
            asset_id = raw_value.get("asset_id")
            if asset_id not in (None, ""):
                try:
                    asset_payload["asset_id"] = int(asset_id)
                except (TypeError, ValueError):
                    pass
            kind = compact_text(raw_value.get("kind"))
            if kind:
                asset_payload["kind"] = kind
            if asset_payload:
                normalized[field_id] = asset_payload
            continue

        if isinstance(raw_value, bool):
            normalized[field_id] = raw_value
            continue

        if isinstance(raw_value, (int, float)):
            normalized[field_id] = raw_value
            continue

        text_value = compact_text(raw_value)
        if text_value:
            normalized[field_id] = text_value

    return normalized


def normalize_record_indexed_meta(
    raw_meta: Any,
    *,
    patient_name: str | None,
    patient_age: str | None,
    patient_sex: str | None,
    case_number: str | None,
) -> dict[str, Any]:
    normalized = dict(raw_meta) if isinstance(raw_meta, dict) else {}

    if patient_name is not None and compact_text(patient_name):
        normalized["patient_name"] = compact_text(patient_name)
    elif patient_name is not None:
        normalized.pop("patient_name", None)

    if patient_age is not None and compact_text(patient_age):
        normalized["patient_age"] = compact_text(patient_age)
    elif patient_age is not None:
        normalized.pop("patient_age", None)

    if patient_sex is not None and compact_text(patient_sex):
        normalized["patient_sex"] = compact_text(patient_sex)
    elif patient_sex is not None:
        normalized.pop("patient_sex", None)

    if case_number is not None and compact_text(case_number):
        normalized["case_number"] = compact_text(case_number)
    elif case_number is not None:
        normalized.pop("case_number", None)

    return normalized


def remove_file_if_present(path_value: str | None) -> None:
    file_path = Path(path_value or "")
    if not file_path.exists() or not file_path.is_file():
        return
    try:
        file_path.unlink()
    except OSError:
        return

    parent = file_path.parent
    stop_dir = RECORD_UPLOADS_DIR.resolve()
    while parent.exists():
        try:
            if parent.resolve() == stop_dir:
                break
        except OSError:
            break
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def remove_file_if_present_under(path_value: str | None, *, stop_dir: Path) -> None:
    file_path = Path(path_value or "")
    if not file_path.exists() or not file_path.is_file():
        return
    try:
        file_path.unlink()
    except OSError:
        return

    parent = file_path.parent
    safe_stop_dir = stop_dir.resolve()
    while parent.exists():
        try:
            if parent.resolve() == safe_stop_dir:
                break
        except OSError:
            break
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def remove_record_asset(
    session: Session,
    asset: RecordAsset,
) -> None:
    remove_file_if_present(asset.storage_path)
    session.delete(asset)


def save_user_avatar(
    session: Session,
    user_id: int,
    *,
    avatar_filename: str = "",
    avatar_content_type: str | None = None,
    avatar_bytes: bytes | None = None,
) -> dict[str, Any]:
    user = get_user_or_none(session, user_id)
    if user is None:
        raise KeyError(user_id)

    mime_type = compact_text(avatar_content_type)
    extension = ALLOWED_IMAGE_CONTENT_TYPES.get(mime_type)
    if extension is None:
        raise ValueError("Only JPG, PNG, and WebP avatars are allowed.")
    if not avatar_bytes:
        raise ValueError("Choose an image before uploading.")
    if len(avatar_bytes) > MAX_USER_AVATAR_BYTES:
        raise ValueError("Avatar image must be 2 MB or smaller.")

    old_avatar_path = user.avatar_path
    old_avatar_name = user.avatar_original_filename
    old_avatar_type = user.avatar_mime_type
    USER_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    new_avatar_path = USER_UPLOADS_DIR / f"user_{user.id}_avatar_{uuid4().hex}{extension}"
    new_avatar_path.write_bytes(avatar_bytes)

    user.avatar_path = str(new_avatar_path)
    user.avatar_original_filename = compact_text(avatar_filename) or new_avatar_path.name
    user.avatar_mime_type = mime_type or None

    try:
        session.add(user)
        session.commit()
    except Exception:
        session.rollback()
        remove_file_if_present_under(str(new_avatar_path), stop_dir=USER_UPLOADS_DIR)
        user.avatar_path = old_avatar_path
        user.avatar_original_filename = old_avatar_name
        user.avatar_mime_type = old_avatar_type
        raise

    if old_avatar_path and old_avatar_path != str(new_avatar_path):
        remove_file_if_present_under(old_avatar_path, stop_dir=USER_UPLOADS_DIR)

    session.refresh(user)
    return serialize_user(user)


def remove_user_avatar(session: Session, user_id: int) -> dict[str, Any]:
    user = get_user_or_none(session, user_id)
    if user is None:
        raise KeyError(user_id)

    old_avatar_path = user.avatar_path
    user.avatar_path = None
    user.avatar_original_filename = None
    user.avatar_mime_type = None
    session.add(user)
    session.commit()
    if old_avatar_path:
        remove_file_if_present_under(old_avatar_path, stop_dir=USER_UPLOADS_DIR)
    session.refresh(user)
    return serialize_user(user)


def save_clinic_profile(
    session: Session,
    payload: ClinicProfilePayload,
    *,
    logo_filename: str = "",
    logo_content_type: str | None = None,
    logo_bytes: bytes | None = None,
) -> dict[str, Any]:
    profile = get_or_create_clinic_profile(session)

    clinic_name = compact_text(payload.clinic_name)
    address = compact_text(payload.address)
    contact_number = compact_text(payload.contact_number)
    contact_email = normalize_email(payload.contact_email) if compact_text(payload.contact_email) else ""

    if not clinic_name:
        raise ValueError("Enter the clinic name.")
    if contact_email and not validate_email_format(contact_email):
        raise ValueError("Enter a valid contact email address.")

    old_logo_path = profile.logo_path
    old_logo_name = profile.logo_original_filename
    old_logo_type = profile.logo_mime_type
    new_logo_path: Path | None = None

    if logo_bytes is not None:
        mime_type = compact_text(logo_content_type)
        extension = ALLOWED_IMAGE_CONTENT_TYPES.get(mime_type)
        if extension is None:
            raise ValueError("Only JPG, PNG, and WebP logos are allowed.")
        if not logo_bytes:
            raise ValueError("Choose an image before uploading.")
        if len(logo_bytes) > MAX_CLINIC_LOGO_BYTES:
            raise ValueError("Logo image must be 5 MB or smaller.")
        CLINIC_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        new_logo_path = CLINIC_UPLOADS_DIR / f"logo_{uuid4().hex}{extension}"
        new_logo_path.write_bytes(logo_bytes)
        profile.logo_path = str(new_logo_path)
        profile.logo_original_filename = compact_text(logo_filename) or new_logo_path.name
        profile.logo_mime_type = mime_type or None

    profile.clinic_name = clinic_name
    profile.address = address or None
    profile.contact_number = contact_number or None
    profile.contact_email = contact_email or None

    try:
        session.add(profile)
        session.commit()
    except Exception:
        session.rollback()
        if new_logo_path is not None:
            remove_file_if_present_under(str(new_logo_path), stop_dir=CLINIC_UPLOADS_DIR)
        profile.logo_path = old_logo_path
        profile.logo_original_filename = old_logo_name
        profile.logo_mime_type = old_logo_type
        raise

    if new_logo_path is not None and old_logo_path and old_logo_path != str(new_logo_path):
        remove_file_if_present_under(old_logo_path, stop_dir=CLINIC_UPLOADS_DIR)

    session.refresh(profile)
    return serialize_clinic_profile(profile)


def save_signatory_stamp_image(
    *,
    stamp_filename: str = "",
    stamp_content_type: str | None = None,
    stamp_bytes: bytes | None = None,
) -> dict[str, Any]:
    mime_type = compact_text(stamp_content_type)
    extension = ALLOWED_IMAGE_CONTENT_TYPES.get(mime_type)
    if extension is None:
        raise ValueError("Only JPG, PNG, and WebP stamp images are allowed.")
    if not stamp_bytes:
        raise ValueError("Choose a stamp image before uploading.")
    if len(stamp_bytes) > MAX_SIGNATORY_STAMP_BYTES:
        raise ValueError("Stamp image must be 5 MB or smaller.")

    SIGNATORY_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    stamp_path = SIGNATORY_UPLOADS_DIR / f"stamp_{uuid4().hex}{extension}"
    stamp_path.write_bytes(stamp_bytes)
    return {
        "url": f"/signatory-stamps/{stamp_path.name}",
        "original_filename": compact_text(stamp_filename) or stamp_path.name,
        "mime_type": mime_type,
        "size_bytes": len(stamp_bytes),
    }


def remove_clinic_logo(session: Session) -> dict[str, Any]:
    profile = get_or_create_clinic_profile(session)
    old_logo_path = profile.logo_path
    profile.logo_path = None
    profile.logo_original_filename = None
    profile.logo_mime_type = None
    session.add(profile)
    session.commit()
    if old_logo_path:
        remove_file_if_present_under(old_logo_path, stop_dir=CLINIC_UPLOADS_DIR)
    session.refresh(profile)
    return serialize_clinic_profile(profile)


def preserve_existing_asset_values(
    existing_values: dict[str, Any],
    incoming_values: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(incoming_values)
    for field_id, value in existing_values.items():
        if field_id in merged:
            continue
        if isinstance(value, dict) and value.get("kind") == "image" and value.get("asset_id"):
            merged[field_id] = value
    return merged


def find_block_by_id(blocks: list[dict[str, Any]], block_id: str) -> dict[str, Any] | None:
    target_id = compact_text(block_id)
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if compact_text(block.get("id")) == target_id:
            return block
        children = normalize_items(block.get("children"))
        if children:
            found = find_block_by_id(children, target_id)
            if found is not None:
                return found
    return None


def resolve_record_image_field(record: Record, field_block_id: str) -> dict[str, Any]:
    block_schema, _ = load_block_storage_document(record.form_version)
    field_block = find_block_by_id(normalize_items(block_schema.get("blocks")), field_block_id)
    if field_block is None or compact_text(field_block.get("kind")) != "field":
        raise ValueError("Image field not found.")
    props = field_block.get("props") if isinstance(field_block.get("props"), dict) else {}
    if compact_text(props.get("data_type")) != "image":
        raise ValueError("This field does not accept image uploads.")
    return field_block


def current_record_values(record: Record) -> dict[str, Any]:
    return normalize_record_values(load_json_object(record.values_json))


def iter_record_field_blocks(
    blocks: list[dict[str, Any]],
    *,
    parents: list[str] | None = None,
):
    parent_names = parents or []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = compact_text(block.get("kind"))
        block_name = compact_text(block.get("name"))
        if kind in {"section", "field_group"}:
            next_parent_names = [*parent_names, block_name] if block_name else parent_names
            yield from iter_record_field_blocks(
                normalize_items(block.get("children")),
                parents=next_parent_names,
            )
            continue
        if kind == "field":
            block_id = compact_text(block.get("id"))
            if not block_id:
                continue
            yield {
                "id": block_id,
                "name": block_name or "Untitled field",
                "path_label": " / ".join([*parent_names, block_name]) if parent_names else block_name,
                "block": block,
            }


def record_field_lookup(block_schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        field["id"]: field
        for field in iter_record_field_blocks(normalize_items(block_schema.get("blocks")))
    }


def normalize_record_identity_config(raw_config: Any) -> dict[str, Any]:
    config = raw_config if isinstance(raw_config, dict) else {}
    primary_field_id = compact_text(config.get("primary_field_id"))
    secondary_field_id = compact_text(config.get("secondary_field_id"))
    searchable_field_ids = []
    for field_id in normalize_items(config.get("searchable_field_ids")):
        normalized = compact_text(field_id)
        if normalized and normalized not in searchable_field_ids:
            searchable_field_ids.append(normalized)

    return {
        "primary_field_id": primary_field_id,
        "secondary_field_id": secondary_field_id,
        "searchable_field_ids": searchable_field_ids,
    }


def record_value_display_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        if value.get("kind") == "image" and value.get("asset_id"):
            return "Image uploaded"
        return " ".join(
            part
            for part in (record_value_display_text(item) for item in value.values())
            if part
        )
    if isinstance(value, list):
        return " ".join(
            part
            for part in (record_value_display_text(item) for item in value)
            if part
        )
    return compact_text(value)


def resolve_record_identity(
    block_schema: dict[str, Any],
    values: dict[str, Any],
    *,
    fallback_primary: str = "",
    fallback_secondary: str = "",
) -> dict[str, Any]:
    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    config = normalize_record_identity_config(meta.get("record_identity"))
    fields = record_field_lookup(block_schema)

    primary_field = fields.get(config["primary_field_id"])
    secondary_field = fields.get(config["secondary_field_id"])
    primary_value = record_value_display_text(values.get(config["primary_field_id"]))
    secondary_value = record_value_display_text(values.get(config["secondary_field_id"]))

    searchable_items: list[dict[str, str]] = []
    search_field_ids = list(config["searchable_field_ids"])
    for field_id in [config["primary_field_id"], config["secondary_field_id"]]:
        if field_id and field_id not in search_field_ids:
            search_field_ids.append(field_id)

    for field_id in search_field_ids:
        field = fields.get(field_id)
        value = record_value_display_text(values.get(field_id))
        if not field or not value:
            continue
        searchable_items.append(
            {
                "field_id": field_id,
                "label": compact_text(field.get("name")) or "Field",
                "value": value,
            }
        )

    fallback_primary_value = compact_text(fallback_primary)
    fallback_secondary_value = compact_text(fallback_secondary)
    search_parts: list[str] = []
    for part in [primary_value, secondary_value, *[item["value"] for item in searchable_items]]:
        text = compact_text(part)
        if text and text not in search_parts:
            search_parts.append(text)

    return {
        "primary_field_id": config["primary_field_id"],
        "primary_label": compact_text(primary_field.get("name")) if primary_field else "",
        "primary_value": primary_value or fallback_primary_value,
        "secondary_field_id": config["secondary_field_id"],
        "secondary_label": compact_text(secondary_field.get("name")) if secondary_field else "",
        "secondary_value": secondary_value or fallback_secondary_value,
        "searchable_fields": searchable_items,
        "search_text": " ".join(search_parts),
    }


def build_record_indexed_meta(
    raw_meta: Any,
    form_version: FormVersion,
    values: dict[str, Any],
    *,
    patient_name: str | None,
    patient_age: str | None,
    patient_sex: str | None,
    case_number: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    block_schema, _ = load_block_storage_document(form_version)
    normalized = normalize_record_indexed_meta(
        raw_meta,
        patient_name=patient_name,
        patient_age=patient_age,
        patient_sex=patient_sex,
        case_number=case_number,
    )
    identity = resolve_record_identity(
        block_schema,
        values,
        fallback_primary=compact_text(patient_name) or compact_text(normalized.get("patient_name")),
        fallback_secondary=compact_text(case_number) or compact_text(normalized.get("case_number")),
    )
    normalized["record_identity"] = identity
    normalized["record_search_text"] = identity["search_text"]
    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    signatory_slots = normalize_signatory_slots(meta.get("signatories"), use_defaults=False)
    signatory_snapshots = normalize_record_signatory_snapshots(
        normalized.get("signatories"),
        signatory_slots,
    )
    normalized["signatories"] = signatory_snapshots
    signatory_search = " ".join(
        compact_text(snapshot.get("name"))
        for snapshot in signatory_snapshots
        if isinstance(snapshot, dict) and compact_text(snapshot.get("name"))
    )
    if signatory_search:
        normalized["record_search_text"] = compact_text(f"{normalized['record_search_text']} {signatory_search}")
    return normalized, identity


def next_record_key(session: Session, form_slug: str) -> str:
    base = f"rec_{slugify(form_slug or 'record')}"
    while True:
        candidate = f"{base}_{uuid4().hex[:8]}"
        exists = session.scalar(select(Record.id).where(Record.record_key == candidate))
        if exists is None:
            return candidate


def form_path_label_for_record(record: Record) -> str:
    location = serialize_form_location(record.form)
    if location["location_kind"] == "top_level":
        return compact_text(record.form.name) or "Untitled Form"
    return f"{location['location_path_label']} / {compact_text(record.form.name) or 'Untitled Form'}"


def serialize_record_asset(asset: RecordAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "field_block_id": asset.field_block_id,
        "field_key": asset.field_key,
        "kind": asset.kind,
        "storage_path": asset.storage_path,
        "original_filename": asset.original_filename,
        "mime_type": asset.mime_type,
        "size_bytes": asset.size_bytes,
        "image_width": asset.image_width,
        "image_height": asset.image_height,
        "created_at": asset.created_at.astimezone(timezone.utc).isoformat(),
    }


def format_timestamp_label(value: Any) -> str:
    if value is None:
        return ""
    try:
        local_value = value.astimezone()
    except Exception:
        return ""
    tz_name = compact_text(local_value.tzname()) or "local"
    return f"{local_value.strftime('%b %d, %Y %I:%M %p')} {tz_name}"


def serialize_record_actor(user: User | None) -> dict[str, Any] | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "full_name": compact_text(user.full_name),
        "email": compact_text(user.email),
        "login_id": compact_text(user.login_id),
        "role": compact_text(user.role),
    }


class RecordCompletionValidationError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("Complete this record after filling the missing required details.")


def has_meaningful_record_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, dict):
        if value.get("kind") == "image" and value.get("asset_id"):
            return True
        return any(has_meaningful_record_value(item) for item in value.values())
    if isinstance(value, list):
        return any(has_meaningful_record_value(item) for item in value)
    return bool(compact_text(value))


def collect_required_record_field_issues(
    blocks: list[dict[str, Any]],
    values: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = compact_text(block.get("kind"))
        if kind in {"section", "field_group"}:
            issues.extend(
                collect_required_record_field_issues(
                    normalize_items(block.get("children")),
                    values,
                )
            )
            continue
        if kind != "field":
            continue
        props = block.get("props") if isinstance(block.get("props"), dict) else {}
        if not bool(props.get("required")):
            continue
        block_id = compact_text(block.get("id"))
        field_name = compact_text(block.get("name")) or "Untitled field"
        if not has_meaningful_record_value(values.get(block_id)):
            issues.append(f"Fill in required field: {field_name}.")
    return issues


def list_record_completion_issues(
    record: Record,
    *,
    values: dict[str, Any],
    indexed_meta: dict[str, Any] | None = None,
) -> list[str]:
    issues: list[str] = []
    block_schema, _ = load_block_storage_document(record.form_version)
    issues.extend(
        collect_required_record_field_issues(
            normalize_items(block_schema.get("blocks")),
            values,
        )
    )
    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    signatory_slots = normalize_signatory_slots(meta.get("signatories"), use_defaults=False)
    resolved_meta = indexed_meta if isinstance(indexed_meta, dict) else load_json_object(record.indexed_meta_json)
    signatory_snapshots = normalize_record_signatory_snapshots(
        resolved_meta.get("signatories"),
        signatory_slots,
    )
    for slot, snapshot in zip(signatory_slots, signatory_snapshots):
        if not normalize_boolean_setting(slot.get("required"), default=False):
            continue
        slot_input_type = compact_text(slot.get("input_type")).lower()
        if slot_input_type in {"person_dropdown", "manual"} and not compact_text(snapshot.get("name")):
            issues.append(f"Choose required signatory: {compact_text(slot.get('label')) or 'Signatory'}.")
    return issues


def validate_record_completion(
    record: Record,
    *,
    values: dict[str, Any],
    indexed_meta: dict[str, Any] | None = None,
) -> None:
    issues = list_record_completion_issues(
        record,
        values=values,
        indexed_meta=indexed_meta,
    )
    if issues:
        raise RecordCompletionValidationError(issues)


def parse_numeric_answer(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = compact_text(value)
    if not text:
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def build_print_reference(props: dict[str, Any]) -> str:
    reference_text = compact_text(props.get("reference_text"))
    if reference_text:
        return reference_text

    normal_min = compact_text(props.get("normal_min"))
    normal_max = compact_text(props.get("normal_max"))
    if normal_min and normal_max:
        return f"{normal_min} to {normal_max}"
    if normal_min:
        return f">= {normal_min}"
    if normal_max:
        return f"<= {normal_max}"
    return ""


def evaluate_numeric_abnormal(props: dict[str, Any], value: Any) -> tuple[bool, str | None]:
    numeric_value = parse_numeric_answer(value)
    if numeric_value is None:
        return False, None

    normal_min = parse_numeric_answer(props.get("normal_min"))
    normal_max = parse_numeric_answer(props.get("normal_max"))
    if normal_min is not None and numeric_value < normal_min:
        return True, "low"
    if normal_max is not None and numeric_value > normal_max:
        return True, "high"
    return False, None


def evaluate_choice_abnormal(props: dict[str, Any], value: Any) -> tuple[bool, str | None]:
    selected = compact_text(value)
    if not selected:
        return False, None

    options = normalize_items(props.get("options"))
    normal_names = {
        compact_text(option.get("name"))
        for option in options
        if isinstance(option, dict) and bool(option.get("is_normal")) and compact_text(option.get("name"))
    }
    if not normal_names:
        return False, None
    if selected in normal_names:
        return False, None
    return True, "abnormal"


def evaluate_print_abnormal(props: dict[str, Any], value: Any) -> tuple[bool, str | None]:
    data_type = compact_text(props.get("data_type"))
    control = compact_text(props.get("control"))

    if data_type == "image":
        return False, None
    if control == "select":
        return evaluate_choice_abnormal(props, value)
    return evaluate_numeric_abnormal(props, value)


def build_print_display_value(
    props: dict[str, Any],
    value: Any,
    image_asset: dict[str, Any] | None,
    *,
    record_id: int,
) -> dict[str, Any]:
    data_type = compact_text(props.get("data_type"))
    if data_type == "image":
        if image_asset is None:
            return {
                "kind": "image",
                "text": "",
                "image_url": None,
                "filename": "",
                "is_empty": True,
            }
        return {
            "kind": "image",
            "text": "",
            "image_url": f"/records/{record_id}/assets/{image_asset['id']}/file",
            "filename": compact_text(image_asset.get("original_filename")),
            "is_empty": False,
        }

    text_value = compact_text(value)
    return {
        "kind": "text",
        "text": text_value,
        "image_url": None,
        "filename": "",
        "is_empty": not text_value,
    }


def build_print_utility_content(props: dict[str, Any]) -> str:
    return compact_text(props.get("content")) or ""


def build_print_table_columns(props: dict[str, Any]) -> list[str]:
    columns = [
        compact_text(column)
        for column in normalize_items(props.get("columns"))
        if compact_text(column)
    ]
    return columns or ["Column 1", "Column 2"]


def build_print_table_sample_rows(props: dict[str, Any]) -> int:
    try:
        sample_rows = int(props.get("sample_rows") or 0)
    except (TypeError, ValueError):
        sample_rows = 0
    return max(1, min(sample_rows or 3, 6))


def build_print_clinic_profile(
    clinic_profile: dict[str, Any] | None,
    *,
    logo_url: str = "",
) -> dict[str, Any]:
    profile = clinic_profile if isinstance(clinic_profile, dict) else {}
    name = compact_text(profile.get("clinic_name")) or ORGANIZATION_SHORT_NAME
    address = compact_text(profile.get("address"))
    contact_number = compact_text(profile.get("contact_number"))
    contact_email = compact_text(profile.get("contact_email"))
    contact_parts = [part for part in [contact_number, contact_email] if part]

    return {
        "name": name,
        "address": address,
        "contact_number": contact_number,
        "contact_email": contact_email,
        "contact_line": " | ".join(contact_parts),
        "logo_url": compact_text(logo_url) if bool(profile.get("has_logo")) else "",
    }


def build_print_field_item(
    block: dict[str, Any],
    values: dict[str, Any],
    asset_by_field: dict[str, dict[str, Any]],
    *,
    record_id: int,
    print_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    props = block.get("props") if isinstance(block.get("props"), dict) else {}
    config = print_config if isinstance(print_config, dict) else normalize_print_config({})
    block_id = compact_text(block.get("id"))
    raw_value = values.get(block_id)
    image_asset = asset_by_field.get(block_id)
    display = build_print_display_value(props, raw_value, image_asset, record_id=record_id)
    is_abnormal, abnormal_reason = evaluate_print_abnormal(props, raw_value)

    return {
        "kind": "field",
        "id": block_id,
        "name": compact_text(block.get("name")) or "Untitled Field",
        "unit_hint": compact_text(props.get("unit_hint")),
        "reference_text": build_print_reference(props),
        "display": display,
        "image_size": normalize_print_image_size(config.get("image_size")),
        "is_abnormal": is_abnormal,
        "abnormal_reason": abnormal_reason,
    }


def is_compact_grid_field_item(item: dict[str, Any]) -> bool:
    if compact_text(item.get("kind")) != "field":
        return False
    display = item.get("display") if isinstance(item.get("display"), dict) else {}
    return compact_text(display.get("kind")) != "image"


def compact_print_field_runs(items: list[dict[str, Any]], print_config: dict[str, Any]) -> list[dict[str, Any]]:
    if normalize_print_result_layout(print_config.get("result_layout")) != "compact_grid":
        return items

    compacted: list[dict[str, Any]] = []
    run: list[dict[str, Any]] = []

    def flush_run() -> None:
        nonlocal run
        if len(run) >= 4:
            compacted.append({"kind": "field_grid", "items": run})
        else:
            compacted.extend(run)
        run = []

    for item in items:
        if is_compact_grid_field_item(item):
            run.append(item)
            continue
        flush_run()
        compacted.append(item)
    flush_run()
    return compacted


def build_print_items(
    blocks: list[dict[str, Any]],
    values: dict[str, Any],
    asset_by_field: dict[str, dict[str, Any]],
    *,
    record_id: int,
    print_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    config = print_config if isinstance(print_config, dict) else normalize_print_config({})
    hide_empty_fields = normalize_boolean_setting(config.get("hide_empty_fields"), default=False)

    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = compact_text(block.get("kind"))
        props = block.get("props") if isinstance(block.get("props"), dict) else {}

        if kind == "section":
            child_items = build_print_items(
                normalize_items(block.get("children")),
                values,
                asset_by_field,
                record_id=record_id,
                print_config=config,
            )
            if hide_empty_fields and not child_items:
                continue
            items.append(
                {
                    "kind": "section",
                    "name": compact_text(block.get("name")) or "Untitled Section",
                    "show_title": normalize_boolean_setting(config.get("show_section_titles"), default=True),
                    "items": child_items,
                }
            )
            continue

        if kind == "field_group":
            child_items = build_print_items(
                normalize_items(block.get("children")),
                values,
                asset_by_field,
                record_id=record_id,
                print_config=config,
            )
            if hide_empty_fields and not child_items:
                continue
            items.append(
                {
                    "kind": "group",
                    "name": compact_text(block.get("name")) or "Untitled Group",
                    "show_title": normalize_boolean_setting(config.get("show_group_titles"), default=True),
                    "items": child_items,
                }
            )
            continue

        if kind == "field":
            item = build_print_field_item(
                block,
                values,
                asset_by_field,
                record_id=record_id,
                print_config=config,
            )
            if hide_empty_fields and bool(item.get("display", {}).get("is_empty")):
                continue
            items.append(item)
            continue

        if kind == "note":
            items.append(
                {
                    "kind": "note",
                    "name": compact_text(block.get("name")) or "",
                    "content": build_print_utility_content(props),
                }
            )
            continue

        if kind == "divider":
            items.append(
                {
                    "kind": "divider",
                    "name": compact_text(block.get("name")) or "",
                    "content": build_print_utility_content(props),
                }
            )
            continue

        if kind == "table":
            items.append(
                {
                    "kind": "table",
                    "name": compact_text(block.get("name")) or "Table",
                    "columns": build_print_table_columns(props),
                    "sample_rows": build_print_table_sample_rows(props),
                    "table_density": normalize_print_table_density(config.get("table_density")),
                }
            )
            continue

    return compact_print_field_runs(items, config)


def build_print_summary_items(
    print_config: dict[str, Any],
    serialized: dict[str, Any],
    values: dict[str, Any],
    *,
    issued_at_label: str,
) -> list[dict[str, str]]:
    if not normalize_boolean_setting(print_config.get("show_summary"), default=False):
        return []

    entry_schema = serialized.get("entry_schema") if isinstance(serialized.get("entry_schema"), dict) else {}
    identity = serialized.get("record_identity") if isinstance(serialized.get("record_identity"), dict) else {}
    fields = record_field_lookup(entry_schema)
    summary_items: list[dict[str, str]] = []

    for item in normalize_items(print_config.get("summary_items")):
        if not isinstance(item, dict):
            continue
        source = compact_text(item.get("source")).lower()
        label = compact_text(item.get("label")) or default_print_summary_label(source)
        value = ""

        if source == "field":
            field_id = compact_text(item.get("field_id"))
            field = fields.get(field_id)
            if not compact_text(item.get("label")) and field:
                label = compact_text(field.get("name")) or "Field"
            value = record_value_display_text(values.get(field_id))
        elif source == "primary_identity":
            label = compact_text(item.get("label")) or compact_text(identity.get("primary_label")) or "Record"
            value = compact_text(identity.get("primary_value"))
        elif source == "secondary_identity":
            label = compact_text(item.get("label")) or compact_text(identity.get("secondary_label")) or "Detail"
            value = compact_text(identity.get("secondary_value"))
        elif source == "record_key":
            value = compact_text(serialized.get("record_key"))
        elif source == "issued_at":
            value = issued_at_label
        elif source == "form_version":
            value = compact_text(serialized.get("form_version_label")) or f"v{serialized['form_version_number']}"

        if source in {"primary_identity", "secondary_identity"} and not value:
            continue
        summary_items.append({"label": label, "value": value or "Not set yet"})

    if not summary_items:
        summary_items.append({"label": "Record", "value": compact_text(serialized.get("record_key"))})
    return summary_items


def resolve_print_signature_name(
    source: str,
    *,
    field_id: str,
    manual_name: str,
    prepared_by_name: str,
    values: dict[str, Any],
) -> str:
    normalized_source = normalize_print_signature_source(source)
    if normalized_source == "prepared_by":
        return compact_text(prepared_by_name)
    if normalized_source == "manual":
        return compact_text(manual_name)
    if normalized_source == "field":
        return record_value_display_text(values.get(field_id))
    return ""


def build_print_signature_items(
    print_config: dict[str, Any],
    values: dict[str, Any],
    *,
    prepared_by_name: str,
    signatories: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    if signatories is not None:
        signature_items = signatory_snapshots_for_print(signatories)
        if signature_items:
            return signature_items

    signatures: list[dict[str, str]] = []
    for side, fallback_label in (("left", "Medical Technologist"), ("right", "Pathologist")):
        label = compact_text(print_config.get(f"signature_{side}_label")) or fallback_label
        source = normalize_print_signature_source(print_config.get(f"signature_{side}_source"))
        manual_name = compact_text(print_config.get(f"signature_{side}_name"))
        field_id = compact_text(print_config.get(f"signature_{side}_field_id"))
        signatures.append(
            {
                "label": label,
                "name": resolve_print_signature_name(
                    source,
                    field_id=field_id,
                    manual_name=manual_name,
                    prepared_by_name=prepared_by_name,
                    values=values,
                ),
                "source": source,
                "field_id": field_id if source == "field" else "",
            }
        )
    return signatures


def sample_print_value_for_field(block: dict[str, Any]) -> Any:
    props = block.get("props") if isinstance(block.get("props"), dict) else {}
    key = compact_text(props.get("key")).lower()
    name = compact_text(block.get("name")).lower()
    label = f"{key} {name}"
    data_type = compact_text(props.get("data_type")).lower()
    control = compact_text(props.get("control")).lower()

    if data_type == "image":
        return ""
    if "case" in label and "number" in label:
        return "NAIC-2026-0001"
    if key == "name" or name == "name" or "patient name" in label:
        return "Juan Dela Cruz"
    if "age" in label:
        return "34"
    if "sex" in label or "gender" in label:
        return "Male"
    if "date" in label and "time" in label:
        return "2026-04-29 09:30"
    if "date" in label:
        return "2026-04-29"
    if "time" in label:
        return "09:30"
    if "requesting" in label and "physician" in label:
        return "Dr. Reyes"
    if "room" in label:
        return "OPD"
    if "medical technologist" in label or "medtech" in label:
        return "Sample Medtech"
    if "pathologist" in label:
        return "Sample Pathologist"

    if control == "select":
        options = [
            option
            for option in normalize_items(props.get("options"))
            if isinstance(option, dict) and compact_text(option.get("name"))
        ]
        normal_option = next((option for option in options if bool(option.get("is_normal"))), None)
        selected_option = normal_option or (options[0] if options else None)
        return compact_text(selected_option.get("name")) if selected_option else "Sample option"

    if data_type == "number":
        normal_min = compact_text(props.get("normal_min"))
        normal_max = compact_text(props.get("normal_max"))
        if normal_min and normal_max:
            min_value = parse_numeric_answer(normal_min)
            max_value = parse_numeric_answer(normal_max)
            if min_value is not None and max_value is not None:
                return f"{((min_value + max_value) / 2):g}"
        return normal_min or normal_max or "1.0"

    return "Sample value"


def build_sample_print_values(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = compact_text(block.get("kind"))
        if kind == "field":
            block_id = compact_text(block.get("id"))
            if block_id:
                values[block_id] = sample_print_value_for_field(block)
            continue
        values.update(build_sample_print_values(normalize_items(block.get("children"))))
    return values


def print_item_fit_units(items: list[dict[str, Any]]) -> float:
    units = 0.0
    for item in normalize_items(items):
        if not isinstance(item, dict):
            continue
        kind = compact_text(item.get("kind"))
        if kind == "section":
            units += 1.7 + print_item_fit_units(normalize_items(item.get("items")))
        elif kind == "group":
            units += 1.25 + print_item_fit_units(normalize_items(item.get("items")))
        elif kind == "field":
            display = item.get("display") if isinstance(item.get("display"), dict) else {}
            units += 1.15
            if compact_text(item.get("reference_text")):
                units += 0.25
            if display.get("kind") == "image" and not display.get("is_empty"):
                units += 5.0
        elif kind == "field_grid":
            fields = normalize_items(item.get("items"))
            row_count = max(1, (len(fields) + 1) // 2)
            reference_count = sum(
                1
                for field in fields
                if isinstance(field, dict) and compact_text(field.get("reference_text"))
            )
            units += 0.45 + (row_count * 0.95) + (reference_count * 0.15)
        elif kind == "table":
            try:
                sample_rows = int(item.get("sample_rows") or 3)
            except (TypeError, ValueError):
                sample_rows = 3
            units += 1.4 + (max(1, min(sample_rows, 6)) * 0.65)
        elif kind in {"note", "divider"}:
            units += 0.8
    return units


def estimate_print_page_fit(document: dict[str, Any]) -> dict[str, Any]:
    print_config = document.get("print_config") if isinstance(document.get("print_config"), dict) else {}
    density = normalize_print_density(print_config.get("density"))
    show_summary = normalize_boolean_setting(print_config.get("show_summary"), default=False)
    summary_count = len(normalize_items(document.get("summary_items"))) if show_summary else 0
    base_units = 8.5
    if normalize_boolean_setting(print_config.get("show_logo"), default=True):
        base_units += 1.2
    if normalize_boolean_setting(print_config.get("show_clinic_info"), default=True):
        base_units += 1.0
    if normalize_boolean_setting(print_config.get("show_signatures"), default=True):
        base_units += 4.2
    if show_summary and summary_count:
        base_units += max(1, (summary_count + 2) // 3) * 2.2

    density_factor = 1.14 if density == "comfortable" else 1.0
    estimated_units = (base_units + print_item_fit_units(normalize_items(document.get("items")))) * density_factor
    limit_units = 52.0
    if estimated_units <= limit_units * 0.82:
        status = "likely"
        label = "Likely fits one page"
        detail = "The current sample looks safely within the A4 target."
    elif estimated_units <= limit_units:
        status = "tight"
        label = "May be tight"
        detail = "This should be checked in browser print preview before release."
    else:
        status = "long"
        label = "Likely exceeds one page"
        detail = "Consider compact density, fewer summary rows, or hiding optional output later."

    return {
        "status": status,
        "label": label,
        "detail": detail,
        "estimated_units": round(estimated_units, 1),
        "limit_units": limit_units,
    }


def build_form_print_preview_document(
    *,
    form_name: str,
    form_path_label: str = "",
    block_schema: dict[str, Any],
    clinic_profile: dict[str, Any] | None = None,
    clinic_logo_url: str = "",
) -> dict[str, Any]:
    entry_schema = json.loads(json.dumps(block_schema if isinstance(block_schema, dict) else {}))
    if not entry_schema:
        entry_schema = {
            "schema_version": 1,
            "source_kind": ACTIVE_BLOCK_SCHEMA_SOURCE,
            "meta": {},
            "blocks": [],
        }
    normalize_active_block_storage_schema(entry_schema)

    values = build_sample_print_values(normalize_items(entry_schema.get("blocks")))
    identity = resolve_record_identity(
        entry_schema,
        values,
        fallback_primary="Juan Dela Cruz",
        fallback_secondary="NAIC-2026-0001",
    )
    meta = entry_schema.get("meta") if isinstance(entry_schema.get("meta"), dict) else {}
    print_config = normalize_print_config(meta.get("print_config"))
    signatory_slots = normalize_signatory_slots(meta.get("signatories"), use_defaults=False)
    signatory_samples = normalize_record_signatory_snapshots({}, signatory_slots)
    print_accent_ink = print_accent_text_color(print_config.get("accent_color"))
    normalized_form_name = compact_text(form_name) or "Untitled Form"
    normalized_path = compact_text(form_path_label) or "Builder preview"
    serialized = {
        "id": 0,
        "record_key": "PREVIEW-0001",
        "entry_schema": entry_schema,
        "values": values,
        "asset_by_field_id": {},
        "record_identity": identity,
        "status": "draft",
        "form_name": normalized_form_name,
        "form_path_label": normalized_path,
        "form_version_number": "draft",
        "form_version_label": "Draft preview",
        "created_at_label": "Preview sample",
        "updated_at_label": "Preview sample",
        "completed_at_label": "",
    }
    summary_items = build_print_summary_items(
        print_config,
        serialized,
        values,
        issued_at_label="Preview sample",
    )
    prepared_by_name = "Sample Medtech"
    document = {
        "record": serialized,
        "clinic": build_print_clinic_profile(clinic_profile, logo_url=clinic_logo_url),
        "print_config": print_config,
        "print_accent_ink": print_accent_ink,
        "template": {
            "id": "clinic_lab_result_v1",
            "name": "Clinic lab result",
            "page_size": "A4",
        },
        "title": normalized_form_name,
        "status": "draft",
        "display_title": compact_text(identity.get("primary_value")) or normalized_form_name,
        "display_subtitle": compact_text(identity.get("secondary_value")),
        "display_subtitle_label": compact_text(identity.get("secondary_label")),
        "summary_items": summary_items,
        "patient_name": compact_text(identity.get("primary_value")),
        "patient_age": "",
        "patient_sex": "",
        "case_number": compact_text(identity.get("secondary_value")),
        "form_name": normalized_form_name,
        "form_path_label": normalized_path,
        "form_version_number": "draft",
        "record_key": "PREVIEW-0001",
        "created_at": "",
        "updated_at": "",
        "created_at_label": "Preview sample",
        "updated_at_label": "Preview sample",
        "completed_at_label": "",
        "issued_at_label": "Preview sample",
        "prepared_by_name": prepared_by_name,
        "signatures": build_print_signature_items(
            print_config,
            values,
            prepared_by_name=prepared_by_name,
            signatories=signatory_samples,
        ),
        "items": build_print_items(
            normalize_items(entry_schema.get("blocks")),
            values,
            {},
            record_id=0,
            print_config=print_config,
        ),
    }
    document["fit_estimate"] = estimate_print_page_fit(document)
    return document


def build_record_print_document(
    record: Record,
    *,
    clinic_profile: dict[str, Any] | None = None,
    clinic_logo_url: str = "",
) -> dict[str, Any]:
    serialized = serialize_record(record, include_entry_schema=True)
    entry_schema = serialized.get("entry_schema") or {}
    values = serialized.get("values") or {}
    asset_by_field = serialized.get("asset_by_field_id") or {}
    updated_by = serialized.get("updated_by") or serialized.get("created_by") or {}
    issued_at_label = (
        serialized.get("completed_at_label")
        or serialized.get("updated_at_label")
        or serialized.get("created_at_label")
        or ""
    )
    meta = entry_schema.get("meta") if isinstance(entry_schema.get("meta"), dict) else {}
    print_config = normalize_print_config(meta.get("print_config"))
    print_accent_ink = print_accent_text_color(print_config.get("accent_color"))
    summary_items = build_print_summary_items(
        print_config,
        serialized,
        values,
        issued_at_label=issued_at_label or "Not set yet",
    )
    prepared_by_name = compact_text(updated_by.get("full_name")) or ""

    document = {
        "record": serialized,
        "clinic": build_print_clinic_profile(clinic_profile, logo_url=clinic_logo_url),
        "print_config": print_config,
        "print_accent_ink": print_accent_ink,
        "template": {
            "id": "clinic_lab_result_v1",
            "name": "Clinic lab result",
            "page_size": "A4",
        },
        "title": serialized["form_name"],
        "status": serialized["status"],
        "display_title": serialized["display_title"],
        "display_subtitle": serialized["display_subtitle"],
        "display_subtitle_label": serialized["display_subtitle_label"],
        "summary_items": summary_items,
        "patient_name": serialized["patient_name"] or "",
        "patient_age": serialized["patient_age"] or "",
        "patient_sex": serialized["patient_sex"] or "",
        "case_number": serialized["case_number"] or "",
        "form_name": serialized["form_name"],
        "form_path_label": serialized["form_path_label"],
        "form_version_number": serialized["form_version_number"],
        "record_key": serialized["record_key"],
        "created_at": serialized["created_at"],
        "updated_at": serialized["updated_at"],
        "created_at_label": serialized.get("created_at_label") or "",
        "updated_at_label": serialized.get("updated_at_label") or "",
        "completed_at_label": serialized.get("completed_at_label") or "",
        "issued_at_label": issued_at_label,
        "prepared_by_name": prepared_by_name,
        "signatures": build_print_signature_items(
            print_config,
            values,
            prepared_by_name=prepared_by_name,
            signatories=normalize_items(serialized.get("signatories")),
        ),
        "items": build_print_items(
            normalize_items(entry_schema.get("blocks")),
            values,
            asset_by_field,
            record_id=serialized["id"],
            print_config=print_config,
        ),
    }
    document["fit_estimate"] = estimate_print_page_fit(document)
    return document


def serialize_record(
    record: Record,
    *,
    include_values: bool = True,
    include_entry_schema: bool = False,
) -> dict[str, Any]:
    location = serialize_form_location(record.form)
    indexed_meta = load_json_object(record.indexed_meta_json)
    stored_values = normalize_record_values(load_json_object(record.values_json))
    block_schema_for_signatories, _ = load_block_storage_document(record.form_version)
    block_meta_for_signatories = (
        block_schema_for_signatories.get("meta")
        if isinstance(block_schema_for_signatories.get("meta"), dict)
        else {}
    )
    signatory_slots = normalize_signatory_slots(block_meta_for_signatories.get("signatories"), use_defaults=False)
    signatory_snapshots = normalize_record_signatory_snapshots(
        indexed_meta.get("signatories"),
        signatory_slots,
    )
    stored_identity = indexed_meta.get("record_identity") if isinstance(indexed_meta.get("record_identity"), dict) else {}
    if stored_identity:
        identity = resolve_record_identity(
            {"meta": {"record_identity": stored_identity}, "blocks": []},
            stored_values,
            fallback_primary=compact_text(stored_identity.get("primary_value")) or compact_text(record.patient_name),
            fallback_secondary=compact_text(stored_identity.get("secondary_value")) or compact_text(record.case_number),
        )
        identity.update(
            {
                "primary_label": compact_text(stored_identity.get("primary_label")),
                "primary_value": compact_text(stored_identity.get("primary_value")) or compact_text(record.patient_name),
                "secondary_label": compact_text(stored_identity.get("secondary_label")),
                "secondary_value": compact_text(stored_identity.get("secondary_value")) or compact_text(record.case_number),
                "searchable_fields": normalize_items(stored_identity.get("searchable_fields")),
                "search_text": compact_text(stored_identity.get("search_text")),
            }
        )
    else:
        block_schema_for_identity, _ = load_block_storage_document(record.form_version)
        identity = resolve_record_identity(
            block_schema_for_identity,
            stored_values,
            fallback_primary=compact_text(record.patient_name),
            fallback_secondary=compact_text(record.case_number),
        )

    display_title = compact_text(identity.get("primary_value")) or compact_text(record.patient_name) or compact_text(record.form.name) or "Untitled record"
    display_subtitle = compact_text(identity.get("secondary_value")) or compact_text(record.case_number) or record.record_key
    display_subtitle_label = compact_text(identity.get("secondary_label")) or ("Record" if display_subtitle == record.record_key else "Secondary")
    asset_by_field_id = {
        compact_text(asset.field_block_id): serialize_record_asset(asset)
        for asset in record.assets
        if compact_text(asset.field_block_id)
    }
    payload = {
        "id": record.id,
        "record_key": record.record_key,
        "status": record.status,
        "patient_name": record.patient_name,
        "patient_age": compact_text(indexed_meta.get("patient_age")) or None,
        "patient_sex": compact_text(indexed_meta.get("patient_sex")) or None,
        "case_number": record.case_number,
        "display_title": display_title,
        "display_subtitle": display_subtitle,
        "display_subtitle_label": display_subtitle_label,
        "record_identity": identity,
        "form_slug": record.form.slug,
        "form_name": record.form.name,
        "form_path_label": form_path_label_for_record(record),
        "location_name": location["location_name"],
        "location_path_label": location["location_path_label"],
        "location_node_key": location["location_node_key"],
        "form_version_id": record.form_version_id,
        "form_version_number": record.form_version.version_number,
        "assets": [serialize_record_asset(asset) for asset in record.assets],
        "asset_by_field_id": asset_by_field_id,
        "created_at": record.created_at.astimezone(timezone.utc).isoformat(),
        "updated_at": record.updated_at.astimezone(timezone.utc).isoformat(),
        "completed_at": record.completed_at.astimezone(timezone.utc).isoformat() if record.completed_at else None,
        "created_at_label": format_timestamp_label(record.created_at),
        "updated_at_label": format_timestamp_label(record.updated_at),
        "completed_at_label": format_timestamp_label(record.completed_at) if record.completed_at else "",
        "created_by": serialize_record_actor(record.created_by_user),
        "updated_by": serialize_record_actor(record.updated_by_user),
        "indexed_meta": indexed_meta,
        "signatories": signatory_snapshots,
    }
    if include_values:
        payload["values"] = stored_values
    if include_entry_schema:
        payload["entry_schema"] = block_schema_for_signatories
    return payload


def get_record_or_none(session: Session, record_id: int) -> Record | None:
    return session.scalar(
        select(Record)
        .where(Record.id == record_id)
        .options(
            selectinload(Record.form).selectinload(FormDefinition.library_node).selectinload(LibraryNode.parent),
            selectinload(Record.form_version),
            selectinload(Record.assets),
            selectinload(Record.created_by_user),
            selectinload(Record.updated_by_user),
        )
    )


def record_query_with_relationships():
    return select(Record).options(
        selectinload(Record.form).selectinload(FormDefinition.library_node).selectinload(LibraryNode.parent),
        selectinload(Record.form_version),
        selectinload(Record.assets),
        selectinload(Record.created_by_user),
        selectinload(Record.updated_by_user),
    )


def apply_record_filters(
    query,
    *,
    status: str | None = None,
    search: str | None = None,
):
    normalized_status = compact_text(status)
    if normalized_status:
        query = query.where(Record.status == normalized_status)

    search_text = compact_text(search)
    if search_text:
        search_pattern = f"%{search_text}%"
        query = query.join(FormDefinition, Record.form_id == FormDefinition.id).where(
            or_(
                Record.patient_name.ilike(search_pattern),
                Record.case_number.ilike(search_pattern),
                Record.record_key.ilike(search_pattern),
                Record.indexed_meta_json.ilike(search_pattern),
                Record.values_json.ilike(search_pattern),
                FormDefinition.name.ilike(search_pattern),
            )
        )

    return query


def count_records(
    session: Session,
    *,
    status: str | None = None,
    search: str | None = None,
) -> int:
    query = select(func.count(Record.id))
    query = apply_record_filters(query, status=status, search=search)
    return int(session.scalar(query) or 0)


def list_records(
    session: Session,
    *,
    status: str | None = None,
    search: str | None = None,
    limit: int = 24,
) -> list[dict[str, Any]]:
    query = record_query_with_relationships()
    query = apply_record_filters(query, status=status, search=search)
    query = query.order_by(Record.updated_at.desc(), Record.id.desc()).limit(limit)
    records = session.scalars(query).all()
    return [serialize_record(record, include_values=False) for record in records]

def create_record(
    session: Session,
    payload: RecordCreatePayload,
    *,
    actor_user_id: int | None = None,
) -> dict[str, Any]:
    form_slug = compact_text(payload.form_slug)
    if not form_slug:
        raise ValueError("Choose a form before you continue.")

    definition = get_form_or_none(session, form_slug)
    if definition is None:
        raise ValueError("Form not found.")

    version = current_version(definition)
    if version is None:
        raise ValueError("This form has no current version yet.")

    patient_name = compact_text(payload.patient_name)
    patient_age = compact_text(payload.patient_age)
    patient_sex = compact_text(payload.patient_sex)
    case_number = compact_text(payload.case_number)
    normalized_values = normalize_record_values(payload.values)
    indexed_meta, identity = build_record_indexed_meta(
        payload.indexed_meta,
        version,
        normalized_values,
        patient_name=patient_name,
        patient_age=patient_age,
        patient_sex=patient_sex,
        case_number=case_number,
    )

    record = Record(
        record_key=next_record_key(session, definition.slug),
        form_id=definition.id,
        form_version_id=version.id,
        status="draft",
        patient_name=identity["primary_value"] or patient_name or None,
        case_number=identity["secondary_value"] or case_number or None,
        values_json=json.dumps(normalized_values, ensure_ascii=False),
        indexed_meta_json=json.dumps(indexed_meta, ensure_ascii=False),
        created_by_user_id=actor_user_id,
        updated_by_user_id=actor_user_id,
    )
    session.add(record)
    session.commit()
    session.expire_all()

    created = get_record_or_none(session, record.id)
    if created is None:
        raise ValueError("Record could not be loaded.")
    return serialize_record(created, include_entry_schema=True)


def update_record(
    session: Session,
    record_id: int,
    payload: RecordUpdatePayload,
    *,
    preserve_asset_fields: bool = False,
    actor_user_id: int | None = None,
) -> dict[str, Any]:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise KeyError(record_id)
    if record.status == "completed":
        raise ValueError("Completed records are read-only.")

    existing_meta = load_json_object(record.indexed_meta_json)
    patient_name = compact_text(payload.patient_name) if payload.patient_name is not None else compact_text(record.patient_name)
    patient_age = compact_text(payload.patient_age) if payload.patient_age is not None else compact_text(existing_meta.get("patient_age"))
    patient_sex = compact_text(payload.patient_sex) if payload.patient_sex is not None else compact_text(existing_meta.get("patient_sex"))
    case_number = compact_text(payload.case_number) if payload.case_number is not None else compact_text(record.case_number)
    normalized_values = normalize_record_values(payload.values)
    if preserve_asset_fields:
        normalized_values = preserve_existing_asset_values(current_record_values(record), normalized_values)
    indexed_meta, identity = build_record_indexed_meta(
        {
            **existing_meta,
            **(payload.indexed_meta if isinstance(payload.indexed_meta, dict) else {}),
        },
        record.form_version,
        normalized_values,
        patient_name=patient_name,
        patient_age=patient_age,
        patient_sex=patient_sex,
        case_number=case_number,
    )

    record.patient_name = identity["primary_value"] or patient_name or None
    record.case_number = identity["secondary_value"] or case_number or None
    record.values_json = json.dumps(normalized_values, ensure_ascii=False)
    record.indexed_meta_json = json.dumps(indexed_meta, ensure_ascii=False)
    record.updated_by_user_id = actor_user_id
    session.commit()
    session.expire_all()

    updated = get_record_or_none(session, record_id)
    if updated is None:
        raise KeyError(record_id)
    return serialize_record(updated, include_entry_schema=True)


def complete_record(
    session: Session,
    record_id: int,
    payload: RecordUpdatePayload,
    *,
    preserve_asset_fields: bool = False,
    actor_user_id: int | None = None,
) -> dict[str, Any]:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise KeyError(record_id)
    if record.status == "completed":
        raise ValueError("This record is already completed.")

    existing_meta = load_json_object(record.indexed_meta_json)
    patient_name = compact_text(payload.patient_name) if payload.patient_name is not None else compact_text(record.patient_name)
    patient_age = compact_text(payload.patient_age) if payload.patient_age is not None else compact_text(existing_meta.get("patient_age"))
    patient_sex = compact_text(payload.patient_sex) if payload.patient_sex is not None else compact_text(existing_meta.get("patient_sex"))
    case_number = compact_text(payload.case_number) if payload.case_number is not None else compact_text(record.case_number)
    normalized_values = normalize_record_values(payload.values)
    if preserve_asset_fields:
        normalized_values = preserve_existing_asset_values(current_record_values(record), normalized_values)
    indexed_meta, identity = build_record_indexed_meta(
        {
            **existing_meta,
            **(payload.indexed_meta if isinstance(payload.indexed_meta, dict) else {}),
        },
        record.form_version,
        normalized_values,
        patient_name=patient_name,
        patient_age=patient_age,
        patient_sex=patient_sex,
        case_number=case_number,
    )

    validate_record_completion(
        record,
        values=normalized_values,
        indexed_meta=indexed_meta,
    )

    record.patient_name = identity["primary_value"] or patient_name or None
    record.case_number = identity["secondary_value"] or case_number or None
    record.values_json = json.dumps(normalized_values, ensure_ascii=False)
    record.indexed_meta_json = json.dumps(indexed_meta, ensure_ascii=False)
    record.status = "completed"
    record.completed_at = utc_now()
    record.updated_by_user_id = actor_user_id
    session.commit()
    session.expire_all()

    completed = get_record_or_none(session, record_id)
    if completed is None:
        raise KeyError(record_id)
    return serialize_record(completed, include_entry_schema=True)


def store_record_image_asset(
    session: Session,
    *,
    record_id: int,
    field_block_id: str,
    original_filename: str,
    content_type: str | None,
    file_bytes: bytes,
) -> dict[str, Any]:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise KeyError(record_id)
    if record.status == "completed":
        raise ValueError("Completed records are read-only.")

    field_block = resolve_record_image_field(record, field_block_id)
    mime_type = compact_text(content_type)
    extension = ALLOWED_IMAGE_CONTENT_TYPES.get(mime_type)
    if extension is None:
        raise ValueError("Only JPG, PNG, and WebP images are allowed.")
    if not file_bytes:
        raise ValueError("Choose an image before uploading.")
    if len(file_bytes) > MAX_RECORD_IMAGE_BYTES:
        raise ValueError("Image must be 10 MB or smaller.")

    props = field_block.get("props") if isinstance(field_block.get("props"), dict) else {}
    field_key = compact_text(props.get("key")) or None
    safe_field = slugify(field_key or field_block_id)
    destination_dir = RECORD_UPLOADS_DIR / record.record_key / safe_field
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_path = destination_dir / f"{uuid4().hex}{extension}"
    destination_path.write_bytes(file_bytes)

    current_values = current_record_values(record)
    existing_ref = current_values.get(field_block_id)
    if isinstance(existing_ref, dict) and existing_ref.get("asset_id"):
        existing_asset = session.scalar(
            select(RecordAsset).where(
                RecordAsset.id == int(existing_ref["asset_id"]),
                RecordAsset.record_id == record.id,
            )
        )
        if existing_asset is not None:
            remove_record_asset(session, existing_asset)

    asset = RecordAsset(
        record_id=record.id,
        field_block_id=compact_text(field_block_id),
        field_key=field_key,
        kind="image",
        storage_path=str(destination_path),
        original_filename=compact_text(original_filename) or destination_path.name,
        mime_type=mime_type or None,
        size_bytes=len(file_bytes),
        image_width=None,
        image_height=None,
    )
    session.add(asset)
    session.flush()

    current_values[compact_text(field_block_id)] = {
        "asset_id": asset.id,
        "kind": "image",
    }
    record.values_json = json.dumps(current_values, ensure_ascii=False)
    session.commit()
    session.expire_all()

    updated = get_record_or_none(session, record_id)
    if updated is None:
        raise KeyError(record_id)
    return serialize_record(updated, include_entry_schema=True)


def delete_record_asset(session: Session, record_id: int, asset_id: int) -> dict[str, Any]:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise KeyError(record_id)
    if record.status == "completed":
        raise ValueError("Completed records are read-only.")

    asset = session.scalar(
        select(RecordAsset).where(
            RecordAsset.id == asset_id,
            RecordAsset.record_id == record.id,
        )
    )
    if asset is None:
        raise KeyError(asset_id)

    current_values = current_record_values(record)
    field_id = compact_text(asset.field_block_id)
    current_ref = current_values.get(field_id)
    if isinstance(current_ref, dict) and current_ref.get("asset_id") == asset.id:
        current_values.pop(field_id, None)
        record.values_json = json.dumps(current_values, ensure_ascii=False)

    remove_record_asset(session, asset)
    session.commit()
    session.expire_all()

    updated = get_record_or_none(session, record_id)
    if updated is None:
        raise KeyError(record_id)
    return serialize_record(updated, include_entry_schema=True)


def serialize_form_location(definition: FormDefinition) -> dict[str, Any]:
    form_node = definition.library_node
    parent_node = form_node.parent if form_node is not None else None

    if parent_node is None:
        return {
            "location_name": "Top level",
            "location_path_label": "Top level",
            "location_node_key": None,
            "location_kind": "top_level",
        }

    path: list[str] = []
    cursor = parent_node
    while cursor is not None:
        path.append(compact_text(cursor.name) or "Untitled Folder")
        cursor = cursor.parent
    path.reverse()

    location_name = path[-1] if path else compact_text(parent_node.name) or "Untitled Folder"
    location_path_label = " / ".join(path) if path else location_name
    return {
        "location_name": location_name,
        "location_path_label": location_path_label,
        "location_node_key": compact_text(parent_node.node_key) or None,
        "location_kind": "folder",
    }


def serialize_form(definition: FormDefinition) -> dict[str, Any]:
    version = current_version(definition)
    if version is None:
        raise ValueError(f"Form '{definition.slug}' has no versions.")

    block_schema, _ = load_block_storage_document(version)

    location = serialize_form_location(definition)
    return {
        "slug": definition.slug,
        "name": definition.name,
        "location_name": location["location_name"],
        "location_path_label": location["location_path_label"],
        "location_node_key": location["location_node_key"],
        "location_kind": location["location_kind"],
        "library_parent_node_key": definition.library_parent_node_key,
        "current_version_number": version.version_number,
        "summary": version.summary,
        "updated_at": definition.updated_at.astimezone(timezone.utc).isoformat(),
        "block_schema": block_schema,
    }


def get_form_or_none(session: Session, slug: str) -> FormDefinition | None:
    return session.scalar(
        select(FormDefinition)
        .where(FormDefinition.slug == slug)
        .options(
            selectinload(FormDefinition.versions),
            selectinload(FormDefinition.library_node).selectinload(LibraryNode.parent),
        )
    )


def list_container_choices(session: Session) -> list[dict[str, Any]]:
    tree = list_library_tree(session)
    choices: list[dict[str, Any]] = []

    def walk(nodes: list[dict[str, Any]], path: list[str]) -> None:
        for node in nodes:
            if compact_text(node.get("kind")) != "container" or node.get("archived"):
                continue
            current_path = [*path, compact_text(node.get("name")) or "Untitled Folder"]
            children = node.get("children", [])
            next_form_order = max((int(child.get("order") or 0) for child in children), default=0) + 1
            choices.append(
                {
                    "node_key": compact_text(node.get("id")),
                    "name": compact_text(node.get("name")) or "Untitled Folder",
                    "folder_path_label": " / ".join(current_path),
                    "depth": len(path),
                    "order": int(node.get("order") or 999),
                    "next_form_order": next_form_order,
                }
            )
            walk(children, current_path)

    walk(tree, [])
    return choices


def list_form_choices(session: Session) -> list[dict[str, Any]]:
    tree = list_library_tree(session)
    choices: list[dict[str, Any]] = []

    def walk(nodes: list[dict[str, Any]], path: list[str]) -> None:
        for node in nodes:
            if node.get("archived"):
                continue
            kind = compact_text(node.get("kind"))
            if kind == "container":
                current_path = [*path, compact_text(node.get("name")) or "Untitled Folder"]
                walk(node.get("children", []), current_path)
                continue
            if kind != "form":
                continue
            form = node.get("form") or {}
            form_name = compact_text(form.get("name")) or compact_text(node.get("name")) or "Untitled Form"
            current_path = [*path, form_name]
            choices.append(
                {
                    "slug": compact_text(form.get("slug")),
                    "name": form_name,
                    "location_name": path[-1] if path else "Top level",
                    "location_path_label": " / ".join(path) or "Top level",
                    "form_path_label": " / ".join(current_path),
                    "depth": len(path),
                    "order": int(node.get("order") or 1),
                    "current_version_number": int(form.get("current_version_number") or 1),
                }
            )

    walk(tree, [])
    return choices


def next_available_container_node_key(session: Session, preferred: str) -> str:
    base = f"container:{slugify(preferred or 'folder')}"
    key = base
    suffix = 2
    while session.scalar(select(LibraryNode.id).where(LibraryNode.node_key == key)) is not None:
        key = f"{base}_{suffix}"
        suffix += 1
    return key


def ensure_container_node(
    session: Session,
    name: str,
    parent_node_key: str | None = None,
) -> LibraryNode:
    container_name = compact_text(name) or "Untitled Folder"
    parent_key = compact_text(parent_node_key)
    parent_id: int | None = None

    if parent_key:
        parent = session.scalar(select(LibraryNode).where(LibraryNode.node_key == parent_key))
        if parent is not None and parent.kind == "container":
            parent_id = parent.id
            if parent.archived:
                parent.archived = False

    query = select(LibraryNode).where(
        LibraryNode.kind == "container",
        LibraryNode.name == container_name,
    )
    if parent_id is None:
        query = query.where(LibraryNode.parent_id.is_(None))
    else:
        query = query.where(LibraryNode.parent_id == parent_id)

    existing = session.scalar(query.order_by(LibraryNode.id))
    if existing is not None:
        if existing.archived:
            existing.archived = False
        return existing

    sibling_query = select(LibraryNode).where(LibraryNode.parent_id == parent_id) if parent_id is not None else select(LibraryNode).where(LibraryNode.parent_id.is_(None))
    next_order = max((node.node_order for node in session.scalars(sibling_query).all()), default=0) + 1
    container = LibraryNode(
        node_key=next_available_container_node_key(session, container_name),
        kind="container",
        name=container_name,
        parent_id=parent_id,
        node_order=next_order,
        archived=False,
    )
    session.add(container)
    session.flush()
    return container


def create_container(
    session: Session,
    name: str,
    parent_node_key: str | None = None,
) -> LibraryNode:
    container_name = compact_text(name)
    if not container_name:
        raise ValueError("Name the folder before you continue.")

    parent_key = compact_text(parent_node_key)
    parent_id: int | None = None
    if parent_key:
        parent = session.scalar(select(LibraryNode).where(LibraryNode.node_key == parent_key))
        if parent is None or parent.kind != "container":
            raise ValueError("Parent folder not found.")
        parent_id = parent.id

    existing_query = select(LibraryNode).where(
        LibraryNode.kind == "container",
        LibraryNode.name == container_name,
    )
    if parent_id is None:
        existing_query = existing_query.where(LibraryNode.parent_id.is_(None))
    else:
        existing_query = existing_query.where(LibraryNode.parent_id == parent_id)

    existing = session.scalar(existing_query.limit(1))
    if existing is not None:
        raise ValueError("A folder with this name already exists here.")

    container = ensure_container_node(session, container_name, parent_key or None)
    session.commit()
    return container


def get_container_or_none(session: Session, node_key: str) -> LibraryNode | None:
    key = compact_text(node_key)
    if not key:
        return None
    node = session.scalar(select(LibraryNode).where(LibraryNode.node_key == key))
    if node is None or node.kind != "container":
        return None
    return node


def next_node_order(session: Session, parent_id: int | None, *, exclude_node_id: int | None = None) -> int:
    query = (
        select(LibraryNode).where(LibraryNode.parent_id == parent_id)
        if parent_id is not None
        else select(LibraryNode).where(LibraryNode.parent_id.is_(None))
    )
    siblings = session.scalars(query).all()
    return max(
        (
            node.node_order
            for node in siblings
            if exclude_node_id is None or node.id != exclude_node_id
        ),
        default=0,
    ) + 1


def resolve_target_container(session: Session, parent_node_key: str | None) -> LibraryNode | None:
    target_key = compact_text(parent_node_key)
    if not target_key:
        return None
    target = get_container_or_none(session, target_key)
    if target is None:
        raise ValueError("Folder not found.")
    if target.archived:
        target.archived = False
    return target


def upsert_form_node_location(
    session: Session,
    definition: FormDefinition,
    *,
    parent_node_key: str | None,
    node_order: int | None = None,
) -> LibraryNode:
    target_parent = resolve_target_container(session, parent_node_key)
    target_parent_id = target_parent.id if target_parent is not None else None
    desired_order = int(node_order or 1)
    node_key = form_node_key(definition.slug)

    form_node = definition.library_node or session.scalar(
        select(LibraryNode).where(LibraryNode.form_definition_id == definition.id)
    )
    if form_node is None:
        form_node = session.scalar(select(LibraryNode).where(LibraryNode.node_key == node_key))

    if form_node is None:
        form_node = LibraryNode(
            node_key=node_key,
            kind="form",
            name=definition.name,
            parent_id=target_parent_id,
            node_order=desired_order,
            archived=False,
            form_definition_id=definition.id,
        )
        session.add(form_node)
        session.flush()
    else:
        form_node.kind = "form"
        form_node.name = definition.name
        form_node.parent_id = target_parent_id
        form_node.node_order = desired_order
        form_node.archived = False
        form_node.form_definition_id = definition.id

    definition.library_parent_node_key = target_parent.node_key if target_parent is not None else None
    return form_node


def create_form_definition_record(
    *,
    slug: str,
    name: str,
    parent_node_key: str | None = None,
) -> FormDefinition:
    return FormDefinition(
        slug=slug,
        name=name,
        library_parent_node_key=parent_node_key,
    )


def sync_definition_parent_node_key(
    session: Session,
    definition: FormDefinition,
    *,
    form_node: LibraryNode | None = None,
) -> bool:
    node = form_node or definition.library_node or session.scalar(
        select(LibraryNode).where(LibraryNode.form_definition_id == definition.id)
    )
    if node is None:
        return False

    parent_container = None
    if node.parent_id is not None:
        parent_container = session.scalar(select(LibraryNode).where(LibraryNode.id == node.parent_id))

    derived_parent_key = parent_container.node_key if parent_container is not None and parent_container.kind == "container" else None
    changed = False
    if compact_text(definition.library_parent_node_key) != compact_text(derived_parent_key):
        definition.library_parent_node_key = derived_parent_key
        changed = True
    return changed


def definition_schema_order_hint(definition: FormDefinition) -> int:
    version = current_version(definition)
    if version is not None:
        schema = load_legacy_storage_document(version)
        return int(schema.get("order") or 1)
    return 1


def container_is_inside(session: Session, candidate: LibraryNode | None, ancestor_id: int) -> bool:
    current = candidate
    while current is not None:
        if current.id == ancestor_id:
            return True
        if current.parent_id is None:
            return False
        current = session.scalar(select(LibraryNode).where(LibraryNode.id == current.parent_id))
    return False


def descendant_container_keys(session: Session, node_key: str) -> set[str]:
    container = get_container_or_none(session, node_key)
    if container is None:
        return set()

    nodes = session.scalars(
        select(LibraryNode).where(LibraryNode.kind == "container")
    ).all()
    children_by_parent: dict[int | None, list[LibraryNode]] = {}
    for node in nodes:
        children_by_parent.setdefault(node.parent_id, []).append(node)

    descendants: set[str] = set()

    def walk(parent_id: int) -> None:
        for child in children_by_parent.get(parent_id, []):
            descendants.add(child.node_key)
            walk(child.id)

    walk(container.id)
    return descendants


def list_move_target_choices(
    session: Session,
    *,
    exclude_node_key: str | None = None,
) -> list[dict[str, Any]]:
    excluded = {compact_text(exclude_node_key)} if compact_text(exclude_node_key) else set()
    if exclude_node_key:
        excluded.update(descendant_container_keys(session, exclude_node_key))
    return [
        option
        for option in list_container_choices(session)
        if option["node_key"] not in excluded
    ]


def move_container(
    session: Session,
    node_key: str,
    parent_node_key: str | None,
) -> LibraryNode:
    ensure_library_tree(session)
    container = get_container_or_none(session, node_key)
    if container is None:
        raise ValueError("Folder not found.")

    target_parent = resolve_target_container(session, parent_node_key)
    target_parent_id = target_parent.id if target_parent is not None else None

    if target_parent is not None:
        if target_parent.id == container.id:
            raise ValueError("A folder cannot be moved inside itself.")
        if container_is_inside(session, target_parent, container.id):
            raise ValueError("A folder cannot be moved inside one of its own child folders.")

    duplicate_query = select(LibraryNode).where(
        LibraryNode.kind == "container",
        LibraryNode.name == container.name,
        LibraryNode.id != container.id,
    )
    if target_parent_id is None:
        duplicate_query = duplicate_query.where(LibraryNode.parent_id.is_(None))
    else:
        duplicate_query = duplicate_query.where(LibraryNode.parent_id == target_parent_id)

    duplicate = session.scalar(duplicate_query.limit(1))
    if duplicate is not None:
        raise ValueError("A folder with this name already exists there.")

    if container.parent_id != target_parent_id:
        container.parent_id = target_parent_id
        container.node_order = next_node_order(session, target_parent_id, exclude_node_id=container.id)

    if container.archived:
        container.archived = False

    session.commit()
    ensure_library_tree(session)
    session.expire_all()
    moved = get_container_or_none(session, node_key)
    if moved is None:
        raise ValueError("Folder not found.")
    return moved


def move_form(
    session: Session,
    slug: str,
    parent_node_key: str | None,
) -> FormDefinition:
    ensure_library_tree(session)
    definition = session.scalar(
        select(FormDefinition)
        .where(FormDefinition.slug == slug)
        .options(selectinload(FormDefinition.versions), selectinload(FormDefinition.library_node))
    )
    if definition is None:
        raise ValueError("Form not found.")

    target_parent = resolve_target_container(session, parent_node_key)
    target_parent_id = target_parent.id if target_parent is not None else None
    form_node = definition.library_node or session.scalar(
        select(LibraryNode).where(LibraryNode.form_definition_id == definition.id)
    )
    if form_node is None:
        raise ValueError("Form node not found.")

    desired_order = (
        int(form_node.node_order or 1)
        if form_node.parent_id == target_parent_id
        else next_node_order(session, target_parent_id, exclude_node_id=form_node.id)
    )
    upsert_form_node_location(
        session,
        definition,
        parent_node_key=target_parent.node_key if target_parent is not None else None,
        node_order=desired_order,
    )
    sync_definition_parent_node_key(session, definition, form_node=form_node)

    session.commit()
    ensure_library_tree(session)
    session.expire_all()
    moved = get_form_or_none(session, slug)
    if moved is None:
        raise ValueError("Form not found.")
    return moved


def rename_container(
    session: Session,
    node_key: str,
    name: str,
) -> LibraryNode:
    container = get_container_or_none(session, node_key)
    if container is None:
        raise ValueError("Folder not found.")

    container_name = compact_text(name)
    if not container_name:
        raise ValueError("Name the folder before you continue.")

    existing_query = select(LibraryNode).where(
        LibraryNode.kind == "container",
        LibraryNode.name == container_name,
        LibraryNode.id != container.id,
    )
    if container.parent_id is None:
        existing_query = existing_query.where(LibraryNode.parent_id.is_(None))
    else:
        existing_query = existing_query.where(LibraryNode.parent_id == container.parent_id)

    existing = session.scalar(existing_query.limit(1))
    if existing is not None:
        raise ValueError("A folder with this name already exists here.")

    container.name = container_name
    if container.archived:
        container.archived = False
    session.commit()
    return container


def delete_container(session: Session, node_key: str) -> None:
    container = get_container_or_none(session, node_key)
    if container is None:
        raise ValueError("Folder not found.")

    child_node = session.scalar(select(LibraryNode.id).where(LibraryNode.parent_id == container.id).limit(1))
    if child_node is not None:
        raise ValueError("This folder is not empty yet. Move or remove the items inside it first.")

    session.delete(container)
    session.commit()


def normalize_location_name_input(value: str | None) -> str:
    normalized = compact_text(value)
    return "Top level" if normalized == "Unassigned" else normalized


def resolve_form_location_metadata(
    session: Session,
    *,
    form_name: str,
    location_name: str,
    library_parent_node_key: str | None,
    library_new_container_name: str | None,
    existing_definition: FormDefinition | None = None,
) -> dict[str, Any]:
    resolved_parent_key = compact_text(library_parent_node_key) or None
    pending_container_name = compact_text(library_new_container_name) or None
    explicit_location_name = normalize_location_name_input(location_name)

    if pending_container_name:
        resolved_parent_key = ensure_container_node(session, pending_container_name, resolved_parent_key).node_key
    elif (
        not resolved_parent_key
        and explicit_location_name
        and explicit_location_name != "Top level"
    ):
        resolved_parent_key = ensure_container_node(session, explicit_location_name, None).node_key

    target_parent = resolve_target_container(session, resolved_parent_key)
    existing_node = existing_definition.library_node if existing_definition is not None else None

    if target_parent is not None:
        if existing_node is not None and existing_node.parent_id == target_parent.id:
            resolved_form_order = int(existing_node.node_order or 1)
        else:
            resolved_form_order = next_node_order(
                session,
                target_parent.id,
                exclude_node_id=existing_node.id if existing_node is not None else None,
            )

        return {
            "resolved_parent_key": target_parent.node_key,
            "resolved_form_order": resolved_form_order,
        }

    if existing_node is not None and existing_node.parent_id is None:
        resolved_form_order = int(existing_node.node_order or 1)
    else:
        resolved_form_order = next_node_order(
            session,
            None,
            exclude_node_id=existing_node.id if existing_node is not None else None,
        )

    return {
        "resolved_parent_key": None,
        "resolved_form_order": resolved_form_order,
    }


def container_node_key(name: str) -> str:
    return f"container:{slugify(name or 'unassigned')}"


def form_node_key(slug: str) -> str:
    return f"form:{slug}"


def ensure_library_tree(session: Session) -> None:
    Base.metadata.create_all(bind=engine)
    definitions = session.scalars(
        select(FormDefinition)
        .options(selectinload(FormDefinition.versions), selectinload(FormDefinition.library_node))
        .order_by(FormDefinition.name, FormDefinition.id)
    ).all()

    nodes = session.scalars(select(LibraryNode)).all()
    nodes_by_key = {node.node_key: node for node in nodes}
    changed = False

    for definition in definitions:
        node_key = form_node_key(definition.slug)
        form_node = nodes_by_key.get(node_key)
        fallback_form_order = definition_schema_order_hint(definition)
        parent_id = None
        parent_node_key: str | None = None
        explicit_parent_key = compact_text(definition.library_parent_node_key)
        desired_form_order = (
            int(form_node.node_order or fallback_form_order)
            if form_node is not None
            else int(fallback_form_order)
        )

        if explicit_parent_key:
            explicit_parent = nodes_by_key.get(explicit_parent_key)
            if explicit_parent is not None and explicit_parent.kind == "container":
                if explicit_parent.archived:
                    explicit_parent.archived = False
                    changed = True
                parent_id = explicit_parent.id
                parent_node_key = explicit_parent.node_key
        elif form_node is not None:
            parent_id = form_node.parent_id
            if form_node.parent_id is not None:
                parent = session.scalar(select(LibraryNode).where(LibraryNode.id == form_node.parent_id))
                if parent is not None and parent.kind == "container":
                    parent_node_key = parent.node_key

        if form_node is None:
            form_node = upsert_form_node_location(
                session,
                definition,
                parent_node_key=parent_node_key,
                node_order=desired_form_order,
            )
            nodes_by_key[node_key] = form_node
            changed = True
        else:
            original_state = (
                form_node.kind,
                form_node.name,
                form_node.parent_id,
                int(form_node.node_order or 1),
                bool(form_node.archived),
                form_node.form_definition_id,
            )
            upsert_form_node_location(
                session,
                definition,
                parent_node_key=parent_node_key,
                node_order=desired_form_order,
            )
            current_state = (
                form_node.kind,
                form_node.name,
                form_node.parent_id,
                int(form_node.node_order or 1),
                bool(form_node.archived),
                form_node.form_definition_id,
            )
            if current_state != original_state:
                changed = True

        if sync_definition_parent_node_key(session, definition, form_node=form_node):
            changed = True

    if changed:
        session.commit()


def list_library_tree(session: Session) -> list[dict[str, Any]]:
    ensure_library_tree(session)
    nodes = session.scalars(
        select(LibraryNode)
        .options(selectinload(LibraryNode.form_definition).selectinload(FormDefinition.versions))
        .order_by(LibraryNode.parent_id, LibraryNode.node_order, LibraryNode.name)
    ).all()

    children_by_parent: dict[int | None, list[LibraryNode]] = {}
    for node in nodes:
        children_by_parent.setdefault(node.parent_id, []).append(node)

    def serialize_node(node: LibraryNode) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": node.node_key,
            "kind": node.kind,
            "name": node.name,
            "order": node.node_order,
            "archived": node.archived,
            "children": [serialize_node(child) for child in children_by_parent.get(node.id, [])],
        }
        if node.kind == "form" and node.form_definition is not None:
            version = current_version(node.form_definition)
            payload["form"] = {
                "slug": node.form_definition.slug,
                "name": node.form_definition.name,
                "current_version_number": version.version_number if version else 0,
            }
        return payload

    return [serialize_node(node) for node in children_by_parent.get(None, [])]


def next_available_slug(session: Session, preferred: str) -> str:
    base = slugify(preferred)
    slug = base
    suffix = 2
    while session.scalar(select(FormDefinition.id).where(FormDefinition.slug == slug)) is not None:
        slug = f"{base}_{suffix}"
        suffix += 1
    return slug


def ensure_reference_seed(session: Session) -> None:
    existing = session.scalar(select(FormDefinition.id).limit(1))
    if existing is not None:
        return

    reference = load_reference_schema()
    try:
        for group in reference.get("groups", []):
            group_name = compact_text(group.get("name"))
            group_kind = compact_text(group.get("kind")) or "category"
            group_order = int(group.get("order") or 999)
            parent_container: LibraryNode | None = None
            parent_node_key: str | None = None

            if group_kind != "standalone_form":
                parent_container = ensure_container_node(session, group_name)
                if parent_container.node_order != group_order:
                    parent_container.node_order = group_order
                parent_node_key = parent_container.node_key

            for form in group.get("forms", []):
                slug = compact_text(form.get("key")) or slugify(form.get("name"))
                name = compact_text(form.get("name")) or "Untitled Form"
                form_order = int(form.get("order") or 1)
                legacy_storage_schema = build_legacy_storage_payload(
                    form,
                    slug=slug,
                    name=name,
                    form_order=form_order,
                )
                block_storage_schema = build_block_storage_document_from_legacy_storage(
                    legacy_storage_schema,
                )

                definition = create_form_definition_record(
                    slug=slug,
                    name=name,
                    parent_node_key=parent_node_key,
                )
                session.add(definition)
                session.flush()
                upsert_form_node_location(
                    session,
                    definition,
                    parent_node_key=parent_node_key,
                    node_order=form_order,
                )
                sync_definition_parent_node_key(session, definition)

                version = build_form_version_record(
                    form_id=definition.id,
                    version_number=1,
                    summary="Seeded from current reference schema.",
                    legacy_storage_schema=legacy_storage_schema,
                    block_storage_schema=block_storage_schema,
                    source="seed",
                    is_current=True,
                )
                session.add(version)

        session.commit()
        ensure_library_tree(session)
    except IntegrityError:
        session.rollback()
        if session.scalar(select(FormDefinition.id).limit(1)) is None:
            raise


def ensure_default_patient_info_fields(session: Session) -> int:
    definitions = session.scalars(
        select(FormDefinition)
        .options(
            selectinload(FormDefinition.versions),
            selectinload(FormDefinition.library_node),
        )
    ).all()
    migrated_count = 0

    for definition in definitions:
        version = current_version(definition)
        if version is None:
            continue

        block_schema, _ = load_block_storage_document(version)
        if not ensure_default_patient_info_block_schema(block_schema):
            continue

        legacy_storage_schema = load_legacy_storage_document(version)
        form_order = int(
            legacy_storage_schema.get("order")
            or (definition.library_node.node_order if definition.library_node is not None else 1)
            or 1
        )
        legacy_storage_schema, stored_block_schema = build_form_version_storage_documents(
            block_schema,
            slug=definition.slug,
            name=definition.name,
            form_order=form_order,
        )

        for existing_version in definition.versions:
            existing_version.is_current = False

        next_version = max((existing_version.version_number for existing_version in definition.versions), default=0) + 1
        session.add(
            build_form_version_record(
                form_id=definition.id,
                version_number=next_version,
                summary="Added default patient information fields.",
                legacy_storage_schema=legacy_storage_schema,
                block_storage_schema=stored_block_schema,
                source="system",
                is_current=True,
            )
        )
        definition.updated_at = utc_now()
        migrated_count += 1

    if migrated_count:
        session.commit()
    return migrated_count


def ensure_form_version_storage_documents(session: Session) -> None:
    versions = session.scalars(select(FormVersion).options(selectinload(FormVersion.form))).all()
    changed = False

    for version in versions:
        legacy_storage_schema = load_legacy_storage_document(version)
        schema_changed = False

        if "common_field_set_id" in legacy_storage_schema:
            legacy_storage_schema.pop("common_field_set_id", None)
            schema_changed = True

        definition_slug = version.form.slug if version.form is not None else compact_text(legacy_storage_schema.get("key"))
        stable_schema_id = stable_form_schema_id(definition_slug)
        if compact_text(legacy_storage_schema.get("id")) != stable_schema_id:
            legacy_storage_schema["id"] = stable_schema_id
            schema_changed = True

        block_schema, block_changed = load_block_storage_document(
            version,
            legacy_storage_schema=legacy_storage_schema,
        )

        meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
        if "common_field_set_id" in meta:
            meta.pop("common_field_set_id", None)
            block_changed = True
        if compact_text(meta.get("form_id")) != stable_schema_id:
            meta["form_id"] = stable_schema_id
            block_changed = True
        if compact_text(meta.get("legacy_form_id")):
            meta.pop("legacy_form_id", None)
            block_changed = True
        stable_form_key = compact_text(legacy_storage_schema.get("key"))
        if compact_text(meta.get("form_key")) != stable_form_key:
            meta["form_key"] = stable_form_key
            block_changed = True
        if compact_text(meta.get("legacy_form_key")):
            meta.pop("legacy_form_key", None)
            block_changed = True
        stable_form_order = int(legacy_storage_schema.get("order") or 1)
        if int(meta.get("form_order") or 1) != stable_form_order:
            meta["form_order"] = stable_form_order
            block_changed = True
        if compact_text(meta.get("legacy_order")):
            meta.pop("legacy_order", None)
            block_changed = True

        if normalize_active_block_storage_schema(block_schema):
            block_changed = True
        block_schema["meta"] = meta

        if schema_changed:
            version.schema_json = json.dumps(legacy_storage_schema, ensure_ascii=False)
            changed = True
        if block_changed:
            version.block_schema_json = json.dumps(block_schema, ensure_ascii=False)
            changed = True

    if changed:
        session.commit()


def create_form(session: Session, payload: FormSavePayload) -> dict[str, Any]:
    raw_block_schema = payload.form_schema if isinstance(payload.form_schema, dict) else {}
    slug = next_available_slug(
        session,
        payload.slug or block_payload_form_key(raw_block_schema) or payload.name or "untitled_form",
    )
    name = compact_text(payload.name) or "Untitled Form"
    location_meta = resolve_form_location_metadata(
        session,
        form_name=name,
        location_name=compact_text(payload.location_name),
        library_parent_node_key=payload.library_parent_node_key,
        library_new_container_name=payload.library_new_container_name,
    )
    legacy_storage_schema, stored_block_schema = build_form_version_storage_documents(
        raw_block_schema,
        slug=slug,
        name=name,
        form_order=location_meta["resolved_form_order"],
    )

    definition = create_form_definition_record(
        slug=slug,
        name=name,
        parent_node_key=location_meta["resolved_parent_key"],
    )
    session.add(definition)
    session.flush()
    upsert_form_node_location(
        session,
        definition,
        parent_node_key=location_meta["resolved_parent_key"],
        node_order=location_meta["resolved_form_order"],
    )
    sync_definition_parent_node_key(session, definition)

    version = build_form_version_record(
        form_id=definition.id,
        version_number=1,
        summary=compact_text(payload.summary) or "Initial builder version.",
        legacy_storage_schema=legacy_storage_schema,
        block_storage_schema=stored_block_schema,
        source="builder",
        is_current=True,
    )
    session.add(version)
    session.commit()
    ensure_library_tree(session)
    session.expire_all()
    return serialize_form(get_form_or_none(session, slug))


def update_form(session: Session, slug: str, payload: FormSavePayload) -> dict[str, Any]:
    definition = get_form_or_none(session, slug)
    if definition is None:
        raise KeyError(slug)

    raw_block_schema = payload.form_schema if isinstance(payload.form_schema, dict) else {}
    name = compact_text(payload.name) or definition.name
    location_meta = resolve_form_location_metadata(
        session,
        form_name=name,
        location_name=compact_text(payload.location_name),
        library_parent_node_key=payload.library_parent_node_key,
        library_new_container_name=payload.library_new_container_name,
        existing_definition=definition,
    )
    legacy_storage_schema, stored_block_schema = build_form_version_storage_documents(
        raw_block_schema,
        slug=definition.slug,
        name=name,
        form_order=location_meta["resolved_form_order"],
    )

    next_version = (current_version(definition).version_number if current_version(definition) else 0) + 1
    for version in definition.versions:
        version.is_current = False

    definition.name = name
    upsert_form_node_location(
        session,
        definition,
        parent_node_key=location_meta["resolved_parent_key"],
        node_order=location_meta["resolved_form_order"],
    )
    sync_definition_parent_node_key(session, definition)

    version = build_form_version_record(
        form_id=definition.id,
        version_number=next_version,
        summary=compact_text(payload.summary) or f"Builder update v{next_version}.",
        legacy_storage_schema=legacy_storage_schema,
        block_storage_schema=stored_block_schema,
        source="builder",
        is_current=True,
    )
    session.add(version)
    session.commit()
    ensure_library_tree(session)
    session.expire_all()
    return serialize_form(get_form_or_none(session, slug))
