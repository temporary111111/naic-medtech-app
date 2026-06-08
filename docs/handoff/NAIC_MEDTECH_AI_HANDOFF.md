# NDHI Laboratory Records AI Handoff

## Purpose
This document explains the core product concept for the NDHI Laboratory Records app so another AI can continue implementation without re-discovering the domain context.

## Handoff Readiness Snapshot
As of June 6, 2026, the codebase is continuation-ready for another AI if it starts from this document and the focused handoff docs listed below.

Current repo state:
- core records/forms/builder/settings/auth foundations are implemented
- recursive builder concept is implemented in the live app, not just in the standalone replica
- patient-facing browser-print output is implemented through the builder-driven print model
- automated print smoke passes across the current 16 seeded forms; browser PDF page-count QA remains a Windows-side validation task when Playwright dependencies are available
- local-first Windows desktop installer foundation exists and has a current `0.1.4-dev` QR/LAN reliability build
- same-network LAN access defaults on for fresh desktop installs; signed-in users can open `Clinic link` for the reliable same-network URL, full QR page, and downloadable QR code
- the admin-only `Backup` page now exposes local/external verified backups, automatic daily backup status, latest-backup verification, and protected restore with an emergency pre-restore backup; `Settings > App preferences` controls browser preference, LAN mode, external backup folder, and retention count
- root UI/UX redesign planning is now active as of June 7, 2026; read `docs/handoff/UI_UX_ROOT_REDESIGN_PLAN.md` before making UI changes

Still not clinic-release-complete:
- manual installed-app QA on a clean Windows machine
- root UI/UX redesign implementation and visual QA
- real clinic device/browser/printer QA
- real production data QA
- clean-PC restore drill and Windows validation of scheduled/external/pre-update backup behavior
- Authenticode signing before distributing a serious release build

## Project Summary
The client is a clinic/laboratory that needs an internal app to make laboratory operations faster during daily use.

The app has two big functional directions:

1. Input
Staff fills up examination forms inside the app, saves records, and uses structured data instead of manually encoding results into scattered templates.

2. Output
The app should generate patient-facing printable results. The first browser-print and form-version print configuration foundation now exists, and `docs/handoff/PRINT_SYSTEM_HANDOFF.md` is the active print continuation guide. Legacy print templates exist and can be used as visual guidance, but they are not the strict source of truth.

## Most Important Product Decision
The app must not be built as a fixed set of hardcoded forms.

The highest-priority feature is an `Exam/Form Builder` so the client can:
- create new exams/forms
- edit existing exams/forms
- change fields, sections, and options
- avoid paying a programmer for every future form change

This means the product should be treated as a:

`schema-driven laboratory platform with an exam builder`

not as a:

`lab app with hardcoded forms`

Current status snapshot:
- the builder and records foundations have landed
- the recursive builder integration is now browser-audited and stabilized across duplicate-form startup, nested editing, copy/remove, hidden advanced-block ordering, save/reload, light/dark, desktop, tablet, and mobile
- the patient-facing print foundation is implemented and should now be validated against real clinic devices, real records, and real printer settings
- print should continue from the builder-driven `record_identity` and `print_config` model
- a local-first Windows desktop-installer foundation now exists under `tools/desktop/`; continue from `docs/handoff/DESKTOP_INSTALLER_ARCHITECTURE.md`
- the desktop layer intentionally keeps FastAPI as the product core: a launcher starts the local server and opens a browser-powered app window
- fresh desktop installs default to LAN mode so same-network clinic devices can connect with the URL/QR shown in `Clinic link`
- the verified backup foundation now includes local/external backup UI, daily automatic backup while the app is open, admin-only restore with a pre-restore emergency backup, and a source installer pre-update hook, but clean-PC restore drills and Windows upgrade-flow validation are still required before clinic release

## Historical Phase 1 Priority
Phase 1 focused on the `Exam/Form Builder`.

Phase 1 should enable:
- creating an exam/form definition
- editing an exam/form definition
- adding sections
- adding fields
- defining choices/options
- defining normal values and unit hints
- reordering fields
- previewing the resulting form structure
- saving the schema definition

Phase 1 is not primarily about:
- user accounts
- full admin portal
- advanced permissions
- broader reporting modules
- full clinic operations suite

Those can come later, but the architecture should still allow them.

## Small Clinic Product Lock
The client is a **small clinic**, not a large hospital network or enterprise laboratory.

That changes the product strategy in an important way:
- the app should feel professional because it is calm, fast, and reliable
- the app should **not** feel professional by adding enterprise workflow complexity the client does not need
- the daily user is primarily the **medtech**
- the builder is an admin/setup tool, not the center of the daily workflow

Current locked assumption:
- most day-to-day usage should happen in `Records` or data-entry runtime
- most users should not need to touch the builder
- the visible workflow should stay extremely simple and obvious

Do not default to:
- enterprise approval chains
- hospital-style multi-stage review flows
- many visible user-role surfaces
- feature-heavy admin portals just because the architecture can support them

## Recommended Minimal Roles
The current recommended role model for this client is intentionally small:

1. `Admin`
- manages forms
- opens the builder
- manages settings and users
- can still fill up and print records if needed

2. `Medtech`
- opens forms
- fills up records
- uploads images when needed
- saves and prints results

Optional later only:
- `View only` or similar support role if the clinic actually needs it

Important:
- keep the architecture expandable
- keep the **visible product** minimal
- do not design the current app around lab-admin / pathologist / reviewer chains unless the real clinic workflow demands it

## Auth And Settings Foundation Status
The first real auth/settings foundation has now landed.

What exists now:
- first-run setup at `/setup`
- login at `/login`
- account request at `/request-account`
- clinic profile settings at `/settings/clinic`
- personal account settings at `/settings/account`
- password change at `/change-password`
- admin user management at `/settings/users`
- hybrid account flow:
  - staff can request an account
  - admin can approve pending accounts
  - admin can also create accounts manually as a fallback
- login accepts `email or login ID`
- admin-created accounts are forced through a first-login password change
- role gating is active now:
  - `Medtech` stays in records
  - `Admin` can access records, forms, builder, and settings
- clinic profile settings now carry the first branding foundation too:
  - clinic name
  - address
  - contact details
  - upload/remove clinic logo
- personal account settings now carry the first profile foundation too:
  - account identity summary
  - password management
  - upload/remove own profile photo
  - shell account avatar with initials fallback
  - avatar/initial identity inside the admin user directory
  - dedicated admin `Manage user` page for full-name/role correction and password reset

Important:
- this is not the final print system
- it is the branding/settings base that future print templates should read from

Important:
- keep this auth model simple
- do not replace it with public consumer signup
- do not introduce heavy enterprise role hierarchy unless the real clinic workflow demands it
- accountability should continue to rely on immutable internal user ids, while admin-facing management stays readable through full name and email
- do not let ordinary users freely edit login ID or email from the personal account page unless a later admin-reviewed flow is deliberately added

## Locked UI Direction
The product now has a locked visual direction for the next UI work.

Chosen design language:
- `Clinical Depth Luxe`

Active root UI/UX plan:
- `docs/handoff/UI_UX_ROOT_REDESIGN_PLAN.md`

Current June 7, 2026 decision:
- the app should now be treated as a compact clinic operations workbench, not just a reskin needing small polish
- the previous live reskin remains useful style context, but the current requested work is root workflow/layout correction
- priority concerns from the user: compactness, accidental double-scroll, light-mode contrast, better back/return behavior, less bulky components, `Complete and print` as the primary record-entry action, a real modal system, and clear data-protection/LAN access IA
- Phase 1/2 foundation plus Phase 3A records workbench/history, Phase 4A record entry/view, Phase 5A shared modal foundation, Phase 5B safety-form modal application, and Phase 6C Backup / Clinic link / App preferences split are now the baseline; Phase 3B is intentionally deferred and the next UI work should not restart shell/atom/modal analysis without evidence
- first Phase 1 pass has landed: authenticated screens now use a fixed-height app frame with body/document scroll disabled, `.app-shell-main` as the normal scroll owner, compact global/page headers, tighter record-edit summary/readiness chrome, and `Complete and print` as the primary record-entry action. Visual QA outputs are under `output/ui-ux-phase1/`
- first Phase 2 atom pass has landed: shared `theme.css` control tokens now compact primary/ghost buttons, inputs, status chips, and modal radius; the risky broad `button:not(...)` primary selector was removed so password toggles, shell icon buttons, modal scrims, and record-picker cards keep their own treatment; public auth, records, forms library, settings, and shell CSS links were cache-busted to `20260607-ui-root-phase2`. Visual QA outputs and computed scroll/style metrics are under `output/ui-ux-phase2/`
- first Phase 3A records workbench/history pass has landed: `/records` and `/records/history` use lighter row-like record surfaces, compact history search/filter controls, and a split new-record picker shared by the modal and `/records/new` fallback; records CSS was cache-busted to `20260607-ui-root-phase3`. Visual QA outputs and computed scroll/style metrics are under `output/ui-ux-phase3/`
- first Phase 4A record entry/view pass has landed: `/records/{id}/edit` now uses a flatter field-first entry panel, compact summary readiness strip, scoped sticky bottom action bar with `Complete and print` primary, and safer long-text wrapping; `/records/{id}` now shows compact draft/completed/voided state hierarchy and no longer lets view-page void actions inherit the edit dock. Records CSS was cache-busted to `20260607-ui-root-phase4`. Visual QA outputs and computed scroll/style metrics are under `output/ui-ux-phase4/`
- first Phase 5A shared modal foundation has landed: authenticated non-print pages now have a shell-level decision modal exposed as `window.NAICApp.confirm()`, record `data-confirm` forms use it instead of browser `confirm()`, delete draft / void record / dirty internal navigation are covered, and destructive actions focus the safe cancel action first. Shell CSS/JS and records JS were cache-busted to `20260607-ui-root-phase5a*`. Visual QA outputs and modal/focus/overflow metrics are under `output/ui-ux-phase5a/`
- Phase 5B safety-form modal application has landed: `shell.js` now owns a generic app-wide `[data-confirm]` submit handler, `/settings/desktop` backup/verify/settings/restore forms use the shared modal system, restore backup gets a destructive safe-cancel-first modal after normal required file/RESTORE validation, and shell JS is cache-busted to `20260607-ui-root-phase5b`. Visual QA outputs and modal/focus/overflow metrics are under `output/ui-ux-phase5b/`
- Phase 6A/6B Safety Center work was superseded by the Phase 6C IA split: the mixed Safety page was split into admin-only `Backup`, all-user `Clinic link`, and admin `Settings > App preferences`.
- Phase 6C IA split has landed: `/backup` is the visible admin protection area, `/clinic-link` is available to every signed-in user for LAN URL/QR sharing, `/settings/desktop` is the admin app-preferences page, and `/safety` now redirects to `/backup` while old `/safety/...` backup action aliases remain compatible. Browser QA screenshots are under `output/ui-ux-phase6c/`
- Phase 7 Builder Workspace has been recalibrated as a no-rewrite polish/QA phase: do not reintroduce a permanent heavy inspector or duplicate content outline; keep the current recursive `Container`/`Field` canvas, optional preview, workspace rail, and command bar. A small builder polish pass has landed with aligned docs, builder asset cache-bust `20260607-builder-polish`, calmer rail/card density, stronger action-menu stacking, and `Copy` wording for duplicate form.
- App-level View size controls now exist in the authenticated topbar and drawer. This is not browser zoom; it uses a scaled virtual app viewport with a flexible 50%-200% range, 5% steps, localStorage persistence, and Reset back to 100%. Print pages remain separate and should not inherit this comfort scaling.

