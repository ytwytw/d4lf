from src.overlay.widget.menu_content import _OverlayMenuContent


def test_menu_content_exposes_each_submenu_builder() -> None:
    assert callable(_OverlayMenuContent._build_gold_submenu_content)
    assert callable(_OverlayMenuContent._build_exp_submenu_content)
    assert callable(_OverlayMenuContent._build_reset_submenu_content)
