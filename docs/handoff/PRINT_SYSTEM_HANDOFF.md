# Print System Handoff

## Purpose
This document captures the current product decisions, implementation state, and next work for patient-facing print output.

Printing is a high-importance feature because this is the result document the clinic gives to patients. Treat print quality, compactness, and configurability as part of the core product, not as a minor browser-print detail.

## Current Product Decisions
- Print output should be compact and patient-facing.
- The practical target is one page when the form content allows it.
- The active print direction is A4 portrait, not the old landscape template shape.
- Header/accent color should be configurable per examination/form so staff can visually recognize the test type.
- Legacy `.dotx` templates in `references/print-templates` are visual guidance only. Do not copy them exactly.
- The app must stay generic. It should not hardcode patient-info concepts such as patient name, age, or case number as special workflow zones in the builder.
- Patient information is just normal form content. If the clinic wants a `Patient info` area, the user should create that section and choose which fields belong there.
- Signatories are generic print-footer slots, not ordinary result fields. Current seeded defaults are two Medical Technologist slots and one fixed Pathologist slot because that matches the source workbook/client workflow, but the builder must allow changing those roles later.
- Required fields are field-level builder settings. The clinic decides which fields are required, including identity-style fields such as name or case number.
- Print configuration belongs to the form builder, preferably in a separate `Print` tab/panel, because print behavior is tied to each saved form version.
- Do not build a full Canva/Figma-style freeform editor right now. The safer direction is a constrained print configuration panel with clear template controls.

## Current Implementation Status
The first print configuration foundation, builder-side preview confidence pass, controlled result-body options, generic signatory configuration, compact real-form result layout, actual-record print smoke coverage, and repeatable browser PDF page-count QA are implemented.

Implemented:
- The recursive builder shell that owns `Print` and `Signatories` has now passed browser QA across duplicate-form startup, nested edits, save/reload, light/dark, desktop, tablet, and mobile layouts.
- Builder fields now support `props.required`.
- Completing a record validates configured required fields.
- Form versions can store generic record identity config at `block_schema.meta.record_identity`.
- Form versions can store print config at `block_schema.meta.print_config`.
- Default lab-request fields from the original source are now materialized as a normal `Patient Information` builder group, not as a hardcoded record-entry panel.
- Existing current forms have new current versions with `Patient Information` first, while old records remain attached to their frozen older form versions.
- The builder now has a `Print` pane/tab.
- Print config is normalized on backend save/read.
- `/records/{id}/print` reads the saved form version's print config.
- The builder `Print` pane can generate a backend-built sample print preview from the current unsaved draft.
- Builder print preview and `/records/{id}/print` share the same print document macro and backend print config normalization path.
- The builder print preview shows an estimated one-page fit signal: likely, tight, or long.
- Controlled result-body options now exist for hiding empty fields, section headings, group headings, image size, and table density.
- Generic signatory configuration now lives at `block_schema.meta.signatories`; it supports role labels, dropdown people, fixed people, fixed stamp images, manual entry, blank lines, required completion, print visibility, signature lines, and license display.
- Medical Technologist and Pathologist were removed from normal Patient Information fields in the runtime forms and moved into signatories. Existing runtime data was migrated with a DB backup under `data/runtime/backups/`.
- Compact result-grid layout now compresses consecutive ordinary scalar fields into a two-column print grid when useful.
- Print output now uses a modern exam identity band powered by each form's `accent_color`, with automatic dark/light title text for readable contrast. This intentionally keeps the old template's quick color-identification value without copying the old Word layout.
- Known seeded NAIC forms now get legacy-guided default accent colors when their print color is still the generic default: Blood Bank magenta, Hematology/Coag red, Blood Chemistry green, Serology orange, Clinical Microscopy cyan/yellow depending form, ABG purple, and Microbiology black.
- A first real-form fit audit improved the current sample set from 5 `long` forms to 0 `long` forms; remaining estimate status is 15 `likely` and 3 `tight`.
- The remaining tight forms, OGTT, Semen, and Serology, were exported through Chromium PDF QA as one A4 page each after the generic print spacing pass.
- A clinic-like stress pass with longer patient names, case numbers, requesting physician, medtech/pathologist names, remarks, and release fields still exported OGTT, Semen, and Serology as one A4 page each.
- Actual `/records/{id}/print` smoke now passes for all 18 current forms by creating temporary completed records and checking the real route; the QA script snapshots/restores the runtime DB by default so the smoke run does not leave QA rows behind.
- Browser PDF QA now generates A4 PDFs from real `/records/{id}/print` pages through Playwright, checks the resulting PDF page counts, restores the runtime DB by default, and currently passes all 18 forms as one-page A4 PDFs.
- Signatories now support a generic `stamp_image` input type for a full uploaded stamp image that already contains signature, name, and license. This is not pathologist-specific; any signatory slot can use it.

Code paths:
- `app/naic_builder/static/app.js`
  - new blank forms start with an editable/removable `Patient Information` group
  - builder `Print` pane
  - print config helpers
  - summary row editor
  - result-body controls
  - result-layout control
  - separate Signatories pane for print-footer roles/people
  - embedded builder print preview iframe and refresh flow
  - required-field toggle handling
