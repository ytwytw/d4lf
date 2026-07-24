from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTabWidget

from src.config.profile_models import TributeFilterModel
from src.gui.i18n import translate, translate_widget_tree
from src.gui.profile_editor.affixes_tab import AFFIXES_TABNAME, AffixesTab
from src.gui.profile_editor.aspect_upgrades_tab import ASPECT_UPGRADES_TABNAME, AspectUpgradesTab
from src.gui.profile_editor.charms_seals_group_tab import CHARMS_TABNAME, SEALS_TABNAME, CharmsTab, SealsTab
from src.gui.profile_editor.global_uniques_tab import UNIQUES_TABNAME, UniquesTab
from src.gui.profile_editor.sigils_tab import SIGILS_TABNAME, SigilsTab
from src.gui.profile_editor.tributes_tab import TRIBUTES_TABNAME, TributesTab

if TYPE_CHECKING:
    from src.config.profile_document import LoadedProfile
    from src.config.profile_models import ProfileModel


def _to_editor_tribute_filter(tributes: TributeFilterModel | None) -> TributeFilterModel:
    return tributes if tributes is not None else TributeFilterModel()


class ProfileEditor(QTabWidget):
    def __init__(self, loaded_profile: LoadedProfile, parent=None):
        super().__init__(parent)

        self.loaded_profile = loaded_profile
        self.profile_model = loaded_profile.profile
        self.profile_model.tributes = _to_editor_tribute_filter(self.profile_model.tributes)
        # Create main tabs
        self.affixes_tab = AffixesTab(self.profile_model.affixes)
        self.charms_tab = CharmsTab(self.profile_model.charms)
        self.seals_tab = SealsTab(self.profile_model.seals)
        self.aspect_upgrades_tab = AspectUpgradesTab(self.profile_model.aspect_upgrades)
        self.sigils_tab = SigilsTab(self.profile_model.sigils)
        self.tributes_tab = TributesTab(self.profile_model.tributes)
        self.uniques_tab = UniquesTab(self.profile_model.global_uniques)

        self.currentChanged.connect(self.tab_changed)
        # Add tabs with icons
        self.addTab(self.affixes_tab, translate(AFFIXES_TABNAME))
        self.addTab(self.charms_tab, translate(CHARMS_TABNAME))
        self.addTab(self.seals_tab, translate(SEALS_TABNAME))
        self.addTab(self.aspect_upgrades_tab, translate(ASPECT_UPGRADES_TABNAME))
        self.addTab(self.sigils_tab, translate(SIGILS_TABNAME))
        self.addTab(self.tributes_tab, translate(TRIBUTES_TABNAME))
        self.addTab(self.uniques_tab, translate(UNIQUES_TABNAME))

        # Configure tab widget properties
        self.setDocumentMode(True)
        self.setMovable(False)
        self.setTabPosition(QTabWidget.TabPosition.North)
        self.setElideMode(Qt.TextElideMode.ElideRight)

    def tab_changed(self, index):
        current_widget = self.widget(index)
        if current_widget is self.affixes_tab:
            self.affixes_tab.load()
        elif current_widget is self.charms_tab:
            self.charms_tab.load()
        elif current_widget is self.seals_tab:
            self.seals_tab.load()
        elif current_widget is self.aspect_upgrades_tab:
            self.aspect_upgrades_tab.load()
        elif current_widget is self.sigils_tab:
            self.sigils_tab.load()
        elif current_widget is self.tributes_tab:
            self.tributes_tab.load()
        elif current_widget is self.uniques_tab:
            self.uniques_tab.load()
        if current_widget is not None:
            translate_widget_tree(current_widget)

    def retranslate_ui(self) -> None:
        tabs = (
            (self.affixes_tab, AFFIXES_TABNAME),
            (self.charms_tab, CHARMS_TABNAME),
            (self.seals_tab, SEALS_TABNAME),
            (self.aspect_upgrades_tab, ASPECT_UPGRADES_TABNAME),
            (self.sigils_tab, SIGILS_TABNAME),
            (self.tributes_tab, TRIBUTES_TABNAME),
            (self.uniques_tab, UNIQUES_TABNAME),
        )
        for widget, source_label in tabs:
            self.setTabText(self.indexOf(widget), translate(source_label))
            refresh_catalog_labels = getattr(widget, "refresh_catalog_labels", None)
            if callable(refresh_catalog_labels):
                refresh_catalog_labels()
        translate_widget_tree(self)

    def get_current_model(self) -> ProfileModel:
        return self.profile_model