Current live status:
- the non-print app now has a materially landed live reskin pass under that direction
- the shell architecture is no longer the main UI problem now; the current live correction is at the page-composition level
- records, forms, and settings are now moving toward a content-first composition model instead of a panel-first one
- helper-text density is now also part of the active UI cleanup:
  - obvious screens should scan fast
  - utility bars should not read like onboarding copy
  - guidance should stay only where it prevents mistakes or clarifies non-obvious steps
- dark mode was intentionally pushed first and browser-audited directly against the locked darker sample
- the strongest finished live surfaces right now are:
  - `Records`
  - `Forms`
  - `Settings > Clinic`
  - `Settings > Users`
  - auth screens
  - the current builder shell
- follow-up browser-audited dark-mode cleanup already fixed the most obvious remaining mismatches:
  - weak accent labels and status-chip strength on `/records`
  - `DRAFT` / `COMPLETED` chip color mismatches
  - overly bright `Settings > Users` stat cards in dark mode
  - overly bright builder content/preview panels in dark mode
- quick light-mode audits were also run across the main non-print screens so the first consolidated review should not hit obvious contrast or raw-browser-control regressions
- a deeper UI consistency pass has now landed too:
  - `auth.css`, `library.css`, `new-form.css`, and `app.css` were normalized against the shared theme tokens instead of keeping older hardcoded warm-palette assumptions
  - live browser checks were rerun across `/login`, `/records`, `/forms`, `/forms/new`, `/settings/clinic`, and `/builder`
  - this pass specifically targeted light-mode visibility and cross-mode consistency so page-local cards, inputs, tabs, and builder panels stop drifting away from the shared luxe system
- a further composition pass has now landed too:
  - the app is no longer treating every section like a large premium wrapper panel
  - `/records` now uses compact metrics, a lighter search toolbar, and open content sections instead of a sidebar plus stacked heavy panels
  - `/forms` now uses a lighter browse/search toolbar and open section flow instead of a persistent browse sidebar
  - `/settings/clinic` and `/settings/users` now use lighter local sectioning instead of wrapping every block in large settings panels
  - record, form, and user cards were also tightened to use desktop width better instead of sitting as oversized full-width slabs
- another architecture-improvement pass has now landed too:
  - `/records` now behaves more like a direct work queue: the metric strip is gone, `Work` and `History` now expose clearer local-nav counts, and the draft queue is the first thing the medtech sees
  - `/records/history` now owns search and completed lookup more explicitly instead of leaving those concerns mixed into the default work surface
  - older drafts now have a direct lookup path too: `Work` exposes `View all drafts` when the recent draft list is truncated, and `/records/history?status=draft` shows a proper `Drafts` filter
  - record edit and view now start faster through a compact summary shell plus a calmer collapsible `Record info` area instead of a heavier hero/meta stack
  - `/forms` now keeps primary actions visible while secondary actions live behind lighter `More` menus, and the top-level jump control is no longer always expanded
  - the builder chrome is lighter too: the old feedback bar is gone, draft status now lives in the top app bar, and the technical JSON panel starts hidden until advanced work actually needs it
- the latest compact work-surface pass has now landed too:
  - the builder no longer has a separate stage-head band; preview, advanced mode, status, new, more, and save now live in the command bar
  - `/records` uses denser record cards, bounded queue/history lists, and a searchable form picker for both `New record` modal use and the `/records/new` fallback page
  - `/forms` uses tighter folder/form rows and reduced repeated metadata so it reads more like a calm library than a heavy admin dashboard
  - `/settings/users` is now one searchable/filterable account directory instead of separate pending/active/disabled buckets
  - global `[hidden]` display handling is hardened in `theme.css`, fixing empty-state leaks caused by component display styles
- the Settings IA has now been corrected too:
  - `Settings` is visible to every signed-in user
  - `/settings` now routes to `My account`, where password/security lives
  - admin-only settings remain `Clinic profile` and `Users & access`
  - the drawer footer no longer exposes a `Password` action; it only carries account identity plus `Log out`
  - drawer icons now use one consistent premium-style 24px stroke icon system
- the account/profile foundation has also landed:
  - `Settings > My account` now shows profile photo upload/remove, password management, and read-only account identity
  - the shell account button and drawer identity use the uploaded profile photo when present, with initials fallback
  - `Settings > Users & access` now shows staff avatar/initial identity on account cards
  - each staff card can open a dedicated `Manage user` page for full-name/role correction and admin password reset
  - email/login ID remain read-only in the personal account page for accountability
- print is still intentionally excluded from the reskin; that work must remain template-driven later instead of being folded into this generic theme pass

Chosen mode pair:
- light mode: `artifacts/ui-explorations/records-home-modern-clinical-depth-luxe.html`
- dark mode: `artifacts/ui-explorations/records-home-modern-clinical-depth-luxe-dark-deeper.html`

Important interpretation:
- the client preference is not for generic dashboard minimalism
- the preferred feel is premium, modern, calm, and authored
- dark mode should stay curated and atmospheric, not neon and not pure black
- light and dark should feel like one product, not two unrelated themes

Important implementation rule:
- do not invent a new UI style from scratch when the live reskin starts
- use the chosen standalone exploration pair as the visual north star
- treat those files as reference mood boards and starting implementation guides, not throwaway experiments

Important current boundary:
- the chosen visual direction is locked
- the live app has only started the first shared theme pass; the full page-by-page reskin is still ahead
- this decision should inform future app-shell, records, auth, settings, and later print styling work
- the concrete rollout plan for the live reskin now lives in `docs/handoff/UI_RESKIN_PLAN.md`

Current live UI checkpoint:
- shared non-print theme assets now exist at:
  - `app/naic_builder/static/theme.css`
  - `app/naic_builder/static/theme.js`
- those assets are now wired into builder, auth, records, forms, and settings templates
  - the current theme control is intentionally simple:
    - the authenticated shell now carries the primary light/dark toggle in the top-right global header
    - public auth screens now use the same inline topbar placement too
    - local persistence
    - system-dark fallback on first load
    - no floating lower-left fallback remains in the live app path anymore
- this is only the foundation pass
- the first records-first live reskin pass has now landed too:
  - `app/naic_builder/static/records.css` has been rewritten toward the locked `Clinical Depth Luxe` direction
  - records home, new, edit, and view now carry the stronger premium shell, card, and form treatment first
  - one immediate follow-up pass also fixed the first obvious theme-foundation gap:
    - stronger heading and helper-text contrast in light mode
    - actual select styling for records pages
    - actual field-shell treatment so records no longer feel like the old scaffold with only recolored surfaces
- the current UI priority is now darker-mode fidelity first:
  - the next follow-up pass focused on `Clinical Depth Luxe Darker` specifically
  - records dark mode now has stronger atmospheric shell treatment, darker glass materials, deeper card structure, and less of the old recolored-scaffold feel
  - another follow-up pass also pushed dark-mode typography and button styling closer to the locked darker sample, so the records experience is no longer relying on the old font/button feel
  - a live browser-audited records follow-up then pushed actual structure too:
    - `/records` now groups top-shell utility actions more intentionally and gives search a more authored workspace shape
    - the record-start flow now lives more directly in the records hub instead of depending on a full separate ceremony page
  - light mode should not be the current judging baseline until the darker luxe direction is considered strong enough
  - a broader live pass has now started on the other non-print surfaces too:
    - `library.css`, `auth.css`, and `new-form.css` were pushed into the same luxe family
    - forms library, auth, clinic settings, user settings, and start-new-form now read less like older warm utility scaffolds
    - native file-upload controls were also styled in `theme.css` so clinic/logo/image flows no longer drop back to default browser chrome
  - builder still needs its own deeper surface-specific reskin work after this
