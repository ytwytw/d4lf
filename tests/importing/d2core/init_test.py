from src.importing.d2core import D2CoreImportError, extract_d2core_share_code, fetch_variants_d2core, import_d2core


def test_d2core_facade_exports_adapter_contract() -> None:
    assert issubclass(D2CoreImportError, RuntimeError)
    assert extract_d2core_share_code("https://www.d2core.com/d4/planner?bd=20eK") == "20eK"
    assert callable(fetch_variants_d2core)
    assert callable(import_d2core)
