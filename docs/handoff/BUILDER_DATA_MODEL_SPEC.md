# Builder Data Model Spec

## Purpose
This document turns the flexible-builder direction into a concrete recommended data model.

It is the next layer after:
- `docs/handoff/FLEXIBLE_BUILDER_FOUNDATION.md`

This spec is meant to answer:
- what the organization tree should look like
- what a form definition should look like
- what a preset should look like
- how records should be stored
- how flexibility can stay high without making the UI overwhelming

## Design Rules
1. Hardcode primitives, not medical assumptions.
2. Separate organization from form layout.
3. Separate form design from saved patient records.
4. Use JSON for dynamic schema storage.
5. Keep the engine more flexible than the UI.
6. Keep advanced meaning optional, not required.

## Current UI Bridge
The live builder now intentionally shows only `Container` and `Field` in the normal Content pane.

This is a UX simplification, not a storage rewrite:
- existing `section` and `field_group` blocks still remain valid internal storage kinds
- a visible top-level `Container` may still save as a `section`
- a visible nested `Container` may still save as a `field_group`
- users should not need to understand that distinction during normal editing

The current Content UI is recursive:
- containers can contain containers or fields
- containers collapse/expand in place
- field name/input type editing happens inside the field card
- extra field details such as required status, references, normal range, and choice options stay collapsed until opened

If the product later needs separate section/group behavior, expose it as an advanced container display setting instead of bringing back separate default primitives.

## Recommended Entity Model

### 1. Library Node
Used to organize forms in a tree.

Node kinds:
- `container`
- `form`

Recommended shape:
```json
{
  "id": "node_001",
  "kind": "container",
  "name": "Serology",
  "parent_id": null,
  "order": 1,
  "archived": false,
  "form_id": null
}
```

```json
{
  "id": "node_002",
  "kind": "form",
  "name": "COVID 19 Antigen (Rapid Test)",
  "parent_id": "node_001",
  "order": 4,
  "archived": false,
  "form_id": "form_001"
}
```

### Why this is the best tree model
- supports root forms
- supports deep nesting
- supports future reorganization without schema rewrite
- avoids fixed `category/subcategory/form` assumptions

## 2. Form
Stable identity for a buildable form.

Recommended shape:
```json
{
  "id": "form_001",
  "slug": "covid_19_antigen_rapid_test",
  "current_draft_version_id": "formver_003",
  "current_published_version_id": "formver_002",
  "created_at": "2026-04-02T00:00:00Z",
  "updated_at": "2026-04-02T00:00:00Z"
}
```

### Notes
- form identity is stable
- draft and published versions may coexist
- the library node decides where the form lives in the tree

## 3. Form Version
Actual schema definition for one version of a form.

Recommended shape:
```json
{
  "id": "formver_003",
  "form_id": "form_001",
  "version_number": 3,
  "state": "draft",
  "name": "COVID 19 Antigen (Rapid Test)",
  "summary": "Added repeatable signatory block.",
  "schema": {},
  "created_at": "2026-04-02T00:00:00Z"
}
```

### Recommended states
- `draft`
- `published`
- `retired`

### Important rule
Patient/result records should always point to a specific `form_version_id`, not just a form id.

### Signatory Config
Signatories should live as form-version metadata, not as ordinary result fields.

Current recommended shape:
```json
{
  "meta": {
    "signatories": [
      {
        "id": "medical_technologist_1",
        "label": "Medical Technologist",
        "input_type": "person_dropdown",
        "required": true,
        "show_on_print": true,
        "show_license": true,
        "signature_line": true,
        "stamp_image_url": "",
        "stamp_image_filename": "",
        "stamp_image_mime_type": "",
        "options": []
      }
    ]
  }
}
```

Supported signatory input types are `person_dropdown`, `fixed`, `stamp_image`, `manual`, and `blank`.

This keeps the engine generic: `Medical Technologist` and `Pathologist` are current clinic defaults, not hardcoded employee concepts. A `stamp_image` slot is still just a generic signatory slot with an uploaded full stamp image, not a special pathologist model.

## 4. Preset
Reusable block bundle.

Recommended shape:
```json
{
  "id": "preset_001",
  "name": "Signatories",
  "category": "Common",
  "schema": {},
  "archived": false
}
```

### Recommended preset categories
- `Common`
- `Laboratory`
- `Custom`

### Important rule
Preset insertion should copy blocks into a form version.
Presets are accelerators, not dependencies.

## 5. Record
Saved patient/result entry using a specific form version.

Recommended shape:
```json
{
  "id": "record_001",
  "form_id": "form_001",
  "form_version_id": "formver_002",
  "status": "completed",
  "values": {},
  "indexed_meta": {},
  "created_at": "2026-04-02T00:00:00Z",
  "updated_at": "2026-04-02T00:00:00Z"
}
```

### Recommended record statuses
- `draft`
- `completed`
- `released`
- `archived`

### Why `values` should be JSON
The form structure is dynamic.
Trying to fully normalize every possible field into relational tables will make the system much more rigid and much harder to evolve.

### Why `indexed_meta` should exist
This is optional but strongly recommended.

It allows the system to store extracted searchable values such as:
- patient name
- date
- case number
- requesting physician

without hardcoding those fields into the form engine.

## Recommended Form Schema
The schema should be an ordered tree of blocks.