- deeper surface-specific reskin work still needs to happen in the rollout order documented in `docs/handoff/UI_RESKIN_PLAN.md`
- the shared authenticated shell foundation has now landed too:
  - shared shell assets now exist at:
    - `app/naic_builder/static/shell.css`
    - `app/naic_builder/static/shell.js`
    - `app/naic_builder/templates/_authenticated_shell.html`
  - authenticated records, forms, settings, and builder screens now sit inside one role-aware product shell
  - the shell now provides:
    - a thin global header with the blurred chrome kept intentionally light
    - a hidden left navigation drawer opened from the top bar instead of a persistent rail or wide sidebar
    - only the real top-level destinations in global navigation: `Records`, `Forms`, and `Settings`
    - page-local headers for title, supporting copy, contextual back links, and page actions
    - a builder workspace variant so the builder stays focused without competing as a global navigation peer
    - a lighter nav treatment too:
      - the helper-copy under each nav item is gone
      - primary nav reads through short labels only
      - the old large texty `Compact` / `Expand` control is gone
  - route-level smoke for the new shell already passed through a real login path and across the main authenticated routes
  - current non-print UI rule going forward:
    - keep the shell
    - avoid reopening nav architecture unless a real workflow problem appears
    - prefer content-first composition, lighter section structure, and cards only for actual objects
    - let builder stay denser than records, forms, and settings
    - keep copy direct:
      - remove helper text from obvious screens and utility strips
      - only keep guidance when it prevents mistakes, explains limits, or clarifies a non-obvious action

## Next Whole-App Milestone
The next major milestone is still the patient-facing print system, but it has now moved from planning into implementation.

Active print handoff:
- `docs/handoff/PRINT_SYSTEM_HANDOFF.md`

Current print direction:
- output should be compact and patient-facing
- target one page when the form content allows it
- use A4 portrait, not the old landscape template shape
- make header/accent color configurable per examination/form
- keep print configuration inside the form builder as a separate `Print` pane/tab
- keep patient info generic and user-configured, not hardcoded by the app
- keep medtech/pathologist generic too: they are configurable signatory slots under `block_schema.meta.signatories`, not ordinary result fields and not hardcoded employee concepts
- use a constrained template/configuration approach instead of a freeform Canva-style editor

Current implementation checkpoint:
- field-level `required` settings are available in the builder
- completion validates builder-marked required fields
- generic record identity config lives at `block_schema.meta.record_identity`
- print config lives at `block_schema.meta.print_config`
- signatory config lives at `block_schema.meta.signatories`
- current forms now have a normal editable `Patient Information` builder group based on the original `default_lab_request` fields, with Name and Case Number marked required and wired as record identity/search hints
- Medical Technologist and Pathologist were removed from normal Patient Information fields and migrated into the generic Signatories pane; current defaults are two medtech slots and one fixed pathologist slot from the source workbook
- the builder `Print` pane now generates a backend-built sample print preview from the current unsaved draft, with an estimated one-page fit signal
- builder preview and `/records/{id}/print` share the same print-page macro and backend print config normalization path
- controlled print options now exist for typography, hiding empty fields, section headings, group headings, image size, and table density
- generic signatory configuration now supports dropdown people, fixed people, fixed stamp images, manual entry, blank lines, required completion, print visibility, signature lines, and license display
- fixed stamp image signatories are generic; use them when the clinic has a full signature/name/license image, but do not hardcode that behavior to Pathologist
- compact result-grid layout now compresses consecutive ordinary scalar fields into a two-column print grid, reducing current long-form estimates to 0 long forms in the automated audit
- Chromium PDF QA confirmed the remaining tight forms OGTT, Semen, and Serology each export as one A4 page after the generic print spacing pass
- clinic-like stress PDF QA confirmed those same tight forms still export as one A4 page with longer names/remarks/signatory-style values
- actual `/records/{id}/print` smoke now passes across all current forms using temporary completed records; the QA script snapshots/restores the runtime DB by default, and real record print pages now show the estimated fit badge too
- browser PDF QA now exists at `tools/scripts/print_pdf_qa.py`; it creates temporary completed records, launches a temporary local server, exports A4 PDFs through Playwright, checks page counts, refreshes artifacts under `output/print-qa/`, and restores the runtime DB by default. Rerun it on Windows for the current 16 forms; WSL currently lacks the Linux system libraries needed by Playwright Chromium
- `/records/{id}/print` now reads form-version print config
- the existing Semen sample was verified as a one-page A4 portrait export

Recommended next product priority:
1. verify clinic-device browser print behavior with real clinic-like values
2. check whether any form needs a per-form override from compact grid back to rows
3. consider section/result accent behavior only if real print review proves it useful

Do not reopen major builder growth now that its core direction is done.
Do not restart print from a blank architecture. Continue from the current builder-driven print config model.

## Records Runtime Foundation Status
The first `Records Runtime` foundation has now landed in the app.

What exists now:
- `/` redirects to `/records`
- `/setup`, `/login`, `/request-account`, `/change-password`, and `/settings/users` now exist as the first auth/settings flow
- `/settings/clinic` now exists as the first clinic identity/branding settings flow
- login now accepts `email or login ID`
- pending account requests, admin approval, and admin manual account creation now all exist in the live app
- admin-created accounts are forced to change password on first login
- auth feedback is steadier now too:
  - pending-account login now says the account is still waiting for admin approval
  - disabled-account login now says admin access is needed again
  - successful password changes now redirect straight back to `Records` with a quiet success banner
- visible role gating is now active for `Admin` and `Medtech`
- clinic profile data and logo upload/remove now exist as the base for future branded output work
- the records module is now split more cleanly by intent:
  - `/records` is the `Work` view for drafts and active entry
  - `/records/history` is the `History` view for completed lookup and search
  - `/records/history?status=draft` is the lookup path for older drafts outside the recent Work queue
  - `/records/history?status=voided` is the audit path for completed records that were voided
  - `/records/history` now paginates 40 records per page and preserves the current search/filter/page when opening records and returning from view, edit, or print
  - History search now auto-submits after a short pause, so users no longer need to press Enter for normal lookup
  - `New record` is now modal-first from those views instead of staying as a separate ceremony page
  - choosing a form creates the draft immediately and redirects straight to `/records/{id}/edit`
  - `/records/new` now stays only as the fallback deep-link picker page
  - the default records experience is now queue-first too:
    - the old metric strip is gone
    - `Work` and `History` now show clearer local-nav counts
    - completed lookup and search live in `History` instead of staying mixed into the default work screen
- `/records/{id}/edit` now supports the first basic record-entry flow
- `/records/{id}` now shows a read-only record view
- records now surface quiet accountability metadata too:
  - who created the record
  - who last updated it
  - when it was last saved or completed
- record completion now has the first trust guards too:
  - drafts remain flexible
  - `Complete` requires the form's required patient identity fields, such as Name and Case Number
  - `Complete` also enforces form-design-required field answers
  - `Complete and print` uses the same validation and then redirects directly to `/records/{id}/print`
  - normal `Print` is completed-only now: draft edit/view no longer expose a generic `Print` action, direct draft `/records/{id}/print` redirects back to edit with a clear warning, and `Complete and print` remains the validated print path while editing a draft
  - the edit screen now shows compact summary readiness when something is missing, instead of a large checklist above the fields
- record cleanup now follows a safety-first lifecycle model:
  - draft records can be soft-deleted through `Delete draft`; this sets status `deleted`, hides the draft from normal work/history lists, and preserves audit data in `indexed_meta.lifecycle.deleted`
  - completed records are not hard-deleted; they can be voided with a required reason, status `voided`, and audit data in `indexed_meta.lifecycle.voided`
  - voided records are view-only and no longer expose normal print actions
  - `/records/history?status=all` includes draft, completed, and voided records, but excludes soft-deleted drafts
- record-entry polish is calmer now too:
  - ordinary draft saves now redirect back with a quiet `Saved the draft.` banner
  - `Sex` now uses the same small standard select in both record create and record edit
  - the image file hint now uses plain ASCII text instead of the old broken separator artifact
- record edit is more self-guiding now too:
  - draft records already show quiet summary readiness while editing
  - if details are still missing, the summary can list what still blocks `Complete`
  - if the draft is ready, the same summary flips into a calm ready-to-complete state
- record edit and view now start faster too:
  - the older heavy record hero/meta stack was replaced by a lighter compact summary shell
  - deeper audit metadata now lives in a calmer collapsible `Record info` area instead of dominating the top of the page
- record forms are safer now too:
  - `edit` now shows a quiet dirty-state label instead of leaving save state implicit
  - internal record navigation away from dirty edits now uses the shared app modal, while browser leave protection still covers tab close/reload
  - `Save draft`, `Complete`, and `Complete and print` now stay available in a sticky bottom action dock scoped to the edit form, with action-specific progress text
  - long record titles and recorded values wrap safely instead of creating horizontal overflow in record view
- record destructive decisions now use the shared shell modal too:
  - `Delete draft` and `Void record` no longer rely on native browser confirm dialogs
  - destructive modals focus the safe cancel action first and keep danger styling in both light and dark mode
