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

        ports = None
        while True:
            new_ports = serial.tools.list_ports.comports()

            if ports is None or [p.name for p in ports] != [p.name for p in new_ports]:
                self.portsUpdate.emit(new_ports)

            time.sleep(self.interval)

            ports = new_ports
            # #print(ports)
            # if (ports != []) and (self.ip_addr == None):
            #     print(str(ports[0]).split()[0])
            #     ser = serial.Serial(str(ports[0]).split()[0], parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS)
            #     print(ser.inWaiting())
            #     i = 0
            #     while True:
            #         if ser.inWaiting() > 0:
            #             data = str(ser.readline())[2:]
            #             print(data)
            #             if data[0:14] == "WiFi connected":
            #                 self.ip_addr = data[23:37]
            #                 print(self.ip_addr)
            #                 break
            #         #if 

            # #print(ports[0])


class FirmwareListThread(QuickThread):
    listLoaded = QtCore.Signal([list])

    def target(self):
        """Downloads list of available firmware updates in separate thread."""
        self.listLoaded.emit(["firmware_ru", "firmware_en"])


class ZeroconfDiscoveryThread(QuickThread):
    deviceDiscovered = QtCore.Signal(str, str, object)
    browser = None
    #print("in ZeroconfDiscoveryThread")

    def target(self):
        """This thread scans for Bonjour/mDNS devices and emits
        deviceDiscovered signal with its name, address and info object"""
        self.zc = zeroconf.Zeroconf()
        self.browser = zeroconf.ServiceBrowser(
            self.zc, "_http._tcp.local.", handlers=[self.on_state_change])
        while True:
            
            time.sleep(0.5)

    def on_state_change(self, zeroconf, service_type, name, state_change):
        #print("on_state_change")
        info = zeroconf.get_service_info(service_type, name)
        #print(info.address)
        if info:
            for addr in info.parsed_addresses():
                self.deviceDiscovered.emit(name, addr, info)

    def stop(self):
        if self.browser:
            self.browser.cancel()
