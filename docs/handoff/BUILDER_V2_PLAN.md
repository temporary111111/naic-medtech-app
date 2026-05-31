# Builder V2 Plan

## Why This Exists
The current builder prototype is functional but still feels like a schema editor.

That is not enough for the real client.

The builder must be comfortable for people who are:
- non-technical
- busy
- under pressure
- easily overwhelmed by too much on screen

Builder V2 exists to reduce mental load first, then improve power and speed second.

## Current Landed Bridge
The live builder has started applying the lab direction without rewriting storage:
- left rail is workspace-only: `Basics`, `Content`, `Signatories`, `Print`
- `Save` stays in the command bar/save dock instead of acting like another builder workspace
- Content shows `Container` and `Field` as the normal primitives
- internal `section` and `field_group` storage remains for compatibility
- Content has an always-live input-form preview on desktop, while full preview remains optional
- Content now uses a recursive canvas instead of organizer/focused-editor columns: containers collapse/expand in place, fields edit inside their own cards, and field details/options open inline only when needed
- browser QA now covers duplicate-form startup, recursive container/field editing, choice options, numeric ranges, subtree copy/remove, mixed advanced blocks, save/reload persistence, light/dark modes, and desktop/tablet/mobile layouts
- copied block subtrees now receive fresh recursive block and option IDs, preventing duplicated record-field identities
- SortableJS ordering now maps visible cards back to their real collection positions, so hidden advanced blocks do not corrupt reorder results
- tablet/mobile workspace navigation now stays above the editor as compact tabs instead of becoming a tall vertical panel or falling below a long form

## Product Problem
The clinic needs a form/exam builder so they can change exams without hiring a programmer every time.

But if the builder itself feels technical or stressful, the feature fails.

The product goal is not:
- "show the full schema clearly"

The product goal is:
- "make creating and editing forms feel calm, obvious, and safe"

## Primary User
Primary user for the builder:
- clinic owner
- admin staff
- trusted back-office person

This user is likely:
- familiar with the exam names
- not familiar with schema concepts
- more comfortable with forms than technical settings

The builder must assume:
- they do not want to think about JSON
- they do not want to think about keys/ids/order indexes
- they want visible actions and immediate results

## Core UX Principles
1. One main task at a time.
2. Show only the settings needed right now.
3. Hide technical metadata by default.
4. Prefer direct manipulation over typed configuration.
5. Prefer duplication over building from zero.
6. Keep the preview easy to access, but not always competing for space.
7. Make destructive actions feel safe.

## What Must Be Removed From Primary UI
These should not appear in the main flow:
- internal form key
- internal section key
- internal field key
- group order
- form order
- raw JSON
- schema-first wording
- overexposed notes fields

These can still exist:
- inside collapsed `Advanced` panels
- in developer-only or support-only tools

## Builder V2 Screen Structure
The builder should not be a permanent three-column layout.

### Default layout
- top header
- left side: collapsible form library drawer
- center: main builder canvas
- right side: hidden by default

### Preview behavior
Preview should be:
- toggleable
- slide-over panel or drawer on desktop
- optional, not permanently visible

### Library behavior
The form library should be:
- searchable
- collapsible
- quick to open
- not always consuming equal visual weight as the editor

## Builder V2 Main Flow
The builder should feel step-based even if it is on one page.

### Step 1: Setup
Show only:
- form title
- category / department
- duplicate from existing form
- shared patient info set

### Step 2: Build
Show:
- sections
- fields
- field groups
- answer type
- options for dropdown fields

### Step 3: Preview
Show:
- what the actual data-entry form will roughly look like

### Step 4: Save
Show:
- version note
- save action

## Builder V2 Interaction Rules

### Ordering
Ordering must be direct manipulation.

Use:
- drag-and-drop for forms in the library
- drag-and-drop for sections
- drag-and-drop for fields

Do not use:
- manual order number inputs

### Duplication
Duplication should be first-class:
- duplicate form
- duplicate section
- duplicate field

This is important because most real clinic changes are edits of existing forms, not blank-slate creation.

### Adding options
Dropdown choices must stay extremely easy.

The current direction is good:
- add choice button
- simple list of choices
- easy delete

Keep this pattern.

### Advanced settings
Advanced settings must be collapsed by default.

Examples:
- internal keys
- notes
- low-level schema metadata
- unusual configuration not needed every day

## Visual Direction
The builder should feel calm, not dense.

### Use stronger visual hierarchy
- form card
- section card
- field card

Each level should be visually distinct.

### Reduce simultaneous information
- fewer panels open at once
- shorter helper text
- less repeated button noise

### Use color deliberately
- one clear accent color for primary actions
- one warm/supporting color for secondary emphasis
- one muted system for metadata and hints

Color should separate:
- library
- builder content
- preview

But should not make the UI loud.

## Technical Direction Decision
Backend remains:
- `FastAPI`
- `SQLite`

Frontend decision for Builder V2:
- keep server-rendered HTML
- use minimal helper libraries for the interactive builder

Recommended:
- `Alpine.js`
- `SortableJS`

Reason:
- simpler than React/Vue
- easier than pure vanilla for dynamic nested UI
- still readable for the current owner/developer
- easier for another AI to continue safely
- much better fit for drag-and-drop and guided stateful forms

Do not move to a full SPA framework unless there is a strong later reason.

## Builder V2 Phases

### Phase 0: Lock UX and architecture
Deliverables:
- this plan
- final screen structure
- frontend helper-library decision

No major UI implementation should happen before this phase is clear.

### Phase 1: Rebuild the shell
Goal:
- replace the heavy three-column layout

Deliverables:
- top header
- collapsible form library
- single main builder canvas
- preview drawer/toggle shell

### Phase 2: Rebuild core editing flow
Goal:
- make setup and field editing feel simple

Deliverables:
- setup step
- section cards
- field cards
- grouped-field cards
- easy options editor
- hidden advanced settings

### Phase 3: Add direct manipulation
Goal:
- remove typed ordering

Deliverables:
- drag-and-drop sections
- drag-and-drop fields
- drag-and-drop form ordering where needed

### Phase 4: Make it safe and pleasant
Goal:
- polish real use

Deliverables:
- clear save states
- duplicate actions
- delete confirmations
- better empty states
- better visual hierarchy

### Phase 5: Stabilize for real use
Goal:
- make Builder V2 a trustworthy foundation

Deliverables:
- consistent save/version behavior
- regression checks against schema structure
- clean docs for future AI continuation

## Acceptance Criteria For Builder V2
The builder passes when these feel true:

1. A non-technical admin can create a new simple form without explanation.
2. A user does not need to understand internal keys or ordering numbers.
3. A user can duplicate an existing form and safely edit it.
4. A user can reorder sections and fields without typing numbers.
5. The preview is easy to access but does not compete with the main task.
6. The page does not feel heavy on first load.
7. Another AI can continue the codebase without rediscovering the product direction.

## Current Builder Status
The non-print builder foundation is now stabilized enough for real client review:
- schema-driven and block-backed
- versioned save flow
- recursive container/field editing
- inline options and numeric-range editing
- live input preview
- direct manipulation through SortableJS
- safe subtree copy/remove behavior
- compact responsive pane navigation

## Rules For The Next Implementation Pass
Do not restart the builder architecture unless real clinic use exposes a concrete blocker.

Next priority:
- real clinic-device and real-data print QA
- builder bug fixes only when confirmed through actual use
- preserve the calm recursive canvas and keep technical metadata behind `Advanced`
