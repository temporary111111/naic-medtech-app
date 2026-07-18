# Client Print Adjustments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved configurable signatory defaults, fixed Pathologist stamp, friendly print dates and units, preserved report banner, and clinic-wide DOH license number across existing and new forms.

**Architecture:** Extend the existing versioned `block_schema.meta.signatories` contract with a slot-level `designation`, seed one replaceable stamp asset into persistent runtime storage, and migrate only current forms into one new version. Keep all visual behavior in the shared print document so builder preview and actual record printing remain identical, while clinic-wide DOH data stays in `clinic_profiles`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, SQLite, Jinja2, vanilla JavaScript, CSS, `unittest`, existing print QA scripts, PyInstaller, Inno Setup.

## Global Constraints

- Do not hardcode MedTech or Pathologist behavior in the print renderer.
- `Role label`, `Designation`, signatory type, people, stamps, visibility, and order remain editable per form version.
- Existing current forms receive two required MedTech choices and one automatically included fixed Pathologist stamp.
- Old form versions and records remain frozen; migration creates one new current version and is idempotent.
- Date formatting is print-only: `MM/DD/YYYY` and `MM/DD/YYYY hh:mm AM/PM`.
- Time-only fields retain current behavior.
- Result and unit stay adjacent in both `Rows` and `Compact grid` print layouts.
- The colored report banner keeps its current visual height, left alignment, configurable color, and A4 fit.
- DOH License No. is optional and clinic-wide.
- Preserve existing LAN, permissions, restore, and internal/external backup behavior.
- Add no runtime dependency; use the standard-library `unittest` runner.

---

## File Map

- `app/naic_builder/config.py`: bundled and runtime default stamp paths.
- `app/naic_builder/models.py`: clinic DOH column.
- `app/naic_builder/schemas.py`: clinic DOH request field.
- `app/naic_builder/database.py`: additive clinic column migration.
- `app/naic_builder/services.py`: signatory defaults, normalization, snapshots, migration, stamp seeding, clinic serialization, and print date formatting.
- `app/naic_builder/main.py`: startup migration and clinic form handling.
- `app/naic_builder/static/app.js`: builder defaults and editable Designation field.
- `app/naic_builder/templates/index.html`: builder JavaScript cache revision.
- `app/naic_builder/templates/records/edit.html`: signatory designation context in record entry.
- `app/naic_builder/templates/records/view.html`: signatory designation display.
- `app/naic_builder/templates/records/_print_document.html`: shared signatory, unit, banner, and DOH rendering.
- `app/naic_builder/static/print.css`: stable banner and inline result/unit/signatory layout.
- `app/naic_builder/templates/forms/print_preview.html`: preview print CSS cache revision.
- `app/naic_builder/templates/records/print.html`: record print CSS cache revision.
- `app/naic_builder/templates/settings/clinic.html`: DOH input and preview.
- `tools/scripts/build_naic_medtech_tree.py`: generated-schema signatory defaults.
- `artifacts/schema/naic_medtech_app_schema.json`: bundled reference defaults.
- `artifacts/seed/signatories/bernardita-mojica-figueroa-stamp.png`: approved initial stamp.
- `tools/desktop/package.spec`: bundle the seed asset.
- `tools/scripts/print_record_qa.py`: assert adjusted print content.
- `tests/test_client_print_adjustments.py`: focused service, migration, and rendering coverage.
- `docs/handoff/PRINT_SYSTEM_HANDOFF.md`: current behavior and QA commands.
- `tools/desktop/VERSION`: installer version for the adjustment build.

---

### Task 1: Bundle And Seed The Approved Stamp

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_client_print_adjustments.py`
- Create: `artifacts/seed/signatories/bernardita-mojica-figueroa-stamp.png`
- Modify: `app/naic_builder/config.py`
- Modify: `app/naic_builder/services.py`
- Modify: `app/naic_builder/main.py`
- Modify: `tools/desktop/package.spec`

**Interfaces:**
- Produces: `ensure_default_pathologist_stamp(*, source_path: Path | None = None, destination_path: Path | None = None) -> Path`.
- Produces: `DEFAULT_PATHOLOGIST_STAMP_URL: str` for form defaults.
- Consumes: existing `RESOURCE_ROOT` and `SIGNATORY_UPLOADS_DIR` paths.

- [ ] **Step 1: Create the test package and failing stamp-copy test**

```python
# tests/__init__.py
```

```python
# tests/test_client_print_adjustments.py
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="ndhi-client-adjustments-")
os.environ["NDHI_LABRECORDS_DATA_DIR"] = TEST_RUNTIME.name

from naic_builder.services import ensure_default_pathologist_stamp


class ClientPrintAdjustmentTests(unittest.TestCase):
    def test_default_stamp_copy_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "seed.png"
            destination = root / "runtime" / "default.png"
            source.write_bytes(b"approved-stamp")

            first = ensure_default_pathologist_stamp(
                source_path=source,
                destination_path=destination,
            )
            destination.write_bytes(b"existing-runtime-copy")
            second = ensure_default_pathologist_stamp(
                source_path=source,
                destination_path=destination,
            )

            self.assertEqual(first, destination)
            self.assertEqual(second, destination)
            self.assertEqual(destination.read_bytes(), b"existing-runtime-copy")
```

- [ ] **Step 2: Run the test and verify the missing interface**

Run:

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe -m unittest tests.test_client_print_adjustments.ClientPrintAdjustmentTests.test_default_stamp_copy_is_idempotent -v
```

Expected: import failure because `ensure_default_pathologist_stamp` does not exist.

- [ ] **Step 3: Copy the approved binary into a bundled seed location**

Run:

```powershell
New-Item -ItemType Directory -Force 'artifacts\seed\signatories' | Out-Null
Copy-Item -LiteralPath 'data\runtime\uploads\signatories\stamp_d18103e0dee04ec8a7fdba2494f81119.png' -Destination 'artifacts\seed\signatories\bernardita-mojica-figueroa-stamp.png'
$sourceHash = (Get-FileHash -Algorithm SHA256 'data\runtime\uploads\signatories\stamp_d18103e0dee04ec8a7fdba2494f81119.png').Hash
$seedHash = (Get-FileHash -Algorithm SHA256 'artifacts\seed\signatories\bernardita-mojica-figueroa-stamp.png').Hash
if ($sourceHash -ne $seedHash) { throw 'Seed stamp hash does not match the approved runtime image.' }
```

Expected: the destination PNG exists and has the same SHA-256 hash as the approved runtime image.

- [ ] **Step 4: Add deterministic resource, runtime, and URL constants**

Add to `app/naic_builder/config.py` after the signatory upload directory:

