#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This file is part of SIFT.
#
# SIFT is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SIFT is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SIFT.  If not, see <http://www.gnu.org/licenses/>.

import os
from PyQt5 import QtCore, QtGui, QtWidgets
from collections import OrderedDict
from typing import Generator, Tuple, Iterable

from satpy import Scene, DatasetID, DATASET_KEYS
from satpy.readers import group_files

from uwsift.ui.open_file_wizard_ui import Ui_openFileWizard

FILE_PAGE = 0
PRODUCT_PAGE = 1
SUMMARY_PAGE = 2

BY_PARAMETER_TAB = 1
BY_ID_TAB = 0

ID_COMPONENTS = [
    'name',
    'wavelength',
    'resolution',
    'calibration',
    'level',
]
READERS = None  # all readers

FORMAT_WIDTH = {
    'name': 20,
    'wavelength': 10,
    'calibration': 15,
    'resolution': 12,
    'polarization': 10,
    'level': 8,
}

EXCLUDE_DATASETS = {'calibration': ['radiance', 'counts']}


def _pretty_identifiers(ds_id: DatasetID) -> Generator[Tuple[str, object, str], None, None]:
    """Determine pretty version of each identifier."""
    for key in ID_COMPONENTS:
        value = getattr(ds_id, key, None)
        if value is None:
            pretty_val = "N/A"
        elif key == 'wavelength':
            pretty_val = "{:0.02f} µm".format(value[1])
        elif key == 'level':
            pretty_val = "{:d} hPa".format(value)
        elif key == 'resolution':
            pretty_val = "{:d}m".format(value)
        else:
            pretty_val = value

        yield key, value, pretty_val


def _filter_identifiers(ids_to_filter: Iterable[DatasetID]) -> Generator[DatasetID, None, None]:
    """Generate only non-filtered DatasetIDs based on EXCLUDE_DATASETS global filters."""
    # skip certain DatasetIDs
    for ds_id in ids_to_filter:
        for filter_key, filtered_values in EXCLUDE_DATASETS.items():
            if getattr(ds_id, filter_key) in filtered_values:
                break
        else:
            yield ds_id


