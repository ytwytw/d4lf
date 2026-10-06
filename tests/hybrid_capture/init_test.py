from src import hybrid_capture


def test_experiment_exposes_evidence_api_without_game_capture_controls() -> None:
    assert set(hybrid_capture.__all__) == {
        "Candidate",
        "CaptureContext",
        "Identity",
        "compare_identity",
        "fuse_evidence",
    }
    assert not hasattr(hybrid_capture, "scan_inventory")
    assert not hasattr(hybrid_capture, "capture_screen")