- `app/naic_builder/static/app.css`
  - builder print-tab, summary editor, and embedded preview styling
- `app/naic_builder/services.py`
  - default patient-info materialization/backfill helpers
  - `normalize_record_identity_config`
  - `normalize_print_config`
  - legacy-guided default print accent migration for known seeded forms
  - `build_print_summary_items`
  - generic signatory normalization/snapshots
  - `build_print_signature_items`
  - `build_record_print_document`
  - `build_form_print_preview_document`
  - controlled print body rendering through `build_print_items`
  - compact field-run grouping for print output
  - sample-data generation and estimated page-fit scoring
  - required-field completion validation
- `app/naic_builder/templates/records/_print_document.html`
  - shared print-page macro used by real record print and builder preview
  - dynamic generic signatory footer rendering, including license numbers
- `app/naic_builder/templates/records/print.html`
  - applies `document.print_config`
  - shows the same estimated fit badge used by builder preview
  - renders configurable summary items
  - supports show/hide clinic logo, clinic info, status, and signatures
- `app/naic_builder/templates/forms/print_preview.html`
  - builder iframe document using sample data and the shared print-page macro
- `app/naic_builder/static/print.css`
  - compact print layout
  - exam identity band using the saved form accent color
  - print density handling
  - no-logo clinic header handling
  - builder-preview fit badge styling
- `tools/scripts/print_record_qa.py`
  - repeatable smoke for actual `/records/{id}/print`
  - creates temporary completed records with stress values
  - validates the real print route and restores the runtime DB by default
  - `--keep-records` intentionally skips DB restore when QA records should be inspected manually
- `tools/scripts/print_pdf_qa.py`
  - repeatable Chromium/Playwright PDF QA for actual `/records/{id}/print`
  - creates temporary completed records with stress values
  - launches a temporary local server, signs a session cookie, exports A4 PDFs, and checks page counts
  - refreshes ignored artifacts and `report.json` under `output/print-qa/`
  - restores the runtime DB by default unless `--keep-records` is used
  - current `--all` run passes all 18 forms at one A4 page each

## Config Shapes
`record_identity` lives under `block_schema.meta.record_identity`.

Current shape:
```json
{
  "primary_field_id": "form.patient.name",
  "secondary_field_id": "form.patient.case_number",
  "searchable_field_ids": [
    "form.patient.name",
    "form.patient.case_number"
  ]
}
```

Important rule: these fields are generic identity hints only. They are not a hardcoded patient-info model.

`print_config` lives under `block_schema.meta.print_config`.

Current shape:
```json
{
  "accent_color": "#2563eb",
  "density": "compact",
  "font_family": "arial_narrow",
  "show_logo": true,
  "show_clinic_info": true,
  "show_status": true,
  "show_summary": false,
  "show_signatures": true,
  "hide_empty_fields": false,
  "show_section_titles": true,
  "show_group_titles": true,
  "image_size": "medium",
  "table_density": "compact",
  "result_layout": "compact_grid",
  "summary_items": [
    {
      "id": "summary_primary",
      "label": "Record",
      "source": "primary_identity",
      "field_id": ""
    },
    {
      "id": "summary_total_volume",
      "label": "TOTAL VOLUME",
      "source": "field",
      "field_id": "form.semen.total_volume"
    }
  ]
}
```

Legacy `signature_left_*` and `signature_right_*` print-config keys still exist as fallback compatibility only. The active model is `block_schema.meta.signatories`.

`signatories` lives under `block_schema.meta.signatories`.

Current shape:
```json
[
  {
    "id": "medical_technologist_1",
    "label": "Medical Technologist",
    "input_type": "person_dropdown",
    "required": true,
    "show_on_print": true,
    "show_license": true,
    "signature_line": true,
    "default_option_id": "",
    "options": [
      {
        "id": "imelda_a_elemia",
        "name": "Imelda A. Elemia, RMT",
        "license": "0036643"
      }
    ]
  },
  {
    "id": "pathologist",
    "label": "Pathologist",
    "input_type": "stamp_image",
    "required": false,
    "show_on_print": true,
    "show_license": true,
    "signature_line": true,
    "stamp_image_url": "/signatory-stamps/stamp_example.png",
    "stamp_image_filename": "pathologist-stamp.png",
    "stamp_image_mime_type": "image/png",
    "options": []
  }
]
```

Existing seeded runtime forms may still use `input_type: "fixed"` for Pathologist until an admin switches that slot to `stamp_image` and uploads the fixed stamp.

Supported summary item sources:
- `field`
- `primary_identity`
- `secondary_identity`
- `record_key`
- `issued_at`
- `form_version`

Supported signatory input types:
- `person_dropdown`
- `fixed`
- `stamp_image`
- `manual`
- `blank`

Supported print font presets:
- `arial`
- `arial_narrow`
- `aptos`
- `segoe_ui`
- `cambria_title`
- `georgia_title`
- `times_new_roman`
- `bahnschrift_title`