class OpenFileWizard(QtWidgets.QWizard):
    AVAILABLE_READERS = []

    def __init__(self, base_dir=None, parent=None):
        super(OpenFileWizard, self).__init__(parent)
        self._last_open_dir = base_dir
        self._filenames = set()
        self._selected_files = []
        # tuple(filenames) -> scene object
        self.scenes = {}
        self.selected_ids = []

        self.ui = Ui_openFileWizard()
        self.ui.setupUi(self)

        font = QtGui.QFont('Andale Mono')
        font.setPointSizeF(14)
        self.ui.productSummaryText.setFont(font)

        self.ui.addButton.released.connect(self.add_file)
        self.ui.removeButton.released.connect(self.remove_file)
        # Connect signals so Next buttons are determined by selections on pages
        self._connect_next_button_signals(self.ui.fileList, self.ui.fileSelectionPage)
        self.ui.fileList.model().rowsInserted.connect(lambda x: self.ui.fileSelectionPage.completeChanged.emit())
        self.ui.fileList.model().rowsRemoved.connect(lambda x: self.ui.fileSelectionPage.completeChanged.emit())
        self.ui.fileList.itemChanged.connect(lambda x: self.ui.fileSelectionPage.completeChanged.emit())
        self.ui.selectByTabWidget.currentChanged.connect(self._product_selection_tab_change)

        # Page 2 - Product selection
        self._connect_product_select_complete()

    def _connect_next_button_signals(self, widget, page):
        widget.model().rowsInserted.connect(page.completeChangedSlot)
        widget.model().rowsRemoved.connect(page.completeChangedSlot)
        widget.itemChanged.connect(page.completeChangedSlot)

    def _disconnect_next_button_signals(self, widget, page):
        widget.model().rowsInserted.disconnect(page.completeChangedSlot)
        widget.model().rowsRemoved.disconnect(page.completeChangedSlot)
        widget.itemChanged.disconnect(page.completeChangedSlot)

    def initializePage(self, p_int):
        self.selected_ids = []
        if p_int == FILE_PAGE:
            self._init_file_page()
        elif p_int == PRODUCT_PAGE:
            self._init_product_select_page()
        elif p_int == SUMMARY_PAGE:
            self._init_summary_page()

    def _init_file_page(self):
        if self.AVAILABLE_READERS:
            readers = self.AVAILABLE_READERS
        else:
            from satpy import available_readers
            readers = sorted(available_readers())
            OpenFileWizard.AVAILABLE_READERS = readers

        self.ui.readerComboBox.addItems(readers)

    def _disconnect_product_select_complete(self, tabs_switched=False):
        current_idx = self.ui.selectByTabWidget.currentIndex()
        if tabs_switched:
            # we want to disconnect the previous tab
            current_idx = 0 if current_idx else 1
        if current_idx == BY_PARAMETER_TAB:
            self._disconnect_next_button_signals(self.ui.selectByNameList, self.ui.productSelectionPage)
            self._disconnect_next_button_signals(self.ui.selectByLevelList, self.ui.productSelectionPage)
        elif current_idx == BY_ID_TAB:
            self._disconnect_next_button_signals(self.ui.selectIDTable, self.ui.productSelectionPage)

    def _connect_product_select_complete(self):
        current_idx = self.ui.selectByTabWidget.currentIndex()
        if current_idx == BY_PARAMETER_TAB:
            self.ui.productSelectionPage.important_children = [
                self.ui.selectByNameList, self.ui.selectByLevelList]
            self._connect_next_button_signals(self.ui.selectByNameList, self.ui.productSelectionPage)
            self._connect_next_button_signals(self.ui.selectByLevelList, self.ui.productSelectionPage)
        elif current_idx == BY_ID_TAB:
            self.ui.productSelectionPage.important_children = [self.ui.selectIDTable]
            self._connect_next_button_signals(self.ui.selectIDTable, self.ui.productSelectionPage)

    def _init_product_select_page(self):
        if self._selected_files == self._filenames:
            return

        # Disconnect the signals until we are done setting up the widgets
        self._disconnect_product_select_complete()

        self._selected_files = self._filenames.copy()
        all_available_products = set()
        reader = self.ui.readerComboBox.currentText()
        for file_group in group_files(self._filenames, reader=reader):
            # file_group includes what reader to use
            # NOTE: We only allow a single reader at a time
            groups_files = tuple(sorted(fn for group_id, group_list in file_group.items() for fn in group_list))
            self.scenes[groups_files] = scn = Scene(filenames=file_group)

            # TODO: Add a check to see if they've already imported these Scenes
            all_available_products.update(scn.available_dataset_ids())

        # update the widgets
        all_available_products = sorted(all_available_products)
        # name and level
        self.ui.selectIDTable.setColumnCount(len(ID_COMPONENTS))
        self.ui.selectIDTable.setHorizontalHeaderLabels([x.title() for x in ID_COMPONENTS])
        properties = OrderedDict(((key, set()) for key in DATASET_KEYS if key in ID_COMPONENTS))
        for idx, ds_id in enumerate(_filter_identifiers(all_available_products)):
            col_idx = 0
            for id_key, id_val, pretty_val in _pretty_identifiers(ds_id):
                if id_key not in ID_COMPONENTS:
                    continue

                self.ui.selectIDTable.setRowCount(idx + 1)
                properties[id_key].add((id_val, pretty_val))
                item = QtWidgets.QTableWidgetItem(pretty_val)
                item.setData(QtCore.Qt.UserRole, id_val)
                item.setFlags((item.flags() ^ QtCore.Qt.ItemIsEditable) | QtCore.Qt.ItemIsUserCheckable)
                if id_key == 'name':
                    item.setCheckState(QtCore.Qt.Unchecked)
                self.ui.selectIDTable.setItem(idx, col_idx, item)
                col_idx += 1

        # Update the per-property lists
        names = sorted(properties['name'])
        for name, pretty_name in names:
            item = QtWidgets.QListWidgetItem(pretty_name)
            item.setData(QtCore.Qt.UserRole, name)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)
            self.ui.selectByNameList.addItem(item)
        levels = sorted(properties['level'])
        for level, pretty_level in levels:
            item = QtWidgets.QListWidgetItem(pretty_level)
            item.setData(QtCore.Qt.UserRole, level)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)
            self.ui.selectByLevelList.addItem(item)

        self._connect_product_select_complete()

    def _get_checked(self, bool_val):
        if bool_val:
            return QtCore.Qt.Checked
        else:
            return QtCore.Qt.Unchecked

    def _reinit_parameter_tab(self):
        # we were on the ID list, now one the parameter lists
        # need to update which selections should be chosen
        names = set()
        levels = set()
        id_idx_name = ID_COMPONENTS.index('name')
        id_idx_level = ID_COMPONENTS.index('level')
        for item_idx in range(self.ui.selectIDTable.rowCount()):
            name_item = self.ui.selectIDTable.item(item_idx, id_idx_name)
            level_item = self.ui.selectIDTable.item(item_idx, id_idx_level)

            if name_item.checkState():
                names.add(name_item.data(QtCore.Qt.UserRole))
                levels.add(level_item.data(QtCore.Qt.UserRole))
        # enable all the names that were checked in the ID list
        for item_idx in range(self.ui.selectByNameList.count()):
            item = self.ui.selectByNameList.item(item_idx)
            name = item.data(QtCore.Qt.UserRole)
            item.setCheckState(self._get_checked(name in names))
        # enable all the levels that were checked in the ID list
        for item_idx in range(self.ui.selectByLevelList.count()):
            item = self.ui.selectByLevelList.item(item_idx)
            level = item.data(QtCore.Qt.UserRole)
            item.setCheckState(self._get_checked(level in levels))

    def _reinit_id_tab(self):
        names = set()
        for item_idx in range(self.ui.selectByNameList.count()):
            item = self.ui.selectByNameList.item(item_idx)
            if item.checkState():
                names.add(item.data(QtCore.Qt.UserRole))

        levels = set()
        for item_idx in range(self.ui.selectByLevelList.count()):
            item = self.ui.selectByLevelList.item(item_idx)
            if item.checkState():
                levels.add(item.data(QtCore.Qt.UserRole))

        for item_idx in range(self.ui.selectIDTable.rowCount()):
            items = {id_comp: self.ui.selectIDTable.item(item_idx, id_idx) for id_idx, id_comp in enumerate(ID_COMPONENTS)}

            name_selected = items['name'].data(QtCore.Qt.UserRole) in names
            level_selected = items['level'].data(QtCore.Qt.UserRole) in levels
            items['name'].setCheckState(self._get_checked(name_selected and level_selected))

    def _product_selection_tab_change(self, tab_idx, force_reinit=True):
        self._disconnect_product_select_complete(tabs_switched=True)
        if tab_idx == BY_PARAMETER_TAB:
            self._reinit_parameter_tab()
        elif tab_idx == BY_ID_TAB:
            self._reinit_id_tab()
        self._connect_product_select_complete()

    def _init_summary_page(self):
        # we are going to use the id table to get our summary
        # so make sure the values are correct
        if self.ui.selectByTabWidget.currentIndex() != BY_ID_TAB:
            self.ui.selectByTabWidget.setCurrentIndex(BY_ID_TAB)

        selected_text = []
        selected_ids = []
        # id_format = "| {name:<20s} | {level:>8s} |"
        id_format = "| " + " | ".join("{{{key}:<{width}}}".format(key=key, width=FORMAT_WIDTH[key]) for key in ID_COMPONENTS) + " |"
        # header_format = "| {name:<20s} | {level:>8s} |"
        header_format = "| " + " | ".join("{{{key}:<{width}}}".format(key=key, width=FORMAT_WIDTH[key]) for key in ID_COMPONENTS) + " |"
        # header_line = "|-{0:-^20s}-|-{0:-^8s}-|".format('-')
        header_line = "|-" + "-|-".join("{{0:-^{width}}}".format(width=FORMAT_WIDTH[key]) for key in ID_COMPONENTS) + "-|"
        header_line = header_line.format('-')
        for item_idx in range(self.ui.selectIDTable.rowCount()):
            id_items = OrderedDict((key, self.ui.selectIDTable.item(item_idx, id_idx)) for id_idx, key in enumerate(ID_COMPONENTS))
            if id_items['name'].checkState():
                id_dict = {key: id_item.data(QtCore.Qt.UserRole) for key, id_item in id_items.items() if id_item is not None}
                text_dict = {key: ("N/A" if id_item is None else id_item.text()) for key, id_item in id_items.items()}
                selected_ids.append(DatasetID(**id_dict))
                selected_text.append(id_format.format(**text_dict))

        self.selected_ids = selected_ids

        summary_text = """Products to be loaded: {}

""".format(len(selected_ids))

        header = header_format.format(**{key: key.title() for key in ID_COMPONENTS})
        summary_text += "\n".join([header, header_line] + selected_text)
        self.ui.productSummaryText.setText(summary_text)

    def add_file(self):
        filename_filters = ['All files (*.*)']
        filter_str = ';;'.join(filename_filters)
        files = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Select one or more files to open", self._last_open_dir or os.getenv("HOME"), filter_str)[0]
        if not files:
            return
        self._last_open_dir = os.path.dirname(files[0])
        for fn in files:
            if fn in self._filenames:
                continue
            item = QtWidgets.QListWidgetItem(fn, self.ui.fileList)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked)
            self.ui.fileList.addItem(item)
            self._filenames.add(fn)

    def remove_file(self):
        # need to go backwards to index numbers don't change
        for item_idx in range(self.ui.fileList.count() - 1, -1, -1):
            item = self.ui.fileList.item(item_idx)
            if self.ui.fileList.isItemSelected(item):
                self.ui.fileList.takeItem(item_idx)
                self._filenames.remove(item.text())
