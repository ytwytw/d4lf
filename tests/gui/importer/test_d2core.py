import json
from types import SimpleNamespace

import pytest

from src.dataloader import Dataloader
from src.gui.importer.d2core import (
    D2CoreCatalog,
    _catalog_build_versions,
    _convert_mods_to_affixes,
    _d2core_affix_aliases,
    _index_affix_aliases,
    extract_d2core_share_code,
    import_d2core,
)
from src.gui.importer.importer_config import ImportConfig
from src.item.data.affix import AffixType
from src.item.data.item_type import ItemType


class _ImmediateWait:
    def __init__(self, driver, _timeout):
        self.driver = driver

    def until(self, method):
        result = method(self.driver)
        if not result:
            message = "fake wait condition did not pass"
            raise AssertionError(message)
        return result


class _D2CoreDriver:
    def __init__(self, build):
        self.build = build
        self.loaded_url = None
        self.share_code = None
        self.quit_called = False

    def get(self, url):
        self.loaded_url = url

    def execute_script(self, script):
        if "window.cloudbase" in script:
            return True
        if "performance.getEntriesByType" in script:
            return ["https://cloudstorage.d2core.com/data/d4/72698/affix_zhCN.json?env=prod&v=8"]
        message = f"unexpected script: {script}"
        raise AssertionError(message)

    def execute_async_script(self, script, share_code):
        assert "function-planner-queryplandetail" in script
        self.share_code = share_code
        return {"ok": True, "data": self.build}

    def quit(self):
        self.quit_called = True


def _response(payload) -> SimpleNamespace:
    return SimpleNamespace(content=json.dumps(payload).encode())


def _catalog_responses():
    return {
        "affix": _response({
            "affix": [
                {"key": "S04_CoreStat_Intelligence", "id": 1, "descTpl": "[{VALUE}] Intelligence"},
                {"key": "X2_Armor_Greater", "id": 2, "descTpl": "+[{VALUE}] Armor", "desc": "+[1 - 3] Armor"},
                {"key": "S04_Damage_All", "id": 3, "descTpl": "x[{VALUE}*100|%|] All Damage Multiplier"},
                {"key": "S04_CooldownReductionCDR", "id": 4, "descTpl": "[{VALUE}*100|%|] Cooldown Reduction"},
                {"key": "Tempered_Generic_LifeMax_Tier3", "id": 5, "descTpl": "+[{VALUE}] Maximum Life"},
            ]
        }),
        "aspect": _response([
            {"key": "Affix_legendary_sorc_008_x2", "id": 11, "name": "Aspect of the Untarnished Blaze"},
            {"key": "Affix_legendary_burningUser_001_x2", "id": 12, "name": "Overheating Aspect"},
        ]),
        "uniqueItem": _response([{"key": "Ring_Unique_Sorc_104_x2", "id": 21, "name": "Drognan's Anguish"}]),
    }


def _build_payload():
    return {
        "title": "S14 Firewall Sorcerer",
        "char": "Sorcerer",
        "season": 14,
        "variants": [
            {
                "name": "Endgame",
                "gear": {
                    "1": {
                        "type": "legendary",
                        "itemType": "ChestArmor",
                        "key": "Affix_legendary_sorc_008_x2",
                        "transfiguredAspect": "Affix_legendary_burningUser_001_x2",
                        "mods": [
                            {"name": "S04_CoreStat_Intelligence", "value": 121},
                            {"name": "X2_Armor_Greater", "value": 2450},
                            {"name": "Unsupported_Greater", "value": 10},
                            {"name": "Tempered_Generic_LifeMax_Tier3", "value": 1500, "greater": True},
                        ],
                    },
                    "9": {
                        "type": "uniqueItem",
                        "itemType": "Ring",
                        "key": "Ring_Unique_Sorc_104_x2",
                        "name": "卓格楠的苦闷",
                        "mods": [{"name": "S04_CooldownReductionCDR", "value": 0.08}],
                    },
                },
            },
            {"name": "Guide Notes", "gear": {}},
            {
                "name": "Speedfarm",
                "gear": {
                    "2": {
                        "type": "legendary",
                        "itemType": "Gloves",
                        "key": "Affix_legendary_sorc_008_x2",
                        "mods": [{"name": "S04_Damage_All", "value": 0.1}],
                    }
                },
            },
        ],
    }


@pytest.mark.parametrize(
    "url", ["https://www.d2core.com/d4/planner?bd=20eK", "http://d2core.com/d4/planner/?foo=1&bd=abc_123-Z"]
)
def test_extract_d2core_share_code(url: str) -> None:
    assert extract_d2core_share_code(url) in {"20eK", "abc_123-Z"}


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/d4/planner?bd=20eK",
        "https://notd2core.com/d4/planner?bd=20eK",
        "https://www.d2core.com/d4/builds?bd=20eK",
        "https://www.d2core.com/d4/planner",
        "https://www.d2core.com/d4/planner?bd=bad%20code",
        "https://www.d2core.com/d4/planner?bd=one&bd=two",
    ],
)
def test_extract_d2core_share_code_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(ValueError, match="Invalid URL|must contain"):
        extract_d2core_share_code(url)


