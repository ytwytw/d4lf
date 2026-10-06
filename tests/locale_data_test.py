from src.locale_data import LocaleGrammar, canonical_text_key, normalize_locale_text


def test_normalize_locale_text_preserves_cjk_and_normalizes_width() -> None:
    assert normalize_locale_text("  ＋７９ 点 智力\xa0") == "+79 点 智力"
    assert canonical_text_key("祖父 （暗金）") == "祖父_暗金"


def test_locale_grammar_ignores_blank_terms() -> None:
    grammar = LocaleGrammar.from_dict(
        "zhCN",
        {"labels": {"ancestral": ["", "  "]}, "identifiers": {"NIGHTMARE_SIGIL": ""}, "rarities": {"Unique": [""]}},
    )

    assert not grammar.contains("ancestral", "未知物品")
    assert not grammar.identifier_matches("NIGHTMARE_SIGIL", "未知物品")
    assert grammar.rarity_name("未知物品") is None
