from typing import Any
from sqlalchemy import JSON, ForeignKey, Integer, String, Text, Float, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class Journey(Base):
    __tablename__ = 'lf_journeys'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    goal: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)


class Document(Base):
    __tablename__ = 'lf_documents'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    journey_id: Mapped[int] = mapped_column(Integer, ForeignKey('lf_journeys.id'), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    passages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)


class Activity(Base):
    __tablename__ = 'lf_activities'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    journey_id: Mapped[int] = mapped_column(Integer, ForeignKey('lf_journeys.id'), nullable=False)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class Attempt(Base):
    __tablename__ = 'lf_attempts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(Integer, ForeignKey('lf_activities.id'), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    feedback: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


# Additive tables preserve existing prototype records without destructive migrations.
class User(Base):
    __tablename__ = 'lf_users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)


class AdminRole(Base):
    __tablename__ = 'lf_admin_roles'
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('lf_users.id'), primary_key=True)


class DocumentTree(Base):
    __tablename__ = 'lf_document_trees'
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey('lf_documents.id'), primary_key=True)
    tree_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    n_value: Mapped[int] = mapped_column(Integer, nullable=False, default=5)


class IngestionCheckpoint(Base):
    __tablename__ = 'lf_ingestion_checkpoints'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    state_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class LoginSession(Base):
    __tablename__ = 'lf_login_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('lf_users.id'), nullable=False)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)


class Ownership(Base):
    __tablename__ = 'lf_journey_ownership'
    journey_id: Mapped[int] = mapped_column(Integer, ForeignKey('lf_journeys.id'), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('lf_users.id'), nullable=False, index=True)


class JourneyState(Base):
    __tablename__ = 'lf_journey_state'
    journey_id: Mapped[int] = mapped_column(Integer, ForeignKey('lf_journeys.id'), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plan_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plan_status: Mapped[str] = mapped_column(String, nullable=False, default='empty')


class Topic(Base):
    __tablename__ = 'lf_topics'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    journey_id: Mapped[int] = mapped_column(Integer, ForeignKey('lf_journeys.id'), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class AttemptMeta(Base):
    __tablename__ = 'lf_attempt_metadata'
    attempt_id: Mapped[int] = mapped_column(Integer, ForeignKey('lf_attempts.id'), primary_key=True)
    submission_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)


class ChatMessage(Base):
    __tablename__ = 'lf_chat_messages'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    journey_id: Mapped[int] = mapped_column(Integer, ForeignKey('lf_journeys.id'), nullable=False, index=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class SourceReview(Base):
    __tablename__ = 'lf_source_reviews'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    journey_id: Mapped[int] = mapped_column(Integer, ForeignKey('lf_journeys.id'), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False, default='pending')
    note: Mapped[str] = mapped_column(Text, nullable=False, default='')


class DocumentIngestion(Base):
    __tablename__ = 'lf_document_ingestion'
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey('lf_documents.id'), primary_key=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='queued', index=True)
    progress: Mapped[str] = mapped_column(Text, nullable=False, default='Waiting to process')
    error: Mapped[str] = mapped_column(Text, nullable=False, default='')
    request_reference: Mapped[str] = mapped_column(String(36), nullable=False, default='')
    plan_error: Mapped[str] = mapped_column(Text, nullable=False, default='')
    plan_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    configuration: Mapped[str] = mapped_column(String(64), nullable=False, default='')
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)


class IngestionMessage(Base):
    """Transactional outbox: committed uploads cannot lose their queue message."""
    __tablename__ = 'lf_ingestion_messages'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    delayed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
