# -* encoding: utf-8 *-
import sys
import os.path
import re
import time
import tempfile
import hashlib
import zlib
import logging

import serial
import serial.tools.list_ports
import requests
from esptool import ESPLoader
from PyQt5 import QtGui, QtCore, QtWidgets

from gui import mainwindow

# Firmware update repository
UPDATE_REPOSITORY = 'https://www.madavi.de/sensor/update/data/'

# URI prefixes (protocol parts, essentially) to be downloaded using requests
ALLOWED_PROTO = ('http://', 'https://')

# vid/pid pairs of known NodeMCU/ESP8266 development boards
PREFERED_PORTS = [
    # CH341
    (0x1A86, 0x7523),

    # CP2102
    (0x10c4, 0xea60),
]

ROLE_DEVICE = QtCore.Qt.UserRole + 1

if getattr(sys, 'frozen', False):
    RESOURCES_PATH = sys._MEIPASS
else:
    RESOURCES_PATH = os.path.dirname(os.path.realpath(__file__))

# FIXME move this into something like qtvariant.py
QtCore.Signal = QtCore.pyqtSignal
QtCore.Slot = QtCore.pyqtSlot

file_index_re = re.compile(r'<a href="([^"]*)">([^<]*)</a>')


def indexof(path):
    """Returns list of filenames parsed off "Index of" page"""
    resp = requests.get(path)
    return [a for a, b in file_index_re.findall(resp.text) if a == b]


class QThread(QtCore.QThread):
    """Provides similar API to threading.Thread but with additional error
    reporting based on Qt Signals"""
    def __init__(self, parent=None, target=None, args=None, kwargs=None,
                 error=None):
        super(QThread, self).__init__(parent)
        self.target = target
        self.args = args or []
        self.kwargs = kwargs or {}
        self.error = error

    def run(self):
        try:
            self.target(*self.args, **self.kwargs)
        except Exception as exc:
            if self.error:
                self.error.emit(str(exc))
            # raise here causes windows builds to just die. ¯\_(ツ)_/¯
            logging.exception('Unhandled exception')


