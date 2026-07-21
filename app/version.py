"""
Semantic Versioning Core
Usage: 
  - Patch (1.0.1): Bug fixes, UI patches.
  - Minor (1.1.0): New features, new endpoints, enhanced workflows.
  - Major (2.0.0): Breaking schema changes, major rewrites.
"""

APP_VERSION = "1.1.0"

def get_version() -> str:
    return APP_VERSION