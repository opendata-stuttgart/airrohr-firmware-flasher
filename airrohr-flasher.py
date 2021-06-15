#!/usr/bin/env python3
# -* encoding: utf-8 *-

import sys
import os.path
import os
import time
import tempfile
import hashlib
import zlib
import logging
import json

import requests
from esptool import ESPLoader, erase_flash, write_flash

import airrohrFlasher
from airrohrFlasher.qtvariant import QtGui, QtCore, QtWidgets
from airrohrFlasher.utils import QuickThread
from airrohrFlasher.workers import PortDetectThread, FirmwareListThread, \
    ZeroconfDiscoveryThread

from gui import mainwindow

from airrohrFlasher.consts import UPDATE_REPOSITORY, ALLOWED_PROTO, \
    PREFERED_PORTS, ROLE_DEVICE, DRIVERS_URL

import spiffsGen
from spiffsGen import spiffsgen
#from spiffsgen import _____________

if getattr(sys, 'frozen', False):
    RESOURCES_PATH = sys._MEIPASS
else:
    RESOURCES_PATH = os.path.dirname(os.path.realpath(__file__))

class MainWindow(QtWidgets.QMainWindow, mainwindow.Ui_MainWindow):
    uploadProgress = QtCore.Signal([str, int])
    configProgress = QtCore.Signal([str, int])
    eraseProgress = QtCore.Signal([str, int])
    errorSignal = QtCore.Signal([str])
    uploadThread = None
    zeroconf_discovery = None
    boards_detected = False
    jsonFinal = ""
    spiffsBinary = b'' 

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

        self.statusbar.showMessage(self.tr("Loading firmware list..."))

        self.versionBox.clear()
        self.firmware_list = FirmwareListThread()
        self.firmware_list.listLoaded.connect(self.populate_versions)
        self.firmware_list.error.connect(self.on_work_error)
        self.firmware_list.start()

        self.port_detect = PortDetectThread()
        self.port_detect.portsUpdate.connect(self.populate_boards)
        self.port_detect.error.connect(self.on_work_error)
        self.port_detect.start()

        self.discovery_start()

        self.globalMessage.hide()

        # Hide WIP GUI parts...
        self.on_expertModeBox_clicked()
        self.expertModeBox.hide()
        self.tabWidget.removeTab(self.tabWidget.indexOf(self.serialTab))

        self.uploadProgress.connect(self.on_work_update)
        self.configProgress.connect(self.on_config_update)
        self.eraseProgress.connect(self.on_erase_update)
        self.errorSignal.connect(self.on_work_error)

        self.cachedir = tempfile.TemporaryDirectory()
        self.cachedirjson = tempfile.TemporaryDirectory()
        self.cachedirspiffs = tempfile.TemporaryDirectory()

        print(self.cachedir.name)
        print(self.cachedirjson.name)
        print(self.cachedirspiffs.name)

        self.sensorsList = ["SDS011", "SPS30", "BME280", "BMP180", "BMP280", "DHT22", "DNMS (noise)"]
        self.languagesList = ["EN","FR","DE"]
        self.populate_sensors1(self.sensorsList)
        self.populate_sensors2(self.sensorsList)
        self.populate_languages(self.languagesList)

        self.sensor1Box.setCurrentIndex(0)
        self.sensor2Box.setCurrentIndex(2)
        self.languageBox.setCurrentIndex(0)

        self.customName.setPlaceholderText("Default = airRohr")

        self.wifiSSID.setPlaceholderText("Please double check...")
        self.wifiPW.setPlaceholderText("Please double check...")

        self.configjson = json.loads('{}')
        self.sensorID = 0
        self.customNameSave = ""
        

        # String		current_lang
        # String		wlanssid
        # Password		wlanpwd
        # String		www_username
        # Password		www_password
        # String		fs_ssid
        # Password		fs_pwd
        # Bool		www_basicauth_enabled
        # Bool		dht_read
        # Bool		htu21d_read
        # Bool		ppd_read
        # Bool		sds_read
        # Bool		pms_read
        # Bool		hpm_read
        # Bool		npm_read
        # Bool		sps30_read
        # Bool		bmp_read
        # Bool		bmx280_read
        # Bool		sht3x_read
        # Bool		ds18b20_read
        # Bool		dnms_read
        # String		dnms_correction
        # String		temp_correction
        # Bool		gps_read
        # Bool		send2dusti
        # Bool		ssl_dusti
        # Bool		send2madavi
        # Bool		ssl_madavi
        # Bool		send2sensemap
        # Bool		send2fsapp
        # Bool		send2aircms
        # Bool		send2csv
        # Bool		auto_update
        # Bool		use_beta
        # Bool		has_display
        # Bool		has_sh1106
        # Bool		has_flipped_display
        # Bool		has_lcd1602
        # Bool		has_lcd1602_27
        # Bool		has_lcd2004
        # Bool		has_lcd2004_27
        # Bool		display_wifi_info
        # Bool		display_device_info
        # UInt		debug
        # Time		sending_intervall_ms
        # Time		time_for_wifi_config
        # String		senseboxid
        # Bool		send2custom
        # String		host_custom
        # String		url_custom
        # UInt		port_custom
        # String		user_custom
        # Password		pwd_custom
        # Bool		ssl_custom
        # Bool		send2influx
        # String		host_influx
        # String		url_influx
        # UInt		port_influx
        # String		user_influx
        # Password		pwd_influx
        # String		measurement_name_influx
        # Bool		ssl_influx

    def show_global_message(self, title, message):
        self.globalMessage.show()
        self.globalMessageTitle.setText(title)
        self.globalMessageText.setText(message)

    def on_work_update(self, status, progress):
        self.statusbar.showMessage(status)
        self.progressBar.setValue(progress)

    def on_config_update(self, status, progress):
        self.statusbar.showMessage(status)
        self.progressBar_config.setValue(progress)

    def on_erase_update(self, status, progress):
        self.statusbar.showMessage(status)
        self.progressBar_erase.setValue(progress)

    def on_work_error(self, message):
        self.statusbar.showMessage(message)

    @property
    def version(self):
        return airrohrFlasher.__version__

    @property
    def build_id(self):
        try:
            from airrohrFlasher._buildid import commit, builddate
        except ImportError:
            import datetime
            commit = 'devel'
            builddate = datetime.datetime.now().strftime('%Y%m%d')

        return '{}-{}/{}'.format(self.version, commit, builddate)

    def i18n_init(self, locale):
        """Initializes i18n to specified QLocale"""

        self.app.removeTranslator(self.translator)
        lang = QtCore.QLocale.languageToString(locale.language())
        self.translator.load(os.path.join(
            RESOURCES_PATH, 'i18n', lang + '.qm'))
        self.app.installTranslator(self.translator)
        self.retranslateUi(self)

    def retranslateUi(self, win):
        super(MainWindow, self).retranslateUi(win)

        win.setWindowTitle(win.windowTitle().format(
            version=self.version))
        win.buildLabel.setText(win.buildLabel.text().format(
            build_id=self.build_id))

    def populate_versions(self, files):
        """Loads available firmware versions into versionbox widget"""

        for fname in files:
            if not fname.endswith('.bin'):
                continue

            item = QtGui.QStandardItem(fname)
            item.setData(UPDATE_REPOSITORY + fname, ROLE_DEVICE)
            self.versionBox.model().appendRow(item)

        self.statusbar.clearMessage()

    def populate_sensors1(self, sensors):
        for sensor in sensors:
            item = QtGui.QStandardItem(sensor)
            #item.setData(UPDATE_REPOSITORY + fname, ROLE_DEVICE)
            self.sensor1Box.model().appendRow(item)
    
    def populate_sensors2(self, sensors):
        for sensor in sensors:
            item = QtGui.QStandardItem(sensor)
            #item.setData(UPDATE_REPOSITORY + fname, ROLE_DEVICE)
            self.sensor2Box.model().appendRow(item)
    
    def populate_languages(self, languages):
        for language in languages:
            item = QtGui.QStandardItem(language)
            #item.setData(UPDATE_REPOSITORY + fname, ROLE_DEVICE)
            self.languageBox.model().appendRow(item)

    def populate_boards(self, ports):
        """Populates board selection combobox from list of pyserial
        ListPortInfo objects"""

        self.boardBox.clear()

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

            # No prefered boards has been found so far and there is a
            # suggested driver download URL available
            if not self.boards_detected and DRIVERS_URL:
                self.show_global_message(
                    self.tr('No boards found'),
                    self.tr('Have you installed <a href="{drivers_url}">'
                            'the drivers</a>?').format(drivers_url=DRIVERS_URL))
        else:
            self.globalMessage.hide()
            self.boards_detected = True

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

    def is_json(self, myjson):
        try:
            json_object = json.loads(myjson)
        except ValueError as e:
            return False
        return True

        #Configuration saver

    def switcher(self, value):
        if value == "DHT22":
            self.configjson['dht_read'] = True
        elif value == "PPD42":
            self.configjson['ppd_read'] = True
        elif value == "SDS011":
            self.configjson['sds_read'] = True
        elif value == "PMSx003":
            self.configjson['pms_read'] = True
        elif value == "HPM":
            self.configjson['hpm_read'] = True
        elif value == "NPM":
            self.configjson['npm_read'] = True
        elif value == "SPS30":
            self.configjson['sps30_read'] = True
        elif value == "BMP":
            self.configjson['bmp_read'] = True
        elif value == "BME280":
            self.configjson['bmx280_read'] = True
        elif value == "SHT3X":
            self.configjson['sht3x_read'] = True
        elif value == "DS18B20":
            self.configjson['ds18b20_read'] = True
        elif value == "DNMS (noise)":
            self.configjson['dnms_read'] = True
        else:
            self.statusbar.showMessage(self.tr("Invalid sensor name."))
            return

    @QtCore.Slot()
    def on_wifiButton_clicked(self):
        self.statusbar.clearMessage()
        
        device = self.boardBox.currentData(ROLE_DEVICE)

        configstring = '{"SOFTWARE_VERSION":"flashingtool","current_lang":"","wlanssid":"","wlanpwd":"","www_username":"admin","www_password":"","fs_ssid":"","fs_pwd":"","www_basicauth_enabled":false,"dht_read":false,"htu21d_read":false,"ppd_read":false,"sds_read":false,"pms_read":false,"hpm_read":false,"npm_read":false,"sps30_read":false,"bmp_read":false,"bmx280_read":false,"sht3x_read":false,"ds18b20_read":false,"dnms_read":false,"dnms_correction":"0.0","temp_correction":"0.0","gps_read":false,"send2dusti":true,"ssl_dusti":false,"send2madavi":true,"ssl_madavi":false,"send2sensemap":false,"send2fsapp":false,"send2aircms":false,"send2csv":false,"auto_update":true,"use_beta":false,"has_display":false,"has_sh1106":false,"has_flipped_display":false,"has_lcd1602":false,"has_lcd1602_27":false,"has_lcd2004":false,"has_lcd2004_27":false,"display_wifi_info":true,"display_device_info":true,"debug":3,"sending_intervall_ms":145000,"time_for_wifi_config":600000,"senseboxid":"","send2custom":false,"host_custom":"192.168.234.1","url_custom":"/data.php","port_custom":80,"user_custom":"","pwd_custom":"","ssl_custom":false,"send2influx":false,"host_influx":"influx.server","url_influx":"/write?db=sensorcommunity","port_influx":8086,"user_influx":"","pwd_influx":"","measurement_name_influx":"feinstaub","ssl_influx":false}'
        self.configjson = json.loads(configstring)
        ssid = self.wifiSSID.text()
        pw = self.wifiPW.text()
        pw_empty = self.wifiPW_empty.isChecked()
        apssid = self.customName.text()
        sensor1 = self.sensorsList[self.sensor1Box.currentIndex()]
        sensor2 = self.sensorsList[self.sensor2Box.currentIndex()]
        language = self.languagesList[self.languageBox.currentIndex()]

        if language not in self.languagesList:
            self.statusbar.showMessage(self.tr("Invalid language."))
            return

        if not ssid:
            self.statusbar.showMessage(self.tr("No SSID typed."))
            return

        if not pw and not pw_empty:
            self.statusbar.showMessage(self.tr("No password typed."))
            return

        if pw_empty:
            pw = ""

        if sensor1 == sensor2:
            self.statusbar.showMessage(self.tr("2 times the same sensor."))
            return

        if not apssid:
            # self.configjson['fs_ssid'] = "airRohr-" + str(self.sensorID)
            self.configjson['fs_ssid'] = ""
            # print(self.configjson['fs_ssid'])
        else:
            self.configjson['fs_ssid'] = apssid + "-" + str(self.sensorID)
            self.customNameSave = apssid
            print(self.configjson['fs_ssid'])        

        self.switcher(sensor1)
        self.switcher(sensor2)

        self.configjson['wlanssid'] = ssid
        self.configjson['wlanpwd'] = pw
        self.configjson['current_lang'] = language
        

        jsonTest = json.dumps(self.configjson)
        
        if not self.is_json(jsonTest):
            self.statusbar.showMessage(self.tr("Created invalid json."))
            return
        else:
            self.jsonFinal = json.dumps(self.configjson)
            self.statusbar.showMessage(self.tr("Created valid json."))
            print(self.jsonFinal)
        
            self.statusbar.showMessage(self.tr("Opening temporary json directory."))

            jsonfile = open(self.cachedirjson.name + "/config.json", "w")
            self.statusbar.showMessage(self.tr("Write json in temporay json directory."))
            jsonfile.write(self.jsonFinal)
            jsonfile.close()

            self.statusbar.showMessage(self.tr("Make SPIFFS bin"))

            args = []
            args.extend(["spiffsgen.py",
                     "--page-size", "256",
                     "--block-size", "8192",
                     "--meta-len=0", "0x100000"])

            args.append("--no-magic-len")
            args.append("--aligned-obj-ix-tables")
  
            args.extend([self.cachedirjson.name, self.cachedirspiffs.name + "/spiffs.bin"])

            sys.argv = args
            spiffsgen.main()
            self.statusbar.showMessage(self.tr("spiffs.bin done!"))

            self.statusbar.clearMessage()
            device = self.boardBox.currentData(ROLE_DEVICE)

            if not device:
                self.statusbar.showMessage(self.tr("No device selected."))
                return

            if self.write_config.running():
                self.statusbar.showMessage(self.tr("Work in progess..."))
                return
            
            self.write_config(self.configProgress, device, self.cachedirspiffs.name + "/spiffs.bin", error=self.errorSignal)

    @QuickThread.wrap
    def write_config(self, progress, device, path, baudrate=460800):

        progress.emit(self.tr('Connecting...'), 0)

        init_baud = min(ESPLoader.ESP_ROM_BAUD, baudrate)
        esp = ESPLoader.detect_chip(device, init_baud, 'default_reset', False)

        progress.emit(self.tr('Connected. Chip type: {chip_type}').format(
                    chip_type=esp.get_chip_description()), 0)
        esp = esp.run_stub()
        esp.change_baud(baudrate)

        with open(path, 'rb') as fd:
            uncimagespiffs = fd.read()

        imagespiffs = zlib.compress(uncimagespiffs, 0)

        address = 0x100000
        blocks = esp.flash_defl_begin(len(uncimagespiffs), len(imagespiffs), address)

        seq = 0
        written = 0
        t = time.time()
        while len(imagespiffs) > 0:

            current_addr = address + seq * esp.FLASH_WRITE_SIZE
            progress.emit(self.tr('Writing at 0x{address:08x}...').format(
                          address=current_addr),
                          100 * (seq + 1) // blocks)

            block = imagespiffs[0:esp.FLASH_WRITE_SIZE]
            esp.flash_defl_block(block, seq, timeout=3.0)
            imagespiffs = imagespiffs[esp.FLASH_WRITE_SIZE:]
            seq += 1
            written += len(block)
            #print("iteration "+str(seq))

        t = time.time() - t

        progress.emit(self.tr(
            'Finished in {time:.2f} seconds. Sensor ID: {sensor_id}').format(
                time=t, sensor_id=esp.chip_id()), 100)

        esp.flash_finish(True)

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

        sel = self.versionBox.model().item(
            self.versionBox.currentIndex())
        if sel:
            orig_version = sel.text()
        else:
            orig_version = ''

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

        if self.flash_board.running():
            self.statusbar.showMessage(self.tr("Work in progess..."))
            return

        self.flash_board(self.uploadProgress, device, binary_uri,
                         error=self.errorSignal)

    def cache_download(self, progress, binary_uri):
        """Downloads and caches file with status reports via Qt Signals"""
        cache_fname = os.path.join(
            self.cachedir.name,
            hashlib.sha256(binary_uri.encode('utf-8')).hexdigest())
        
        #print(self.cachedir)

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

    @QuickThread.wrap
    def erase_board(self, progress, device, baudrate=460800):

        progress.emit(self.tr('Connecting...'), 0)
        init_baud = min(ESPLoader.ESP_ROM_BAUD, baudrate)
        esp = ESPLoader.detect_chip(device, init_baud, 'default_reset', False)

        progress.emit(self.tr('Connected. Chip type: {chip_type}').format(
                      chip_type=esp.get_chip_description()), 0)
        esp = esp.run_stub()
        esp.change_baud(baudrate)
        esp.erase_flash()
        progress.emit(self.tr('Erasing complete!'), 100)

    @QtCore.Slot()
    def on_eraseButton_clicked(self):
        self.statusbar.clearMessage()
        device = self.boardBox.currentData(ROLE_DEVICE)

        if not device:
            self.statusbar.showMessage(self.tr("No device selected."))
            return

        if self.erase_board.running():
            self.statusbar.showMessage(self.tr("Erasing in progress..."))
            return

        self.erase_board(self.eraseProgress, device,
                         error=self.errorSignal)

    @QuickThread.wrap
    def flash_board(self, progress, device, binary_uri, baudrate=460800):

        if binary_uri.startswith(ALLOWED_PROTO):
            binary_uri = self.cache_download(progress, binary_uri)

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

        esp.flash_finish(True)

    @QtCore.Slot()
    def on_expertModeBox_clicked(self):
        self.expertForm.setVisible(self.expertModeBox.checkState())
        # self.centralwidget.setFixedHeight(
        #     self.centralwidget.sizeHint().height())
        # self.setFixedHeight(self.sizeHint().height())

    # Zeroconf page
    def discovery_start(self):
        if self.zeroconf_discovery:
            self.zeroconf_discovery.stop()

        self.zeroconf_discovery = ZeroconfDiscoveryThread()
        self.zeroconf_discovery.deviceDiscovered.connect(
            self.on_zeroconf_discovered)
        self.zeroconf_discovery.start()

    def on_zeroconf_discovered(self, name, address, info):
        """Called on every zeroconf discovered device"""
        # if (name.lower().startswith('feinstaubsensor')
        #         or name.lower().startswith('nam')
        #         or name.lower().startswith('smogomierz')
        #         or name.lower().startswith('airrohr')
        #         or name.lower().startswith(self.customNameSave)):
        item = QtWidgets.QListWidgetItem('{}: {}'.format(address, name.split('.')[0]))
        item.setData(ROLE_DEVICE, 'http://{}:{}'.format(address, info.port))
        self.discoveryList.addItem(item)

    @QtCore.Slot(QtWidgets.QListWidgetItem)
    def on_discoveryList_itemDoubleClicked(self, index):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(index.data(ROLE_DEVICE)))

    @QtCore.Slot()
    def on_discoveryRefreshButton_clicked(self):
        self.discoveryList.clear()
        self.discovery_start()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(app=app)
    window.show()
    sys.exit(app.exec_())