```python
DEFAULT_PATHOLOGIST_STAMP_FILENAME = "default-pathologist-stamp.png"
DEFAULT_PATHOLOGIST_STAMP_RESOURCE_PATH = (
    RESOURCE_ROOT / "artifacts" / "seed" / "signatories" / "bernardita-mojica-figueroa-stamp.png"
)
DEFAULT_PATHOLOGIST_STAMP_RUNTIME_PATH = SIGNATORY_UPLOADS_DIR / DEFAULT_PATHOLOGIST_STAMP_FILENAME
DEFAULT_PATHOLOGIST_STAMP_URL = f"/signatory-stamps/{DEFAULT_PATHOLOGIST_STAMP_FILENAME}"
```

Import those constants in `services.py` and add:

```python
def ensure_default_pathologist_stamp(
    *,
    source_path: Path | None = None,
    destination_path: Path | None = None,
) -> Path:
    source = source_path or DEFAULT_PATHOLOGIST_STAMP_RESOURCE_PATH
    destination = destination_path or DEFAULT_PATHOLOGIST_STAMP_RUNTIME_PATH
    if destination.is_file():
        return destination
    if not source.is_file():
        raise FileNotFoundError(f"Default Pathologist stamp was not bundled: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    shutil.copyfile(source, partial)
    os.replace(partial, destination)
    return destination
```

Add `import shutil` and use the existing `os` import in `services.py`.

- [ ] **Step 5: Seed before forms are loaded and package the resource**

Import and call `ensure_default_pathologist_stamp()` at the start of `main.py` lifespan, before `ensure_reference_seed(session)`.

Add to `tools/desktop/package.spec`:

```python
SEED_SIGNATORY_DIR = PROJECT_ROOT / "artifacts" / "seed" / "signatories"
```

and add this `datas` entry:

```python
(str(SEED_SIGNATORY_DIR), "artifacts/seed/signatories"),
```

- [ ] **Step 6: Run the focused test and compile check**

Run:

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe -m unittest tests.test_client_print_adjustments.ClientPrintAdjustmentTests.test_default_stamp_copy_is_idempotent -v
.\env\Scripts\python.exe -m compileall app\naic_builder tests
```

Expected: test passes and compilation exits `0`.

- [ ] **Step 7: Commit the seed foundation**

```powershell
git add app/naic_builder/config.py app/naic_builder/services.py app/naic_builder/main.py tools/desktop/package.spec artifacts/seed/signatories/bernardita-mojica-figueroa-stamp.png tests/__init__.py tests/test_client_print_adjustments.py
git commit -m "feat: seed configurable pathologist stamp"
```

---

### Task 2: Extend Generic Signatory Configuration

**Files:**
- Modify: `tests/test_client_print_adjustments.py`
- Modify: `app/naic_builder/services.py`
- Modify: `app/naic_builder/static/app.js`
- Modify: `app/naic_builder/templates/index.html`
- Modify: `app/naic_builder/templates/records/edit.html`
- Modify: `app/naic_builder/templates/records/view.html`
- Modify: `tools/scripts/build_naic_medtech_tree.py`
- Modify: `artifacts/schema/naic_medtech_app_schema.json`

**Interfaces:**
- Produces: normalized slot and snapshot property `designation: str`.
- Produces: printable `signature_line: bool` so the existing builder toggle remains effective.
- Produces: approved defaults from `default_signatory_slots() -> list[dict[str, Any]]`.
- Consumes: `DEFAULT_PATHOLOGIST_STAMP_URL` from Task 1.

- [ ] **Step 1: Add failing default and round-trip tests**

Add these imports at module scope, then add the three methods inside the existing `ClientPrintAdjustmentTests` class:

```python
from naic_builder.models import FormVersion, Record
from naic_builder.services import (
    build_signatory_snapshot,
    default_signatory_slots,
    list_record_completion_issues,
    normalize_signatory_slot,
    signatory_snapshots_for_print,
)

    def test_default_signatories_match_approved_workflow(self) -> None:
        slots = default_signatory_slots()
        self.assertEqual(
            [(slot["label"], slot["designation"], slot["input_type"], slot["required"]) for slot in slots],
            [
                ("Analyzed by:", "Medical Technologist (RMT)", "person_dropdown", True),
                ("Verified by:", "Medical Technologist (RMT)", "person_dropdown", True),
                ("Noted by:", "Pathologist", "stamp_image", False),
            ],
        )
        self.assertTrue(slots[2]["stamp_image_url"].endswith("default-pathologist-stamp.png"))

    def test_designation_round_trips_to_print_snapshot(self) -> None:
        slot = normalize_signatory_slot(
            {
                "id": "reviewer",
                "label": "Reviewed by:",
                "designation": "Laboratory Reviewer",
                "input_type": "manual",
                "manual_name": "Alex Cruz",
                "manual_license": "1234",
                "signature_line": False,
            },
            1,
        )
        snapshot = build_signatory_snapshot(slot)
        printable = signatory_snapshots_for_print([snapshot])
        self.assertEqual(snapshot["designation"], "Laboratory Reviewer")
        self.assertEqual(printable[0]["designation"], "Laboratory Reviewer")
        self.assertFalse(printable[0]["signature_line"])

    def test_two_medtech_choices_are_required_but_stamp_needs_no_record_input(self) -> None:
        slots = default_signatory_slots()
        version = FormVersion(
            form_id=1,
            version_number=1,
            schema_json="{}",
            block_schema_json=json.dumps({"meta": {"signatories": slots}, "blocks": []}),
            source="builder",
            is_current=True,
        )
        record = Record(record_key="TEST-1", form_id=1, form_version_id=1, form_version=version)
        self.assertEqual(
            list_record_completion_issues(record, values={}, indexed_meta={}),
            [
                "Choose required signatory: Analyzed by.",
                "Choose required signatory: Verified by.",
            ],
        )

        first_option = slots[0]["options"][0]["id"]
        completed_meta = {
            "signatories": {
                "medical_technologist_1": {"option_id": first_option},
                "medical_technologist_2": {"option_id": first_option},
            }
        }
        self.assertEqual(
            list_record_completion_issues(record, values={}, indexed_meta=completed_meta),
            [],
        )
```

- [ ] **Step 2: Verify both tests fail**

Run:

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe -m unittest tests.test_client_print_adjustments -v
```

Expected: failures for missing `designation` and old default labels/types.

- [ ] **Step 3: Update backend defaults and normalization**

In `services.py`, make the three defaults exactly:

Remove the old `pathologist_options` and `pathologist_default` locals; the approved Pathologist default uses the stamp asset rather than the person list.

