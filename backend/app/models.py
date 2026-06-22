import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


class Role(str, enum.Enum):
    admin = "admin"
    engineer = "engineer"
    customer = "customer"


class StatusType(str, enum.Enum):
    not_received = "not_received"
    received = "received"
    counted = "counted"
    feedback = "feedback"


JsonType = JSON().with_variant(JSONB, "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.engineer, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    scopes: Mapped[list["AccessScope"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AccessScope(Base):
    __tablename__ = "access_scopes"
    __table_args__ = (UniqueConstraint("user_id", "customer_id", "project_id", name="uq_scope_user_customer_project"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customer_snapshots.id", ondelete="CASCADE"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("project_snapshots.id", ondelete="CASCADE"), nullable=True)
    can_write: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="scopes")


class CustomerSnapshot(TimestampMixin, Base):
    __tablename__ = "customer_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    oracle_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(380), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    projects: Mapped[list["CustomerProject"]] = relationship(back_populates="customer")


class ProjectSnapshot(TimestampMixin, Base):
    __tablename__ = "project_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    optypes: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customers: Mapped[list["CustomerProject"]] = relationship(back_populates="project")


class CustomerProject(TimestampMixin, Base):
    __tablename__ = "customer_projects"
    __table_args__ = (UniqueConstraint("customer_id", "project_id", name="uq_customer_project"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer_snapshots.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project_snapshots.id", ondelete="CASCADE"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    customer: Mapped[CustomerSnapshot] = relationship(back_populates="projects")
    project: Mapped[ProjectSnapshot] = relationship(back_populates="customers")
    expected_reports: Mapped[list["ExpectedReport"]] = relationship(back_populates="customer_project")


class OracleDictionaryQuery(TimestampMixin, Base):
    __tablename__ = "oracle_dictionary_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    sql_text: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class DictionaryItem(TimestampMixin, Base):
    __tablename__ = "dictionary_items"
    __table_args__ = (UniqueConstraint("kind", "external_id", "name", name="uq_dictionary_kind_external_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(80), index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict] = mapped_column(JsonType, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExpectedReport(TimestampMixin, Base):
    __tablename__ = "expected_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_project_id: Mapped[int] = mapped_column(ForeignKey("customer_projects.id", ondelete="CASCADE"), index=True)
    country_id: Mapped[int | None] = mapped_column(ForeignKey("dictionary_items.id"), nullable=True)
    data_type_id: Mapped[int | None] = mapped_column(ForeignKey("dictionary_items.id"), nullable=True)
    distributor_id: Mapped[int | None] = mapped_column(ForeignKey("dictionary_items.id"), nullable=True)
    period: Mapped[date] = mapped_column(Date, index=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    customer_project: Mapped[CustomerProject] = relationship(back_populates="expected_reports")
    country: Mapped[DictionaryItem | None] = relationship(foreign_keys=[country_id])
    data_type: Mapped[DictionaryItem | None] = relationship(foreign_keys=[data_type_id])
    distributor: Mapped[DictionaryItem | None] = relationship(foreign_keys=[distributor_id])
    files: Mapped[list["UploadedFile"]] = relationship(back_populates="expected_report")


class UploadedFile(TimestampMixin, Base):
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    expected_report_id: Mapped[int] = mapped_column(ForeignKey("expected_reports.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(512))
    stored_filename: Mapped[str] = mapped_column(String(512), unique=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(128), index=True)
    storage_path: Mapped[str] = mapped_column(String(1024))
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pack_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    status: Mapped[StatusType] = mapped_column(Enum(StatusType), default=StatusType.received, index=True)

    expected_report: Mapped[ExpectedReport] = relationship(back_populates="files")
    comments: Mapped[list["FileComment"]] = relationship(back_populates="file", cascade="all, delete-orphan")
    status_events: Mapped[list["FileStatusEvent"]] = relationship(back_populates="file", cascade="all, delete-orphan")


class FileStatusEvent(Base):
    __tablename__ = "file_status_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int | None] = mapped_column(ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=True, index=True)
    expected_report_id: Mapped[int | None] = mapped_column(ForeignKey("expected_reports.id", ondelete="CASCADE"), nullable=True)
    event_type: Mapped[StatusType] = mapped_column(Enum(StatusType), index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    file: Mapped[UploadedFile | None] = relationship(back_populates="status_events")


class FileComment(Base):
    __tablename__ = "file_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("uploaded_files.id", ondelete="CASCADE"), index=True)
    comment: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    file: Mapped[UploadedFile] = relationship(back_populates="comments")

class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity: Mapped[str] = mapped_column(String(120), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

