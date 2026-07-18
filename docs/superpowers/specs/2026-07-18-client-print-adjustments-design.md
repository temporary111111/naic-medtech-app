# Client Print Adjustments Design

## Purpose

Implement the approved NDH client adjustments without weakening the form builder's generic, versioned architecture. The changes must reduce manual setup for the clinic while keeping signatory roles, designations, people, stamps, and print behavior configurable per form version.

The approved source request is `others/adjustment-request/Request for System Adjustment  - NDH.docx`.

## Design Principles

- Keep the print engine generic. It must not contain MedTech- or Pathologist-specific rendering conditions.
- Keep print and signatory configuration in each saved form version.
- Provide clinic-ready defaults for every existing and new form so staff do not configure the same three signatories repeatedly.
- Preserve old frozen form versions and records. Apply the client defaults through a new current form version.
- Keep clinic identity data, including the DOH license number, clinic-wide rather than per form.
- Use the same shared print document for builder preview and actual record printing.

## Signatory Model

Each signatory slot will support two independent display properties:

```json
{
  "label": "Analyzed by:",
  "designation": "Medical Technologist (RMT)"
}
```

- `label` is the editable Role label shown above the signature or stamp.
- `designation` is optional editable text shown below the signature line.
- Existing generic controls remain: input type, people, default person, required, show on print, show license, signature line, stamp image, and ordering.
- New custom signatory slots remain generic and do not receive MedTech- or Pathologist-specific behavior.
- Signatory snapshots stored with records will include `label` and `designation`, so completed records retain the form-version configuration used when they were created.
- Legacy snapshot `title` values remain readable as a compatibility fallback, but `designation` is the canonical slot-level display value.

### Clinic Defaults

All existing current forms and all newly created forms receive these defaults:

| Slot | Role label | Designation | Type | Completion behavior |
| --- | --- | --- | --- | --- |
| `medical_technologist_1` | `Analyzed by:` | `Medical Technologist (RMT)` | Person choice | A MedTech selection is required |
| `medical_technologist_2` | `Verified by:` | `Medical Technologist (RMT)` | Person choice | A MedTech selection is required |
| `pathologist` | `Noted by:` | `Pathologist` | Fixed stamp image | The configured stamp is automatically included; no per-record selection is required |

The existing MedTech people and license list remains preconfigured. The approved Bernardita Mojica Figueroa stamp is the initial Pathologist stamp.

The fixed stamp feature remains generic and configurable. An admin may replace the image, change its type, hide it from print, remove the slot, or change any label or designation in the Forms Builder.

## Default Stamp Asset

The approved Pathologist stamp currently stored in the development runtime will be copied into a bundled seed resource under `artifacts/seed/signatories/`. Packaging will include that resource.

On first use, the app will copy the seed image into the persistent runtime `uploads/signatories` directory and use its authenticated `/signatory-stamps/...` URL in default form configurations. Existing custom stamp files and configured stamp URLs will not be overwritten.

The runtime copy remains part of verified local and external backups. The bundled copy is only a replaceable initial default, not a hardcoded print image.

## Existing Form Migration

An idempotent startup migration will inspect the current version of each form. For the three recognized default slot IDs, it will apply the approved defaults and create one new current form version.

- Existing versions remain unchanged and non-current.
- Existing records remain tied to their original frozen form version.
- Unknown or additional signatory slots remain unchanged.
- The migration writes a versioned marker in form metadata so repeated startup does not create repeated versions.
- The migration runs transactionally. A failure rolls back the affected database transaction instead of leaving partially migrated forms.
- The existing post-commit backup request will produce an after-change backup once the worker starts. Installer upgrades remain protected by the existing pre-update backup.

The reference schema generator, generated reference schema, backend defaults, and frontend new-form defaults must all use the same approved three-slot configuration.

## Builder Experience

`Forms Builder > Signatories` will expose `Role label` and `Designation` together for each slot.

- Role label examples include `Analyzed by:`, `Verified by:`, `Noted by:`, `Released by:`, or any clinic-defined wording.
- Designation examples include `Medical Technologist (RMT)`, `Pathologist`, or any clinic-defined wording.
- Add, remove, reorder, type selection, people choices, fixed person, manual entry, blank line, and fixed stamp image behavior remain available.
- The builder print preview immediately reflects label, designation, stamp, and ordering changes.
- A stamp-image slot configured to print without an available image shows a clear builder warning. It does not create a fake per-record selection requirement.