- record entry, record view, and print now render utility blocks more honestly too: note text, divider captions, and sample tables no longer fall back to generic placeholder cards
- the record header is more clinic-ready too: new, edit, view, and print resolve generic record identity/search hints from builder fields instead of relying on a hardcoded patient panel
- records are stored separately from forms and point to a frozen `form_version_id`
- the first records API surface now exists:
  - `/api/records/bootstrap`
  - `/api/records`
  - `/api/records/{id}`
  - `/api/records/{id}/complete`

Current intentional limits:
- record entry is still the first calm server-rendered foundation, not the final polished runtime
- image upload now has a first real end-to-end pass in record entry: upload, replace, preview, serve, and remove are wired for image answer fields
- print rendering now has a first real browser-printable pass at `/records/{id}/print`
- record statuses are intentionally minimal right now:
  - `draft`
  - `completed`
  - `deleted` for soft-deleted drafts
  - `voided` for completed records invalidated with an audit reason

What the next AI should continue from here:
- run real clinic-device and real-data print QA before reopening major builder architecture debates
- improve the record-entry runtime only where actual use exposes friction
- refine the new image/file answer flow instead of re-planning it from zero
- preserve the current quiet accountability layer in records instead of replacing it with heavy workflow
- preserve the current draft-versus-complete behavior:
  - drafts should stay forgiving
  - completion should stay trustworthy
- refine record rendering for richer block kinds
- improve the print renderer instead of starting from a blank page
- keep extending records history/search only as needed; the first calm search/filter pass is already landed
- when visual work resumes, align it to the locked `Clinical Depth Luxe` light/dark pair instead of exploring a different style family first
- preserve the current non-print page-behavior rule too:
  - list-heavy pages should use bounded scroll regions instead of unbounded endless pages
  - utility rows should stay light and direct, not read like major hero sections
  - edit and detail pages should stay normal-scroll instead of inheriting nested list containers everywhere

## Builder Direction Note
The current builder foundation is ready for client review. It is not frozen forever, but future changes should respond to concrete real-use findings instead of restarting the architecture.

Before continuing major builder work, read in this order:
- `docs/handoff/FLEXIBLE_BUILDER_FOUNDATION.md`
- `docs/handoff/BUILDER_DATA_MODEL_SPEC.md`
- `docs/handoff/BUILDER_UX_FLOW_SPEC.md`
- `docs/handoff/BUILDER_WIREFRAME_IMPLEMENTATION_PLAN.md`
- `docs/handoff/BUILDER_V2_PLAN.md`

Important:
- `FLEXIBLE_BUILDER_FOUNDATION.md` is the current long-term architecture recommendation
- `BUILDER_DATA_MODEL_SPEC.md` is the current concrete data-model recommendation
- `BUILDER_UX_FLOW_SPEC.md` is the current recommended user experience flow
- `BUILDER_WIREFRAME_IMPLEMENTATION_PLAN.md` is the current screen-by-screen build plan
- `BUILDER_V2_PLAN.md` remains the active short-term UX simplification plan for the current prototype

## Alignment Lock
This section is meant to keep the next AI aligned without re-opening solved debates.

Current locked direction:
- the engine should stay flexible and future-proof
- the visible UX should stay calm and simple for non-technical users
- keep the `container | form` tree direction
- keep the ordered-block direction under the hood
- keep one top-level `Content` editor; do not reintroduce a sibling `Arrange` or `Layout` pane
- do not reintroduce presets into the active user flow right now
- do not add new product surfaces unless they clearly reduce complexity or complete the current core goal

Current honest status:
- the core builder-direction goal is effectively **done**
- the recursive integration stabilization pass is also **done**
- the remaining builder work is confirmed bug/polish work from real use, not another architecture pivot
- the active major gate is real clinic-device and real-data print QA

What the next AI should optimize for:
- keep the current builder as one real content tree, not parallel editing lanes
- make the current builder feel more like arranging content and less like managing schema
- keep simplifying wording, actions, and deeper editor surfaces
- avoid undoing the calmness passes just to expose more power
- preserve the current block-backed migration path instead of restarting from a new architecture idea

## Current Implementation Checkpoint
The first real screen from the newer builder direction now exists.

What is implemented:
- `/` now redirects to `/records`
- `/records`, `/records/{id}/edit`, and `/records/{id}` now exist as the first small-clinic records runtime
- records are now stored separately from form design and point to a frozen `form_version_id`
- the first records API surface now exists:
  - `/api/records/bootstrap`
  - `/api/records`
  - `/api/records/{id}`
  - `/api/records/{id}/complete`
- the current records runtime already supports a basic server-rendered draft/save/complete flow for ordinary scalar fields
- image answer fields now support the first real upload, replace, preview, serve, and remove flow in record entry
- `/records/{id}/print` now exists as the first printable record/result surface, including initial abnormal red-highlighting for numeric and choice fields plus inline image rendering
- the backend now includes a first future-proof library foundation: a persisted generic `container | form` tree
- the compatibility tree is exposed at `/api/library/tree`
- form reads now expose `block_schema` as the active form shape
- `/api/forms/{slug}` now carries the ordered-block view directly via `block_schema`
- live create and update flows now use the block-based `form_schema` contract only
- each form version now also stores a real `block_schema_json` payload alongside the legacy `schema_json`
- startup now backfills missing stored block schemas for older versions
- non-legacy block kinds like `note` and `divider` can now be preserved in stored block schema even when the legacy compatibility projection skips them
- the frontend builder draft is now block-first too: the live editor state no longer keeps a duplicated `draft.schema`, and setup details like `Key` and `Notes` now read and write directly through `block_schema.meta`
- builder saves now go out through `block_schema` instead of posting the legacy `fields + sections` shape directly
- the current focused editor and live preview now also read and write through block-backed paths for real edit flows, not just save-time bridging
- top-level content editing now operates through block-backed collection handling while the visible UI stays calm
- advanced mode now keeps one real `Content` pane for editing the ordered block tree instead of exposing a sibling `Layout` pane
- the live preview now follows the actual root block order, including multiple top-field clusters when top-level fields appear in different positions
- advanced mode can now add real `note`, `divider`, and `table` blocks in the same `Content` flow, including inside sections and groups
- the live preview can now render stored `note` and `divider` blocks while the calmer default panes still stay focused on ordinary fields and sections
- the live preview can now render real `table` blocks too, including nested tables inside sections
- selected sections can now add `note`, `divider`, and `table` blocks too, but only in advanced mode so the normal section flow stays calm by default
- selected groups can now add `note`, `divider`, and `table` blocks in advanced mode too, and the live preview now renders those nested utility blocks from the real block tree
- selected sections and groups now keep nested organizers and focused editors inside the same `Content` flow, so there is no separate child-layout workspace anymore
- when a section contains advanced utility blocks, the default section editor now hides them and shows a small hint instead of exposing extra controls in the standard flow
- richer stored block schema now survives builder hydration correctly, so advanced-only blocks are preserved after normal save/reload flows instead of collapsing back to the legacy projection in the frontend
- `/forms` now renders a dedicated `Form Library` screen
- `/forms` now renders directly from the real persisted `container | form` tree instead of the older one-level grouped library view
- the library can now show both root-level forms and folders in one calm tree-first browse surface
- library search now works against the full folder path text instead of only one-level group labels
- folder cards in `/forms` can now launch folder-scoped creation directly via `New form here` and `New folder here`
- folder cards in `/forms` can now also launch `Edit folder`, so the visible tree flow is no longer create-only
- folder cards in `/forms` can now also launch `Move`, and form cards can now launch `Move` too, so the visible tree flow now supports real relocation as well as browse/create/edit
- the library top bar now also has a direct `New folder` path for root-level folder creation
- `/forms/new` now renders a dedicated guided `Start New Form` screen
- `New Form`, `Open Builder`, and `Duplicate` are all routed from the new library screen
- guided creation now asks for:
  - form name
  - destination folder
  - starting method (`Blank` or `Duplicate Existing Form`)
