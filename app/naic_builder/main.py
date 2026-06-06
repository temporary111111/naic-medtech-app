from __future__ import annotations

import asyncio
import mimetypes
import tempfile
import threading
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .backup import (
    BackupOperationBusyError,
    backup_operation_lock,
    copy_backup_archive_to_destination,
    backup_health_summary,
    create_verified_backup,
    external_backup_status,
    local_backup_status,
    prune_backup_archives,
    restore_verified_backup,
    verify_latest_backup_archive,
    verify_latest_external_backup_archive,
)
from .backup_schedule import backup_schedule_summary, scheduled_backup_loop
from .config import APP_TITLE, PRODUCT_ID, SESSION_SECRET, SIGNATORY_UPLOADS_DIR, STATIC_DIR, TEMPLATES_DIR
from .database import SessionLocal, ensure_runtime_schema, get_session
from .desktop_settings import (
    BROWSER_PREFERENCE_OPTIONS,
    NETWORK_MODE_OPTIONS,
    detect_desktop_browsers,
    desktop_runtime_status,
    lan_access_details,
    read_desktop_settings,
    save_desktop_settings,
)
from .qr import qr_svg_bytes
from .schemas import (
    AccountRequestPayload,
    ClinicProfilePayload,
    FormSavePayload,
    LoginPayload,
    PasswordChangePayload,
    PrintPreviewPayload,
    RecordCreatePayload,
    RecordUpdatePayload,
    SetupAdminPayload,
    UserCreatePayload,
)
from .services import (
    authenticate_user,
    build_form_print_preview_document,
    build_record_print_document,
    change_user_password,
    count_records,
    count_users,
    complete_record,
    create_initial_admin,
    create_container,
    delete_container,
    get_clinic_profile,
    delete_record_asset,
    create_form,
    create_record,
    create_user_account,
    current_record_values,
    ensure_default_patient_info_fields,
    ensure_form_version_storage_documents,
    ensure_library_tree,
    ensure_reference_seed,
    get_user_or_none,
    get_form_or_none,
    get_container_or_none,
    get_record_or_none,
    has_any_users,
    list_container_choices,
    list_form_choices,
    list_library_tree,
    list_record_completion_issues,
    list_records,
    list_users,
    list_move_target_choices,
    move_container,
    move_form,
    request_account,
    RecordCompletionValidationError,
    remove_clinic_logo,
    remove_user_avatar,
    reset_user_password_by_admin,
    rename_container,
    serialize_user,
    serialize_record,
    serialize_form,
    serialize_form_location,
    save_clinic_profile,
    save_signatory_stamp_image,
    save_user_avatar,
    store_record_image_asset,
    update_user_admin_details,
    update_user_status,
    approve_user_account,
    update_record,
    update_form,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_runtime_schema()
    with SessionLocal() as session:
        ensure_reference_seed(session)
        ensure_form_version_storage_documents(session)
        ensure_default_patient_info_fields(session)
        ensure_library_tree(session)
    backup_stop_event = asyncio.Event()
    backup_task = asyncio.create_task(scheduled_backup_loop(backup_stop_event))
    try:
        yield
    finally:
        backup_stop_event.set()
        with suppress(asyncio.CancelledError):
            await backup_task


app = FastAPI(title=APP_TITLE, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


PUBLIC_PATHS = {
    "/api/health",
    "/login",
    "/logout",
    "/request-account",
    "/setup",
    "/change-password",
}
PUBLIC_PREFIXES = ("/static",)
ADMIN_PREFIXES = ("/forms", "/folders", "/builder", "/api/forms", "/api/builder", "/api/library")
ADMIN_SETTINGS_PREFIXES = ("/settings/users", "/settings/desktop")
RESTORE_CONFIRMATION_TEXT = "RESTORE"
_RESTORE_MAINTENANCE_LOCK = threading.Lock()
_RESTORE_MAINTENANCE_ACTIVE = False


def redirect_for_html(path: str) -> RedirectResponse:
    return RedirectResponse(url=path, status_code=303)


def auth_error_response(path: str, status_code: int, detail: str, redirect_path: str) -> JSONResponse | RedirectResponse:
    if path.startswith("/api/"):
        return JSONResponse(status_code=status_code, content={"detail": detail})
    return redirect_for_html(redirect_path)


def restore_maintenance_active() -> bool:
    with _RESTORE_MAINTENANCE_LOCK:
        return _RESTORE_MAINTENANCE_ACTIVE


def begin_restore_maintenance() -> bool:
    global _RESTORE_MAINTENANCE_ACTIVE
    with _RESTORE_MAINTENANCE_LOCK:
        if _RESTORE_MAINTENANCE_ACTIVE:
            return False
        _RESTORE_MAINTENANCE_ACTIVE = True
        return True


def end_restore_maintenance() -> None:
    global _RESTORE_MAINTENANCE_ACTIVE
    with _RESTORE_MAINTENANCE_LOCK:
        _RESTORE_MAINTENANCE_ACTIVE = False


def restore_maintenance_response(path: str) -> JSONResponse | HTMLResponse:
    message = "Backup restore is in progress. Wait for the admin restore step to finish, then reopen the app."
    if path.startswith("/api/"):
        return JSONResponse(status_code=503, content={"detail": message})
    return HTMLResponse(
        status_code=503,
        content=(
            "<!doctype html><title>Restore in progress</title>"
            "<main style='font-family:Segoe UI,Arial,sans-serif;max-width:680px;margin:12vh auto;padding:24px'>"
            "<h1>Restore in progress</h1>"
            f"<p>{message}</p>"
            "</main>"
        ),
    )


class AuthFlowMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            return await call_next(request)
        if path == "/api/health":
            return await call_next(request)
        if restore_maintenance_active():
            return restore_maintenance_response(path)

        with SessionLocal() as session:
            user_present = has_any_users(session)
            session_user = None
            clinic_profile = get_clinic_profile(session) if user_present else {}
            raw_user_id = request.session.get("user_id")
            if raw_user_id not in (None, ""):
                try:
                    session_user = get_user_or_none(session, int(raw_user_id))
                except (TypeError, ValueError):
                    session_user = None
            if session_user is not None and session_user.status != "active":
                request.session.pop("user_id", None)
                session_user = None

            request.state.current_user = serialize_user(session_user) if session_user is not None else None
            request.state.has_users = user_present
            request.state.is_admin = bool(session_user is not None and session_user.role == "admin")
            request.state.clinic_profile = clinic_profile

            if not user_present:
                if path == "/setup":
                    return await call_next(request)
                return auth_error_response(path, 503, "Initial setup is required.", "/setup")

            if session_user is None:
                if path in PUBLIC_PATHS:
                    return await call_next(request)
                return auth_error_response(path, 401, "Login required.", "/login")

            password_change_allowed_path = path in {"/change-password", "/logout", "/api/health"}
            password_change_allowed_path = password_change_allowed_path or (
                request.method == "GET" and path == "/settings/account/avatar"
            )
            if session_user.must_change_password and not password_change_allowed_path:
                return auth_error_response(
                    path,
                    403,
                    "Password change required.",
                    "/change-password",
                )

            if path == "/login" and request.query_params.get("restored") == "1":
                request.session.clear()
                request.state.current_user = None
                request.state.is_admin = False
                return await call_next(request)

            if path in {"/login", "/request-account", "/setup"}:
                return redirect_for_html("/records")

            admin_settings_path = any(path.startswith(prefix) for prefix in ADMIN_SETTINGS_PREFIXES)
            admin_settings_path = admin_settings_path or (
                path.startswith("/settings/clinic") and path != "/settings/clinic/logo"
            )
            if (any(path.startswith(prefix) for prefix in ADMIN_PREFIXES) or admin_settings_path) and session_user.role != "admin":
                return auth_error_response(path, 403, "Admin access required.", "/records")

        return await call_next(request)


app.add_middleware(AuthFlowMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax")


def render_builder_page(
    request: Request,
    *,
    initial_form_slug: str = "",
    initial_builder_mode: str = "",
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_title": APP_TITLE,
            "initial_form_slug": initial_form_slug,
            "initial_builder_mode": initial_builder_mode,
        },
    )


def current_user_id(request: Request) -> int | None:
    current_user = getattr(request.state, "current_user", None) or {}
    raw_user_id = current_user.get("id")
    return int(raw_user_id) if raw_user_id not in (None, "") else None


def render_login_page(
    request: Request,
    *,
    identifier: str = "",
    error_message: str = "",
    success_message: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "app_title": APP_TITLE,
            "identifier": identifier,
            "error_message": error_message,
            "success_message": success_message,
            "needs_setup": not getattr(request.state, "has_users", True),
        },
        status_code=status_code,
    )


def render_request_account_page(
    request: Request,
    *,
    full_name: str = "",
    email: str = "",
    login_id: str = "",
    error_message: str = "",
    success_message: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="auth/request_account.html",
        context={
            "app_title": APP_TITLE,
            "full_name": full_name,
            "email": email,
            "login_id": login_id,
            "error_message": error_message,
            "success_message": success_message,
        },
        status_code=status_code,
    )


def render_setup_page(
    request: Request,
    *,
    full_name: str = "",
    email: str = "",
    login_id: str = "",
    error_message: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="auth/setup.html",
        context={
            "app_title": APP_TITLE,
            "full_name": full_name,
            "email": email,
            "login_id": login_id,
            "error_message": error_message,
        },
        status_code=status_code,
    )


def render_change_password_page(
    request: Request,
    *,
    error_message: str = "",
    success_message: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="auth/change_password.html",
        context={
            "app_title": APP_TITLE,
            "error_message": error_message,
            "success_message": success_message,
        },
        status_code=status_code,
    )


def render_settings_clinic_page(
    request: Request,
    session: Session,
    *,
    profile_override: dict[str, Any] | None = None,
    error_message: str = "",
    success_message: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    clinic_profile = profile_override or get_clinic_profile(session)
    return templates.TemplateResponse(
        request=request,
        name="settings/clinic.html",
        context={
            "app_title": APP_TITLE,
            "clinic_profile": clinic_profile,
            "clinic_logo_url": "/settings/clinic/logo" if clinic_profile.get("has_logo") else "",
            "error_message": error_message,
            "success_message": success_message,
        },
        status_code=status_code,
    )


def render_settings_users_page(
    request: Request,
    session: Session,
    *,
    error_message: str = "",
    success_message: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="settings/users.html",
        context={
            "app_title": APP_TITLE,
            "pending_users": list_users(session, status="pending"),
            "active_users": list_users(session, status="active"),
            "disabled_users": list_users(session, status="disabled"),
            "pending_count": count_users(session, status="pending"),
            "active_count": count_users(session, status="active"),
            "disabled_count": count_users(session, status="disabled"),
            "error_message": error_message,
            "success_message": success_message,
        },
        status_code=status_code,
    )


def render_settings_desktop_page(
    request: Request,
    *,
    settings_override: dict[str, str] | None = None,
    error_message: str = "",
    success_message: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    desktop_settings = settings_override or read_desktop_settings()
    backup_status = local_backup_status()
    external_status = external_backup_status(desktop_settings.get("external_backup_dir"))
    return templates.TemplateResponse(
        request=request,
        name="settings/desktop.html",
        context={
            "app_title": APP_TITLE,
            "desktop_settings": desktop_settings,
            "browser_options": BROWSER_PREFERENCE_OPTIONS,
            "network_options": NETWORK_MODE_OPTIONS,
            "browser_status": detect_desktop_browsers(),
            "lan_access": lan_access_details(),
            "desktop_status": desktop_runtime_status(desktop_settings),
            "backup_status": backup_status,
            "external_backup_status": external_status,
            "backup_health": backup_health_summary(backup_status, external_status),
            "backup_schedule": backup_schedule_summary(local_status=backup_status),
            "restore_confirmation_text": RESTORE_CONFIRMATION_TEXT,
            "error_message": error_message,
            "success_message": success_message,
        },
        status_code=status_code,
    )


def render_new_user_page(
    request: Request,
    *,
    full_name: str = "",
    email: str = "",
    login_id: str = "",
    role: str = "medtech",
    error_message: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="settings/new_user.html",
        context={
            "app_title": APP_TITLE,
            "full_name": full_name,
            "email": email,
            "login_id": login_id,
            "selected_role": role,
            "error_message": error_message,
        },
        status_code=status_code,
    )


def render_manage_user_page(
    request: Request,
    session: Session,
    *,
    user_id: int,
    full_name: str = "",
    role: str = "",
    error_message: str = "",
    success_message: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    target_user = get_user_or_none(session, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    serialized_user = serialize_user(target_user)
    return templates.TemplateResponse(
        request=request,
        name="settings/edit_user.html",
        context={
            "app_title": APP_TITLE,
            "target_user": serialized_user,
            "full_name": full_name or serialized_user["full_name"],
            "selected_role": role or serialized_user["role"],
            "error_message": error_message,
            "success_message": success_message,
        },
        status_code=status_code,
    )


def build_record_start_context(
    session: Session,
    *,
    form_choices: list[dict[str, Any]] | None = None,
    recent_drafts: list[dict[str, Any]] | None = None,
    recent_completed: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    resolved_form_choices = form_choices if form_choices is not None else list_form_choices(session)
    resolved_recent_drafts = recent_drafts if recent_drafts is not None else list_records(session, status="draft", limit=8)
    resolved_recent_completed = (
        recent_completed if recent_completed is not None else list_records(session, status="completed", limit=8)
    )

    quick_form_choices: list[dict[str, Any]] = []
    seen_quick_slugs: set[str] = set()
    for record in [*resolved_recent_drafts, *resolved_recent_completed]:
        form_slug = str(record.get("form_slug") or "").strip()
        if not form_slug or form_slug in seen_quick_slugs:
            continue
        matching_choice = next((choice for choice in resolved_form_choices if choice["slug"] == form_slug), None)
        if matching_choice is None:
            continue
        quick_form_choices.append(matching_choice)
        seen_quick_slugs.add(form_slug)
        if len(quick_form_choices) >= 6:
            break

    if len(quick_form_choices) < 6:
        for choice in resolved_form_choices:
            if choice["slug"] in seen_quick_slugs:
                continue
            quick_form_choices.append(choice)
            seen_quick_slugs.add(choice["slug"])
            if len(quick_form_choices) >= 6:
                break

    return {
        "form_choices": resolved_form_choices,
        "quick_form_choices": quick_form_choices,
        "recent_drafts": resolved_recent_drafts,
        "recent_completed": resolved_recent_completed,
    }


def render_records_work_page(
    request: Request,
    session: Session,
    *,
    success_message: str = "",
    record_start_open: bool = False,
    record_start_error: str = "",
    record_start_selected_slug: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    recent_drafts = list_records(session, status="draft", limit=8)
    recent_completed = list_records(session, status="completed", limit=8)
    draft_count = count_records(session, status="draft")
    completed_count = count_records(session, status="completed")
    record_start_context = build_record_start_context(
        session,
        recent_drafts=recent_drafts,
        recent_completed=recent_completed,
    )
    return templates.TemplateResponse(
        request=request,
        name="records/home.html",
        context={
            "app_title": APP_TITLE,
            **record_start_context,
            "records_mode": "work",
            "success_message": success_message,
            "record_start_open": record_start_open,
            "record_start_error": record_start_error,
            "record_start_selected_slug": record_start_selected_slug,
            "draft_count": draft_count,
            "completed_count": completed_count,
            "recent_drafts": recent_drafts,
            "drafts_truncated": draft_count > len(recent_drafts),
        },
        status_code=status_code,
    )


def render_new_record_page(
    request: Request,
    session: Session,
    *,
    selected_form_slug: str = "",
    error_message: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    record_start_context = build_record_start_context(session)
    return templates.TemplateResponse(
        request=request,
        name="records/new.html",
        context={
            "app_title": APP_TITLE,
            **record_start_context,
            "selected_form_slug": selected_form_slug,
            "error_message": error_message,
        },
        status_code=status_code,
    )


def render_records_history_page(
    request: Request,
    session: Session,
    *,
    search_query: str = "",
    status_filter: str = "completed",
    record_start_open: bool = False,
    record_start_error: str = "",
    record_start_selected_slug: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    active_status = (status_filter or "completed").strip().lower()
    if active_status not in {"completed", "draft", "all"}:
        active_status = "completed"
    query_text = (search_query or "").strip()
    record_status = None if active_status == "all" else active_status
    matching_records = list_records(
        session,
        status=record_status,
        search=query_text or None,
        limit=40,
    )
    matching_total_count = count_records(
        session,
        status=record_status,
        search=query_text or None,
    )
    record_start_context = build_record_start_context(session)
    draft_count = count_records(session, status="draft")
    completed_count = count_records(session, status="completed")
    return templates.TemplateResponse(
        request=request,
        name="records/history.html",
        context={
            "app_title": APP_TITLE,
            **record_start_context,
            "records_mode": "history",
            "search_query": query_text,
            "status_filter": active_status,
            "matching_records": matching_records,
            "matching_count": matching_total_count,
            "matching_truncated": matching_total_count > len(matching_records),
            "draft_count": draft_count,
            "completed_count": completed_count,
            "record_start_open": record_start_open,
            "record_start_error": record_start_error,
            "record_start_selected_slug": record_start_selected_slug,
        },
        status_code=status_code,
    )


def render_record_edit_page(
    request: Request,
    session: Session,
    *,
    record_id: int,
    error_message: str = "",
    success_message: str = "",
    validation_issues: list[str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")

    resolved_success_message = success_message
    if not resolved_success_message and request.query_params.get("saved") == "1":
        resolved_success_message = "Saved the draft."

    resolved_validation_issues = validation_issues or []
    if record.status == "draft" and not resolved_validation_issues:
        resolved_validation_issues = list_record_completion_issues(
            record,
            values=current_record_values(record),
        )

    back_to_history = request.query_params.get("from") == "history"
    return templates.TemplateResponse(
        request=request,
        name="records/edit.html",
        context={
            "app_title": APP_TITLE,
            "record": serialize_record(record, include_entry_schema=True),
            "error_message": error_message,
            "success_message": resolved_success_message,
            "validation_issues": resolved_validation_issues,
            "back_href": "/records/history" if back_to_history else "/records",
            "back_label": "Back to history" if back_to_history else "Back to records",
        },
        status_code=status_code,
    )


def render_record_view_page(
    request: Request,
    session: Session,
    *,
    record_id: int,
) -> HTMLResponse:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")

    back_to_history = request.query_params.get("from") == "history"
    return templates.TemplateResponse(
        request=request,
        name="records/view.html",
        context={
            "app_title": APP_TITLE,
            "record": serialize_record(record, include_entry_schema=True),
            "back_href": "/records/history" if back_to_history else "/records",
            "back_label": "Back to history" if back_to_history else "Back to records",
        },
    )


def render_record_print_page(
    request: Request,
    session: Session,
    *,
    record_id: int,
) -> HTMLResponse:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")

    clinic_profile = get_clinic_profile(session)
    clinic_logo_url = "/settings/clinic/logo" if clinic_profile.get("has_logo") else ""
    back_to_history = request.query_params.get("from") == "history"

    return templates.TemplateResponse(
        request=request,
        name="records/print.html",
        context={
            "app_title": APP_TITLE,
            "back_href": f"/records/{record.id}?from=history" if back_to_history else f"/records/{record.id}",
            "back_label": "Back to record",
            "document": build_record_print_document(
                record,
                clinic_profile=clinic_profile,
                clinic_logo_url=clinic_logo_url,
            ),
        },
    )


def record_update_payload_from_form_data(form_data: dict[str, list[str]]) -> RecordUpdatePayload:
    values: dict[str, Any] = {}
    signatories_by_slot: dict[str, dict[str, str]] = {}
    for key, raw_values in form_data.items():
        if not key.startswith("value__"):
            continue
        block_id = key.removeprefix("value__").strip()
        if not block_id:
            continue
        value = (raw_values or [""])[0]
        values[block_id] = value

    for key, raw_values in form_data.items():
        if not key.startswith("signatory__"):
            continue
        parts = key.split("__", 2)
        if len(parts) != 3:
            continue
        _, slot_id, field_name = parts
        slot_id = slot_id.strip()
        field_name = field_name.strip()
        if not slot_id or field_name not in {"option_id", "name", "title", "license"}:
            continue
        signatories_by_slot.setdefault(slot_id, {})[field_name] = (raw_values or [""])[0]

    return RecordUpdatePayload(
        patient_name=(form_data.get("patient_name") or [None])[0],
        patient_age=(form_data.get("patient_age") or [None])[0],
        patient_sex=(form_data.get("patient_sex") or [None])[0],
        case_number=(form_data.get("case_number") or [None])[0],
        values=values,
        indexed_meta={"signatories": signatories_by_slot},
    )


@app.get("/", include_in_schema=False)
def root(request: Request) -> RedirectResponse:
    if not getattr(request.state, "has_users", True):
        return redirect_for_html("/setup")
    if getattr(request.state, "current_user", None):
        if request.state.current_user.get("must_change_password"):
            return redirect_for_html("/change-password")
        return redirect_for_html("/records")
    return redirect_for_html("/login")


@app.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request) -> HTMLResponse:
    if getattr(request.state, "has_users", True):
        return redirect_for_html("/login")
    return render_setup_page(request)


@app.post("/setup")
async def create_initial_admin_page(request: Request, session: Session = Depends(get_session)):
    if getattr(request.state, "has_users", True):
        return redirect_for_html("/login")
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    payload = SetupAdminPayload(
        full_name=(form_data.get("full_name") or [""])[0],
        email=(form_data.get("email") or [""])[0],
        login_id=(form_data.get("login_id") or [""])[0],
        password=(form_data.get("password") or [""])[0],
    )
    try:
        user = create_initial_admin(session, payload)
    except ValueError as exc:
        return render_setup_page(
            request,
            full_name=payload.full_name,
            email=payload.email,
            login_id=payload.login_id or "",
            error_message=str(exc),
            status_code=422,
        )
    request.session["user_id"] = user["id"]
    return redirect_for_html("/records")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    if not getattr(request.state, "has_users", True):
        return redirect_for_html("/setup")
    success_message = ""
    if request.query_params.get("restored") == "1":
        success_message = "Backup restore completed. Sign in using an account from the restored backup."
    return render_login_page(request, success_message=success_message)


@app.post("/login")
async def login_action(request: Request, session: Session = Depends(get_session)):
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    payload = LoginPayload(
        identifier=(form_data.get("identifier") or [""])[0],
        password=(form_data.get("password") or [""])[0],
    )
    try:
        user = authenticate_user(session, payload)
    except ValueError as exc:
        return render_login_page(
            request,
            identifier=payload.identifier,
            error_message=str(exc),
            status_code=422,
        )
    request.session["user_id"] = user["id"]
    if user.get("must_change_password"):
        return redirect_for_html("/change-password")
    return redirect_for_html("/records")


@app.get("/request-account", response_class=HTMLResponse)
def request_account_page(request: Request) -> HTMLResponse:
    return render_request_account_page(request)


@app.post("/request-account")
async def request_account_action(request: Request, session: Session = Depends(get_session)):
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    payload = AccountRequestPayload(
        full_name=(form_data.get("full_name") or [""])[0],
        email=(form_data.get("email") or [""])[0],
        login_id=(form_data.get("login_id") or [""])[0],
        password=(form_data.get("password") or [""])[0],
    )
    try:
        user = request_account(session, payload)
    except ValueError as exc:
        return render_request_account_page(
            request,
            full_name=payload.full_name,
            email=payload.email,
            login_id=payload.login_id or "",
            error_message=str(exc),
            status_code=422,
        )
    return render_request_account_page(
        request,
        success_message=f"Account request saved for {user['full_name']}. Wait for admin approval before logging in.",
    )


@app.get("/change-password", response_class=HTMLResponse)
def change_password_page(request: Request) -> HTMLResponse:
    if not getattr(request.state, "current_user", None):
        return redirect_for_html("/login")
    return render_change_password_page(request)


@app.post("/change-password")
async def change_password_action(request: Request, session: Session = Depends(get_session)):
    user_id = current_user_id(request)
    if user_id is None:
        return redirect_for_html("/login")
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    return_to = ((form_data.get("return_to") or ["records"])[0] or "records").strip().lower()
    payload = PasswordChangePayload(
        current_password=(form_data.get("current_password") or [""])[0],
        new_password=(form_data.get("new_password") or [""])[0],
    )
    try:
        change_user_password(
            session,
            user_id,
            payload,
            require_current_password=not bool((request.state.current_user or {}).get("must_change_password")),
        )
    except KeyError:
        request.session.pop("user_id", None)
        return redirect_for_html("/login")
    except ValueError as exc:
        return render_change_password_page(
            request,
            error_message=str(exc),
            status_code=422,
        )
    if return_to == "settings" and not bool((request.state.current_user or {}).get("must_change_password")):
        return redirect_for_html("/settings/account?saved=1")
    return redirect_for_html("/records?password_changed=1")


@app.post("/logout")
def logout_action(request: Request) -> RedirectResponse:
    request.session.clear()
    return redirect_for_html("/login")


@app.get("/records", response_class=HTMLResponse)
def records_home(
    request: Request,
    q: str = "",
    status: str = "",
    password_changed: str = "",
    session: Session = Depends(get_session),
) -> HTMLResponse:
    if q or status:
        query: dict[str, str] = {}
        if q:
            query["q"] = q
        normalized_status = (status or "").strip().lower()
        if normalized_status in {"completed", "draft", "all"}:
            query["status"] = normalized_status
        history_url = "/records/history"
        if query:
            history_url = f"{history_url}?{urlencode(query)}"
        return redirect_for_html(history_url)

    return render_records_work_page(
        request,
        session,
        success_message="Password updated." if password_changed == "1" else "",
    )


@app.get("/records/new", response_class=HTMLResponse)
def start_new_record_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return render_new_record_page(request, session)


@app.get("/records/history", response_class=HTMLResponse)
def records_history_page(
    request: Request,
    q: str = "",
    status: str = "completed",
    session: Session = Depends(get_session),
) -> HTMLResponse:
    return render_records_history_page(
        request,
        session,
        search_query=q,
        status_filter=status,
    )


@app.post("/records/new")
async def create_record_page(
    request: Request,
    session: Session = Depends(get_session),
):
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    return_to = ((form_data.get("return_to") or ["work"])[0] or "work").strip().lower()
    return_query = ((form_data.get("return_query") or [""])[0] or "").strip()
    return_status = ((form_data.get("return_status") or ["completed"])[0] or "completed").strip().lower()
    payload = RecordCreatePayload(
        form_slug=(form_data.get("form_slug") or [""])[0],
    )
    try:
        created = create_record(session, payload, actor_user_id=current_user_id(request))
    except ValueError as exc:
        if return_to == "history":
            return render_records_history_page(
                request,
                session,
                search_query=return_query,
                status_filter=return_status,
                record_start_open=True,
                record_start_selected_slug=payload.form_slug,
                record_start_error=str(exc),
                status_code=422,
            )
        if return_to == "new":
            return render_new_record_page(
                request,
                session,
                selected_form_slug=payload.form_slug,
                error_message=str(exc),
                status_code=422,
            )
        return render_records_work_page(
            request,
            session,
            record_start_open=True,
            record_start_selected_slug=payload.form_slug,
            record_start_error=str(exc),
            status_code=422,
        )
    return RedirectResponse(url=f"/records/{created['id']}/edit", status_code=303)


@app.get("/records/{record_id}/edit", response_class=HTMLResponse)
def edit_record_page(
    record_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    return render_record_edit_page(request, session, record_id=record_id)


@app.post("/records/{record_id}/edit")
async def update_record_page(
    record_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    action = ((form_data.get("action") or ["draft"])[0] or "draft").strip().lower()
    payload = record_update_payload_from_form_data(form_data)
    current_query = request.url.query

    try:
        if action == "complete":
            completed = complete_record(
                session,
                record_id,
                payload,
                preserve_asset_fields=True,
                actor_user_id=current_user_id(request),
            )
            redirect_url = f"/records/{completed['id']}"
            if current_query:
                redirect_url = f"{redirect_url}?{current_query}"
            return RedirectResponse(url=redirect_url, status_code=303)

        update_record(
            session,
            record_id,
            payload,
            preserve_asset_fields=True,
            actor_user_id=current_user_id(request),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Record not found.") from exc
    except RecordCompletionValidationError as exc:
        update_record(
            session,
            record_id,
            payload,
            preserve_asset_fields=True,
            actor_user_id=current_user_id(request),
        )
        return render_record_edit_page(
            request,
            session,
            record_id=record_id,
            error_message=str(exc),
            validation_issues=exc.issues,
            status_code=422,
        )
    except ValueError as exc:
        return render_record_edit_page(
            request,
            session,
            record_id=record_id,
            error_message=str(exc),
            status_code=422,
        )

    redirect_url = f"/records/{record_id}/edit?saved=1"
    if current_query:
        redirect_url = f"/records/{record_id}/edit?{current_query}&saved=1"
    return RedirectResponse(url=redirect_url, status_code=303)


@app.post("/records/{record_id}/assets")
async def upload_record_asset_page(
    record_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    form = await request.form()
    field_block_id = str(form.get("field_block_id") or "")
    image_file = form.get("image_file")

    try:
        if image_file is None or not hasattr(image_file, "read") or not getattr(image_file, "filename", ""):
            raise ValueError("Choose an image before uploading.")
        file_bytes = await image_file.read()
        store_record_image_asset(
            session,
            record_id=record_id,
            field_block_id=field_block_id,
            original_filename=image_file.filename,
            content_type=image_file.content_type,
            file_bytes=file_bytes,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Record not found.") from exc
    except ValueError as exc:
        return render_record_edit_page(
            request,
            session,
            record_id=record_id,
            error_message=str(exc),
            status_code=422,
        )

    redirect_url = f"/records/{record_id}/edit"
    if request.url.query:
        redirect_url = f"{redirect_url}?{request.url.query}"
    return RedirectResponse(url=redirect_url, status_code=303)


@app.post("/records/{record_id}/assets/{asset_id}/remove")
def remove_record_asset_page(
    record_id: int,
    asset_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    try:
        delete_record_asset(session, record_id, asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Record asset not found.") from exc
    except ValueError as exc:
        return render_record_edit_page(
            request,
            session,
            record_id=record_id,
            error_message=str(exc),
            status_code=422,
        )
    redirect_url = f"/records/{record_id}/edit"
    if request.url.query:
        redirect_url = f"{redirect_url}?{request.url.query}"
    return RedirectResponse(url=redirect_url, status_code=303)


@app.get("/records/{record_id}/assets/{asset_id}/file")
def record_asset_file(
    record_id: int,
    asset_id: int,
    session: Session = Depends(get_session),
) -> FileResponse:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")

    asset = next((item for item in record.assets if item.id == asset_id), None)
    if asset is None:
        raise HTTPException(status_code=404, detail="Record asset not found.")
    if not asset.storage_path:
        raise HTTPException(status_code=404, detail="Record asset file not found.")

    return FileResponse(
        asset.storage_path,
        media_type=asset.mime_type or None,
        filename=asset.original_filename,
    )


@app.get("/records/{record_id}", response_class=HTMLResponse)
def view_record_page(
    record_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    return render_record_view_page(request, session, record_id=record_id)


@app.get("/records/{record_id}/print", response_class=HTMLResponse)
def print_record_page(
    record_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    return render_record_print_page(request, session, record_id=record_id)


@app.get("/forms", response_class=HTMLResponse)
def forms_library(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    library_tree = list_library_tree(session)
    library_stats = summarize_library_tree(library_tree)
    return templates.TemplateResponse(
        request=request,
        name="forms/library.html",
        context={
            "app_title": APP_TITLE,
            "library_tree": library_tree,
            "library_stats": library_stats,
        },
    )


def summarize_library_tree(nodes: list[dict[str, Any]]) -> dict[str, int]:
    stats = {"folder_count": 0, "form_count": 0, "item_count": 0}

    def walk(node_list: list[dict[str, Any]]) -> None:
        for node in node_list:
            if node.get("archived"):
                continue
            if node.get("kind") == "container":
                stats["folder_count"] += 1
                walk(node.get("children") or [])
            elif node.get("kind") == "form" and node.get("form"):
                stats["form_count"] += 1

    walk(nodes)
    stats["item_count"] = stats["folder_count"] + stats["form_count"]
    return stats


def render_new_folder_page(
    request: Request,
    session: Session,
    *,
    folder_name: str = "",
    parent_node_key: str = "",
    error_message: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    container_options = list_container_choices(session)
    return templates.TemplateResponse(
        request=request,
        name="forms/new_folder.html",
        context={
            "app_title": APP_TITLE,
            "container_options": container_options,
            "folder_name": folder_name,
            "selected_parent_key": parent_node_key.strip(),
            "error_message": error_message,
        },
        status_code=status_code,
    )


def render_edit_folder_page(
    request: Request,
    session: Session,
    *,
    node_key: str,
    folder_name: str = "",
    error_message: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    container = get_container_or_none(session, node_key)
    if container is None:
        raise HTTPException(status_code=404, detail="Folder not found.")

    container_options = list_container_choices(session)
    current_choice = next((option for option in container_options if option["node_key"] == container.node_key), None)
    parent_choice = next((option for option in container_options if option["node_key"] == container.parent.node_key), None) if container.parent else None
    return templates.TemplateResponse(
        request=request,
        name="forms/edit_folder.html",
        context={
            "app_title": APP_TITLE,
            "folder_node_key": container.node_key,
            "folder_name": folder_name or container.name,
            "folder_path_label": current_choice["folder_path_label"] if current_choice else container.name,
            "parent_path_label": parent_choice["folder_path_label"] if parent_choice else "Top level",
            "error_message": error_message,
        },
        status_code=status_code,
    )


def render_move_folder_page(
    request: Request,
    session: Session,
    *,
    node_key: str,
    selected_parent_key: str = "",
    error_message: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    container = get_container_or_none(session, node_key)
    if container is None:
        raise HTTPException(status_code=404, detail="Folder not found.")

    current_choices = list_container_choices(session)
    current_choice = next((option for option in current_choices if option["node_key"] == container.node_key), None)
    selected_key = selected_parent_key.strip()
    if not selected_key and container.parent is not None:
        selected_key = container.parent.node_key

    return templates.TemplateResponse(
        request=request,
        name="forms/move_folder.html",
        context={
            "app_title": APP_TITLE,
            "folder_node_key": container.node_key,
            "folder_name": container.name,
            "folder_path_label": current_choice["folder_path_label"] if current_choice else container.name,
            "selected_parent_key": selected_key,
            "container_options": list_move_target_choices(session, exclude_node_key=container.node_key),
            "error_message": error_message,
        },
        status_code=status_code,
    )


def render_move_form_page(
    request: Request,
    session: Session,
    *,
    slug: str,
    selected_parent_key: str = "",
    error_message: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    definition = get_form_or_none(session, slug)
    if definition is None:
        raise HTTPException(status_code=404, detail="Form not found.")

    form_choices = list_form_choices(session)
    current_choice = next((option for option in form_choices if option["slug"] == definition.slug), None)
    container_options = list_move_target_choices(session)
    resolved_parent_key = definition.library_parent_node_key or ""

    return templates.TemplateResponse(
        request=request,
        name="forms/move_form.html",
        context={
            "app_title": APP_TITLE,
            "form_slug": definition.slug,
            "form_name": definition.name,
            "form_path_label": current_choice["form_path_label"] if current_choice else definition.name,
            "selected_parent_key": selected_parent_key.strip() or resolved_parent_key,
            "container_options": container_options,
            "error_message": error_message,
        },
        status_code=status_code,
    )


@app.get("/folders/new", response_class=HTMLResponse)
def start_new_folder_page(
    request: Request,
    parent: str = "",
    session: Session = Depends(get_session),
) -> HTMLResponse:
    return render_new_folder_page(request, session, parent_node_key=parent)


@app.post("/folders/new")
async def create_folder_page(
    request: Request,
    session: Session = Depends(get_session),
):
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    name = (form_data.get("name") or [""])[0]
    parent_node_key = (form_data.get("parent_node_key") or [""])[0]
    try:
        created = create_container(session, name, parent_node_key or None)
    except ValueError as exc:
        return render_new_folder_page(
            request,
            session,
            folder_name=name,
            parent_node_key=parent_node_key,
            error_message=str(exc),
            status_code=422,
        )
    node_anchor = created.node_key.replace(":", "-")
    return RedirectResponse(url=f"/forms#node-{node_anchor}", status_code=303)


@app.get("/folders/edit", response_class=HTMLResponse)
def edit_folder_page(
    request: Request,
    node: str = "",
    session: Session = Depends(get_session),
) -> HTMLResponse:
    return render_edit_folder_page(request, session, node_key=node)


@app.post("/folders/edit")
async def update_folder_page(
    request: Request,
    session: Session = Depends(get_session),
):
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    node_key = (form_data.get("node_key") or [""])[0]
    name = (form_data.get("name") or [""])[0]
    action = (form_data.get("action") or ["save"])[0]

    try:
        if action == "delete":
            delete_container(session, node_key)
            return RedirectResponse(url="/forms", status_code=303)

        updated = rename_container(session, node_key, name)
    except ValueError as exc:
        return render_edit_folder_page(
            request,
            session,
            node_key=node_key,
            folder_name=name,
            error_message=str(exc),
            status_code=422,
        )

    node_anchor = updated.node_key.replace(":", "-")
    return RedirectResponse(url=f"/forms#node-{node_anchor}", status_code=303)


@app.get("/folders/move", response_class=HTMLResponse)
def move_folder_page(
    request: Request,
    node: str = "",
    session: Session = Depends(get_session),
) -> HTMLResponse:
    return render_move_folder_page(request, session, node_key=node)


@app.post("/folders/move")
async def update_folder_location_page(
    request: Request,
    session: Session = Depends(get_session),
):
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    node_key = (form_data.get("node_key") or [""])[0]
    parent_node_key = (form_data.get("parent_node_key") or [""])[0]

    try:
        moved = move_container(session, node_key, parent_node_key or None)
    except ValueError as exc:
        return render_move_folder_page(
            request,
            session,
            node_key=node_key,
            selected_parent_key=parent_node_key,
            error_message=str(exc),
            status_code=422,
        )

    node_anchor = moved.node_key.replace(":", "-")
    return RedirectResponse(url=f"/forms#node-{node_anchor}", status_code=303)


@app.get("/forms/new", response_class=HTMLResponse)
def start_new_form_page(
    request: Request,
    source: str = "",
    parent: str = "",
    create_folder: bool = False,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    container_options = list_container_choices(session)
    duplicate_options = list_form_choices(session)

    source_form = None
    source_slug = source.strip()
    if source_slug:
        source_form = get_form_or_none(session, source_slug)
        if source_form is None:
            raise HTTPException(status_code=404, detail="Source form not found.")

    explicit_parent_node_key = parent.strip()
    default_parent_node_key = ""
    default_location_mode = "existing" if container_options else "root"
    if source_form and source_form.library_parent_node_key:
        default_parent_node_key = source_form.library_parent_node_key
        default_location_mode = "existing"
    elif source_form:
        default_location_mode = "root"
    elif container_options:
        default_parent_node_key = container_options[0]["node_key"]
        default_location_mode = "existing"

    if explicit_parent_node_key:
        matching_parent = next(
            (option for option in container_options if option["node_key"] == explicit_parent_node_key),
            None,
        )
        if matching_parent is not None:
            default_parent_node_key = matching_parent["node_key"]
            default_location_mode = "new" if create_folder else "existing"

    selected_container = next(
        (option for option in container_options if option["node_key"] == default_parent_node_key),
        None,
    )
    default_location_name = selected_container["name"] if selected_container else (serialize_form_location(source_form)["location_name"] if source_form else "")
    default_new_folder_parent_key = default_parent_node_key if default_location_mode in {"existing", "new"} else ""

    return templates.TemplateResponse(
        request=request,
        name="forms/new.html",
        context={
            "app_title": APP_TITLE,
            "container_options": container_options,
            "duplicate_options": duplicate_options,
            "default_parent_node_key": default_parent_node_key,
            "default_location_mode": default_location_mode,
            "default_location_name": default_location_name,
            "default_new_folder_parent_key": default_new_folder_parent_key,
            "source_form": source_form,
        },
    )


@app.get("/builder", response_class=HTMLResponse)
def builder_page(
    request: Request,
    slug: str = "",
    mode: str = "",
    session: Session = Depends(get_session),
) -> HTMLResponse:
    initial_slug = slug.strip()
    if initial_slug and get_form_or_none(session, initial_slug) is None:
        raise HTTPException(status_code=404, detail="Form not found.")
    initial_mode = mode.strip().lower()
    if initial_mode not in {"", "new", "duplicate"}:
        initial_mode = ""
    return render_builder_page(
        request,
        initial_form_slug=initial_slug,
        initial_builder_mode=initial_mode,
    )


@app.get("/forms/{slug}/builder", response_class=HTMLResponse)
def form_builder_page(
    slug: str,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    definition = get_form_or_none(session, slug)
    if definition is None:
        raise HTTPException(status_code=404, detail="Form not found.")
    return render_builder_page(request, initial_form_slug=definition.slug)


@app.get("/forms/move", response_class=HTMLResponse)
def move_form_page(
    request: Request,
    slug: str = "",
    session: Session = Depends(get_session),
) -> HTMLResponse:
    return render_move_form_page(request, session, slug=slug)


@app.post("/forms/move")
async def update_form_location_page(
    request: Request,
    session: Session = Depends(get_session),
):
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    slug = (form_data.get("slug") or [""])[0]
    parent_node_key = (form_data.get("parent_node_key") or [""])[0]

    try:
        moved = move_form(session, slug, parent_node_key or None)
    except ValueError as exc:
        return render_move_form_page(
            request,
            session,
            slug=slug,
            selected_parent_key=parent_node_key,
            error_message=str(exc),
            status_code=422,
        )

    node_anchor = f"node-form-{moved.slug}"
    return RedirectResponse(url=f"/forms#{node_anchor}", status_code=303)


@app.get("/settings", response_class=HTMLResponse)
def settings_home() -> RedirectResponse:
    return redirect_for_html("/settings/account")


@app.get("/settings/account", response_class=HTMLResponse)
def settings_account_page(request: Request) -> HTMLResponse:
    success_message = ""
    if request.query_params.get("saved") == "1":
        success_message = "Saved the new password."
    elif request.query_params.get("avatar_saved") == "1":
        success_message = "Updated your profile photo."
    elif request.query_params.get("avatar_removed") == "1":
        success_message = "Removed your profile photo."
    return render_change_password_page(request, success_message=success_message)


@app.post("/settings/account/avatar")
async def save_settings_account_avatar_page(request: Request, session: Session = Depends(get_session)):
    user_id = current_user_id(request)
    if user_id is None:
        return redirect_for_html("/login")

    form = await request.form()
    avatar_file = form.get("avatar_file")
    try:
        if avatar_file is None or not hasattr(avatar_file, "read") or not getattr(avatar_file, "filename", ""):
            raise ValueError("Choose an image before uploading.")
        save_user_avatar(
            session,
            user_id,
            avatar_filename=str(getattr(avatar_file, "filename", "") or ""),
            avatar_content_type=str(getattr(avatar_file, "content_type", "") or ""),
            avatar_bytes=await avatar_file.read(),
        )
    except KeyError:
        request.session.pop("user_id", None)
        return redirect_for_html("/login")
    except ValueError as exc:
        return render_change_password_page(request, error_message=str(exc), status_code=422)
    return RedirectResponse(url="/settings/account?avatar_saved=1", status_code=303)


@app.post("/settings/account/avatar/remove")
def remove_settings_account_avatar_page(request: Request, session: Session = Depends(get_session)):
    user_id = current_user_id(request)
    if user_id is None:
        return redirect_for_html("/login")
    try:
        remove_user_avatar(session, user_id)
    except KeyError:
        request.session.pop("user_id", None)
        return redirect_for_html("/login")
    return RedirectResponse(url="/settings/account?avatar_removed=1", status_code=303)


@app.get("/settings/account/avatar")
def settings_account_avatar_file(request: Request, session: Session = Depends(get_session)) -> FileResponse:
    user_id = current_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Login required.")
    user = get_user_or_none(session, user_id)
    if user is None or not user.avatar_path or not Path(user.avatar_path).is_file():
        raise HTTPException(status_code=404, detail="Profile photo not found.")
    response = FileResponse(
        user.avatar_path,
        media_type=user.avatar_mime_type or None,
        filename=user.avatar_original_filename or None,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/settings/clinic", response_class=HTMLResponse)
def settings_clinic_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    success_message = ""
    if request.query_params.get("saved") == "1":
        success_message = "Saved the clinic profile."
    elif request.query_params.get("logo_removed") == "1":
        success_message = "Removed the clinic logo."
    return render_settings_clinic_page(request, session, success_message=success_message)


@app.post("/settings/clinic")
async def save_settings_clinic_page(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    payload = ClinicProfilePayload(
        clinic_name=str(form.get("clinic_name") or ""),
        address=str(form.get("address") or ""),
        contact_number=str(form.get("contact_number") or ""),
        contact_email=str(form.get("contact_email") or ""),
    )
    logo_file = form.get("logo_file")
    logo_bytes: bytes | None = None
    logo_filename = ""
    logo_content_type = ""
    if logo_file is not None and hasattr(logo_file, "read") and getattr(logo_file, "filename", ""):
        logo_bytes = await logo_file.read()
        logo_filename = str(getattr(logo_file, "filename", "") or "")
        logo_content_type = str(getattr(logo_file, "content_type", "") or "")

    try:
        save_clinic_profile(
            session,
            payload,
            logo_filename=logo_filename,
            logo_content_type=logo_content_type,
            logo_bytes=logo_bytes,
        )
    except ValueError as exc:
        return render_settings_clinic_page(
            request,
            session,
            profile_override={
                **get_clinic_profile(session),
                "clinic_name": payload.clinic_name,
                "address": payload.address or "",
                "contact_number": payload.contact_number or "",
                "contact_email": payload.contact_email or "",
            },
            error_message=str(exc),
            status_code=422,
        )
    return RedirectResponse(url="/settings/clinic?saved=1", status_code=303)


@app.post("/settings/clinic/logo/remove")
def remove_settings_clinic_logo_page(request: Request, session: Session = Depends(get_session)):
    remove_clinic_logo(session)
    return RedirectResponse(url="/settings/clinic?logo_removed=1", status_code=303)


@app.get("/settings/clinic/logo")
def settings_clinic_logo_file(session: Session = Depends(get_session)) -> FileResponse:
    clinic_profile = get_clinic_profile(session)
    logo_path = str(clinic_profile.get("logo_path") or "")
    if not logo_path or not Path(logo_path).is_file():
        raise HTTPException(status_code=404, detail="Clinic logo not found.")
    return FileResponse(
        logo_path,
        media_type=str(clinic_profile.get("logo_mime_type") or "") or None,
        filename=str(clinic_profile.get("logo_original_filename") or "") or None,
    )


@app.get("/settings/desktop", response_class=HTMLResponse)
def settings_desktop_page(request: Request) -> HTMLResponse:
    success_message = ""
    if request.query_params.get("saved") == "1":
        success_message = "Saved the desktop app settings."
    elif request.query_params.get("backup") == "created":
        success_message = "Created and verified a local backup."
    elif request.query_params.get("backup") == "created_external":
        success_message = "Created and verified local and external backups."
    elif request.query_params.get("backup") == "verified":
        success_message = "Verified the latest local backup."
    elif request.query_params.get("backup") == "external_verified":
        success_message = "Verified the latest external backup."
    return render_settings_desktop_page(request, success_message=success_message)


@app.post("/settings/desktop")
async def save_settings_desktop_page(request: Request):
    form = await request.form()
    save_desktop_settings(
        browser_preference=str(form.get("browser_preference") or ""),
        network_mode=str(form.get("network_mode") or ""),
        external_backup_dir=str(form.get("external_backup_dir") or ""),
        backup_retention_count=str(form.get("backup_retention_count") or ""),
    )
    return RedirectResponse(url="/settings/desktop?saved=1", status_code=303)


@app.get("/settings/desktop/lan-qr.svg")
def settings_desktop_lan_qr(download: str = "") -> Response:
    lan_access = lan_access_details()
    svg = qr_svg_bytes(str(lan_access.get("qr_url") or ""))
    headers = {"Cache-Control": "no-store"}
    if download == "1":
        headers["Content-Disposition"] = 'attachment; filename="ndhi-lan-access-qr.svg"'
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers=headers,
    )


@app.post("/settings/desktop/backup-now")
def settings_desktop_backup_now_page(request: Request) -> Response:
    desktop_settings = read_desktop_settings()
    external_backup_dir = str(desktop_settings.get("external_backup_dir") or "")
    backup_retention_count = int(desktop_settings.get("backup_retention_count") or 30)
    try:
        with backup_operation_lock(blocking=False):
            try:
                backup_path = create_verified_backup(reason="manual-app")
                prune_backup_archives(keep_count=backup_retention_count)
            except Exception as exc:
                return render_settings_desktop_page(
                    request,
                    error_message=f"Backup failed: {exc}",
                    status_code=500,
                )
            try:
                external_backup_path = copy_backup_archive_to_destination(backup_path, external_backup_dir)
                if external_backup_path is not None:
                    prune_backup_archives(
                        keep_count=backup_retention_count,
                        backup_dir=Path(external_backup_dir).expanduser(),
                    )
            except Exception as exc:
                return render_settings_desktop_page(
                    request,
                    error_message=f"Local backup was created and verified, but the external copy failed: {exc}",
                    status_code=500,
                )
    except BackupOperationBusyError as exc:
        return render_settings_desktop_page(
            request,
            error_message=str(exc),
            status_code=409,
        )
    if external_backup_path is not None:
        return RedirectResponse(url="/settings/desktop?backup=created_external", status_code=303)
    return RedirectResponse(url="/settings/desktop?backup=created", status_code=303)


@app.post("/settings/desktop/backup-verify-latest")
def settings_desktop_backup_verify_latest_page(request: Request) -> Response:
    try:
        with backup_operation_lock(blocking=False):
            verify_latest_backup_archive()
    except BackupOperationBusyError as exc:
        return render_settings_desktop_page(
            request,
            error_message=str(exc),
            status_code=409,
        )
    except Exception as exc:
        return render_settings_desktop_page(
            request,
            error_message=f"Backup verification failed: {exc}",
            status_code=500,
        )
    return RedirectResponse(url="/settings/desktop?backup=verified", status_code=303)


@app.post("/settings/desktop/backup-verify-external-latest")
def settings_desktop_backup_verify_external_latest_page(request: Request) -> Response:
    desktop_settings = read_desktop_settings()
    try:
        with backup_operation_lock(blocking=False):
            verify_latest_external_backup_archive(str(desktop_settings.get("external_backup_dir") or ""))
    except BackupOperationBusyError as exc:
        return render_settings_desktop_page(
            request,
            error_message=str(exc),
            status_code=409,
        )
    except Exception as exc:
        return render_settings_desktop_page(
            request,
            error_message=f"External backup verification failed: {exc}",
            status_code=500,
        )
    return RedirectResponse(url="/settings/desktop?backup=external_verified", status_code=303)


@app.post("/settings/desktop/restore-backup")
async def settings_desktop_restore_backup_page(
    request: Request,
    backup_file: UploadFile = File(...),
    confirmation: str = Form(""),
) -> Response:
    if str(confirmation or "").strip() != RESTORE_CONFIRMATION_TEXT:
        return render_settings_desktop_page(
            request,
            error_message=f'Type {RESTORE_CONFIRMATION_TEXT} before restoring a backup.',
            status_code=400,
        )

    original_filename = Path(backup_file.filename or "").name
    if not original_filename.lower().endswith(".zip"):
        return render_settings_desktop_page(
            request,
            error_message="Choose an NDHI backup ZIP archive.",
            status_code=400,
        )

    with tempfile.TemporaryDirectory(prefix="ndhi-restore-upload-") as temp_dir:
        uploaded_path = Path(temp_dir) / original_filename
        bytes_written = 0
        with uploaded_path.open("wb") as target:
            while True:
                chunk = await backup_file.read(1024 * 1024)
                if not chunk:
                    break
                target.write(chunk)
                bytes_written += len(chunk)

        if bytes_written <= 0:
            return render_settings_desktop_page(
                request,
                error_message="The selected backup archive is empty.",
                status_code=400,
            )

        if not begin_restore_maintenance():
            return render_settings_desktop_page(
                request,
                error_message="A backup restore is already in progress.",
                status_code=409,
            )
        try:
            with backup_operation_lock(blocking=False):
                restore_verified_backup(uploaded_path)
        except BackupOperationBusyError as exc:
            return render_settings_desktop_page(
                request,
                error_message=str(exc),
                status_code=409,
            )
        except Exception as exc:
            return render_settings_desktop_page(
                request,
                error_message=f"Backup restore failed: {exc}",
                status_code=500,
            )
        finally:
            end_restore_maintenance()

    request.session.clear()
    return RedirectResponse(url="/login?restored=1", status_code=303)


@app.get("/settings/desktop/lan-qr", response_class=HTMLResponse)
def settings_desktop_lan_qr_page(request: Request) -> HTMLResponse:
    lan_access = lan_access_details()
    return templates.TemplateResponse(
        request=request,
        name="settings/lan_qr.html",
        context={
            "app_title": APP_TITLE,
            "lan_access": lan_access,
            "desktop_settings": read_desktop_settings(),
            "desktop_status": desktop_runtime_status(),
        },
    )


@app.get("/settings/users", response_class=HTMLResponse)
def settings_users_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return render_settings_users_page(request, session)


@app.get("/settings/users/{user_id}/edit", response_class=HTMLResponse)
def settings_manage_user_page(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    return render_manage_user_page(request, session, user_id=user_id)


@app.post("/settings/users/{user_id}/edit")
async def update_managed_user_page(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    action = ((form_data.get("action") or ["details"])[0] or "details").strip().lower()

    if action == "reset_password":
        temporary_password = (form_data.get("temporary_password") or [""])[0]
        if current_user_id(request) == user_id:
            return render_manage_user_page(
                request,
                session,
                user_id=user_id,
                error_message="Use My account to change your own password.",
                status_code=422,
            )
        try:
            updated = reset_user_password_by_admin(
                session,
                user_id,
                temporary_password=temporary_password,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="User not found.") from exc
        except ValueError as exc:
            return render_manage_user_page(
                request,
                session,
                user_id=user_id,
                error_message=str(exc),
                status_code=422,
            )
        return render_manage_user_page(
            request,
            session,
            user_id=user_id,
            success_message=f"Reset password for {updated['full_name']}. They must change it on next login.",
        )

    full_name = (form_data.get("full_name") or [""])[0]
    role = (form_data.get("role") or ["medtech"])[0]
    try:
        updated = update_user_admin_details(
            session,
            user_id,
            full_name=full_name,
            role=role,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="User not found.") from exc
    except ValueError as exc:
        return render_manage_user_page(
            request,
            session,
            user_id=user_id,
            full_name=full_name,
            role=role,
            error_message=str(exc),
            status_code=422,
        )
    return render_manage_user_page(
        request,
        session,
        user_id=user_id,
        success_message=f"Saved {updated['full_name']}.",
    )


@app.get("/settings/users/{user_id}/avatar")
def settings_user_avatar_file(user_id: int, session: Session = Depends(get_session)) -> FileResponse:
    user = get_user_or_none(session, user_id)
    if user is None or not user.avatar_path or not Path(user.avatar_path).is_file():
        raise HTTPException(status_code=404, detail="Profile photo not found.")
    response = FileResponse(
        user.avatar_path,
        media_type=user.avatar_mime_type or None,
        filename=user.avatar_original_filename or None,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/settings/users/new", response_class=HTMLResponse)
def settings_new_user_page(request: Request) -> HTMLResponse:
    return render_new_user_page(request)


@app.post("/settings/users/new")
async def create_user_account_page(request: Request, session: Session = Depends(get_session)):
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    payload = UserCreatePayload(
        full_name=(form_data.get("full_name") or [""])[0],
        email=(form_data.get("email") or [""])[0],
        login_id=(form_data.get("login_id") or [""])[0],
        role=(form_data.get("role") or ["medtech"])[0],
        password=(form_data.get("password") or [""])[0],
    )
    try:
        created = create_user_account(session, payload)
    except ValueError as exc:
        return render_new_user_page(
            request,
            full_name=payload.full_name,
            email=payload.email,
            login_id=payload.login_id or "",
            role=payload.role,
            error_message=str(exc),
            status_code=422,
        )
    return render_settings_users_page(
        request,
        session,
        success_message=f"Created {created['full_name']} as an active {created['role']} account.",
    )


@app.post("/settings/users/{user_id}/approve")
async def approve_user_account_page(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body, keep_blank_values=True)
    role = (form_data.get("role") or ["medtech"])[0]
    try:
        updated = approve_user_account(session, user_id, role=role)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="User not found.") from exc
    except ValueError as exc:
        return render_settings_users_page(request, session, error_message=str(exc), status_code=422)
    return render_settings_users_page(
        request,
        session,
        success_message=f"Approved {updated['full_name']} as {updated['role']}.",
    )


@app.post("/settings/users/{user_id}/disable")
def disable_user_account_page(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    try:
        updated = update_user_status(session, user_id, status="disabled")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="User not found.") from exc
    except ValueError as exc:
        return render_settings_users_page(request, session, error_message=str(exc), status_code=422)
    return render_settings_users_page(
        request,
        session,
        success_message=f"Disabled {updated['full_name']}.",
    )


@app.post("/settings/users/{user_id}/activate")
def activate_user_account_page(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    try:
        updated = update_user_status(session, user_id, status="active")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="User not found.") from exc
    except ValueError as exc:
        return render_settings_users_page(request, session, error_message=str(exc), status_code=422)
    return render_settings_users_page(
        request,
        session,
        success_message=f"Reactivated {updated['full_name']}.",
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "product_id": PRODUCT_ID}


@app.get("/api/records/bootstrap")
def records_bootstrap(session: Session = Depends(get_session)) -> dict[str, Any]:
    return {
        "app_title": APP_TITLE,
        "form_choices": list_form_choices(session),
        "recent_drafts": list_records(session, status="draft", limit=8),
        "recent_completed": list_records(session, status="completed", limit=8),
    }


@app.get("/api/records")
def records_index(
    status: str = "",
    q: str = "",
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return {"records": list_records(session, status=status or None, search=q or None)}


@app.post("/api/records", status_code=201)
def create_record_endpoint(
    payload: RecordCreatePayload,
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        return create_record(session, payload, actor_user_id=current_user_id(request))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/records/{record_id}")
def get_record(record_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    return serialize_record(record, include_entry_schema=True)


@app.put("/api/records/{record_id}")
def update_record_endpoint(
    record_id: int,
    payload: RecordUpdatePayload,
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        return update_record(session, record_id, payload, actor_user_id=current_user_id(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Record not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/records/{record_id}/complete")
def complete_record_endpoint(
    record_id: int,
    payload: RecordUpdatePayload,
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        return complete_record(session, record_id, payload, actor_user_id=current_user_id(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Record not found.") from exc
    except RecordCompletionValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(exc),
                "issues": exc.issues,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/records/{record_id}/assets")
async def upload_record_asset_endpoint(
    record_id: int,
    field_block_id: str = Form(...),
    image_file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        file_bytes = await image_file.read()
        return store_record_image_asset(
            session,
            record_id=record_id,
            field_block_id=field_block_id,
            original_filename=image_file.filename or "",
            content_type=image_file.content_type,
            file_bytes=file_bytes,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Record not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/api/records/{record_id}/assets/{asset_id}")
def delete_record_asset_endpoint(
    record_id: int,
    asset_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        return delete_record_asset(session, record_id, asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Record asset not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/builder/bootstrap")
def builder_bootstrap(session: Session = Depends(get_session)) -> dict[str, Any]:
    form_choices = list_form_choices(session)
    container_options = list_container_choices(session)
    selected_slug = form_choices[0]["slug"] if form_choices else None
    return {
        "app_title": APP_TITLE,
        "container_options": container_options,
        "form_choices": form_choices,
        "selected_form_slug": selected_slug,
    }


@app.get("/api/library/tree")
def library_tree(session: Session = Depends(get_session)) -> dict[str, Any]:
    return {"nodes": list_library_tree(session)}


@app.post("/api/forms/print-preview", response_class=HTMLResponse)
def form_print_preview(
    request: Request,
    payload: PrintPreviewPayload,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    clinic_profile = get_clinic_profile(session)
    clinic_logo_url = "/settings/clinic/logo" if clinic_profile.get("has_logo") else ""
    return templates.TemplateResponse(
        request=request,
        name="forms/print_preview.html",
        context={
            "app_title": APP_TITLE,
            "document": build_form_print_preview_document(
                form_name=payload.name,
                form_path_label=payload.location_name or "Builder preview",
                block_schema=payload.form_schema,
                clinic_profile=clinic_profile,
                clinic_logo_url=clinic_logo_url,
            ),
        },
    )


@app.post("/api/forms/signatory-stamp")
async def upload_signatory_stamp_endpoint(stamp_file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        return save_signatory_stamp_image(
            stamp_filename=stamp_file.filename or "",
            stamp_content_type=stamp_file.content_type,
            stamp_bytes=await stamp_file.read(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/signatory-stamps/{filename}")
def signatory_stamp_file(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=404, detail="Stamp image not found.")
    stamp_path = SIGNATORY_UPLOADS_DIR / safe_name
    if not stamp_path.is_file():
        raise HTTPException(status_code=404, detail="Stamp image not found.")
    return FileResponse(
        stamp_path,
        media_type=mimetypes.guess_type(str(stamp_path))[0] or None,
        filename=safe_name,
    )


@app.get("/api/forms/{slug}")
def get_form(slug: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    definition = get_form_or_none(session, slug)
    if definition is None:
        raise HTTPException(status_code=404, detail="Form not found.")
    return serialize_form(definition)


@app.post("/api/forms", status_code=201)
def create_form_endpoint(payload: FormSavePayload, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        return create_form(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.put("/api/forms/{slug}")
def update_form_endpoint(
    slug: str,
    payload: FormSavePayload,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        return update_form(session, slug, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Form not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
