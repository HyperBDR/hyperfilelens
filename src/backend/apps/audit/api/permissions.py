"""
Audit API permissions (tenant read access).
"""

from apps.iam.permissions_org import IsOrgReader

AuditOrgPermission = IsOrgReader
