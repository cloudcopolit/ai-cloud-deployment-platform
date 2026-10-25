"""CloudPilot AI layer.

Import direction is one way: the backend imports this package; this package never
imports the backend and never touches the database (ADR-009).
"""

from cloudpilot_ai.contracts import SCHEMA_VERSION

__all__ = ["SCHEMA_VERSION"]
