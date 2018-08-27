# -* encoding: utf-8 *-
import sys
import os.path

import serial
import serial.tools.list_ports
from PyQt5 import QtGui, QtCore, QtWidgets

from gui import mainwindow


PREFERED_PORTS = [
    # CH341
    (0x1A86, 0x7523),

    # CP2102
    (0x10c4, 0xea60),
]

ROLE_DEVICE = QtCore.Qt.UserRole + 1


class MainWindow(QtWidgets.QMainWindow, mainwindow.Ui_MainWindow):
    def __init__(self, parent=None, app=None):
        super(MainWindow, self).__init__(parent)

        # FIXME: dirty hack to solve relative paths in *.ui
        oldcwd = os.getcwd()
        os.chdir('assets')
        self.setupUi(self)
        os.chdir(oldcwd)

        self.app = app
        self.translator = QtCore.QTranslator()

        self.i18n_init(QtCore.QLocale.system())
        self.populate_boards(serial.tools.list_ports.comports())

        self.on_expertModeBox_clicked()

    def i18n_init(self, locale):
        self.app.removeTranslator(self.translator)
        self.translator.load(os.path.join('i18n', QtCore.QLocale.languageToString(locale.language())+ '.qm'))
        self.app.installTranslator(self.translator)
        self.retranslateUi(self)

    def populate_boards(self, ports):
        prefered, others = self.group_ports(serial.tools.list_ports.comports())

        for b in prefered:
            item = QtGui.QStandardItem(
                '{0.description} ({0.device})'.format(b))
            item.setData(b.device, ROLE_DEVICE)
            self.boardBox.model().appendRow(item)

        if not prefered:
            sep = QtGui.QStandardItem(self.tr('No boards found'))
            sep.setEnabled(False)
            self.boardBox.model().appendRow(sep)

        if others:
            sep = QtGui.QStandardItem(self.tr('Others...'))
            sep.setEnabled(False)
            self.boardBox.model().appendRow(sep)

        for b in others:
            item = QtGui.QStandardItem(
                '{0.description} ({0.device})'.format(b))
            item.setData(b.device, ROLE_DEVICE)
            self.boardBox.model().appendRow(item)

    def group_ports(self, ports):
        prefered = []
        others = []

        for p in ports:
            if (p.vid, p.pid) in PREFERED_PORTS:
                prefered.append(p)
            else:
                others.append(p)
        return prefered, others

    def on_actionExit_triggered(self):
        """This handles activation of "Exit" menu action"""
        self.app.exit()

    def on_uploadButton_clicked(self):
        self.statusbar.clearMessage()

        device = self.boardBox.currentData(ROLE_DEVICE)
        version = self.versionBox.currentText()

        if not device:
            self.statusbar.showMessage(self.tr("No device selected."))
            return

        if not version:
            self.statusbar.showMessage(self.tr("No version selected."))
            return

    def on_expertModeBox_clicked(self):
        self.expertForm.setVisible(self.expertModeBox.checkState())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(app=app)
    window.show()
    sys.exit(app.exec_())
