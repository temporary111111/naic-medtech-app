# UI/UX Root Redesign Plan

Date: 2026-06-07

## Why This Exists
The current app is functional, but the user review and visual audit show that the UI should not be treated as ordinary polish anymore.

The root issue is not that the app is ugly. The root issue is that too many screens feel like a collection of polished panels instead of a compact clinic operations workstation.

The redesign goal is:
- keep the current working product and data model
- preserve the local-first Windows clinic workflow
- make the UI faster, clearer, denser, and safer for non-technical staff
- stop solving UI issues through one-off page patches

This document supersedes the older assumption that remaining non-print UI work is only bug/polish. The older `UI_RESKIN_PLAN.md` remains useful historical context for the current `Clinical Depth Luxe` styling, but this plan is now the active root UI/UX direction.

Visual audit screenshots were captured in:
- `output/ui-ux-audit/contact-core-light.png`
- `output/ui-ux-audit/contact-admin-light.png`
- `output/ui-ux-audit/contact-dark-mobile.png`

## Product Frame
Treat the app as a clinic operations tool, not as a marketing site and not as a generic admin dashboard.

Primary user:
- medtech staff entering records, completing results, and printing immediately

Secondary user:
- admin managing forms, users, backup safety, clinic identity, and app access

The desired UI feeling is:
- compact
- calm
- clear
- trustworthy
- fast
- professionally clinical

The app may still feel premium, but premium must come from discipline and clarity, not oversized cards, excessive empty space, or decorative atmosphere.

## Core Diagnosis
Current strengths:
- core workflows exist
- records work queue is understandable
- form builder is functional
- print output exists
- authentication, users, clinic profile, backup, and desktop settings are wired
- visual direction is more coherent than the earlier scaffold

Current root problems:
- components are too bulky for repeated clinic work
- light mode has weak contrast in important edit surfaces
- too many surfaces use card/panel treatment even when rows or plain sections would work better
- some screens can produce nested scrolling, where both the page and inner section scroll
- record edit shows too much chrome/status before the actual fields
- builder reads more like a polished settings page than a real editor workspace
- backup/restore/LAN safety is buried inside Settings instead of being elevated as operational safety
- back/return behavior exists but does not feel like a fully designed product navigation model
- modal behavior exists but does not yet feel like one consistent app-wide system
- global navigation may be too compressed for admin responsibilities

## Non-Negotiable UX Rules
1. One screen should have one primary scroll owner.
   - The body should not casually scroll while an inner app area also scrolls.
   - The app shell should own the viewport.
   - The main content area should usually be the scroll owner.
   - Nested scroll is allowed only for deliberate bounded lists, tables, or editor panes.

2. Repeated work must be compact.
   - Records lists, forms lists, users lists, and history search should be dense and scannable.
   - Detail and safety flows may use more space, but only where it reduces risk.

3. The next action must be obvious.
   - Every workflow should make the most likely next action visually primary.
   - Avoid equal-weight action clusters.

4. Status must be explicit.
   - Draft, ready, completed, voided, deleted, and blocked states should be visibly different.
   - A user should not need to infer whether something is safe to edit or print.

5. Cards are not the default layout primitive.
   - Use cards for real objects, such as records, forms, users, and focused modal content.
   - Use sections, rows, split panes, and toolbars for structure.
   - Avoid cards inside cards.

6. Light mode must be operationally clear.
   - Important boundaries need stronger contrast.
   - Inputs, validation, alerts, and status areas should not be pale-on-pale.

7. Modals must become a real system.
   - Use one consistent layout for confirmations, pickers, destructive actions, and safety flows.
   - Dangerous modals need clear consequences and a stable button order.

8. Navigation should match roles.
   - Medtech should mostly live in Records.
   - Admin should see the extra product responsibilities without hiding safety-critical work.

9. Helper text must earn its space.
   - Keep guidance only when it prevents a mistake or explains a non-obvious constraint.
   - Remove descriptive copy from obvious repeated surfaces.

10. Mobile should reach the task quickly.
   - Mobile record entry must expose actual fields earlier.
   - Header, summary, status, and tab chrome must not consume the whole first viewport.

## Information Architecture
Current global nav:
- Records
- Forms (admin)
- Clinic link
- Backup (admin)
- Settings

Recommended target nav:
- Records
- Forms (admin)
- Clinic link
- Backup (admin)
- Settings

Medtech view:
- Records as the main app area
- Clinic link for sharing the app on the same network without needing admin
- account/settings access remains available

