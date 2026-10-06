from src.native_filter import Action, NativeFilter


def test_documents_own_their_rules_and_only_enabled_hide_actions_count():
    first, second = NativeFilter(), NativeFilter()
    first.rules[0].action = Action.HIDE_LABEL
    assert first.hides_items
    assert not second.hides_items
    first.rules[0].enabled = False
    assert not first.hides_items
