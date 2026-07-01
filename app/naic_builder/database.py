from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DB_PATH, ensure_runtime_directories


ensure_runtime_directories()


class Base(DeclarativeBase):
    pass


engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
_CHANGE_BACKUP_AFTER_COMMIT_KEY = "ndhi_change_backup_after_commit"
SKIP_CHANGE_BACKUP_SESSION_KEY = "skip_change_backup"


@event.listens_for(Session, "before_commit")
def mark_session_for_change_backup(session: Session) -> None:
    if session.info.get(SKIP_CHANGE_BACKUP_SESSION_KEY):
        return
    if session.new or session.dirty or session.deleted:
        session.info[_CHANGE_BACKUP_AFTER_COMMIT_KEY] = True


@event.listens_for(Session, "after_commit")
def request_change_backup_after_commit(session: Session) -> None:
    if not session.info.pop(_CHANGE_BACKUP_AFTER_COMMIT_KEY, False):
        return
    try:
        from .backup_schedule import request_change_backup

        request_change_backup()
    except Exception:
        pass


@event.listens_for(Session, "after_rollback")
def clear_change_backup_after_rollback(session: Session) -> None:
    session.info.pop(_CHANGE_BACKUP_AFTER_COMMIT_KEY, None)


def migrate_form_definitions_tree_first_shape(connection) -> None:
    connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        connection.exec_driver_sql(
            """
            CREATE TABLE form_definitions_new (
                id INTEGER NOT NULL PRIMARY KEY,
                slug VARCHAR(120) NOT NULL,
                name VARCHAR(255) NOT NULL,
                library_parent_node_key TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO form_definitions_new (
                id,
                slug,
                name,
                library_parent_node_key,
                created_at,
                updated_at
            )
            SELECT
                id,
                slug,
                name,
                library_parent_node_key,
                created_at,
                updated_at
            FROM form_definitions
            """
        )
        connection.exec_driver_sql("DROP TABLE form_definitions")
        connection.exec_driver_sql("ALTER TABLE form_definitions_new RENAME TO form_definitions")
        connection.exec_driver_sql("CREATE UNIQUE INDEX ix_form_definitions_slug ON form_definitions (slug)")
    finally:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def migrate_users_auth_shape(connection) -> None:
    user_columns = {
        str(row[1]): row
        for row in connection.exec_driver_sql("PRAGMA table_info(users)").all()
    }

    select_email = "email" if "email" in user_columns else "NULL"
    select_login_id = (
        "login_id"
        if "login_id" in user_columns
        else ("username" if "username" in user_columns else "('user_' || id)")
    )
    select_full_name = (
        "full_name"
        if "full_name" in user_columns
        else ("display_name" if "display_name" in user_columns else "('User ' || id)")
    )
    select_role = "role" if "role" in user_columns else "'medtech'"
    select_password_hash = "password_hash" if "password_hash" in user_columns else "NULL"
    select_avatar_path = "avatar_path" if "avatar_path" in user_columns else "NULL"
    select_avatar_original_filename = (
        "avatar_original_filename" if "avatar_original_filename" in user_columns else "NULL"
    )
    select_avatar_mime_type = "avatar_mime_type" if "avatar_mime_type" in user_columns else "NULL"
    if "status" in user_columns:
        select_status = "status"
    elif "is_active" in user_columns:
        select_status = "CASE WHEN is_active THEN 'active' ELSE 'disabled' END"
    else:
        select_status = "'pending'"
    select_must_change_password = "must_change_password" if "must_change_password" in user_columns else "0"
    select_created_at = "created_at" if "created_at" in user_columns else "CURRENT_TIMESTAMP"
    select_updated_at = "updated_at" if "updated_at" in user_columns else "CURRENT_TIMESTAMP"

    connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        connection.exec_driver_sql(
            """
            CREATE TABLE users_new (
                id INTEGER NOT NULL PRIMARY KEY,
                email VARCHAR(255),
                login_id VARCHAR(120) NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                role VARCHAR(40) NOT NULL,
                password_hash VARCHAR(255),
                status VARCHAR(40) NOT NULL,
                must_change_password BOOLEAN NOT NULL,
                avatar_path TEXT,
                avatar_original_filename VARCHAR(255),
                avatar_mime_type VARCHAR(120),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            f"""
            INSERT INTO users_new (
                id,
                email,
                login_id,
                full_name,
                role,
                password_hash,
                status,
                must_change_password,
                avatar_path,
                avatar_original_filename,
                avatar_mime_type,
                created_at,
                updated_at
            )
            SELECT
                id,
                {select_email},
                {select_login_id},
                {select_full_name},
                {select_role},
                {select_password_hash},
                {select_status},
                {select_must_change_password},
                {select_avatar_path},
                {select_avatar_original_filename},
                {select_avatar_mime_type},
                {select_created_at},
                {select_updated_at}
            FROM users
            """
        )
        connection.exec_driver_sql("DROP TABLE users")
        connection.exec_driver_sql("ALTER TABLE users_new RENAME TO users")
        connection.exec_driver_sql("CREATE UNIQUE INDEX ix_users_email ON users (email)")
        connection.exec_driver_sql("CREATE UNIQUE INDEX ix_users_login_id ON users (login_id)")
    finally:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def ensure_runtime_schema() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(form_versions)").all()
        }
        if "block_schema_json" not in columns:
            connection.exec_driver_sql("ALTER TABLE form_versions ADD COLUMN block_schema_json TEXT")
        form_definition_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(form_definitions)").all()
        }
        if "library_parent_node_key" not in form_definition_columns:
            connection.exec_driver_sql("ALTER TABLE form_definitions ADD COLUMN library_parent_node_key TEXT")
        form_definition_info = {
            str(row[1]): row
            for row in connection.exec_driver_sql("PRAGMA table_info(form_definitions)").all()
        }
        needs_tree_first_rebuild = any(
            column in form_definition_info
            for column in ("group_name", "group_kind", "common_field_set_id", "group_order", "form_order")
        )
        if needs_tree_first_rebuild:
            migrate_form_definitions_tree_first_shape(connection)
        user_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(users)").all()
        }
        needs_user_auth_rebuild = any(
            column not in user_columns
            for column in ("email", "login_id", "full_name", "status", "must_change_password")
        ) or any(
            legacy_column in user_columns
            for legacy_column in ("username", "display_name", "is_active")
        )
        if needs_user_auth_rebuild:
            migrate_users_auth_shape(connection)
            user_columns = {
                str(row[1])
                for row in connection.exec_driver_sql("PRAGMA table_info(users)").all()
            }
        avatar_columns = {
            "avatar_path": "TEXT",
            "avatar_original_filename": "VARCHAR(255)",
            "avatar_mime_type": "VARCHAR(120)",
        }
        for column_name, column_type in avatar_columns.items():
            if column_name not in user_columns:
                connection.exec_driver_sql(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
