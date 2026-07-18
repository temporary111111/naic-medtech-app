from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FormDefinition(Base):
    __tablename__ = "form_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    library_parent_node_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    versions: Mapped[list["FormVersion"]] = relationship(
        back_populates="form",
        cascade="all, delete-orphan",
        order_by="FormVersion.version_number",
    )
    library_node: Mapped["LibraryNode | None"] = relationship(
        back_populates="form_definition",
        uselist=False,
    )
    records: Mapped[list["Record"]] = relationship(
        back_populates="form",
        cascade="all, delete-orphan",
        order_by="Record.updated_at",
    )


class FormVersion(Base):
    __tablename__ = "form_versions"
    __table_args__ = (UniqueConstraint("form_id", "version_number", name="uq_form_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    form_id: Mapped[int] = mapped_column(ForeignKey("form_definitions.id"))
    version_number: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_json: Mapped[str] = mapped_column(Text)
    block_schema_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="builder")
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    form: Mapped[FormDefinition] = relationship(back_populates="versions")
    records: Mapped[list["Record"]] = relationship(back_populates="form_version")


class LibraryNode(Base):
    __tablename__ = "library_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(255))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("library_nodes.id"), nullable=True)
    node_order: Mapped[int] = mapped_column(Integer, default=1)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    form_definition_id: Mapped[int | None] = mapped_column(
        ForeignKey("form_definitions.id"),
        nullable=True,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    parent: Mapped["LibraryNode | None"] = relationship(
        "LibraryNode",
        remote_side="LibraryNode.id",
        back_populates="children",
    )
    children: Mapped[list["LibraryNode"]] = relationship(
        "LibraryNode",
        back_populates="parent",
    )
    form_definition: Mapped[FormDefinition | None] = relationship(
        back_populates="library_node",
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    login_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), default="medtech")
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    created_records: Mapped[list["Record"]] = relationship(
        back_populates="created_by_user",
        foreign_keys="Record.created_by_user_id",
    )
    updated_records: Mapped[list["Record"]] = relationship(
        back_populates="updated_by_user",
        foreign_keys="Record.updated_by_user_id",
    )


class ClinicProfile(Base):
    __tablename__ = "clinic_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_name: Mapped[str] = mapped_column(String(255), default="")
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    doh_license_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    form_id: Mapped[int] = mapped_column(ForeignKey("form_definitions.id"), index=True)
    form_version_id: Mapped[int] = mapped_column(ForeignKey("form_versions.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    patient_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    case_number: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    values_json: Mapped[str] = mapped_column(Text, default="{}")
    indexed_meta_json: Mapped[str] = mapped_column(Text, default="{}")
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    form: Mapped[FormDefinition] = relationship(back_populates="records")
    form_version: Mapped[FormVersion] = relationship(back_populates="records")
    created_by_user: Mapped["User | None"] = relationship(
        back_populates="created_records",
        foreign_keys=[created_by_user_id],
    )
    updated_by_user: Mapped["User | None"] = relationship(
        back_populates="updated_records",
        foreign_keys=[updated_by_user_id],
    )
    assets: Mapped[list["RecordAsset"]] = relationship(
        back_populates="record",
        cascade="all, delete-orphan",
        order_by="RecordAsset.created_at",
    )


class RecordAsset(Base):
    __tablename__ = "record_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("records.id"), index=True)
    field_block_id: Mapped[str] = mapped_column(String(255), index=True)
    field_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    kind: Mapped[str] = mapped_column(String(40), default="image")
    storage_path: Mapped[str] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    record: Mapped[Record] = relationship(back_populates="assets")
