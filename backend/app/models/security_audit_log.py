from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, Text, func

from app.core.database import Base


class SecurityAuditLog(Base):
    """변조 위험을 줄이기 위해 갱신 없이 추가만 하는 보안 감사 기록입니다."""

    __tablename__ = "security_audit_log"
    __table_args__ = (
        Index("ix_security_audit_created_event", "created_at", "event_type"),
        Index("ix_security_audit_actor_created", "actor_user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    event_type = Column(String(64), nullable=False, index=True)
    outcome = Column(String(16), nullable=False)
    actor_user_id = Column(Integer, nullable=True)
    actor_key = Column(String(255), nullable=True)
    resource_type = Column(String(64), nullable=True)
    resource_id = Column(String(255), nullable=True)
    request_id = Column(String(128), nullable=True)
    client_ip = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    detail = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