Admin view:
- Records for daily work
- Forms for form library and builder
- Clinic link for same-network URL/QR sharing
- Backup for backup, restore, and data-protection readiness
- Settings for account, users, clinic profile, and preferences

Why the old `Safety` concept was split:
- backup and restore are not ordinary preferences
- LAN sharing is useful to all signed-in users, not only admins
- local-first Windows apps need visible operational trust, but one page mixing backup, QR sharing, browser preference, and diagnostics becomes too heavy
- a non-technical admin should know where to check whether the clinic data is safe, so Backup is visible and admin-only
- app behavior settings should live in Settings, not beside day-to-day sharing links

Builder should stay under Forms:
- it is an admin setup tool
- it should not become a first-class global nav peer unless real usage proves admins constantly jump into it

## Shell Redesign Rules
Target shell:
- fixed app frame
- no default body scroll
- smaller global header
- compact brand treatment
- hidden drawer can remain; visible nav labels should stay role-based and not overload one catch-all operations page
- page headers should be shorter and less hero-like
- page actions should be close to the page task

Scroll model:
- app viewport: fixed
- global header: fixed or non-scrolling inside the app frame
- page header: compact and part of the main flow unless the screen is a tool workspace
- main content: primary scroll owner
- bounded inner scroll: only for lists/tables/editor canvases with obvious boundaries

Back/return model:
- from Work draft: return to Work
- from History record: return to the same History search/filter/page
- from Forms builder: return to the form library location
- from Settings subpage: return to the relevant settings area only if the user came from a deeper child screen
- avoid relying on browser back as the intended product navigation

## Component System
Buttons:
- one primary action per scope
- destructive actions use danger treatment, not just another ghost button
- secondary actions should not compete with the primary action
- icon-only buttons are allowed for familiar tool actions, but must have tooltips or accessible labels

Record edit action hierarchy:
- primary: `Complete and print`
- secondary: `Save`
- tertiary: `Complete`
- destructive: `Delete draft`

Rationale:
- the actual clinic workflow is encode, complete, then print immediately
- `Complete and print` should be the fastest and clearest path
- `Complete` alone is still useful but should not be visually dominant

Rows vs cards:
- repeated lists should usually be row-like
- rows may have subtle elevation or grouping, but should not become tall feature cards
- object cards are acceptable when there are few items or when the object needs richer preview

Status chips:
- must be compact and high-contrast
- use consistent labels and colors across records, forms, users, and backup safety

Alerts:
- validation and risk alerts should be clear, not decorative
- warnings should be visually distinct from neutral info blocks
- readiness panels should not consume excessive vertical space

Tabs and segmented controls:
- use tabs for actual peer views
- use segmented controls for filters
- do not make weak pill navigation that looks like status labels

Modals:
- standard modal sizes:
  - confirm
  - picker
  - form
  - destructive/safety
- consistent button order:
  - secondary/cancel on the left
  - primary/confirm on the right
  - destructive confirm visually dangerous
- modals should trap focus and close predictably

Forms:
- reduce field shell bulk
- keep labels readable and close to inputs
- required markers should be visible but not loud
- validation should point to fields and summarize the remaining blockers
- on mobile, fields should start earlier and use less wrapper chrome

## Workflow Targets
### Records Workbench
Goal:
- make `/records` the medtech's fast daily work queue

Target changes:
- compact queue rows
- clearer Work/History local nav
- `New record` obvious but not oversized
- drafts sorted by recency
- truncated drafts expose a clear route to all drafts
- reduce decorative background and large spacing
- preserve fast actions: Continue, View, Delete

### Records History
Goal:
- make completed/draft/voided lookup fast and trustworthy

Target changes:
- search/filter controls read as one compact toolbar
- row density should support scanning many results
- status is clear
- print appears only where appropriate
- return-to-history behavior stays preserved

### Record Entry
Goal:
- make actual form entry visible and fast

Target changes:
- reduce page header height
- compress record summary
- move readiness warning into a tighter status strip or side panel
- show fields earlier, especially on mobile
- make `Complete and print` the main action
- keep Save visible but secondary
- improve light-mode contrast for field boundaries
- refine sticky actions without blocking fields
- ensure direct draft print attempts redirect to edit with a warning

### Record View
Goal:
- make completed results easy to inspect and print

Target changes:
- completed view primary action is `Print`
- draft view primary action is `Continue editing`
- voided view is clearly view-only and not printable through normal action
- summary should be compact and not duplicate too much record metadata

### Print
Goal:
- keep print output document-focused

