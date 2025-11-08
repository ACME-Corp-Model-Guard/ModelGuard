"""
Type definitions for the artifact system.
"""

from typing import Literal

# Strictly define allowed artifact types
ArtifactType = Literal["model", "dataset", "code"]
