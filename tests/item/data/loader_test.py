import json
import threading
from types import SimpleNamespace

import pytest

from src.importing.d2core import catalog as d2core_catalog
from src.item.data import loader as loader_module
from src.item.data.item_type import ItemType
from src.item.data.loader import Dataloader
from src.item.data.localized_maps import load_localized_nested_string_map, load_string_map


class _LoaderFailure(BaseException):
    pass


def _load_zhcn_catalog(monkeypatch) -> Dataloader:
    settings = SimpleNamespace(general=SimpleNamespace(language="zhCN"))
    monkeypatch.setattr(loader_module, "get_settings", lambda: settings)
    catalog = object.__new__(Dataloader)
    catalog.load_data()
    return catalog


def test_dataloader_has_expected_data_containers():
    assert isinstance(Dataloader.affix_dict, dict)
    assert isinstance(Dataloader.aspect_list, list)


def test_zhcn_catalog_loads_all_runtime_aliases(monkeypatch) -> None:
    catalog = _load_zhcn_catalog(monkeypatch)

    assert catalog.resolve_affix("闪避给予的移动速度，持续 秒") == "evade_grants_movement_speed_for_seconds"
    assert catalog.resolve_tribute("巨人贡品") == "tribute_of_titans"
    assert catalog.resolve_item_type("胸甲") == "ChestArmor"
    assert catalog.resolve_unique("命运之拳") == "fists_of_fate"


def test_zhcn_catalog_contains_only_production_seal_keys(monkeypatch) -> None:
    catalog = _load_zhcn_catalog(monkeypatch)
    language_root = loader_module.BASE_DIR / "assets" / "lang"
    english = load_string_map(language_root / "enUS" / "seals_affixes.json")
    chinese = load_string_map(language_root / "zhCN" / "seals_affixes.json")

    assert len(english) == 305
    assert english.keys() == chinese.keys() == catalog.seal_affix_dict.keys()


def test_zhcn_catalog_uses_english_for_unresolved_production_text(monkeypatch) -> None:
    catalog = _load_zhcn_catalog(monkeypatch)
    english = loader_module.BASE_DIR / "assets" / "lang" / "enUS"
    english_sigils = load_localized_nested_string_map(english, "sigils.json")
    english_tributes = load_string_map(english / "tributes.json")

    assert catalog.affix_dict["crafting_material_drop_rate"] == "crafting material drop rate"
    assert catalog.charm_affix_dict["crafting_material_drop_rate"] == "crafting material drop rate"
    assert catalog.affix_sigil_dict_all["positive"]["ruptures"] == english_sigils["positive"]["ruptures"]
    assert catalog.tribute_dict["greater_tribute_of_armaments"] == english_tributes["greater_tribute_of_armaments"]


def test_zhcn_production_scope_is_stable_and_explicit() -> None:
    chinese = loader_module.BASE_DIR / "assets" / "lang" / "zhCN"
    flat_files = ("affixes.json", "charms_affixes.json", "seals_affixes.json", "tributes.json")
    resolved = sum(
        sum(bool(value.strip()) for value in load_string_map(chinese / file_name).values()) for file_name in flat_files
    )
    resolved += sum(bool(value.strip()) for value in load_string_map(chinese / "aspects.json").values())
    resolved += sum(bool(value.strip()) for value in load_string_map(chinese / "sets.json").values())
    resolved += sum(bool(value.strip()) for value in load_string_map(chinese / "item_types.json").values())
    unique_data = json.loads((chinese / "uniques.json").read_text(encoding="utf-8"))
    resolved += sum(bool(metadata.get("display_name", "").strip()) for metadata in unique_data.values())
    sigils = json.loads((chinese / "sigils.json").read_text(encoding="utf-8"))
    resolved += sum(
        bool(value.strip())
        for section_name in ("dungeons", "major", "minor", "positive")
        for value in sigils[section_name].values()
    )
    resolved += 1

    report = json.loads((chinese / "quality-report.json").read_text(encoding="utf-8"))
    manifest = json.loads((chinese / "manifest.json").read_text(encoding="utf-8"))
    assert resolved == 2724
    assert report["summary"]["source_records"] == 2742
    assert report["summary"]["unresolved_records"] == 18
    assert resolved + report["summary"]["unresolved_records"] == report["summary"]["source_records"]
    assert report["runtime_ready"] is True
    assert manifest["runtime_ready"] is True


def test_runtime_catalog_does_not_depend_on_d2core_availability(monkeypatch) -> None:
    def unavailable():
        message = "D2Core unavailable"
        raise AssertionError(message)

    monkeypatch.setattr(d2core_catalog, "load_d2core_catalog", unavailable)

    catalog = _load_zhcn_catalog(monkeypatch)

    assert len(catalog.affix_dict) == 877
    assert len(catalog.aspect_dict) == 530
    assert len(catalog.aspect_unique_dict) == 298