Target changes:
- do not fold print pages into generic app reskin
- print toolbar can be compact, but printable document must stay patient-facing and clean

### Forms Library
Goal:
- make admin form management readable without feeling like a dashboard

Target changes:
- denser rows for forms/folders
- clear edit/more actions
- stronger location/tree affordance
- reduce bulky open card treatment

### Builder
Goal:
- redesign as a real editor workspace

Recommended builder architecture:
- left pane: form structure/navigation
- center pane: content/canvas/list
- right pane: inspector/properties for selected item
- top command bar: preview, advanced, new, save/status
- persistent dirty/saved state
- compact but accessible controls

Builder can be denser than the rest of the app because it is a power tool.

### Backup And Clinic Access
Goal:
- make data safety obvious for a non-technical admin and same-network sharing easy for all signed-in staff

Move or regroup:
- backup now, latest backup status, external backup status, restore backup, restore warnings, and emergency backup behavior under admin-only `Backup`
- same-network URL, QR preview, full QR page, QR download, and hostname alternate under all-user `Clinic link`
- browser preference, LAN mode, external backup folder, retention count, and technical readiness diagnostics under admin-only `Settings > App preferences`
- update/release readiness if added later

Backup target structure:
- status overview at top
- plain language: `Protected`, `Needs attention`, `Not configured`
- guided actions
- dangerous restore flow behind a strong modal or dedicated step-by-step screen

Clinic link target structure:
- reliable URL first
- QR preview and full QR access
- minimal copy
- no admin diagnostics for ordinary users

### Settings
Goal:
- keep settings focused on identity and preferences

Recommended settings groups:
- My account
- Users and access
- Clinic profile
- App preferences

Backup and restore should stay in Backup, not in ordinary Settings. LAN/app behavior preferences stay in App preferences.

### Auth
Goal:
- fast workstation sign-in

Target changes:
- reduce landing-page feel
- keep request-account available but secondary
- direct sign-in form should dominate
- facts panel can remain only if it helps first-time users

## Implementation Phases
### Phase 0: Spec And Audit Lock
Status: active now.

Deliverables:
- this document
- screenshot references under `output/ui-ux-audit`
- explicit decision that UI/UX root redesign is active work

### Phase 1: Shell And Scroll Model
Fix the foundation first:
- app frame height
- one scroll owner per screen
- smaller global header
- compact page header
- back/return pattern
- nav IA decision for `Safety`

Current status:
- first foundation pass landed on 2026-06-07
- authenticated shell now owns the viewport through a fixed-height app frame
- browser body/document scrolling is disabled on authenticated app screens
- `.app-shell-main` is the normal page scroll owner
- global header and page headers are more compact
- record edit summary/readiness chrome is tighter so fields appear earlier, including mobile
- record edit action hierarchy now makes `Complete and print` the primary action and `Complete` secondary
- visual QA screenshots and scroll metrics were saved under `output/ui-ux-phase1/`

Definition of done:
- no accidental body plus inner double-scroll on main workflows
- records, edit, history, forms, settings, builder still route correctly
- desktop and mobile screenshots confirm the shell no longer dominates the task

### Phase 2: Design System Atoms
Unify:
- spacing scale
- buttons
- inputs
- rows/cards
- status chips
- alerts
- modals
- tabs/segmented controls
- light/dark contrast tokens

Current status:
- first shared atom pass landed on 2026-06-07
- `theme.css` now owns compact shared control variables for buttons, inputs, chips, and modal radius
- primary styling no longer uses a broad `button:not(...)` selector, so special controls such as password toggles, shell icon buttons, modal scrims, and record-picker card buttons are not accidentally promoted to primary buttons
- shared primary/ghost controls now use a 40px default height, calmer shadows, and consistent focus/disabled behavior
- shared inputs/selects now use a 40px field height, 12px field radius, and a smaller focus ring
- textareas remain multiline-sized instead of being collapsed by the compact field rule
- status chips are compacted to a 24px shared chip height with consistent casing and color behavior across records/settings
- record start modal and picker card radii are aligned with the shared modal/control tokens
- public auth, authenticated shell, records, forms library, and settings CSS links were cache-busted to `20260607-ui-root-phase2`
- visual QA screenshots and computed metrics were saved under `output/ui-ux-phase2/`

Definition of done:
- feature CSS files use shared primitives instead of repeatedly inventing local variants
- light mode has clearly stronger operational contrast

### Phase 3: Records Workbench And History
Redesign:
- `/records`
- `/records/history`
- record start modal/picker