- preset support has now been deliberately removed from the active product path so the builder can stay focused on the core flow
- builder bootstrap no longer exposes preset data
- advanced editing no longer exposes insert/save preset actions
- guided creation now hands the user off into the current builder with cleaner defaults instead of dropping them straight into `Untitled Form`
- `/forms/new` now uses real container choices from the persisted library tree instead of the older one-level grouped-folder list
- `/forms/new` can now also intentionally place a form at the top level instead of forcing every new form into a folder
- `/forms/new` duplicate choices now use the real tree too, showing full folder paths instead of the older grouped optgroup list
- `/forms/new` can now also create a brand-new folder inside an existing folder, and the first save path resolves that pending nested folder into the real library tree
- `/folders/new` now exists as a small standalone folder-creation screen, so empty folders can be created directly before any forms exist inside them
- `/folders/edit` now gives folders a real management path too: they can be renamed, and they can be deleted once empty
- `/folders/move` and `/forms/move` now exist as calm single-purpose move screens, so folders and forms can change parent location inside the real tree without dropping back to the old one-level group model
- the first save path can now carry a real `library_parent_node_key`, so new drafts can keep their intended container parent without collapsing back to a one-level folder assumption
- the current builder workspace now has a real left outline plus one focused editing context at a time
- the default workspace now lands on a single `Content` pane driven by real root block order, instead of splitting the main flow into separate `Ungrouped fields` and `Sections` panes
- the live top-level builder flow now stays on just `Basics`, `Content`, and `Save`
- the root `Content` pane now inserts new top-level blocks relative to the current selected block when possible, so the main workspace follows real root order instead of old bucket placement rules
- the left outline now follows that same root content model too, showing real top-level content items instead of a section-only shortcut list
- in advanced mode, the root `Content` pane can now add `note`, `divider`, and `table` blocks directly without forcing users into another pane just to place them
- the old `Top of form` language is now reframed as `Free fields`
- `Shared patient info` is no longer a primary always-visible setting in the default form-details surface; it now sits in advanced mode as a default record-details option
- the content pane now uses a compact root organizer plus one focused editor instead of forcing users to switch between separate root buckets
- nested section and group content now also inserts relative to the currently selected child block when possible, so deeper editing follows real ordered block behavior instead of always appending at the end
- selected groups can now add nested groups in the normal flow too, so grouped content is less locked to a field-only structure
- selected groups now use the same compact child organizer plus one focused child editor pattern as selected sections, instead of spilling every child card open at once
- the old separate root `Ungrouped fields` and `Sections` panes are no longer active workspace paths; the builder now uses one real root `Content` path instead of keeping both models alive
- the old root section-only focus path has now been removed from the active builder flow, so the workspace no longer keeps that extra root shortcut model alive behind the scenes
- root and nested `Content` add actions now insert relative to the current selected block when possible, so the true ordered-block surface no longer blindly appends new blocks
- advanced and fallback wording is calmer now too: the builder now prefers `content` and `item` language over more technical `block` wording in the visible UI
- the live preview now also uses calmer root labels like `Top content` instead of the older `Top fields` or `Layout` wording for mixed root content
- repeated add-button clusters are now collapsed into a quieter `Add` menu in `Content`, sections, and groups, so deeper editing feels less like managing buckets and more like inserting content pieces
- focused group cards are lighter too: the dead disabled `Type = Group` row is gone, and the focused spotlight now uses quieter summary copy like `Nested content` instead of repeating mechanical metadata
- focused field cards are lighter too: their focused state no longer repeats the field-type label above the title, their spotlight only shows truly useful metadata, advanced labels like `Normal` and `Unit` are shorter, and multi-cluster preview labels now read `More content` instead of awkward numbering like `Top content 2`
- focused section cards are lighter too: the duplicate `Section` spotlight strip is gone, and deeper editing now stays in the same focused `Content` flow instead of jumping to a separate layout action
- focused field and option editors are flatter too: the extra focused spotlight panels are gone, so those editors now read more like direct content editing and less like schema inspector cards
- preview root clusters now use calmer labels like `Details` and `More details` instead of `Top content`
- focused section, group, and utility cards are flatter too: redundant kind chips and utility spotlights are gone, so those editors now spend less space repeating what the item already is
- organizer rows and the left outline are quieter too: named sections and groups no longer repeat redundant `Section` or `Group` subtitles, while field and utility cues still appear when they actually help with scanning
- field organizers are quieter too: plain text and number fields no longer repeat type subtitles, while higher-signal cues like `Dropdown`, `Date`, `Time`, and utility kinds stay visible for faster scanning
- field input wording is calmer too: the picker now says `Input`, with simpler choices like `Text`, `Choices`, and `Date & time`
- field reference handling is more print-ready too: the live builder now uses `Reference` in the active field UI, numeric fields now use a `Normal range` with `From` / `To`, and choice options can be marked `Counts as normal` for future abnormal highlighting
- the builder can now model `Image` as a real answer type too: the active schema can save image fields cleanly, while the preview stays honest that actual file upload belongs to the future fill-up runtime
- legacy compatibility is preserved too: builder storage now keeps `reference_text` as the active block prop while still projecting it back into legacy `normal_value` where older storage expects it
- the visible field UX stays calm too: the duplicate top `Reference` heading is gone, a tiny hint stays above the inputs, `Normal range` gets one small line for meaning, and choice options stay simple without extra tooltip clutter
- active organizer rows are quieter too: the old `Editing` pills are gone from the outline and nested organizers, so focus now reads through the active highlight instead of extra status chips
- advanced labels and helper copy are calmer too: shorter labels like `Key` and `Notes`, plus tighter Basics/Content/Save help copy, now keep the builder less technical without adding extra clutter
- the old shared `Record defaults` selector is now hidden from the visible builder flow, so setup stays closer to the flexible lego model while backend compatibility remains intact
- the builder left rail is now workspace navigation only: `Basics`, `Content`, `Signatories`, and `Print`; the previous content sub-outline and separate `Save` rail step were removed because they duplicated the focused canvas and added ceremony
- the visible Content model now says `Container` and `Field`; this is a UI bridge over the existing `section` and `field_group` storage so the app stays compatible while users get a simpler mental model
- the Content pane now includes an always-live input-form preview beside the editor on desktop, while the existing full preview panel remains optional; this keeps the user oriented without making preview a permanent third top-level workspace
- root and nested content editing now use a recursive canvas instead of side-by-side organizer/focused-editor columns: containers collapse/expand in place, field name/input edits stay inside each field card, and details/options open inline only when needed
- the guided `/forms/new` flow is less legacy too: it no longer carries old grouping/order hidden fields into the builder, only the tree/location data the current flow actually needs
- the frontend draft logic is less legacy too: new and duplicated drafts no longer depend on old grouping/order fields just to keep the current builder working
- library-tree sync is stronger too: `FormDefinition` location metadata is now backfilled from real library nodes, so page flows rely less on old `group_name/group_kind` fallbacks
- top-level drafts are more stable too: renaming a top-level form now keeps the fallback location state in sync, so the builder no longer shows a stale old location name
- the builder no longer tracks `common_field_set_id` in the active frontend draft path, so the visible editing flow is less tied to the old shared-metadata model
- serialized form responses no longer expose `common_field_set_id` either, so the active API shape is less tied to the old shared-metadata model
- serialized form responses no longer expose `group_name`, `group_kind`, `group_order`, or `form_order`; the live API now exposes only tree-first `location_*` metadata, and the builder reads that location state directly
- the visible builder location helpers now read from `location_*` directly too; the sync helper now just keeps location labels and node keys consistent instead of maintaining old grouped-era shadow metadata
- the active save contract is leaner too: `FormSavePayload` no longer declares `group_name`, and legacy callers are mapped into `location_name` during validation instead of staying as a first-class field
- `FormDefinition.common_field_set_id` is no longer actively mirrored during seed/create flows, and update flows now clear that old mirror field instead of keeping it in sync with the schema
- the active schema/block normalizers are less special too: new create/update/seed flows no longer inject a synthetic `common_field_set_id` into saved `schema_json` or `block_schema_json`, so the hidden shared-record concept is no longer minted into fresh versions by default
- generated legacy schema ids are less location-bound too: new create/update/seed flows now use stable form-based ids like `form.urine` instead of encoding the old folder/group name into the schema id
- the schema seed/reset path is more tree-first too: `ensure_reference_seed()` now creates real container and form nodes first, then backfills legacy location mirrors from those nodes instead of seeding forms through the old grouped-first path
- `ensure_library_tree()` is more tree-first too: it no longer orchestrates sync work in old `group_order/form_order` order, it prefers real node parent/order first, and it now uses the shared form-node/container helpers for rebuilds instead of manually recreating grouped-first state
- direct model-layer placeholder writes are more isolated too: create and seed flows now build `FormDefinition` rows through one small compatibility-shell helper instead of open-coding `group_*` values in multiple places
- stale `FormDefinition.common_field_set_id` values no longer survive active tree sync either: the same compatibility-sync path now clears that old mirror field back to `None`
- the `FormDefinition` model contract is less legacy too: old `group_name`, `group_kind`, `group_order`, and `form_order` columns are now nullable compatibility shadows instead of required first-class fields
- runtime schema migration now upgrades older SQLite DBs to that nullable shape too, so existing local DBs no longer force placeholder writes just to satisfy the old grouped model
- the reset script now follows that same runtime migration path too, so a fresh sample DB no longer regresses back to the old NOT NULL grouped-column shape
- the last-resort tree rebuild fallback is safer too: if a definition loses its node, parent key, and all usable legacy location hints, it now rebuilds as a top-level form instead of inventing a self-named folder from missing legacy data
- stored version metadata is cleaner too: startup/reset backfill now strips stale `common_field_set_id` from old `schema_json` and `block_schema_json`, and it normalizes old `legacy_form_*` block meta into cleaner `form_*` keys with stable `form.<slug>` ids
- the save payload alias path is thinner too: `group_name` is now just a tolerated legacy input alias that gets normalized into `location_name` and removed before validation, instead of lingering as part of the active request shape
- top-level compatibility shadows are more honest too: when a form lives at the root, legacy `group_name`, `group_kind`, and `group_order` are now kept `NULL` instead of being filled with a fake self-named group
- grouped compatibility shadows are thinner too: live tree sync no longer actively maintains legacy `group_kind`; grouped fallback now relies on `group_name` and ordering hints only
- stale self-named top-level shadows are safer too: if an old form still carries a fake self-named `group_name`, rebuild fallback now treats that as top-level instead of recreating a bogus folder
- the stored model shape is thinner too: `FormDefinition.group_kind` is gone from the live SQLAlchemy/runtime DB shape, and older local DBs are rebuilt forward automatically on startup
- the stored model shape is thinner again too: `FormDefinition.common_field_set_id` is gone from the live SQLAlchemy/runtime DB shape now too, and older local DBs are rebuilt forward automatically on startup
- the stored model shape is thinner again too: `FormDefinition.group_order` is gone from the live SQLAlchemy/runtime DB shape, and grouped fallback now preserves existing container order instead of mirroring that old field
- the stored model shape is thinner again too: `FormDefinition.group_name` is gone from the live SQLAlchemy/runtime DB shape, and if a form loses both its real node and parent key, fallback now treats it as top-level instead of trusting old grouped-name shadows
- the stored model shape is thinner again too: `FormDefinition.form_order` is gone from the live SQLAlchemy/runtime DB shape, and rebuild fallback now uses the current version schema order instead of a separate legacy mirror column
- the backend resolver path is thinner too: `ensure_library_tree()` now reads schema order directly instead of going through a leftover legacy location-hint wrapper, and `resolve_form_location_metadata()` no longer returns unused `resolved_parent_name` / `resolved_parent_order` scaffolding
- the live contract is thinner too: save validation no longer maps `group_name` into `location_name`, and `/builder` new-draft startup now reads only `location_name` instead of tolerating old grouped-era query params
- the live save contract is thinner too: the builder now posts `form_schema` directly, and backend validation no longer remaps old `schema` into `form_schema`
- the live save contract is stricter too: `FormSavePayload` now expects the block-based `form_schema` shape in active API usage, so old `fields/sections` save payloads are no longer part of the live builder contract
- the live form-read contract is thinner too: `/api/forms/{slug}` now returns only `block_schema` for the active form shape, and the builder derives any temporary legacy projection locally
- backend naming is more honest too: the no-op save alias validator is gone, and the remaining form-definition helpers in `services.py` now read like tree-first helpers instead of grouped-era compatibility names
- the active create/update path is thinner too: block-based save payloads now normalize directly through a block-first storage helper instead of passing through older schema-bridge wrappers
- the active create/update entry path is thinner too: it no longer materializes a full legacy schema just to derive slug/name before saving; live saves now read those directly from `payload` and block metadata
- active block metadata is cleaner too: new writes now use `form_id`, `form_key`, and `form_order` in `block_schema.meta`, while old `legacy_form_*` keys are only read/backfilled for stored compatibility
- active block source metadata is more honest too: live builder-created block schemas now store `source_kind = builder_blocks_v1`, while true legacy conversions still keep the compatibility marker
- the live backend block-meta path is thinner too: active create/update conversion no longer reads `legacy_form_*` keys, and those old keys are now only part of startup cleanup/backfill logic
- version storage assembly is more honest too: create/update/seed now go through explicit storage builders and one `FormVersion` storage-record helper, so `schema_json` reads more clearly as compatibility storage instead of a parallel live model
- live read and startup cleanup are more explicit too: `serialize_form()` and startup backfill now go through dedicated storage-document loaders, and the startup pass is named around full form-version storage cleanup instead of only `block_schema` backfill
- old `legacy_form_*` block meta is thinner still: startup cleanup now drops those keys without reading them as fallback inputs, and the frontend draft meta sync strips `legacy_form_id` too
- live frontend node helpers are thinner too: core builder helpers now treat blocks as the only active node shape, instead of falling back to old `fields/sections`-style field objects in the live UI path
- live option data is more consistent too: the builder now uses option `name` as the active key end to end, and old `label` values are only normalized away during helper cleanup
- focused section and field cards are thinner too: they now render directly from the passed live block node instead of re-looking up the same path and carrying fallback source juggling
- mixed-content render helpers are more aligned too: the live builder now uses `item`-oriented helper naming for shared section/group/field render paths instead of pretending those helpers are field-only
- active builder selection state is more aligned too: the shared item selection path and item focus/toggle actions now use `item` naming instead of `field` naming in the live JS flow
- internal preview and traversal helpers are more aligned too: shared item-path, item-summary, preview-item, and item-count helpers now read like mixed-content block code instead of field-era helper code
- mixed-content organizer chrome is more aligned too: the live builder now uses `item-*` organizer/list/focus CSS and markup naming instead of `field-*` naming for shared section/group/utility content flows
- shared item-card chrome is more aligned too: the live builder now uses `item-*` card/head/meta/summary/title/focus/basics/input CSS and markup naming instead of `field-*` naming for shared mixed-content cards
- preview segment plumbing is more aligned too: the live preview now groups shared root content under `item` segment naming instead of carrying `fields` as the internal mixed-content segment shape
- live choice seeding is cleaner too: when an input switches to `Choices`, the first seeded option now uses the active `name` shape directly instead of minting the old `label` key
- blank item factories are more honest too: field and group creation now use separate helpers, and shared insertion helpers no longer pretend every mixed content add path is field-only
- input-type internals are more aligned too: the live builder now uses `input`-oriented helper naming for control/data/unit/normal/options/type logic instead of keeping those paths under broader `field` helper names
- active input props are leaner too: the live builder now relies on `control + data_type` instead of minting a duplicate `field_type` mirror in new drafts and edits
- stored block cleanup is leaner too: startup/save cleanup now strips stale `field_type` and old option `label` residue from active block-schema storage
- legacy-to-block option conversion is cleaner too: when older storage is bridged into block schema, options now come out with the active `name` shape directly instead of minting old `label` keys first
- form-version storage assembly is cleaner too: raw live block payloads are normalized before the legacy storage bridge runs, so the live save path no longer depends on fallback reads of stale option `label` keys
- old option `label` residue is thinner in the browser too: legacy `label -> name` cleanup now lives in draft-ingress normalization, while repeated live option helpers read the active `name` shape only
- seed and missing-block fallback storage are cleaner too: both now rebuild block storage through one explicit legacy-storage -> block-storage bridge helper instead of open-coding direct legacy block conversion paths
- form-choice payloads are more location-first too: builder quick-switch reads now prefer `location_path_label` and explicit `form_path_label`, instead of depending on older `path_label/location_label` aliases in the live browser path
- live form-choice payloads are thinner too: `list_form_choices()` no longer emits the old `path_label/location_label` aliases, and active builder/new/move flows now read the explicit location-first keys directly
- live container-choice payloads are thinner too: `list_container_choices()` now exposes explicit `folder_path_label`, and builder/new/move folder flows no longer depend on the old generic `path_label` alias
- browser-side path naming is more explicit too: duplicate form choices now use `data-form-path-label`, and the remaining location helpers distinguish `form_path_label` from `folder_path_label` instead of carrying a generic `pathLabel` pocket
- form create, update, and move flows now use a shared tree-first form-node sync helper, so the real `LibraryNode` state is updated directly before legacy mirrors are backfilled
- `resolve_form_location_metadata()` is more tree-first too: it now feeds create/update with `resolved_parent_*` and `resolved_form_order` values instead of returning `group_*` as the primary active shape
- legacy `group_*` mirror backfill is now centralized too: one helper derives those compatibility fields from the real node state instead of duplicating that logic across create/update/move/tree-sync paths
- top-level new and copied drafts are cleaner too: they no longer start from the old `Unassigned` sentinel or keep a stale previous form name as fake location state
- `/forms/new` root-mode handoff is more explicit too: it now passes `location_name = Top level` into `/builder` instead of using the old form-name placeholder for top-level drafts
- the active browser path is stricter too: the builder no longer treats `location_name === form name` as a top-level shortcut, so top-level handling in the live UI now depends on explicit `Top level` state instead of that old placeholder convention
- the live save resolver matches that now too: backend create/update no longer treats `location_name === form name` as top-level, so same-name locations are resolved as real folders unless `Top level` is sent explicitly
- old `Unassigned` location residue is thinner too: stale inputs are now normalized once at ingress to `Top level`, instead of being special-cased across multiple live location helpers
- the builder frontend reads more tree-first too: active suggestion helpers and setup variables now use `location` language instead of old `group` wording where the UI already treats folders as locations
- the active create/update resolver is more tree-first too: it now derives parent/order state from real library nodes and the current location intent, instead of depending on old `group_kind/group_order/form_order` inputs
- the `/forms/new` flow reads more consistently now too: its template and browser-side logic use `location` wording for the visible create flow, and the handoff into `/builder` now uses `location_name` only
- serialized form payloads are more tree-first too: `serialize_form()` now returns `location_name`, `location_path_label`, `location_node_key`, and `location_kind`, and the builder display/helpers use those aliases directly
- the active save API is more tree-first too: the current builder now posts `location_name`, and the live save contract no longer treats `group_name` as an active alias
- active read compatibility is more tree-first too: legacy `group_*` metadata is now derived from the real library tree during serialization and grouped listings, instead of trusting the raw stored legacy columns
- the visible builder setup flow is more tree-first too: the `Location` input now binds to `location_name` instead of the old `group_name`, while the draft keeps its real location state synchronized directly
- the active builder draft is more tree-first too: `location_*` is now the only active location state in the editor
- the active builder setup internals are thinner too: `Key` and `Notes` now bind straight to `block_schema.meta`, and the live draft no longer keeps a duplicated `draft.schema` object just to drive those fields
- the active organizer/render path is thinner too: content organizers, focused cards, and preview section labels now read directly from block nodes instead of carrying a synthetic legacy `.view` projection through the live builder UI
- the live frontend draft contract is thinner too: the builder no longer accepts a `form_schema` fallback when hydrating local drafts, and now expects `block_schema` directly in the active UI path
- the live frontend block state is more honest too: new drafts and edited drafts now keep `source_kind = builder_blocks_v1` instead of reusing the old compatibility label
- the save payload schema is leaner too: `group_kind`, `group_order`, and `form_order` are no longer part of `FormSavePayload`, and old callers can still send them as ignored compatibility extras
- dead grouped-library backend helpers are gone too: the codebase no longer keeps `list_grouped_forms` / `split_library_groups` around even though the live app is already tree-first
- the old separate `Arrange` pane is gone; `Advanced` now means deeper controls inside the same `Content` editor
- builder action wording is quieter too: `Duplicate` now reads `Copy`, `More` is shorter and calmer than the old `More options`, and destructive actions now prefer `Remove` language for a less tool-like feel
- toggle and preview wording are calmer too: setup/save/section cards now use `Show` and `Hide` instead of `Open` and `Done`, and preview helper copy now says `Choose` or `Show` instead of `Open`
- selected sections/groups are no longer edited through separate compact organizers; they are recursive containers that reveal their children in place
- fields now keep only the common edits visible by default (`Name` and `Input`); required status, reference/unit, normal range, and choice options live in the field details area
- choice fields now render options inline inside field details, with simple `Add option`, `Copy`, `Remove`, and `Normal` controls instead of a separate focused choice editor
- `Form details` and `Save` now use a calmer narrow centered treatment instead of wide full-width surfaces
- `Form details` now offers folder suggestions from the existing library to reduce typing friction
- `Save` now uses a clearer draft-state spotlight (`Ready to save` / `Already saved`) with a simpler optional note field
- the top shell is now more compact: lighter status bar, calmer workspace header, and a tighter preview/advanced control strip
- the live preview panel now reads more like a polished form surface: read-only controls, stronger section grouping, and a clearer preview paper layout
- the preview now includes sticky quick-jump section chips for long forms, with active state so the user can navigate the preview faster
- advanced mode now keeps actual root ordered-block editing inside the same `Content` pane instead of opening a separate lane
- the preview now respects root block order instead of always forcing one single ungrouped-fields area before every section
- the left outline and library wording are now less technical, using calmer labels like `Basics`, `Content`, `Location`, and `Edit`
- the builder basics flow is clearer too: it now says `Name` and `Location`, and top-level forms read as `Top level` instead of the old `Unassigned`
- item editors are calmer too: fields, options, and utility items now use `Name` instead of the more technical `Label`
- the builder `Location` field is now tree-aware too: it suggests real folder paths from the persisted container tree and resolves the correct parent container when one is selected
- the builder quick-switch drawer is tree-aware now too: it searches and lists forms by real folder path instead of the old one-level grouped drawer
- the builder bootstrap path is tree-first now too: quick-switch data comes from `form_choices`, not the old grouped builder payload
- the builder bootstrap payload no longer sends old shared-metadata options either, since that control is no longer part of the visible builder flow
- the current builder save path is less legacy too: it no longer posts old grouping/order fields, and the backend now derives folder/order metadata from the real tree when possible
- the committed sample runtime DB has been reset back to the clean schema-seeded state, and a maintenance script now exists at `tools/scripts/reset_builder_runtime_db.py`
- the focused field editor is now lighter: reorder stays in the organizer above, while the selected field uses a compact basics row and a calmer choice editor
- the focused section editor is now lighter too: reorder stays in the organizer above, while the selected section uses a compact summary strip and a simpler section basics row
- duplicate and delete for selected sections and fields now live in a quieter footer `More` area instead of staying in the header
- the `Sections` pane is now less mechanical: it shows a simple section count, removes organizer row numbers, and marks only the active row as `Editing`