Top-level shape:
```json
{
  "schema_version": 1,
  "blocks": []
}
```

### Important rule
Do not special-case:
- `top_of_form`
- `shared_patient_info`
- `section_area`

The form should just have:
- ordered `blocks`

## Canonical Block Shape
Every block should have the same base structure.

Recommended base shape:
```json
{
  "id": "blk_001",
  "kind": "section",
  "name": "Macroscopic Finding",
  "props": {},
  "children": []
}
```

### Base fields
- `id`
- `kind`
- `name`
- `props`
- `children`

### Why this is better
One consistent block shape makes the engine much easier to extend later.

## Recommended Block Kinds

### Section
Used for labeled grouping.

Example:
```json
{
  "id": "blk_001",
  "kind": "section",
  "name": "Macroscopic Finding",
  "props": {
    "collapsible": false
  },
  "children": []
}
```

### Field
Used for a single input.

Example:
```json
{
  "id": "blk_002",
  "kind": "field",
  "name": "Color",
  "props": {
    "field_type": "select",
    "required": false,
    "options": [
      { "id": "opt_001", "label": "YELLOW" },
      { "id": "opt_002", "label": "AMBER" }
    ],
    "unit_hint": "",
    "normal_value": "",
    "placeholder": ""
  },
  "children": []
}
```

### Field Group
Used for a related bundle of fields.

Example:
```json
{
  "id": "blk_003",
  "kind": "field_group",
  "name": "Vital Signs",
  "props": {},
  "children": [
    {
      "id": "blk_004",
      "kind": "field",
      "name": "Blood Pressure",
      "props": {
        "field_type": "text"
      },
      "children": []
    }
  ]
}
```

### Note
Used for static instructional text.

### Divider
Used for visual separation.

### Table
Used for row/column input where repeated structured data matters.

### Repeater
Used when a block or block group may appear multiple times.

Good future examples:
- multiple signatories
- multiple samples
- multiple observations

### Columns
Optional layout block for limited side-by-side presentation.

Important:
- support later if needed
- do not make arbitrary visual layout a Phase 1 requirement

## Recommended Field Types
- `text`
- `textarea`
- `number`
- `select`
- `multi_select`
- `date`
- `time`
- `datetime`
- `checkbox`
- `radio`

Optional later:
- `lookup`
- `computed`
- `signature`
- `image`

## Recommended Field Props
For `field` blocks, recommended props:

```json
{
  "field_type": "text",
  "required": false,
  "placeholder": "",
  "default_value": null,
  "options": [],
  "unit_hint": "",
  "normal_value": "",
  "allow_multiple": false,
  "validation": {}
}
```

## Optional Semantic Hints
This is the important middle ground between:
- fully generic chaos
- overly hardcoded system fields

Fields may include optional semantic hints.

Example:
```json
{
  "id": "blk_010",
  "kind": "field",
  "name": "Patient Name",
  "props": {
    "field_type": "text"
  },
  "meta": {
    "semantic_tags": ["patient_name"]
  },
  "children": []
}
```

### Why semantic hints are useful
They help later with:
- search
- record indexing
- print templates
- reporting
- interoperability

### Important rule
Semantic hints must be:
- optional
- editable
- non-blocking

They should not become mandatory hardcoded field kinds.

## Recommended Preset Schema
Presets should use the same block structure as forms.

Example:
```json
{
  "id": "preset_002",
  "name": "Patient Info",
  "category": "Common",
  "schema": {
    "blocks": [
      {
        "id": "blk_a",
        "kind": "field_group",
        "name": "Patient Info",
        "props": {},
        "children": [
          {
            "id": "blk_b",
            "kind": "field",
            "name": "Patient Name",
            "props": { "field_type": "text" },
            "meta": { "semantic_tags": ["patient_name"] },
            "children": []
          }
        ]
      }
    ]
  }
}
```

## Recommended UI Exposure Model
The engine supports many block kinds.
The UI should not expose them all equally.

### Default visible actions
- Add section
- Add field
- Add group
- Add preset
- Duplicate
- Reorder
- Preview
- Save

### Advanced actions
Hide by default:
- Add note
- Add divider
- Add repeater
- Add table
- Add columns
- semantic hints
- validation rules
- advanced metadata

This is the key to keeping the product usable for non-technical users.

## Recommended Builder Creation Flow

### 1. Choose location
Pick:
- root
- existing container
- new container

### 2. Choose starting pattern
Pick:
- blank form
- duplicate existing form
- start from preset

### 3. Build with blocks
Use simple actions first.

### 4. Arrange
Use drag-and-drop only.

### 5. Preview
Preview should stay obvious and easy to access.

### 6. Save
Save as draft, later publish.

## Recommended Phase 1 Storage Approach
For Phase 1, the best tradeoff is:

- relational tables for:
  - library nodes
  - forms
  - form versions
  - presets
  - records

- JSON storage for:
  - form schema
  - preset schema
  - record values

This is much more future-proof than over-normalizing every field into database tables.

## Concrete Recommendation
If a single implementation choice must be made now, choose this:

### Organization
`container | form` tree

### Form definition
single ordered block tree

### Shared/common content
presets, not hardcoded sections

### Saved data
record JSON tied to form version

### UI
simple builder with hidden advanced controls

That is the cleanest exact data model currently recommended for NAIC Medtech.