```python
{
    "id": "medical_technologist_1",
    "label": "Analyzed by:",
    "designation": "Medical Technologist (RMT)",
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
    "label": "Verified by:",
    "designation": "Medical Technologist (RMT)",
    "input_type": "person_dropdown",
    "required": True,
    "show_on_print": True,
    "show_license": True,
    "signature_line": True,
    "default_option_id": "",
    "options": medtech_2_options,
},
{
    "id": "pathologist",
    "label": "Noted by:",
    "designation": "Pathologist",
    "input_type": "stamp_image",
    "required": False,
    "show_on_print": True,
    "show_license": False,
    "signature_line": True,
    "default_option_id": "",
    "stamp_image_url": DEFAULT_PATHOLOGIST_STAMP_URL,
    "stamp_image_filename": DEFAULT_PATHOLOGIST_STAMP_FILENAME,
    "stamp_image_mime_type": "image/png",
    "options": [],
},
```

Add `designation` to `normalize_signatory_slot()`, `build_signatory_snapshot()`, and every dictionary returned by `signatory_snapshots_for_print()`. Use this compatibility fallback when printing:

```python
designation = compact_text(snapshot.get("designation")) or compact_text(snapshot.get("title"))
```

`build_signatory_snapshot()` must keep the existing person-level `title` key and add the independent slot-level value:

```python
"designation": compact_text(slot.get("designation")) or compact_text(slot.get("title")),
```

Change the return annotation of `signatory_snapshots_for_print()` to `list[dict[str, Any]]`. Both branches must return `designation` and:

```python
"signature_line": normalize_boolean_setting(snapshot.get("signature_line"), default=True),
```

The stamp branch must continue returning blank `name`, `title`, and `license` so text already embedded in the approved image is not duplicated. Change `build_print_signature_items()` and its local `signatures` annotation to `list[dict[str, Any]]`, and add `"signature_line": True` to each legacy fallback dictionary it creates.

Because the approved labels end in colons, replace the required-signatory message construction in `list_record_completion_issues()` with:

```python
label = compact_text(slot.get("label")).rstrip(":") or "Signatory"
issues.append(f"Choose required signatory: {label}.")
```

- [ ] **Step 4: Update builder defaults, normalization, and editor controls**

Replace `defaultSignatorySlots()` in `app.js` with:

```javascript
function defaultSignatorySlots() {
  const medtech1Options = makeDefaultSignatoryOptions("medical_technologist_1", DEFAULT_MEDTECH_SIGNATORY_OPTIONS);
  const medtech2Options = makeDefaultSignatoryOptions("medical_technologist_2", DEFAULT_MEDTECH_SIGNATORY_OPTIONS);
  return [
    {
      id: "medical_technologist_1",
      label: "Analyzed by:",
      designation: "Medical Technologist (RMT)",
      input_type: "person_dropdown",
      required: true,
      show_on_print: true,
      show_license: true,
      signature_line: true,
      default_option_id: "",
      options: medtech1Options,
    },
    {
      id: "medical_technologist_2",
      label: "Verified by:",
      designation: "Medical Technologist (RMT)",
      input_type: "person_dropdown",
      required: true,
      show_on_print: true,
      show_license: true,
      signature_line: true,
      default_option_id: "",
      options: medtech2Options,
    },
    {
      id: "pathologist",
      label: "Noted by:",
      designation: "Pathologist",
      input_type: "stamp_image",
      required: false,
      show_on_print: true,
      show_license: false,
      signature_line: true,
      default_option_id: "",
      stamp_image_url: "/signatory-stamps/default-pathologist-stamp.png",
      stamp_image_filename: "default-pathologist-stamp.png",
      stamp_image_mime_type: "image/png",
      options: [],
    },
  ];
}
```

Add this normalized property immediately after `label` in `normalizeSignatorySlot()`:

```javascript
designation: compactText(slot.designation || slot.title),
```

Add `designation: ""` to `makeBlankSignatorySlot()`. Change the first branch in `updateDraftSignatorySlot()` to:

```javascript
if (key === "label" || key === "designation") {
  slot[key] = key === "label" ? (compactText(value) || "Signatory") : compactText(value);
  return;
}
```

Add this field beside Role label in `renderSignatoryCard()`:

```html
<label>
  <span>Designation</span>
  <input data-action="signatory-field" data-id="${escapeHtml(slot.id)}" data-key="designation" value="${escapeHtml(slot.designation)}" placeholder="Example: Medical Technologist (RMT)">
</label>
```

Inside the existing stamp editor, immediately after `.signatory-stamp-preview-frame`, add:

```javascript
${slot.show_on_print && !slot.stamp_image_url
  ? `<p class="field-error">Stamp image required for print.</p>`
  : ""}
```

Do not add a per-record Required control for stamp slots.

In `templates/index.html`, change the `app.js` query string to `?v=20260718-client-signatories` so installed browsers do not retain the old builder behavior.

- [ ] **Step 5: Show designation in record entry/view context**

In `records/edit.html`, add this immediately after `.entry-field-head`:

```jinja2
{% if slot.designation %}
<small class="entry-inline-hint">{{ slot.designation }}</small>
{% endif %}
```

In `records/view.html`, add this before the closing `.entry-signatory-value` tag:

```jinja2
{% if item.designation %}
<span>{{ item.designation }}</span>
{% endif %}
```

Do not add name/license text for stamp slots; their snapshots keep those fields blank because the approved image already contains them.

- [ ] **Step 6: Keep generated defaults aligned**

In `DEFAULT_SIGNATORIES` in `tools/scripts/build_naic_medtech_tree.py`, preserve the existing MedTech `options` arrays and apply these exact key changes:

```python
# medical_technologist_1
"label": "Analyzed by:",
"designation": "Medical Technologist (RMT)",
"input_type": "person_dropdown",
"required": True,

# medical_technologist_2
"label": "Verified by:",
"designation": "Medical Technologist (RMT)",
"input_type": "person_dropdown",
"required": True,

# Replace the pathologist dictionary completely.
{
    "id": "pathologist",
    "label": "Noted by:",
    "designation": "Pathologist",
    "input_type": "stamp_image",
    "required": False,
    "show_on_print": True,
    "show_license": False,
    "signature_line": True,
    "default_option_id": "",
    "stamp_image_url": "/signatory-stamps/default-pathologist-stamp.png",
    "stamp_image_filename": "default-pathologist-stamp.png",
    "stamp_image_mime_type": "image/png",
    "options": [],
}
```

Apply those values with JSON booleans (`true`/`false`) only inside `default_signatories` in `artifacts/schema/naic_medtech_app_schema.json`. Do not regenerate unrelated derived HTML or timestamps.

- [ ] **Step 7: Run tests and commit**