Important reading for the next implementation step:
- treat `/forms` as the new entry surface
- treat `/forms/new` as the new creation surface
- the current builder page is still using the older underlying schema shape, but the workspace shell is now significantly calmer
- the next large build step should continue from the newer flexible builder docs, not from a full V3 reset
- important limitation: the current builder is now partially block-backed, but deeper editing still contains compatibility behavior while the root flow moves toward true ordered blocks
- richer block kinds like `note` and `divider` are currently exposed through advanced `Content` editing, while the legacy compatibility projection remains limited on purpose
- reusable presets are deferred for now because they added cognitive load before the core builder flow was finished

## Current Builder Progress
Current implementation status:
- `Phase 1` shell rebuild is done
- `Phase 2` core editing simplification is in place for the current builder direction
- `Phase 3` drag-and-drop ordering is now implemented
- `Phase 4` safety/usability polish is meaningfully underway

What is already true in the current builder:
- form library is now a collapsible left drawer
- live preview is now a docked side-by-side panel in the workspace on desktop
- live preview is now treated as a first-class builder feature, not just a utility button
- the main canvas focuses on one form at a time
- the left outline can switch between `Form details`, `Free fields`, `Sections`, and `Save`
- form setup collapses by default on existing forms
- top-of-form fields are collapsible
- sections are collapsible
- only one section stays open at a time for calmer editing
- the sections view now keeps a compact organizer list at the top and a single focused section editor below it
- the `Free fields` and selected-section editors now keep a compact item organizer list and one focused item editor at a time
- dropdown `Choices` editors now keep a compact choice organizer list and one focused choice editor at a time
- `Form details` and `Save` now render as narrower, calmer guided sheets inside the focused editor
- the top shell now uses a lighter first-glance hierarchy, with less stacked copy before the main workspace
- the preview panel now behaves as a true read-only preview instead of looking like another editable form
- the preview now has quick-jump section navigation for long forms
- fields now use a calmer `Edit` / `Done` flow instead of exposing every field editor at once
- sections and fields now use a calmer `More` action menu instead of always showing all actions
- the save note is now separated into its own save step card
- sections can be reordered by drag-and-drop
- fields can be reordered by drag-and-drop
- `SortableJS` is now used locally for reliable drag-and-drop ordering
- a floating save/reset dock appears while the draft is dirty
- the builder warns before discarding unsaved changes on form switch or page unload
- clean state now shows a disabled `Saved` button instead of an active save action
- the save step stays collapsed by default until needed
- closed sections and closed fields now render as compact outline rows instead of repeating helper text
- the shell summary updates live while the user edits the form title
- preview control was moved out of the crowded top bar into a dedicated main-flow `Live Preview` callout
- the live preview now stays visible while editing instead of blocking the builder in an overlay
- the preview panel updates live while the user edits builder fields and form titles
- on desktop, the preview panel uses its own internal scroll area so long forms remain fully inspectable without losing the builder view
- the preview hide/show path is now hardened so hiding the panel fully removes it from layout instead of leaving a bottom leak in stacked layouts
- helper text is now reduced and moved into small `?` popovers in the main editing cards
- open help popovers and `More` menus now close when the user clicks elsewhere
- in-app destructive/dirty decisions now use a calmer custom modal instead of browser `confirm()` dialogs
- the floating dirty-state bar is now smaller and less visually aggressive while still keeping save/reset obvious
- the top bar now uses shorter, smaller actions to reduce first-glance weight
- row actions now use quieter icon-like drag and `...` controls instead of heavier text buttons
- drag and `...` controls stay visually subdued until a card is active or hovered
- open section cards now use a compact header row where section title and quick add-actions live together
- the save step now uses a single compact inline row (note input + one save action) to reduce vertical weight
- open field cards now use lighter metadata chrome by default (less repetitive labeling noise)
- `Advanced mode` toggle is now available in the stage header and defaults to `Off`
- when `Advanced mode` is `Off`, technical panels are hidden (`Advanced` blocks + `Technical JSON`) to keep first-time editing focused on core actions

