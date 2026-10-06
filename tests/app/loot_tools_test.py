from src.app.shell import UnifiedMainWindow


def test_profile_tools_retain_selected_profile_and_separate_document_windows(mocker):
    window = UnifiedMainWindow.__new__(UnifiedMainWindow)
    show = mocker.patch.object(window, "_show_singleton_modal")
    window.open_native_filter("variant_a")
    window.open_native_filter("variant_b")
    window.open_equipment_knowledge("variant_a")
    keys = [call.args[0] for call in show.call_args_list]
    assert keys == ["native_filter:variant_a", "native_filter:variant_b", "equipment_knowledge:variant_a"]
    assert [call.kwargs["profile_name"] for call in show.call_args_list] == ["variant_a", "variant_b", "variant_a"]


def test_standalone_tools_do_not_require_an_active_profile(mocker):
    window = UnifiedMainWindow.__new__(UnifiedMainWindow)
    show = mocker.patch.object(window, "_show_singleton_modal")
    window.open_native_filter()
    window.open_equipment_knowledge()
    assert all(call.kwargs["profile_name"] is None for call in show.call_args_list)
