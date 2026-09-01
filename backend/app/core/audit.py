"""Compatibility import for the Identity-owned security audit operation."""

from app.identity.audit import record_security_event

__all__ = ["record_security_event"]
