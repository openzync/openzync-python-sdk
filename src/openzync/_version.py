"""Version information for openzync.

This module is intentionally import-free so it can be imported
anywhere without circular dependency issues.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _metadata_version

try:
    __version__ = _metadata_version("openzync")
except PackageNotFoundError as err:
    # No silent "0.0.0" fallback: a fake version would propagate into the
    # User-Agent and X-SDK-Version headers, misidentifying the client to
    # the backend. Fail loudly so a broken install is fixed, not masked.
    raise RuntimeError(
        "openzync package metadata not found; reinstall the package "
        "(pip install openzync) instead of importing from an unpackaged tree"
    ) from err