Current status:
- first records workbench/history pass landed on 2026-06-07
- `/records` and `/records/history` now use lighter, row-like record surfaces with compact metadata, 12px row radius, and calmer shadows
- history search and status filters now compute to compact 34px filter pills and stay in a tighter lookup toolbar
- the new-record modal and `/records/new` fallback now use the same split picker layout on desktop, with recent forms as a side rail and all forms as the primary searchable list
- mobile work queue keeps one app-shell scroll owner, full-width primary `New record`, and three reachable row actions without horizontal overflow
- records CSS was cache-busted to `20260607-ui-root-phase3`
- visual QA screenshots and computed scroll/style metrics were saved under `output/ui-ux-phase3/`

Definition of done:
- work queue is compact and fast
- history is a proper lookup tool
- no print workflow regression

### Phase 4: Record Entry And View
Redesign:
- `/records/{id}/edit`
- `/records/{id}`
- sticky action dock
- completion/readiness UI

Current status:
- first record entry/view pass landed on 2026-06-07; Phase 3B remains deferred for later
- all records templates now load records CSS with `20260607-ui-root-phase4`
- `/records/{id}/edit` has a compact summary readiness strip instead of the older large pre-field completion checklist, and the record-entry panel is flattened so fields start earlier
- `Complete and print` remains the primary draft action and now sits in a sticky bottom action bar inside the app's real scroll owner; view-page void actions stay static and are not accidentally docked
- `/records/{id}` now shows a compact draft/completed/voided state in the summary, with completed records reading as print-ready and voided records reading as view-only
- long record titles and recorded values now wrap instead of creating horizontal overflow, including extreme patient-name cases
- mobile record entry has tighter page-header actions and a denser summary block, while keeping the sticky `Complete and print` path reachable
- visual QA screenshots and computed scroll/style metrics were saved under `output/ui-ux-phase4/`

Definition of done:
- fields appear earlier
- `Complete and print` is the primary draft completion action
- mobile edit is usable without excessive pre-field chrome
- completed/draft/voided action hierarchy is clear

### Phase 5: Modal System
Standardize:
- new record picker
- delete draft
- void completed record
- unsaved changes
- restore backup
- backup/safety confirmations

Current status:
- first shared authenticated-shell modal foundation landed on 2026-06-07
- `_authenticated_shell.html`, `shell.css`, and `shell.js` now provide a reusable decision modal for authenticated non-print pages through `window.NAICApp.confirm()`
- record `data-confirm` forms now use the shared modal instead of native browser `confirm()`
- `Delete draft` and `Void completed record` now have structured modal copy, safe-cancel focus, danger confirm styling, mobile bottom-sheet layout, and dark-mode destructive styling
- record edit now intercepts internal navigation away from dirty forms and shows the shared unsaved-changes modal; native `beforeunload` remains only for browser tab close/reload because browsers require it
- record view now loads `records.js` too, so the void-confirmation behavior is active there
- visual QA screenshots and computed modal/focus/overflow metrics were saved under `output/ui-ux-phase5a/`
- Phase 5B has now landed too: `shell.js` owns a generic app-wide `[data-confirm]` submit handler, so non-record authenticated forms can use the same modal system without duplicating page-local JavaScript
- `/settings/desktop` backup creation, local backup verification, external backup verification, desktop app settings save, and restore backup now declare explicit modal copy through `data-confirm*` attributes
- restore backup now gets a destructive shared modal after normal required file/RESTORE form validation, with safe cancel focused first and the current typed-confirmation server guard still intact
- visual QA screenshots and computed modal/focus/overflow metrics were saved under `output/ui-ux-phase5b/`

Definition of done:
- all important modal interactions share one visual and behavioral system

### Phase 6: Backup, Clinic Link, And App Preferences IA
Create or reorganize:
- `/backup` as the admin-only protection area
- `/clinic-link` as the all-user same-network share/QR area
- `/settings/desktop` as admin-only app preferences and technical readiness
- compatibility redirects/aliases for older `/safety` routes

