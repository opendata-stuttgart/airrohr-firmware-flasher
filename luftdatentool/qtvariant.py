"""PyQt5 & PySide2 compatiblity layer stub. This will be updated when PySide2
gets mature enough"""

from PyQt5 import QtGui, QtCore, QtWidgets

# Replace nonsense prefixes
QtCore.Signal = QtCore.pyqtSignal
QtCore.Slot = QtCore.pyqtSlot