## Print Rendering

Builder print preview and actual record print continue to use `templates/records/_print_document.html` and the shared print document builders.

### Signatory Layout

The generic rendering order is:

```text
ROLE LABEL
[signature, blank signing area, or fixed stamp image]
Selected/fixed/manual name
License number
--------------------------------
Designation
```

Elements that are blank or disabled do not reserve an unnecessary text line. A fixed stamp may already contain a name and license; the renderer will not duplicate those values unless they are separately configured for the slot.

### Date Display

Stored values and record-entry controls remain ISO/browser-compatible. Formatting occurs only when building printable display values.

| Field data type | Printed format | Example |
| --- | --- | --- |
| `date` | `MM/DD/YYYY` | `07/16/2026` |
| `datetime` | `MM/DD/YYYY hh:mm AM/PM` | `07/16/2026 10:15 AM` |

If a legacy value cannot be parsed safely, the original text is printed unchanged. Time-only fields are outside this adjustment and retain their current behavior.

### Result And Unit

For both `Rows` and `Compact grid`, the unit appears directly after the recorded result:

```text
PULSE RATE      -2 bpm
TEMPERATURE      4 deg C
```

- The unit is no longer rendered beside the field name or in a distant third column.
- The result and unit form one wrapping inline group.
- Empty results do not append a unit to `No value recorded.`
- Image fields are unaffected.

### Report Banner

- Remove the fixed `Examination` eyebrow above the report title.
- Preserve the current colored banner's visual height and horizontal padding.
- Increase the report title size slightly.
- Keep the title left-aligned and vertically centered.
- Preserve configurable accent colors, draft status behavior, responsive print rules, and A4 fit.
- Do not remove or rename actual form fields whose configured name is `Examination`.

## DOH License Number

Add optional clinic-wide `doh_license_number` data.

- Add a nullable `VARCHAR(120)` column to `clinic_profiles` through the existing runtime schema migration mechanism.
- Add the field to `ClinicProfilePayload`, clinic profile serialization, save handling, and `Settings > Clinic profile`.
- Show it in the clinic brand preview.
- Print `DOH License No.: <value>` below the clinic contact details when configured.
- When blank, render no placeholder and reserve no line.
- Clinic profile saves continue to trigger the existing after-change backup flow.

## Error Handling And Compatibility

- Invalid legacy date values remain visible unchanged.
- Missing optional labels, designations, licenses, and DOH numbers do not create empty print rows.
- Both required MedTech choices block record completion when missing.
- The fixed Pathologist stamp is automatically included and does not require a per-record action.
- Missing stamp files are surfaced in the builder and omitted safely from print rather than producing a broken image.
- Existing custom signatory slots and custom stamp images are preserved.
- Existing desktop permissions, LAN behavior, restore protection, and backup behavior are outside the change and must not regress.

## Verification

### Unit And Service Tests

- Normalize and round-trip `label` and `designation`.
- Preserve legacy `title` fallback behavior.
- Verify the approved three-slot defaults.
- Verify migration idempotency and preservation of unknown slots.
- Verify date and datetime display formatting plus invalid-value fallback.
- Verify DOH clinic-profile serialization and persistence.
- Verify required MedTech completion validation and fixed-stamp no-input behavior.

### Integration And UI Tests

- Edit, save, reload, and preview Role label and Designation in the builder.
- Replace a fixed stamp and verify that the selected form version uses it.
- Save and clear the DOH License No. setting.
- Compare builder preview and actual record print for the same configuration.
- Check `Rows` and `Compact grid` result/unit rendering.
- Check blank optional values and missing stamp behavior.

### Print And Desktop QA

- Run actual-record print smoke coverage for all 16 seeded forms.
- Run browser A4 PDF page-count QA for all 16 forms.
- Visually inspect the banner, signatories, units, dates, and clinic header at print resolution.
- Verify fresh-install seed stamp availability.
- Verify upgrade migration creates one new current version per form and does not repeat on restart.
- Verify local and configured external backup status after migration and settings changes.

## Out Of Scope

- A global live-linked signatory directory that retroactively changes saved form versions.
- Hardcoded MedTech or Pathologist conditions in the print renderer.
- Changes to time-only field formatting.
- New approval-chain workflow or additional user roles.
- Redesign of the already working fixed stamp upload feature.
- Changes to desktop LAN, permissions, restore, or backup architecture beyond regression verification.