What is still not done:
- final reduction of header and action noise
- deeper visual polish for truly client-ready comfort
- full stabilization and real-use QA

## Current Strategic Recommendation
The strongest future-proof direction currently recommended is:
- organization tree using generic `container | form` nodes
- block-based form schema instead of special zones like `top_of_form`
- generic fields instead of hardcoded domain-specific field concepts
- optional reusable blocks later if they can be reintroduced without hurting simplicity
- versioned records separate from form design
- a small-clinic runtime centered on medtech record entry instead of enterprise workflow choreography

This is documented in:
- `docs/handoff/FLEXIBLE_BUILDER_FOUNDATION.md`
- `docs/handoff/BUILDER_DATA_MODEL_SPEC.md`
- `docs/handoff/BUILDER_UX_FLOW_SPEC.md`
- `docs/handoff/BUILDER_WIREFRAME_IMPLEMENTATION_PLAN.md`

Important:
- the engine should be highly flexible
- the UI should still stay very simple for non-technical users
- visible role complexity should stay minimal unless the real clinic workflow proves otherwise

Current migration status:
- the generic library tree foundation has started in the real backend via a new persisted `library_nodes` table
- current forms are automatically backfilled into that tree for compatibility
- the visible library now runs on the real persisted tree, while the builder still contains compatibility behavior during the ordered-block migration
- the backend now includes a compatibility bridge between the current legacy schema and an ordered-block schema
- current safe bridge coverage is limited to `field`, `field_group`, and `section`
- stored block schemas can now preserve extra block kinds even when the legacy compatibility projection cannot render them directly
- advanced `Content` editing now provides the UI foothold for extra block kinds like `note`, `divider`, and `table`
- the next cleanup milestone should keep reducing the remaining compatibility-only `fields + sections` thinking without reintroducing a separate editing pane

## Source Of Truth
Primary source of truth:
- `artifacts/schema/naic_medtech_app_schema.json`

Derived from:
- `data/source/NAIC MEDTECH SYSTEM DATA.xlsx`

Supporting references:
- `artifacts/schema/naic_medtech_structure.json`
- `artifacts/schema/naic_medtech_tree_diagram.html`

Legacy print/layout guidance only:
- `references/print-templates/*.dotx`

If there is a conflict:
- schema wins for structure and fields
- legacy print templates only guide presentation and print style

## Product Philosophy
The system should be built on strong reusable primitives instead of unlimited freeform layout editing.

Target:
- flexible enough that the client can build most future exams without a programmer
- structured enough that saving, validating, previewing, and printing remain consistent

Avoid trying to support totally arbitrary desktop-publishing behavior in Phase 1.

