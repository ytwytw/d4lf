"""D2Core source adapter facade."""

from src.importing.d2core.adapter import (
    D2CoreImportError,
    extract_d2core_share_code,
    fetch_variants_d2core,
    import_d2core,
)

__all__ = ["D2CoreImportError", "extract_d2core_share_code", "fetch_variants_d2core", "import_d2core"]