Run:

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe -m unittest tests.test_client_print_adjustments -v
.\env\Scripts\python.exe -m compileall app\naic_builder tests tools\scripts
```

Expected: all focused tests pass and compilation exits `0`.

```powershell
git add app/naic_builder/services.py app/naic_builder/static/app.js app/naic_builder/templates/index.html app/naic_builder/templates/records/edit.html app/naic_builder/templates/records/view.html tools/scripts/build_naic_medtech_tree.py artifacts/schema/naic_medtech_app_schema.json tests/test_client_print_adjustments.py
git commit -m "feat: add configurable signatory designations"
```

---

### Task 3: Migrate Existing Current Forms Once

**Files:**
- Modify: `tests/test_client_print_adjustments.py`
- Modify: `app/naic_builder/services.py`
- Modify: `app/naic_builder/main.py`
- Modify: `app/naic_builder/static/app.js`

**Interfaces:**
- Produces: `ensure_client_signatory_defaults(session: Session) -> int`.
- Produces: metadata marker `client_signatory_defaults_2026_07`.
- Consumes: `default_signatory_slots()` and existing form-version storage builders.

- [ ] **Step 1: Add a failing idempotent migration test**

Add these imports at module scope and add the method inside the existing `ClientPrintAdjustmentTests` class:

```python
import json
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from naic_builder.database import Base
from naic_builder.models import FormDefinition
from naic_builder.services import ensure_client_signatory_defaults

    def test_existing_form_defaults_create_one_new_version(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        with Session() as session:
            definition = FormDefinition(slug="blood_bank", name="Blood Bank")
            session.add(definition)
            session.flush()
            schema = {
                "schema_version": 1,
                "source_kind": "builder_blocks_v1",
                "meta": {
                    "form_key": "blood_bank",
                    "form_order": 1,
                    "signatories": [
                        {
                            "id": "medical_technologist_1",
                            "label": "Medical Technologist",
                            "input_type": "person_dropdown",
                            "options": [],
                        },
                        {
                            "id": "pathologist",
                            "label": "Custom pathologist",
                            "input_type": "stamp_image",
                            "stamp_image_url": "/signatory-stamps/custom.png",
                            "stamp_image_filename": "custom.png",
                            "stamp_image_mime_type": "image/png",
                        },
                        {
                            "id": "custom_release",
                            "label": "Released by",
                            "input_type": "manual",
                            "manual_name": "Staff",
                        },
                    ],
                },
                "blocks": [],
            }
            session.add(FormVersion(
                form_id=definition.id,
                version_number=1,
                summary="Old defaults",
                schema_json=json.dumps({
                    "id": "form.blood_bank",
                    "key": "blood_bank",
                    "name": "Blood Bank",
                    "order": 1,
                    "fields": [],
                    "sections": [],
                }),
                block_schema_json=json.dumps(schema),
                source="builder",
                is_current=True,
            ))
            session.commit()

            self.assertEqual(ensure_client_signatory_defaults(session), 1)
            self.assertEqual(ensure_client_signatory_defaults(session), 0)
            versions = session.scalars(select(FormVersion).order_by(FormVersion.version_number)).all()
            current = json.loads(versions[-1].block_schema_json)
            slots = current["meta"]["signatories"]
            self.assertEqual(len(versions), 2)
            self.assertFalse(versions[0].is_current)
            self.assertTrue(versions[1].is_current)
            self.assertEqual(
                [slot["id"] for slot in slots[:3]],
                ["medical_technologist_1", "medical_technologist_2", "pathologist"],
            )
            self.assertTrue(current["meta"]["client_signatory_defaults_2026_07"])
            self.assertEqual(slots[2]["stamp_image_url"], "/signatory-stamps/custom.png")
            self.assertIn("custom_release", [slot["id"] for slot in slots])
```

- [ ] **Step 2: Run and confirm the migration interface is missing**

Run:

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe -m unittest tests.test_client_print_adjustments.ClientPrintAdjustmentTests.test_existing_form_defaults_create_one_new_version -v
```

Expected: import failure for `ensure_client_signatory_defaults`.

- [ ] **Step 3: Implement recognized-slot merge and version creation**

In `services.py`, define:

```python
CLIENT_SIGNATORY_DEFAULTS_META_KEY = "client_signatory_defaults_2026_07"

def merge_client_signatory_defaults(raw_slots: Any) -> list[dict[str, Any]]:
    defaults = default_signatory_slots()
    existing = normalize_signatory_slots(raw_slots, use_defaults=False)
    by_id = {compact_text(slot.get("id")): slot for slot in existing}
    merged: list[dict[str, Any]] = []
    for default in defaults:
        current = by_id.pop(default["id"], None)
        if current is None:
            merged.append(default)
            continue
        preserved_stamp = {
            key: current.get(key)
            for key in ("stamp_image_url", "stamp_image_filename", "stamp_image_mime_type")
            if compact_text(current.get(key))
        }
        next_slot = {**current, **default}
        if default["id"] == "pathologist" and preserved_stamp:
            next_slot.update(preserved_stamp)
        merged.append(normalize_signatory_slot(next_slot, len(merged) + 1))
    merged.extend(by_id.values())
    return merged
```

Use this complete implementation directly after `ensure_default_patient_info_fields()`:

```python
def ensure_client_signatory_defaults(session: Session) -> int:
    definitions = session.scalars(
        select(FormDefinition)
        .options(
            selectinload(FormDefinition.versions),
            selectinload(FormDefinition.library_node),
        )
    ).all()
    migrated_count = 0

    try:
        for definition in definitions:
            version = current_version(definition)
            if version is None:
                continue

            block_schema, _ = load_block_storage_document(version)
            meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
            if normalize_boolean_setting(meta.get(CLIENT_SIGNATORY_DEFAULTS_META_KEY), default=False):
                continue

            meta["signatories"] = merge_client_signatory_defaults(meta.get("signatories"))
            meta[CLIENT_SIGNATORY_DEFAULTS_META_KEY] = True
            block_schema["meta"] = meta

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
            next_version = max(
                (existing_version.version_number for existing_version in definition.versions),
                default=0,
            ) + 1
            session.add(
                build_form_version_record(
                    form_id=definition.id,
                    version_number=next_version,
                    summary="Applied approved client signatory defaults.",
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
    except Exception:
        session.rollback()
        raise
    return migrated_count
```

- [ ] **Step 4: Mark truly new defaults and run migration at startup**

In `normalize_active_block_storage_schema()`, capture `had_signatories = "signatories" in meta` before normalization. After assigning generated defaults, set `meta[CLIENT_SIGNATORY_DEFAULTS_META_KEY] = True` only when `had_signatories` is false. Add `client_signatory_defaults_2026_07: true` beside `signatories: defaultSignatorySlots()` in the blank new-form metadata in `app.js`.

Import `ensure_client_signatory_defaults` in `main.py` and make the startup sequence exactly:

```python
ensure_reference_seed(session)
ensure_client_signatory_defaults(session)
ensure_form_version_storage_documents(session)
ensure_default_patient_info_fields(session)
ensure_library_tree(session)
```

This order lets fresh seed schemas carry the marker from normalization, while every pre-existing unmarked current form is versioned before generic storage normalization can touch it.

- [ ] **Step 5: Run migration tests twice and commit**

Run:

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe -m unittest tests.test_client_print_adjustments -v
.\env\Scripts\python.exe -m compileall app\naic_builder tests
```

Expected: the first migration reports one form, the second reports zero, and the custom slot remains.

```powershell
git add app/naic_builder/services.py app/naic_builder/main.py app/naic_builder/static/app.js tests/test_client_print_adjustments.py
git commit -m "feat: migrate default form signatories"
```

---

### Task 4: Add Clinic-Wide DOH License Number

**Files:**
- Modify: `tests/test_client_print_adjustments.py`
- Modify: `app/naic_builder/models.py`
- Modify: `app/naic_builder/schemas.py`
- Modify: `app/naic_builder/database.py`
- Modify: `app/naic_builder/services.py`
- Modify: `app/naic_builder/main.py`
- Modify: `app/naic_builder/templates/settings/clinic.html`
- Modify: `app/naic_builder/templates/records/_print_document.html`

**Interfaces:**
- Produces: `ClinicProfilePayload.doh_license_number: str | None`.
- Produces: serialized and print clinic key `doh_license_number: str`.

- [ ] **Step 1: Add failing persistence and print-profile tests**

```python
from naic_builder.schemas import ClinicProfilePayload
from naic_builder.services import build_print_clinic_profile, save_clinic_profile

    def test_doh_license_persists_prints_and_clears(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        with Session() as session:
            saved = save_clinic_profile(session, ClinicProfilePayload(
                clinic_name="Naic Doctors Hospital Inc.",
                doh_license_number="03-123456-10",
            ))
            printed = build_print_clinic_profile(saved)
            self.assertEqual(saved["doh_license_number"], "03-123456-10")
            self.assertEqual(printed["doh_license_number"], "03-123456-10")

            cleared = save_clinic_profile(session, ClinicProfilePayload(
                clinic_name="Naic Doctors Hospital Inc.",
                doh_license_number="",
            ))
            self.assertEqual(cleared["doh_license_number"], "")
```

- [ ] **Step 2: Run and confirm the schema rejects the new field behavior**

Run:

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe -m unittest tests.test_client_print_adjustments.ClientPrintAdjustmentTests.test_doh_license_persists_prints_and_clears -v
```

Expected: failure because the model and serialized profile have no DOH field.

- [ ] **Step 3: Add the model, additive migration, payload, and services**

Add to `ClinicProfile`:

```python
doh_license_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
```

In `ensure_runtime_schema()`, inspect `PRAGMA table_info(clinic_profiles)` and run:

```python
if "doh_license_number" not in clinic_profile_columns:
    connection.exec_driver_sql(
        "ALTER TABLE clinic_profiles ADD COLUMN doh_license_number VARCHAR(120)"
    )
```

Add to `ClinicProfilePayload`:

```python
doh_license_number: str | None = None
```

Add to `serialize_clinic_profile()`:

```python
"doh_license_number": compact_text(profile.doh_license_number),
```

In `build_print_clinic_profile()`, the source is already a dictionary, so use:

```python
doh_license_number = compact_text(profile.get("doh_license_number"))
```

and return `"doh_license_number": doh_license_number`.

In `save_clinic_profile()`, normalize and assign the value with the other text fields:

```python
doh_license_number = compact_text(payload.doh_license_number)
old_doh_license_number = profile.doh_license_number
profile.doh_license_number = doh_license_number or None
```

Inside its existing `except Exception:` rollback branch, restore:

```python
profile.doh_license_number = old_doh_license_number
```

- [ ] **Step 4: Wire the clinic settings form and print header**

Add this constructor argument in `main.py` POST `/settings/clinic`:

```python
doh_license_number=str(form.get("doh_license_number") or ""),
```

Add this key to the validation-error `profile_override` dictionary:

```python
"doh_license_number": payload.doh_license_number or "",
```

Add this field to `settings/clinic.html`:

```html
<label class="field-stack">
  <span>DOH License No.</span>
  <input type="text" name="doh_license_number" value="{{ clinic_profile.doh_license_number }}" placeholder="Optional">
</label>
```

Show the value in the brand snapshot. In the print clinic copy, render only when populated:

```html
{% if clinic.doh_license_number %}
<span>DOH License No.: {{ clinic.doh_license_number }}</span>
{% endif %}
```

Use this exact preview block after contact email in `settings/clinic.html`:

```html
{% if clinic_profile.doh_license_number %}
<p>DOH License No.: {{ clinic_profile.doh_license_number }}</p>
{% endif %}
```

- [ ] **Step 5: Test, compile, and commit**

Run:

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe -m unittest tests.test_client_print_adjustments -v
.\env\Scripts\python.exe -m compileall app\naic_builder tests
```

Expected: all tests pass.

```powershell
git add app/naic_builder/models.py app/naic_builder/schemas.py app/naic_builder/database.py app/naic_builder/services.py app/naic_builder/main.py app/naic_builder/templates/settings/clinic.html app/naic_builder/templates/records/_print_document.html tests/test_client_print_adjustments.py
git commit -m "feat: add clinic DOH license number"
```

---

### Task 5: Format Printed Dates Without Changing Stored Values

**Files:**
- Modify: `tests/test_client_print_adjustments.py`
- Modify: `app/naic_builder/services.py`

**Interfaces:**
- Produces: `format_print_temporal_value(data_type: Any, value: Any) -> str`.
- Consumes: field `props.data_type` in `build_print_display_value()` and field-backed `build_print_summary_items()` entries.

- [ ] **Step 1: Add failing formatting tests**

```python
from naic_builder.services import (
    build_print_display_value,
    build_print_summary_items,
    format_print_temporal_value,
)

    def test_print_temporal_values_are_nontechnical(self) -> None:
        self.assertEqual(format_print_temporal_value("date", "2026-07-16"), "07/16/2026")
        self.assertEqual(format_print_temporal_value("datetime", "2026-07-16T10:15"), "07/16/2026 10:15 AM")
        self.assertEqual(format_print_temporal_value("datetime", "2026-07-16T22:05"), "07/16/2026 10:05 PM")
        self.assertEqual(format_print_temporal_value("time", "22:05"), "22:05")
        self.assertEqual(format_print_temporal_value("datetime", "legacy value"), "legacy value")
        self.assertEqual(
            build_print_display_value(
                {"data_type": "date"},
                "2026-07-16",
                None,
                record_id=1,
            )["text"],
            "07/16/2026",
        )
        summary = build_print_summary_items(
            {
                "show_summary": True,
                "summary_items": [{"source": "field", "field_id": "collected_at"}],
            },
            {
                "entry_schema": {
                    "blocks": [{
                        "id": "collected_at",
                        "kind": "field",
                        "name": "Collected at",
                        "props": {"data_type": "datetime"},
                    }],
                },
                "record_identity": {},
                "record_key": "TEST-1",
            },
            {"collected_at": "2026-07-16T22:05"},
            issued_at_label="",
        )
        self.assertEqual(summary[0]["value"], "07/16/2026 10:05 PM")
```

- [ ] **Step 2: Verify the function is missing**

Run:

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe -m unittest tests.test_client_print_adjustments.ClientPrintAdjustmentTests.test_print_temporal_values_are_nontechnical -v
```

Expected: import failure because `format_print_temporal_value` does not exist.

- [ ] **Step 3: Implement strict display-only parsing**

Add to `services.py`:

```python
def format_print_temporal_value(data_type: Any, value: Any) -> str:
    text = compact_text(value)
    kind = compact_text(data_type).lower()
    if not text or kind not in {"date", "datetime"}:
        return text
    try:
        if kind == "date":
            parsed_date = datetime.fromisoformat(text).date()
            return parsed_date.strftime("%m/%d/%Y")
        parsed_datetime = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed_datetime.strftime("%m/%d/%Y %I:%M %p")
    except ValueError:
        return text
```

In `build_print_display_value()`, replace `compact_text(value)` with:

```python
text_value = format_print_temporal_value(data_type, value)
```

In the `source == "field"` branch of `build_print_summary_items()`, replace the raw value conversion with:

```python
field_block = field.get("block") if isinstance(field, dict) and isinstance(field.get("block"), dict) else {}
field_props = field_block.get("props") if isinstance(field_block.get("props"), dict) else {}
field_data_type = compact_text(field_props.get("data_type"))
if field_data_type in {"date", "datetime"}:
    value = format_print_temporal_value(field_data_type, values.get(field_id))
else:
    value = record_value_display_text(values.get(field_id))
```

- [ ] **Step 4: Run all focused tests and commit**

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe -m unittest tests.test_client_print_adjustments -v
git add app/naic_builder/services.py tests/test_client_print_adjustments.py
git commit -m "feat: format dates for printed results"
```

Expected: all tests pass; no record-entry or storage code changed.

---

### Task 6: Update Shared Print Layout

**Files:**
- Modify: `tests/test_client_print_adjustments.py`
- Modify: `app/naic_builder/templates/records/_print_document.html`
- Modify: `app/naic_builder/static/print.css`
- Modify: `app/naic_builder/templates/forms/print_preview.html`
- Modify: `app/naic_builder/templates/records/print.html`

**Interfaces:**
- Consumes: printable signatory `label`, `designation`, image, name, and license.
- Produces: `.print-result-inline`, `.print-result-unit`, `.print-signature-label`, and `.print-signature-designation` markup.

- [ ] **Step 1: Add a failing shared-template rendering test**

```python
from jinja2 import Environment, FileSystemLoader

    def test_shared_print_template_places_units_and_labels_correctly(self) -> None:
        environment = Environment(loader=FileSystemLoader(ROOT / "app" / "naic_builder" / "templates"))
        macro = environment.get_template("records/_print_document.html").module.render_print_page
        row_field = {
            "kind": "field",
            "name": "PULSE RATE",
            "unit_hint": "bpm",
            "reference_text": "",
            "display": {"kind": "text", "text": "-2"},
            "is_abnormal": False,
        }
        grid_field = {
            **row_field,
            "name": "TEMPERATURE",
            "unit_hint": "deg C",
            "display": {"kind": "text", "text": "4"},
        }
        html = macro({
            "items": [row_field, {"kind": "field_grid", "items": [grid_field]}],
            "clinic": {
                "name": "NDH",
                "address": "",
                "contact_line": "",
                "doh_license_number": "03-123456-10",
            },
            "print_config": {
                "show_logo": False,
                "show_clinic_info": True,
                "show_status": False,
                "show_summary": False,
                "show_signatures": True,
            },
            "report_title": "Blood Bank",
            "form_name": "Blood Bank",
            "form_path_label": "Blood Bank",
            "status": "completed",
            "summary_items": [],
            "signatures": [{
                "label": "Analyzed by:",
                "designation": "Medical Technologist (RMT)",
                "name": "Crystel C. Tesoro, RMT",
                "license": "0103760",
                "image_url": "",
            }],
        })
        self.assertEqual(html.count('class="print-result-inline"'), 2)
        self.assertIn('class="print-result-unit">bpm', html)
        self.assertIn('class="print-result-unit">deg C', html)
        self.assertIn("DOH License No.: 03-123456-10", html)
        label_at = html.index('class="print-signature-label">Analyzed by:')
        name_at = html.index('class="print-signature-name">Crystel C. Tesoro, RMT')
        designation_at = html.index('class="print-signature-designation">Medical Technologist (RMT)')
        self.assertLess(label_at, name_at)
        self.assertLess(name_at, designation_at)
        self.assertNotIn(">Examination<", html)
        self.assertNotIn('class="print-row-unit"', html)
```

- [ ] **Step 2: Run and verify markup assertions fail**

Run:

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe -m unittest tests.test_client_print_adjustments.ClientPrintAdjustmentTests.test_shared_print_template_places_units_and_labels_correctly -v
```

Expected: assertion failure because the new result, unit, and signatory classes are absent and `Examination` still renders.

- [ ] **Step 3: Create one shared result-and-unit macro**

Add:

```jinja2
{% macro render_print_field_result(item) %}
  {% set display = item["display"] or {} %}
  <span class="print-result-inline">
    {{ render_print_field_answer(item) }}
    {% if display.kind != "image" and display.text and item.unit_hint %}
    <span class="print-result-unit">{{ item.unit_hint }}</span>
    {% endif %}
  </span>
{% endmacro %}
```

Use it in row and compact-grid results. Remove unit markup from `.print-grid-cell-head` and remove the `.print-row-unit` column entirely.

- [ ] **Step 4: Reorder generic signatory markup**

Replace the body of each `.print-signature` in `_print_document.html` with this generic order. Do not add checks for role words or slot IDs:

```jinja2
<strong class="print-signature-label">{{ signature.label }}</strong>
<span class="print-signature-mark">
  {% if signature.image_url %}
  <img class="print-signature-stamp" src="{{ signature.image_url }}" alt="{{ signature.image_alt or signature.label }}">
  {% endif %}
</span>
{% if signature.name or signature.license %}
<span class="print-signature-identity">
  {% if signature.name %}
  <span class="print-signature-name">{{ signature.name }}</span>
  {% endif %}
  {% if signature.license %}
  <small>Lic. No. {{ signature.license }}</small>
  {% endif %}
</span>
{% endif %}
{% if signature.signature_line is not sameas false %}
<span class="print-signature-rule" aria-hidden="true"></span>
{% endif %}
{% if signature.designation %}
<span class="print-signature-designation">{{ signature.designation }}</span>
{% endif %}
```

Add these selectors in `print.css`; replace the old `.print-signature strong` and `.print-signature em` selector usage with the named classes:

```css
.print-signature-label {
  color: var(--muted);
  font-size: 10px;
  font-weight: 800;
  line-height: 1.15;
}

.print-signature-designation,
.print-signature small {
  color: var(--muted);
  font-size: 9.5px;
  line-height: 1.15;
}
```

In the print-media block set both named signatory classes to `font-size: 7.5px`; keep the license text at the existing `7.2px` value.

- [ ] **Step 5: Preserve the banner while removing its eyebrow**

Remove only:

```jinja2
<p class="print-eyebrow">Examination</p>
```

Update `print.css`:

```css
.print-exam-head {
  min-height: 46px;
}

.print-exam-copy {
  display: flex;
  min-width: 0;
  min-height: 34px;
  align-items: center;
}

.print-title {
  margin-top: 0;
  font-size: 23px;
  letter-spacing: 0;
}

.print-row {
  grid-template-columns: minmax(0, 1.08fr) minmax(140px, 1fr);
}

.print-result-inline {
  display: inline-flex;
  max-width: 100%;
  min-width: 0;
  gap: 4px;
  align-items: baseline;
  flex-wrap: nowrap;
}

.print-result-unit {
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
```

In the existing print media block, use `min-height: 38px` for the banner, `min-height: 27px` for the copy, `19px` for the title, and `grid-template-columns: minmax(0, 1.08fr) minmax(124px, 1fr)` for rows. Remove obsolete `.print-row-unit` rules in both normal and print-media sections.

- [ ] **Step 6: Test template output and compile**

Set the `print.css` query string in both `forms/print_preview.html` and `records/print.html` to `?v=20260718-client-print` before running verification.

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe -m unittest tests.test_client_print_adjustments -v
.\env\Scripts\python.exe -m compileall app\naic_builder tests
```

Expected: all tests pass.

- [ ] **Step 7: Commit the shared print layout**

```powershell
git add app/naic_builder/templates/records/_print_document.html app/naic_builder/static/print.css app/naic_builder/templates/forms/print_preview.html app/naic_builder/templates/records/print.html tests/test_client_print_adjustments.py
git commit -m "feat: refine client print layout"
```

---

### Task 7: Strengthen Print QA And Handoff Documentation

**Files:**
- Modify: `tools/scripts/print_record_qa.py`
- Modify: `docs/handoff/PRINT_SYSTEM_HANDOFF.md`
- Modify: `tests/test_client_print_adjustments.py`

**Interfaces:**
- Consumes: completed-record print route and all 16 current forms.
- Produces: smoke assertions for approved labels/designation/layout and absence of the fixed Examination eyebrow; focused Task 5 tests own date-format assertions.

- [ ] **Step 1: Update smoke expectations**

Replace the `missing` construction in `qa_record_print()` with:

```python
required_tokens = [
    "print-page",
    "print-fit-badge",
    compact_text(result.get("record_key")),
    compact_text(result.get("form_name")),
    "Analyzed by:",
    "Verified by:",
    "Noted by:",
    "Medical Technologist (RMT)",
    "print-result-inline",
]
missing = [token for token in required_tokens if token and token not in html_text]
forbidden_tokens = [">Examination<", 'class="print-row-unit"']
forbidden = [token for token in forbidden_tokens if token in html_text]
```

Add `"forbidden": forbidden` to the returned dictionary. In `main()`, print `forbidden=none` or the joined forbidden tokens beside `missing=...`, and fail a slug when `result["missing"]`, `result["forbidden"]`, or `result["fit"] == "long"`. The exact markup check keeps actual form fields named Examination valid.

- [ ] **Step 2: Run focused tests and all-form route smoke**

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe -m unittest tests.test_client_print_adjustments -v
.\env\Scripts\python.exe tools\scripts\print_record_qa.py --all
```

Expected: all tests pass; all 16 forms report `missing=none`, `forbidden=none`, and no `long` fit.

- [ ] **Step 3: Run A4 PDF QA**

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe tools\scripts\print_pdf_qa.py --all --max-pages 1
```

Expected: all 16 PDFs have one page. Inspect Blood Bank plus one compact-grid chemistry form and one long/tight form for banner height, inline units, dates, signatory order, and stamp rendering.

- [ ] **Step 4: Update the print handoff**

Document the new `designation` property, approved default slots, print-only temporal formatting, inline result/unit rule, banner rule, DOH header line, migration marker, seed stamp packaging, and exact QA commands/results in `PRINT_SYSTEM_HANDOFF.md`.

- [ ] **Step 5: Commit QA and docs**

```powershell
git add tools/scripts/print_record_qa.py docs/handoff/PRINT_SYSTEM_HANDOFF.md tests/test_client_print_adjustments.py
git commit -m "test: cover client print adjustments"
```

---

### Task 8: Build And Verify The Adjustment Installer

**Files:**
- Modify: `tools/desktop/VERSION`
- Generated: `dist/desktop/installer/NDHI-LabRecords-Setup-0.1.5-dev-x64.exe`

**Interfaces:**
- Consumes: Tasks 1-7 and the existing repeatable installer build.
- Produces: an x64 development installer containing the seed stamp and database migrations.

- [ ] **Step 1: Bump the development version**

Set `tools/desktop/VERSION` to:

```text
0.1.5-dev
```

- [ ] **Step 2: Run the complete source verification**

```powershell
$env:PYTHONPATH='app'
.\env\Scripts\python.exe -m unittest tests.test_client_print_adjustments -v
.\env\Scripts\python.exe -m compileall app\naic_builder tests tools\scripts tools\desktop
.\env\Scripts\python.exe tools\scripts\print_record_qa.py --all
git diff --check
```

Expected: all tests pass, compilation exits `0`, all 16 route smokes pass, and diff check reports no errors.

- [ ] **Step 3: Build the x64 installer**

```powershell
.\tools\desktop\build-installer.ps1 -Architecture x64
```

Expected: packaged server health, bundled backup verification, and Inno Setup compilation pass; output is `dist\desktop\installer\NDHI-LabRecords-Setup-0.1.5-dev-x64.exe`.

- [ ] **Step 4: Run upgrade and fresh-runtime smoke checks**

Use the packaged executable left by Step 3 at `dist\desktop\package\NDHI-LabRecords\NDHI-LabRecords.exe` with a new temporary `--data-dir`. The build script already performs the hidden packaged health/backup smoke; repeat it without deleting the runtime until these values are inspected:

```text
current form count = 16
all current form metadata markers = true
all first three slot IDs = medical_technologist_1, medical_technologist_2, pathologist
required flags = true, true, false
pathologist type = stamp_image
runtime stamp = uploads/signatories/default-pathologist-stamp.png
```

Run this disposable fresh-runtime check from the repository root:

```powershell
$qaRuntime = Join-Path $env:TEMP 'ndhi-client-adjustment-fresh-runtime'
$qaExternal = Join-Path $env:TEMP 'ndhi-client-adjustment-external-backups'
foreach ($path in @($qaRuntime, $qaExternal)) {
  $full = [IO.Path]::GetFullPath($path)
  $temp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
  if (-not $full.StartsWith($temp, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to prepare a QA path outside TEMP: $full"
  }
  if (Test-Path -LiteralPath $full) { Remove-Item -LiteralPath $full -Recurse -Force }
  New-Item -ItemType Directory -Force -Path $full | Out-Null
}
New-Item -ItemType Directory -Force -Path "$qaRuntime\config" | Out-Null
@{
  browser_preference = 'auto'
  network_mode = 'local'
  external_backup_dir = $qaExternal
  backup_retention_count = 30
} | ConvertTo-Json | Set-Content -LiteralPath "$qaRuntime\config\desktop.json" -Encoding UTF8

$exe = (Resolve-Path 'dist\desktop\package\NDHI-LabRecords\NDHI-LabRecords.exe').Path
$port = 18116
function Invoke-FreshRuntimeStartStop {
  $server = Start-Process -FilePath $exe -ArgumentList @('--serve', '--host', '127.0.0.1', '--port', $port, '--data-dir', $qaRuntime) -PassThru -WindowStyle Hidden
  try {
    $healthy = $false
    foreach ($attempt in 1..80) {
      try {
        $health = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 1
        if ($health.status -eq 'ok') { $healthy = $true; break }
      } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $healthy) { throw 'Disposable packaged server did not become healthy.' }
    Start-Sleep -Seconds 6
  } finally {
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    Wait-Process -Id $server.Id -Timeout 10 -ErrorAction SilentlyContinue
  }
}

Invoke-FreshRuntimeStartStop
$beforeVersions = @'
import json
from pathlib import Path
import sqlite3
import sys

root = Path(sys.argv[1])
db = root / "database" / "ndhi_labrecords.db"
with sqlite3.connect(db) as connection:
    rows = connection.execute(
        "SELECT fv.block_schema_json FROM form_versions fv WHERE fv.is_current = 1"
    ).fetchall()
    assert len(rows) == 16, len(rows)
    for (raw_schema,) in rows:
        schema = json.loads(raw_schema)
        meta = schema.get("meta") or {}
        slots = meta.get("signatories") or []
        assert meta.get("client_signatory_defaults_2026_07") is True
        assert [slot.get("id") for slot in slots[:3]] == [
            "medical_technologist_1", "medical_technologist_2", "pathologist"
        ]
        assert [slot.get("required") for slot in slots[:3]] == [True, True, False]
        assert slots[2].get("input_type") == "stamp_image"
    version_count = connection.execute("SELECT COUNT(*) FROM form_versions").fetchone()[0]
assert (root / "uploads" / "signatories" / "default-pathologist-stamp.png").is_file()
print(version_count)
'@ | .\env\Scripts\python.exe - $qaRuntime

$localBackup = Get-ChildItem -LiteralPath "$qaRuntime\backups" -Filter '*.zip' | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
$externalBackup = Get-ChildItem -LiteralPath $qaExternal -Filter '*.zip' | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if ($null -eq $localBackup -or $null -eq $externalBackup) { throw 'Local or external after-change backup is missing.' }
Invoke-FreshRuntimeStartStop
$afterVersions = .\env\Scripts\python.exe -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('SELECT COUNT(*) FROM form_versions').fetchone()[0])" "$qaRuntime\database\ndhi_labrecords.db"
if ([int]$beforeVersions -ne [int]$afterVersions) { throw 'Restart created duplicate form versions.' }
```

Restart that packaged runtime and confirm the total `form_versions` count is unchanged. Verify the latest local archive with:

```powershell
$exe = Resolve-Path 'dist\desktop\package\NDHI-LabRecords\NDHI-LabRecords.exe'
$latest = Get-ChildItem -LiteralPath "$qaRuntime\backups" -Filter '*.zip' | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if ($null -eq $latest) { throw 'Fresh-runtime backup archive was not created.' }
$verify = Start-Process -FilePath $exe -ArgumentList @('--verify-backup', $latest.FullName, '--data-dir', $qaRuntime) -Wait -PassThru -WindowStyle Hidden
if ($verify.ExitCode -ne 0) { throw 'Fresh-runtime backup verification failed.' }
```

For upgrade QA, close the installed `0.1.4-dev` app, run the `0.1.5-dev` installer, and start the installed executable once. Confirm `%ProgramData%\NDHI\LabRecords\backups` contains a newly verified `pre-update` archive, every previously unmarked current form received exactly one new system version, a second restart adds zero versions, ProgramData records/uploads remain present, and normal launch does not request elevation.

Complete this UI matrix as an admin on the installed build:

```text
Forms Builder: edit Role label + Designation -> save -> reload -> values remain -> preview matches
Forms Builder: replace fixed stamp -> save -> preview uses replacement
Clinic profile: save DOH License No. -> record print shows it -> clear it -> print reserves no line
Record completion: omit either MedTech -> completion blocked; select both -> completion succeeds
Pathologist: complete/print without per-record selection -> configured stamp appears automatically
Rows + Compact grid: result and unit remain adjacent
Backup: wait for after-change sync -> verify latest local and configured external archives in Backup
```

- [ ] **Step 5: Commit the release version**

```powershell
git add tools/desktop/VERSION
git commit -m "build: prepare 0.1.5 development installer"
```

- [ ] **Step 6: Record final evidence**

Report the installer path and timestamp, unit-test count, all-form route smoke result, all-form PDF page-count result, migration first/second-run counts, fresh/upgrade stamp checks, and local/external backup status. State explicitly if physical-printer or clean-PC checks remain manual.