## Builder Requirements
The builder should support these structural primitives:
- group/category
- form/exam
- section
- field
- field group
- option list
- display order
- normal value
- unit hint
- notes/instructions

Recommended field controls and data types:
- `input/text`
- `input/textarea`
- `input/number`
- `input/date`
- `input/time`
- `input/datetime`
- `select`
- `multi_select`
- `field_group`
- repeatable rows/table, if needed later

The builder should also support:
- duplicating an existing exam/form
- versioning forms so old patient records remain valid
- previewing the data-entry form
- later mapping the same schema to printable output

## Core Technical Direction
The app should have three clearly separated layers:

1. Exam definition
- schema metadata describing the form

2. Data entry rendering
- UI generated from schema

3. Output rendering
- printable result document generated from schema and record data

Do not tightly couple output layout to a single fixed hardcoded screen.

## Current Frontend Note
Current builder implementation is still:
- server-rendered HTML
- vanilla JS
- local `SortableJS`

## Current Builder UX Checkpoint
- Phase 7B browser QA/polish landed on 2026-06-08: builder desktop light/dark, mobile light/dark, Content details/Choices, Signatories, Print settings, generated print preview, and save/reload were checked using a temporary QA runtime under `output/ui-ux-phase7b/runtime`.
- The current live builder is recursive and inline: `Content` uses `Container` and `Field` cards, field details/options open inside the card, and there is no permanent right inspector or duplicate content outline.
- Mobile builder command actions are compacted so `Preview/Advanced` and `New/.../Saved` share one row with the status strip below; mobile card action menus now open upward and left-aligned so `Copy`/`Remove` does not clip off-screen.
- the builder now uses calmer non-technical wording such as `Basics`, `Content`, `Location`, and `Edit`
- the workspace uses `outline + focused editor + live preview`
- the live preview is read-only and uses sticky quick-jump section navigation
- selected sections and fields keep destructive actions in a quieter footer `More options` area
- the `Sections` pane is less mechanical: simple count, no organizer row numbers, only the active section shows `Editing`
- the nested `Choices` organizer now follows the same calmer pattern: no choice row numbers, only the active choice shows `Editing`, and the selected choice uses a smaller spotlight card
- selected choice actions now follow the same quiet pattern too: footer `More`, `Copy`, and a calmer confirmed `Delete` dialog
- the left outline is lighter too: section subitems no longer show per-row counts, and only the active section shows `Editing`
- the top shell is calmer now as well: the status strip is subtler, status messages are shorter, and the live-preview callout uses steadier less repetitive copy
- the top-right app-bar actions are quieter now too: `New` and `Save` stay visible, while `Duplicate` lives inside a small overflow menu
- the preview panel header is quieter now too: shorter heading/copy, shorter hide action, and less repeated live/read-only wording inside the preview card
- the left rail header is quieter too: `This form` became `Outline`, the extra summary line was removed, and the navigation block reads less like a mini dashboard
- the center workspace header is quieter too: `Editing` became `Builder`, the title now uses the form name directly, and the supporting copy is shorter and less repetitive
- the focused section/field/choice strips are quieter too: they now use small label-style cues like `Section`, `Field`, `Group`, and `Choice` instead of sentence-style `Editing this ...` copy
- the top-level outline is quieter too: `Ungrouped fields` and `Sections` no longer show count chips, so the left rail reads more like navigation than a mini manager
- the center and preview chrome are quieter too: the builder header, `Sections` header, and preview surfaces no longer repeat summary count badges
- the center organizer metadata is quieter too: section rows no longer repeat item counts, field rows use simpler type cues like `Dropdown`, and the choices editor no longer repeats choice counts in its header and spotlight
- the preview wording is calmer too: shorter `Show` and `Hide` actions, `Live preview` callout language, and preview copy that reads more like a live companion than a technical sample panel
- the empty-state and no-data copy are warmer too: builder and library messages now guide the user more gently instead of sounding like raw system states
- the save surface is calmer too: `Save draft` is now just `Save`, the finish-step wording is softer, the floating save dock is quieter, and the save card now stays in sync with dirty state while editing the note
- the library page is calmer too: folder jump counts and repeated folder metadata are gone, and form card actions now use shorter labels like `Copy` and `Edit`
- the library cards are lighter too: version labels are subtler (`v1`), card spacing is tighter, and the library now reads more like a calm folder browser than an admin list
- the top of the library page is calmer too: shorter header copy, quieter `Find` search affordance, and a lighter `New` action for a cleaner first glance
- the library header itself is tighter too: spacing is calmer, the top band sits lower visually, and the first impression is less crowded

The repo has not been migrated to Alpine.js. Alpine.js was only a possible helper direction discussed for future UI simplification, not a current dependency.

## Current Backup And Clinic Access UX Checkpoint
- Phase 6C landed on 2026-06-08 and should be treated as the current IA baseline.
- Do not recombine Backup, Clinic link, and App preferences into one broad Safety page unless the user explicitly asks for that direction again.
- `/backup` is admin-only and should stay focused on protection: backup health, latest local/external backup, create/verify actions, retention readout, and protected restore.
- `/clinic-link` is available to every signed-in user and should stay lightweight: reliable share URL, QR preview, full QR page, QR download, and hostname alternate. Do not expose firewall/browser diagnostics to normal users.
- `/settings/desktop` is admin-only and owns app preferences: preferred browser, LAN mode, external backup folder, retention count, and compact readiness diagnostics.
- `/safety` is now only a compatibility redirect to `/backup`; old `/safety/...` backup action aliases remain so stale pages/forms do not break.
- Restore must remain visually and operationally protected with typed `RESTORE`, server guard, and destructive modal.
- Browser QA used a temp runtime copy under `output/ui-ux-phase6c/runtime-20260608-ia-split`; screenshots include admin Backup, Clinic link, App preferences, full QR, dark/mobile states, and medtech drawer/access checks.

## Current Domain Structure
Client-approved current groups:
- Clinical Microscopy
- Blood Chemistry
- Serology
- Blood Bank
- Blood Gas Analysis
- Hematology
- Microbiology

Current important rule:
- `COVID 19 Antigen (Rapid Test)` belongs under `Serology`

## Current Important Schema Decisions
These decisions already exist in the current schema and should not be casually undone:

1. Shared patient/request metadata still exists as a backend compatibility field set, but it is intentionally hidden from the visible builder flow.
Included examples:
- Name
- Age
- Sex
- Date / Date-Time
- Requesting Physician
- Room
- Case Number
- Medical Technologist
- Pathologist

2. `Blood Bank > Type of Crossmatching > VITAL SIGNS` is normalized as a `field_group`, not a select field.
Its child fields are:
- BLOOD PRESSURE
- PULSE RATE
- RESPIRATORY RATE
- TEMPERATURE

3. In `Blood Chemistry > Male` and `Blood Chemistry > Female`, `IONIZED CALCIUM` must come immediately after `CHLORIDE`.

4. Standalone departments in raw extraction are normalized consistently in the app schema.

## Print Output Guidance
The `references/print-templates` folder contains `.dotx` templates that show the clinic's current print style.

Observed recurring print pattern:
- clinic branding/header
- patient info block
- exam title or department title
- result table or structured result sections
- medtech/pathologist footer
- distinct header/accent colors per examination

These templates are useful for:
- understanding print tone
- understanding result-document hierarchy
- guiding future print output styling

They are not the strict implementation source.

Important product clarifications:
- do not copy the old landscape layout
- do not hardcode a patient-info zone into the engine
- do not assume the app knows the clinic's workflow semantics
- keep patient-info as a normal editable builder-owned section; current forms already start from the original default lab-request fields
- keep print settings configurable per form version through the builder `Print` pane

The detailed print handoff is in:
- `docs/handoff/PRINT_SYSTEM_HANDOFF.md`

## Known Conservative Areas
Some fields in the schema were intentionally left conservative because the workbook did not give enough reliable signal to force a stricter type.

Examples include:
- `TOTAL VOLUME`
- `LIQUEFACTION TIME`
- several `OTHERS` fields
- some Blood Bank phase result fields
- `NOTE` text areas

These should be treated as safe defaults, not as final product truth.

## What Another AI Should Do First
When continuing implementation, the next AI should:

1. Read this file first.
2. Read `docs/handoff/NAIC_MEDTECH_AI_CONTEXT.json`.
3. Read `docs/handoff/PRINT_SYSTEM_HANDOFF.md` for print state and rules.
4. Read `docs/handoff/DESKTOP_INSTALLER_ARCHITECTURE.md` before touching installer, LAN, browser, or backup behavior.
5. Skim `docs/handoff/BUILDER_V2_PLAN.md` and `docs/handoff/FLEXIBLE_BUILDER_FOUNDATION.md` before changing builder architecture; do not restart the builder unless real clinic use exposes a concrete blocker.
6. Treat the app as schema-driven and form-version-driven.
7. Continue the existing builder-driven print config model.
8. Avoid hardcoding individual lab forms, patient-info zones, signatory roles, or old template layouts.

## What Another AI Should Avoid
- Do not build one screen per exam.
- Do not treat legacy `.dotx` templates as the source of truth.
- Do not copy the old landscape print layout.
- Do not hardcode patient-info fields or zones; keep them user-configurable.
- Do not make the first version depend on programmer-only form changes.
- Do not assume accounts/admin features are the current main milestone.

## Ideal Phase 1 Outcome
By the end of Phase 1, the client should be able to:
- define or edit an exam/form without developer help
- preview the resulting structure
- preserve logical sections and field order
- keep the system ready for future patient-result entry and printable outputs