class MainWindow(QtWidgets.QMainWindow, mainwindow.Ui_MainWindow):
    signal = QtCore.Signal([str, int])
    errorSignal = QtCore.Signal([str])
    uploadThread = None

    def __init__(self, parent=None, app=None):
        super(MainWindow, self).__init__(parent)
        self.setWindowFlags(QtCore.Qt.Dialog)

        # FIXME: dirty hack to solve relative paths in *.ui
        oldcwd = os.getcwd()
        os.chdir(os.path.join(RESOURCES_PATH, 'assets'))
        self.setupUi(self)
        os.chdir(oldcwd)

        self.app = app
        self.translator = QtCore.QTranslator()

        self.i18n_init(QtCore.QLocale.system())

        # TODO: extract this to separate thread
        self.populate_versions()
        self.populate_boards(serial.tools.list_ports.comports())

        self.on_expertModeBox_clicked()

        self.signal.connect(self.on_work_update)
        self.errorSignal.connect(self.on_work_error)

        self.cachedir = tempfile.TemporaryDirectory()

    def on_work_update(self, status, progress):
        self.statusbar.showMessage(status)
        self.progressBar.setValue(progress)

    def on_work_error(self, message):
        self.statusbar.showMessage(message)

    def i18n_init(self, locale):
        """Initializes i18n to specified QLocale"""

        self.app.removeTranslator(self.translator)
        lang = QtCore.QLocale.languageToString(locale.language())
        self.translator.load(os.path.join(
            RESOURCES_PATH, 'i18n', lang + '.qm'))
        self.app.installTranslator(self.translator)
        self.retranslateUi(self)

    def populate_versions(self):
        """Loads available firmware versions into versionbox widget"""

        for fname in indexof(UPDATE_REPOSITORY):
            if not fname.endswith('.bin'):
                continue

            item = QtGui.QStandardItem(fname)
            item.setData(UPDATE_REPOSITORY + fname, ROLE_DEVICE)
            self.versionBox.model().appendRow(item)

    def populate_boards(self, ports):
        """Populates board selection combobox from list of pyserial
        ListPortInfo objects"""

        prefered, others = self.group_ports(ports)

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

    @QtCore.Slot()
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

        orig_version = self.versionBox.model().item(
            self.versionBox.currentIndex()).text()

        if version == orig_version:
            # Editable combobox has been unchanged
            binary_uri = self.versionBox.currentData(ROLE_DEVICE)
        elif version.startswith(ALLOWED_PROTO):
            # User has provided a download URL
            binary_uri = version
        elif os.path.exists(version):
            binary_uri = version
        else:
            self.statusbar.showMessage(self.tr(
                "Invalid version / file does not exist"))
            return

        if self.uploadThread and self.uploadThread.isRunning():
            self.statusbar.showMessage(self.tr("Work in progess..."))
            return

        self.uploadThread = QThread(self, self.flash_board, [
            self.signal, device, binary_uri], error=self.errorSignal)
        self.uploadThread.start()

    def cache_download(self, progress, binary_uri):
        """Downloads and caches file with status reports via Qt Signals"""
        cache_fname = os.path.join(
            self.cachedir.name,
            hashlib.sha256(binary_uri.encode('utf-8')).hexdigest())

        if os.path.exists(cache_fname):
            return cache_fname

        with open(cache_fname, 'wb') as fd:
            progress.emit(self.tr('Downloading...'), 0)
            response = requests.get(binary_uri, stream=True)
            total_length = response.headers.get('content-length')

            dl = 0
            total_length = int(total_length or 0)
            for data in response.iter_content(chunk_size=4096):
                dl += len(data)
                fd.write(data)

                if total_length:
                    progress.emit(self.tr('Downloading...'),
                                  (100*dl) // total_length)

        return cache_fname

    def flash_board(self, progress, device, binary_uri, baudrate=460800):
        if binary_uri.startswith(ALLOWED_PROTO):
            binary_uri = self.cache_download(progress, binary_uri)

        print(binary_uri)

        progress.emit(self.tr('Connecting...'), 0)

        init_baud = min(ESPLoader.ESP_ROM_BAUD, baudrate)
        esp = ESPLoader.detect_chip(device, init_baud, 'default_reset', False)

        progress.emit(self.tr('Connected. Chip type: {chip_type}').format(
                      chip_type=esp.get_chip_description()), 0)
        esp = esp.run_stub()
        esp.change_baud(baudrate)

        with open(binary_uri, 'rb') as fd:
            uncimage = fd.read()

        image = zlib.compress(uncimage, 9)

        address = 0x0
        blocks = esp.flash_defl_begin(len(uncimage), len(image), address)

        seq = 0
        written = 0
        t = time.time()
        while len(image) > 0:
            current_addr = address + seq * esp.FLASH_WRITE_SIZE
            progress.emit(self.tr('Writing at 0x{address:08x}...').format(
                          address=current_addr),
                          100 * (seq + 1) // blocks)

            block = image[0:esp.FLASH_WRITE_SIZE]
            esp.flash_defl_block(block, seq, timeout=3.0)
            image = image[esp.FLASH_WRITE_SIZE:]
            seq += 1
            written += len(block)
        t = time.time() - t

        progress.emit(self.tr(
            'Finished in {time:.2f} seconds. Sensor ID: {sensor_id}').format(
                time=t, sensor_id=esp.chip_id()), 100)

    @QtCore.Slot()
    def on_expertModeBox_clicked(self):
        self.expertForm.setVisible(self.expertModeBox.checkState())
        self.centralwidget.setFixedHeight(
            self.centralwidget.sizeHint().height())
        self.setFixedHeight(self.sizeHint().height())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(app=app)
    window.show()
    sys.exit(app.exec_())
