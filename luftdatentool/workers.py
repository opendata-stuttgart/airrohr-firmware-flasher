import time
import socket

import serial
import serial.tools.list_ports
import zeroconf

from .qtvariant import QtCore
from .utils import indexof, QuickThread
from .consts import UPDATE_REPOSITORY


class PortDetectThread(QuickThread):
    interval = 1.0
    portsUpdate = QtCore.Signal([list])

    def target(self):
        """Checks list of available ports and emits signal when necessary"""

        ports = []
        while True:
            new_ports = serial.tools.list_ports.comports()

            if [p.name for p in ports] != [p.name for p in new_ports]:
                self.portsUpdate.emit(new_ports)

            time.sleep(self.interval)

            ports = new_ports


class FirmwareListThread(QuickThread):
    listLoaded = QtCore.Signal([list])

    def target(self):
        """Downloads list of available firmware updates in separate thread."""
        self.listLoaded.emit(list(indexof(UPDATE_REPOSITORY)))


class ZeroconfDiscoveryThread(QuickThread):
    deviceDiscovered = QtCore.Signal(str, str, object)

    def target(self):
        zc = zeroconf.Zeroconf()
        browser = zeroconf.ServiceBrowser(zc, "_http._tcp.local.",
                                          handlers=[self.on_state_change])
        while True:
            time.sleep(0.5)

    def on_state_change(self, zeroconf, service_type, name, state_change):
        info = zeroconf.get_service_info(service_type, name)
        if info:
            self.deviceDiscovered.emit(name, socket.inet_ntoa(info.address), info)