## Current Print Pane Controls
The builder Print pane currently supports:
- exam identity/header accent color
- density: compact or comfortable
- font preset for the printed result
- show/hide clinic logo
- show/hide clinic info
- show/hide record status
- show/hide top summary strip
- show/hide signatures
- configurable summary rows
- summary rows sourced from ordinary fields or system values
- sample print preview generated from the current unsaved builder draft
- estimated one-page fit warning
- hide/show empty result fields
- hide/show section headings
- hide/show group headings
- image size: small, medium, or large
- table density: compact or comfortable
- result layout: compact grid or rows
- show/hide signatures
- Signatories pane controls role label, input type, required state, print visibility, license visibility, signature line, selectable people, fixed default person, and fixed stamp image upload

This is intentionally a constrained editor. It should stay easier than a design canvas.

## Legacy Template Guidance
Legacy templates showed these recurring patterns:
- clinic branding/header
- patient info block
- exam title or department title
- compact result table or structured result sections
- medtech/pathologist footer
- colored visual identity per examination

Use those patterns as reference only. The new app should produce a better, cleaner, configurable patient-facing document and should not inherit the old landscape layout.

## Known Limits
- One-page output cannot be guaranteed for arbitrarily long forms.
- The builder page-fit signal is an estimate only. Browser print preview remains the final confirmation.
- Chromium PDF QA now confirms OGTT, Semen, and Serology as one A4 page each with sample data; rerun real-device checks after real clinic data are reviewed.
- Chromium PDF stress QA also confirms OGTT, Semen, and Serology as one A4 page each with longer clinic-like values.
- Current automated fit audit after compact grid: 15 likely, 3 tight, 0 long across the current 18-form sample set.
- Top summary is off by default for patient-facing output because patient information is expected to print from the form body. It can be enabled only when a clinic explicitly wants a duplicate quick strip.
- Current summary configuration is row-based and simple. There are no conditional expressions yet.
- Empty-field hiding affects result body rows only; enabled summary rows still show configured summary information.
- Footer/signatory layout is intentionally constrained to a compact auto-fit signature footer, not a freeform print canvas.
- Existing records point to frozen form versions. New print config applies naturally to records created from newer saved form versions unless old versions are intentionally migrated.
- Clinic data and logo come from Settings > Clinic profile.
- This is not yet a full PDF generation engine. The current implementation is browser-print based.

## Recommended Next Work
Phase 2B is now landed:
- real print preview inside the builder using sample data
- estimated page-fit indicator or warning
- visible copy that preview changes are saved into the next form version
- shared print macro and backend config normalization between builder preview and `/records/{id}/print`

Phase 2C is now landed:
- hide empty fields
- choose whether section titles appear
- tune table density and image sizing rules
- keep the result body driven by form structure, not by a freeform canvas

Phase 2D is now landed:
- generic configurable signatory slots
- dropdown/fixed/manual/blank signatory modes
- cleaner clinic/footer rules without treating medtech/pathologist as ordinary result fields

Phase 2E should test real forms next:
- Semen
- Urinalysis
- Hematology
- Blood Chemistry
- forms with image fields
- long forms that may exceed one page

Phase 2E initial compacting pass is now landed:
- default `result_layout` is `compact_grid`
- ordinary consecutive scalar fields are grouped into a compact two-column print grid
- image fields stay as full-width rows
- the current automated audit has no remaining `long` estimates

Phase 2E browser/PDF QA is now landed:
- Chromium PDF export confirmed OGTT, Semen, and Serology as one A4 page each.
- Text-presence checks confirmed expected key sections/signatories were still present.
- Clinic-like stress PDF export confirmed those same forms still fit one A4 page with longer names and remarks.
- A generic print spacing pass landed: tighter print page margins, compact section headers, no repeated `Section` eyebrow in print mode, tighter meta/body/footer spacing.

Phase 2F actual-record print smoke is now landed:
- `/records/{id}/print` now receives `document.fit_estimate`.
- The real record print toolbar shows an estimated fit badge.
- `tools/scripts/print_record_qa.py --all` passes across all current 18 forms.
- The script uses temporary completed records and restores the runtime DB by default; use `--keep-records` only for manual inspection.
- `tools/scripts/print_pdf_qa.py --all` generates real A4 PDFs through Playwright, fails when any generated PDF exceeds the configured page limit, and currently passes all 18 forms as one-page A4 PDFs.

Next print QA should focus on:
- real clinic device/browser behavior
- real production records once available
- whether any form needs a per-form override from compact grid back to rows

Later, consider server-side PDF generation only if browser print is not reliable enough for the clinic's actual devices and workflow.

## Rule For Future AI
Do not restart the print architecture from scratch. Continue from the current generic builder-driven model:

`form_version.block_schema.meta.record_identity`

and

`form_version.block_schema.meta.print_config`

The user already clarified that flexibility is the priority. Patient info and required identity fields must remain user-configurable in the form builder.
