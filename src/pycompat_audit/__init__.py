"""Audit Python package compatibility metadata against CI coverage."""

from .audit import AuditIssue, AuditResult, audit_repository

__all__ = ["AuditIssue", "AuditResult", "audit_repository"]
__version__ = "0.2.0"
