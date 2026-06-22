from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import Role, StatusType


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    active: bool


class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str = Field(min_length=8)
    role: Role = Role.engineer
    active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=8)
    role: Role | None = None
    active: bool | None = None


class AccessScopeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    customer_id: int | None = None
    project_id: int | None = None
    can_write: bool


class AccessScopeCreate(BaseModel):
    customer_id: int | None = None
    project_id: int | None = None
    can_write: bool = False


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    oracle_id: int
    name: str
    code: str
    display_name: str
    active: bool


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    optypes: str
    active: bool


class CustomerProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    active: bool
    customer: CustomerRead
    project: ProjectRead


class CustomerProjectUpdate(BaseModel):
    active: bool


class OracleDictionaryQueryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    sql_text: str
    active: bool
    last_error: str | None = None


class OracleDictionaryQueryUpdate(BaseModel):
    sql_text: str
    active: bool = True


class DictionaryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    external_id: str | None = None
    name: str
    code: str | None = None
    active: bool


class ExpectedReportCreate(BaseModel):
    customer_project_id: int
    country_id: int | None = None
    data_type_id: int | None = None
    distributor_id: int | None = None
    period: date
    deadline: date | None = None
    active: bool = True

    @field_validator("period")
    @classmethod
    def period_must_be_month_start(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("period must be the first day of a month, for example 2026-06-01")
        return value


class ExpectedReportUpdate(BaseModel):
    country_id: int | None = None
    data_type_id: int | None = None
    distributor_id: int | None = None
    period: date | None = None
    deadline: date | None = None
    active: bool | None = None

    @field_validator("period")
    @classmethod
    def period_must_be_month_start(cls, value: date | None) -> date | None:
        if value and value.day != 1:
            raise ValueError("period must be the first day of a month, for example 2026-06-01")
        return value


class UploadedFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    content_type: str | None
    file_size: int
    checksum: str
    uploaded_at: datetime
    row_count: int | None
    pack_count: int | None
    comment: str | None
    active: bool
    status: StatusType


class ExpectedReportRead(BaseModel):
    id: int
    customer_project: CustomerProjectRead
    country: DictionaryItemRead | None = None
    data_type: DictionaryItemRead | None = None
    distributor: DictionaryItemRead | None = None
    period: date
    deadline: date | None = None
    active: bool
    status: StatusType
    files: list[UploadedFileRead] = []


class FileMetadataUpdate(BaseModel):
    row_count: int | None = Field(default=None, ge=0)
    pack_count: int | None = Field(default=None, ge=0)
    comment: str | None = None
    active: bool | None = None


class FeedbackCreate(BaseModel):
    comment: str = Field(min_length=1)


class CommentCreate(BaseModel):
    comment: str = Field(min_length=1)


class SyncResult(BaseModel):
    key: str
    synced: int = 0
    matrix_created: int = 0
    warning: str | None = None