Current status:
- Phase 6A/6B were intermediate Safety Center passes and are now superseded by Phase 6C.
- Phase 6C landed on 2026-06-08: the mixed Safety page was split into `Backup`, `Clinic link`, and `Settings > App preferences`.
- Admin drawer now shows Records, Forms, Clinic link, Backup, Settings.
- Medtech drawer now shows Records, Clinic link, Settings.
- `/backup` is admin-only and focuses on backup health, latest local/external backup, create/verify actions, retention readout, and protected restore.
- `/clinic-link` is available to all signed-in users and focuses only on reliable share URL, QR preview, full QR page, download, and hostname alternate. Normal users do not see firewall/browser diagnostics.
- `/settings/desktop` is admin-only and is advertised in Settings as `App preferences`; it owns preferred browser, LAN mode, external backup folder, retention count, and compact readiness diagnostics.
- `/safety` now redirects to `/backup`; old `/safety/...` backup action aliases remain compatible.
- existing backend backup/restore/LAN behavior was preserved; this phase changed IA/routing and page framing, not the backup engine.
- browser QA screenshots were saved under `output/ui-ux-phase6c/`.

Definition of done:
- non-technical admin can understand whether clinic data is protected from Backup
- any signed-in staff member can share the LAN app link/QR without logging in as admin
- restore remains deliberately hard to do accidentally

### Phase 7: Builder Workspace
Refine builder as an editor without restarting the current architecture:
- workspace rail for `Basics`, `Content`, `Signatories`, and `Print`
- recursive content canvas with `Container` and `Field` as the normal primitives
- optional live preview that does not permanently compete with the editing task
- command bar for preview, advanced mode, new/copy, save/status
- responsive compact tabs for smaller screens

Do not implement a permanent heavy inspector pane. Earlier builder experiments showed that a constant right inspector and duplicate content outline make the workspace feel wider and heavier. If deeper properties are needed, keep them inline, collapsed, or contextual.

Current status:
- the current builder already has the core no-rewrite direction in place
- Phase 7B browser QA/polish landed on 2026-06-08 using an isolated temp runtime under `output/ui-ux-phase7b/runtime`
- desktop light/dark builder checks covered Content, field details, Choices, Signatories, expanded signatory controls, Print settings, and generated print preview
- mobile light/dark checks covered the builder command bar, compact workspace tabs, Content cards, and item action menus
- mobile builder command actions are now more compact: view/file actions share a row and the status strip sits below them, reducing the pre-content chrome without changing desktop behavior
- mobile card action menus now open upward and left-aligned from card triggers, preventing the `Copy` / `Remove` menu from clipping off-screen
- save/reload smoke passed in the temp DB by adding a QA-only choice to Blood Bank `Examination`, saving Version 8, reloading, and verifying the persisted input value
- remaining work should be treated as real-user bug/polish from manual review, not a builder architecture restart

Definition of done:
- builder feels like a controlled tool, not a settings page
- non-technical admins can edit a form without understanding schema concepts
- current builder data model and save semantics remain intact

## QA Requirements
Every UI phase should include visual QA screenshots for:
- desktop light
- desktop dark
- mobile light
- at least one narrow viewport where action buttons wrap

Must check:
- no accidental horizontal overflow
- no incoherent text/button overlap
- no body plus inner double-scroll unless intentionally designed
- focus states visible
- primary action obvious
- dangerous action not visually equal to primary action
- light-mode contrast readable
- dark-mode contrast readable
- route behavior unchanged

Use temporary DB copies for visual QA whenever records need to be created or completed.

## Do Not Do
- do not patch individual margins without fixing the layout rule
- do not add more large cards to solve hierarchy
- do not make every section a floating panel
- do not keep adding helper text to compensate for unclear layout
- do not redesign print output as part of generic app chrome
- do not bury backup/restore deeper inside ordinary settings
- do not make `Complete` visually stronger than `Complete and print` in record entry
- do not rely on browser back as the designed return path

## Current Implementation Recommendation
Phase 1, Phase 2, Phase 3A, Phase 4A, Phase 5A, Phase 5B, Phase 6C, and Phase 7B have landed. Phase 6A/6B were intermediate Safety Center passes and should be treated as superseded by the current Backup / Clinic link / App preferences split.

The next highest-value work is manual review or real-world QA, not another speculative UI restructure:
- manual Backup, Clinic link, and App preferences review if the user wants to judge the current IA split in real use
- manual builder review if the user wants to personally judge the Phase 7B browser-verified builder feel before more code
- installed-app, LAN, backup/restore, and print QA on real or clinic-like Windows devices
- keep restore deliberately hard to trigger accidentally
- preserve the existing backup/restore engine unless a validated release requirement demands backend changes
- continue using temporary DB copies for browser visual QA

Do not redesign every remaining page at once. Continue from the browser-verified shell/atom/modal foundation, keep behavior changes minimal unless they improve operational safety directly, preserve the already fixed `Complete and print` priority, and keep validating with temp-DB browser screenshots plus scroll metrics.
