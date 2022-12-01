# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'dataset_statistics_widget.ui'
#
# Created by: PyQt5 UI code generator 5.15.7
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_datasetStatisticsPane(object):
    def setupUi(self, datasetStatisticsPane):
        datasetStatisticsPane.setObjectName("datasetStatisticsPane")
        datasetStatisticsPane.resize(334, 300)
        self.verticalLayout = QtWidgets.QVBoxLayout(datasetStatisticsPane)
        self.verticalLayout.setObjectName("verticalLayout")
        self.formLayout = QtWidgets.QFormLayout()
        self.formLayout.setObjectName("formLayout")
        self.currDatasetLabel = QtWidgets.QLabel(datasetStatisticsPane)
        self.currDatasetLabel.setObjectName("currDatasetLabel")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.currDatasetLabel)
        self.datasetNameLabel = QtWidgets.QLabel(datasetStatisticsPane)
        self.datasetNameLabel.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.datasetNameLabel.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.datasetNameLabel.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.datasetNameLabel.setObjectName("datasetNameLabel")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.SpanningRole, self.datasetNameLabel)
        self.verticalLayout.addLayout(self.formLayout)
        self.statisticsTableWidget = QtWidgets.QTableWidget(datasetStatisticsPane)
        self.statisticsTableWidget.setAlternatingRowColors(True)
        self.statisticsTableWidget.setObjectName("statisticsTableWidget")
        self.statisticsTableWidget.setColumnCount(0)
        self.statisticsTableWidget.setRowCount(0)
        self.verticalLayout.addWidget(self.statisticsTableWidget)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.decimalPlacesLabel = QtWidgets.QLabel(datasetStatisticsPane)
        self.decimalPlacesLabel.setObjectName("decimalPlacesLabel")
        self.horizontalLayout.addWidget(self.decimalPlacesLabel)
        self.decimalPlacesSpinBox = QtWidgets.QSpinBox(datasetStatisticsPane)
        self.decimalPlacesSpinBox.setWrapping(True)
        self.decimalPlacesSpinBox.setMinimum(-1)
        self.decimalPlacesSpinBox.setMaximum(25)
        self.decimalPlacesSpinBox.setObjectName("decimalPlacesSpinBox")
        self.horizontalLayout.addWidget(self.decimalPlacesSpinBox)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(datasetStatisticsPane)
        QtCore.QMetaObject.connectSlotsByName(datasetStatisticsPane)

    def retranslateUi(self, datasetStatisticsPane):
        _translate = QtCore.QCoreApplication.translate
        datasetStatisticsPane.setWindowTitle(_translate("datasetStatisticsPane", "Form"))
        self.currDatasetLabel.setText(_translate("datasetStatisticsPane", "Current Dataset:"))
        self.datasetNameLabel.setText(_translate("datasetStatisticsPane", "Dataset name"))
        self.decimalPlacesLabel.setText(_translate("datasetStatisticsPane", "Decimal Places:"))
        self.decimalPlacesSpinBox.setSpecialValueText(_translate("datasetStatisticsPane", "unlimited"))