def test_zhcn_ambiguous_damage_aliases_use_range_precision(monkeypatch) -> None:
    catalog = _load_zhcn_catalog(monkeypatch)

    assert catalog.resolve_affix_exact("暗影伤害") is None
    assert catalog.resolve_affix_exact("暗影伤害", range_precision="decimal") == "shade_damage"
    assert catalog.resolve_affix_exact("暗影伤害", range_precision="integer") == "shadow_damage"
    assert catalog.resolve_affix_exact("毒素伤害", range_precision="decimal") == "poisoning_damage"
    assert catalog.resolve_affix_exact("毒素伤害", range_precision="integer") == "poison_damage"


def test_loading_zhcn_does_not_mutate_stable_item_type_values(monkeypatch) -> None:
    _load_zhcn_catalog(monkeypatch)

    assert ItemType.ChestArmor.value == "chest armor"
    assert ItemType.Sigil.value == "nightmare sigil"


def test_dataloader_does_not_publish_while_loading(monkeypatch):
    monkeypatch.setattr(Dataloader, "_instance", None)
    monkeypatch.setattr(Dataloader, "data_loaded", False)
    load_started = threading.Event()
    allow_load = threading.Event()
    second_lock_attempted = threading.Event()
    second_returned = threading.Event()
    instances = []
    second_aspect_list = []
    errors = []
    underlying_lock = threading.Lock()
    lock_enter_count = 0
    lock_enter_count_lock = threading.Lock()

    class SignalingLock:
        def __enter__(self):
            nonlocal lock_enter_count
            with lock_enter_count_lock:
                lock_enter_count += 1
                if lock_enter_count == 2:
                    second_lock_attempted.set()
            underlying_lock.acquire()
            return self

        def __exit__(self, _exc_type, _exc_value, _traceback):
            underlying_lock.release()

    def load_data(instance):
        load_started.set()
        if not allow_load.wait(timeout=2):
            message = "timed out waiting to finish loading"
            raise AssertionError(message)
        instance.affix_dict = {"ready": "yes"}
        instance.aspect_list = ["ready"]

    def construct(second=False):
        try:
            instance = Dataloader()
            instances.append(instance)
            if second:
                second_aspect_list.append(instance.aspect_list)
        except Exception as error:  # ruff:ignore[blind-except]
            errors.append(error)
        finally:
            if second:
                second_returned.set()

    monkeypatch.setattr(loader_module, "DATALOADER_LOCK", SignalingLock())
    monkeypatch.setattr(Dataloader, "load_data", load_data)
    first_thread = threading.Thread(target=construct)
    second_thread = None
    try:
        first_thread.start()
        assert load_started.wait(timeout=1)

        second_thread = threading.Thread(target=construct, kwargs={"second": True})
        second_thread.start()
        assert second_lock_attempted.wait(timeout=1)
        assert not second_returned.wait(timeout=0.1)

        allow_load.set()
        first_thread.join(timeout=2)
        second_thread.join(timeout=2)
        assert not first_thread.is_alive()
        assert not second_thread.is_alive()
        assert errors == []
        assert len(instances) == 2
        assert instances[0] is instances[1]
        assert instances[1].data_loaded is True
        assert instances[1].affix_dict == {"ready": "yes"}
        assert second_aspect_list == [["ready"]]
    finally:
        allow_load.set()
        first_thread.join(timeout=2)
        if second_thread is not None:
            second_thread.join(timeout=2)


@pytest.mark.parametrize("failure", [RuntimeError("load failed"), _LoaderFailure()])
def test_dataloader_retries_after_failed_initialization(monkeypatch, failure):
    monkeypatch.setattr(Dataloader, "_instance", None)
    monkeypatch.setattr(Dataloader, "data_loaded", False)
    attempts = 0

    def load_data(instance):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise failure
        instance.affix_dict = {"ready": "yes"}

    monkeypatch.setattr(Dataloader, "load_data", load_data)
    with pytest.raises(type(failure)):
        Dataloader()
    assert Dataloader._instance is None
    assert Dataloader.data_loaded is False

    instance = Dataloader()
    assert attempts == 2
    assert instance.data_loaded is True
    assert instance.affix_dict == {"ready": "yes"}


def test_dataloader_allows_same_thread_reentrant_access(monkeypatch):
    monkeypatch.setattr(Dataloader, "_instance", None)
    monkeypatch.setattr(Dataloader, "data_loaded", False)
    inner_instances = []
    result = []
    errors = []

    def load_data(instance):
        inner_instances.append(Dataloader())
        instance.aspect_list = ["ready"]

    def construct():
        try:
            result.append(Dataloader())
        except Exception as error:  # ruff:ignore[blind-except]
            errors.append(error)

    monkeypatch.setattr(Dataloader, "load_data", load_data)
    thread = threading.Thread(target=construct, daemon=True)
    thread.start()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert errors == []
    assert len(result) == 1
    assert inner_instances == result
    assert result[0].data_loaded is True
    assert result[0].aspect_list == ["ready"]
