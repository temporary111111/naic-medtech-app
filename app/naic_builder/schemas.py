from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FormSavePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    slug: str | None = None
    name: str = ""
    location_name: str | None = None
    library_parent_node_key: str | None = None
    library_new_container_name: str | None = None
    summary: str | None = None
    form_schema: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_block_schema(self) -> "FormSavePayload":
        if self.form_schema and "blocks" not in self.form_schema:
            raise ValueError("form_schema must use the block-based builder shape.")
        return self


class PrintPreviewPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str = ""
    location_name: str | None = None
    form_schema: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_block_schema(self) -> "PrintPreviewPayload":
        if self.form_schema and "blocks" not in self.form_schema:
            raise ValueError("form_schema must use the block-based builder shape.")
        return self


class RecordCreatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    form_slug: str = ""
    patient_name: str | None = None
    patient_age: str | None = None
    patient_sex: str | None = None
    case_number: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)
    indexed_meta: dict[str, Any] = Field(default_factory=dict)


class RecordUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    patient_name: str | None = None
    patient_age: str | None = None
    patient_sex: str | None = None
    case_number: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)
    indexed_meta: dict[str, Any] = Field(default_factory=dict)


class AccountRequestPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str = ""
    email: str = ""
    login_id: str | None = None
    password: str = ""


class UserCreatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str = ""
    email: str = ""
    login_id: str | None = None
    role: str = "medtech"
    password: str = ""


class ClinicProfilePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    clinic_name: str = ""
    address: str | None = None
    contact_number: str | None = None
    contact_email: str | None = None
    doh_license_number: str | None = None


class LoginPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    identifier: str = ""
    password: str = ""


class PasswordChangePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    current_password: str = ""
    new_password: str = ""


class SetupAdminPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str = ""
    email: str = ""
    login_id: str | None = None
    password: str = ""