def test_catalog_build_versions_reads_only_d2core_data_resources() -> None:
    urls = [
        "https://cloudstorage.d2core.com/data/d4/72698/affix_zhCN.json?env=prod&v=8",
        "https://cloudstorage.d2core.com/data/d4/72698/uniqueItem_enUS.json",
        "https://www.d2core.com/assets/index.js",
        42,
    ]

    assert _catalog_build_versions(urls) == {"72698"}


def test_d2core_affix_aliases_remove_formulas_and_multiplier_marker() -> None:
    aliases = _d2core_affix_aliases("x[{VALUE}*100|%|] All Damage Multiplier", "S04_Damage_All")

    assert "x All Damage Multiplier" in aliases
    assert "All Damage Multiplier" in aliases


def test_index_affix_aliases_uses_resolved_description_for_plural_labels() -> None:
    aliases = _index_affix_aliases([
        {
            "key": "X2_Evade_Charges",
            "descTpl": "+[{VALUE}] Maximum Evade Charge",
            "desc": "+[1 - 3] Maximum Evade Charges",
        }
    ])

    assert "Maximum Evade Charges" in aliases["X2_Evade_Charges"]


def test_convert_mods_uses_english_catalog_independent_of_active_language(mocker) -> None:
    dataloader = Dataloader()
    mocker.patch.object(dataloader, "affix_dict", {"intelligence": "智力", "armor": "护甲"})
    catalog = D2CoreCatalog(
        build_version="72698",
        affix_aliases={
            "S04_CoreStat_Intelligence": ("Intelligence",),
            "X2_Armor_Greater": ("Armor",),
            "Tempered_Generic_LifeMax_Tier3": ("Maximum Life",),
        },
        aspect_names={},
        unique_names={},
    )

    affixes = _convert_mods_to_affixes(
        [
            {"name": "S04_CoreStat_Intelligence"},
            {"name": "X2_Armor_Greater"},
            {"name": "Tempered_Generic_LifeMax_Tier3", "greater": True},
        ],
        ItemType.Helm,
        catalog,
        import_greater_affixes=True,
    )

    assert [(affix.name, affix.type) for affix in affixes] == [
        ("armor", AffixType.greater),
        ("intelligence", AffixType.normal),
    ]


def test_import_d2core_maps_variants_affixes_uniques_and_aspects(mock_ini_loader, mocker) -> None:
    Dataloader()
    driver = _D2CoreDriver(_build_payload())
    mocker.patch("src.gui.importer.d2core.WebDriverWait", _ImmediateWait)
    responses = _catalog_responses()

    def fake_get(url):
        dataset = next(name for name in responses if f"/{name}_enUS.json" in url)
        return responses[dataset]

    get_with_retry = mocker.patch("src.gui.importer.d2core.get_with_retry", side_effect=fake_get)
    saved = []

    def fake_save_new(*, file_name, profile, source):
        saved.append({"file_name": file_name, "profile": profile, "source": source})
        return SimpleNamespace(file_name=file_name)

    profile_store = mocker.Mock()
    profile_store.save_new.side_effect = fake_save_new
    mocker.patch("src.gui.importer.import_pipeline.ProfileDocumentStore.default", return_value=profile_store)

    result = import_d2core(
        config=ImportConfig(
            url="https://www.d2core.com/d4/planner?bd=20eK",
            import_aspect_upgrades=True,
            add_to_profiles=False,
            import_greater_affixes=True,
            require_greater_affixes=True,
            export_paragon=False,
            custom_file_name="d2core-test",
        ),
        driver=driver,
    )

    assert result == ["d2core-test_1", "d2core-test_2"]
    assert driver.loaded_url == "https://www.d2core.com/d4/planner?bd=20eK"
    assert driver.share_code == "20eK"
    assert driver.quit_called
    assert get_with_retry.call_count == 3
    assert [entry["file_name"] for entry in saved] == result
    assert all(entry["source"].endswith("bd=20eK") for entry in saved)

    endgame = saved[0]["profile"]
    assert endgame.aspect_upgrades == ["of_the_untarnished_blaze", "overheating"]
    filters = {next(iter(entry.root)): next(iter(entry.root.values())) for entry in endgame.affixes}
    assert set(filters) == {"ChestArmor", "Ring"}
    chest = filters["ChestArmor"]
    assert [(affix.name, affix.want_greater) for affix in chest.affix_pool[0].count] == [
        ("armor", True),
        ("intelligence", False),
    ]
    assert chest.min_greater_affix_count == 1
    assert filters["Ring"].unique_aspect[0].name == "drognans_anguish"

    speedfarm = saved[1]["profile"]
    assert speedfarm.aspect_upgrades == ["of_the_untarnished_blaze"]
    gloves = next(iter(speedfarm.affixes[0].root.values()))
    assert gloves.affix_pool[0].count[0].name == "all_damage_multiplier"
