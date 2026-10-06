from annotationlib import Format
from inspect import signature

from src import inventory_dump


def test_public_scan_interface_exposes_only_format_and_runtime_controls() -> None:
    assert set(inventory_dump.__all__) == {"ExportFormat", "ScanProgress", "ScanResult", "scan_inventory"}
    parameters = signature(inventory_dump.scan_inventory, annotation_format=Format.STRING).parameters
    assert tuple(parameters) == ("output_format", "cancel", "on_progress")
    assert {choice.value for choice in inventory_dump.ExportFormat} == {"json", "md", "txt"}
