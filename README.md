# NDHI Laboratory Records Workspace

This workspace is organized to separate raw inputs, generated artifacts, reference materials, and future app source code.

## Structure
- `app/`
  Future application source code should live here.
- `data/source/`
  Raw source workbook and other authoritative input files.
- `references/print-templates/`
  Legacy `.dotx` print templates used only as visual/layout guidance.
- `tools/scripts/`
  Utility and generation scripts for parsing and maintaining structured data artifacts.
- `artifacts/schema/`
  Generated schema, tree, and HTML outputs derived from the workbook.
- `artifacts/inspection/playwright/`
  Screenshots and inspection artifacts.
- `docs/handoff/`
  AI handoff and project-context documents.
- `scratch/`
  Temporary or disposable local files.

## Current Source Of Truth
- Workbook: `data/source/NAIC MEDTECH SYSTEM DATA.xlsx`
- App schema: `artifacts/schema/naic_medtech_app_schema.json`
- Active handoff: `docs/handoff/NAIC_MEDTECH_AI_HANDOFF.md`
- Print handoff: `docs/handoff/PRINT_SYSTEM_HANDOFF.md`

## Notes
- The app should be built from the schema, not from legacy print templates.
- The highest-priority feature is the exam/form builder.
- The active builder UX direction is documented in `docs/handoff/BUILDER_V2_PLAN.md`.
- Current record date/time behavior intentionally keeps native browser inputs for safety and adds workflow helpers: builder-level `Default answer`, smart blank-field auto-fill, quick chips, and readable previews.
- Current print workflow intentionally uses explicit post-print actions: `Print / Save PDF`, `Next same form`, `Choose form`, and secondary `Back to record`.
