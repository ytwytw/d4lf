from src.utils.roi_operations import fit_roi_to_window_size


def test_fit_roi_clips_negative_origin_without_expanding_visible_area() -> None:
    assert fit_roi_to_window_size((-30, -20, 100, 80), (1920, 1080)) == (True, (0, 0, 70, 60))


def test_fit_roi_rejects_regions_entirely_outside_left_or_top_edge() -> None:
    assert fit_roi_to_window_size((-100, 10, 50, 20), (1920, 1080)) == (False, None)
    assert fit_roi_to_window_size((10, -100, 20, 50), (1920, 1080)) == (False, None)
