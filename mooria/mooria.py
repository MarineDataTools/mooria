import sys
import os
import logging
import argparse
import time
import locale
import yaml
import pkg_resources
import datetime
import geojson

# Get the version
version_file = pkg_resources.resource_filename('mooria','VERSION')

with open(version_file) as version_f:
   version = version_f.read().strip()

version_f.close()
# Get all builtin devices
dev_files = pkg_resources.resource_listdir('mooria','devices')
devices = {}
for fname in dev_files:
    fname_full = pkg_resources.resource_filename('mooria','devices/' + fname)
    print(fname,fname_full)    
    if(fname_full.endswith('.yaml')):
       f = open(fname_full,'r')
       devtmp = yaml.safe_load(f)
       f.close()
       devices.update(devtmp)


print(devices)

try:
    from PyQt5 import QtCore, QtGui, QtWidgets
except:
    from qtpy import QtCore, QtGui, QtWidgets


import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure




class mooriaMainWindow(QtWidgets.QMainWindow):
    def __init__(self,logging_level=logging.INFO):
        self.builtin_devices = devices
        QtWidgets.QMainWindow.__init__(self)
        mainMenu = self.menuBar()
        self.setWindowTitle("Mooria")
        self.mainwidget = mainWidget()
        self.setCentralWidget(self.mainwidget)
        
        quitAction = QtWidgets.QAction("&Quit", self)
        quitAction.setShortcut("Ctrl+Q")
        quitAction.setStatusTip('Closing the program')
        quitAction.triggered.connect(self.close_application)

        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(quitAction)
        self.statusBar()

    def close_application(self):
        sys.exit()                                



def main():
    app = QtWidgets.QApplication(sys.argv)
    window = mooriaMainWindow()
    w = 1000
    h = 600
    window.resize(w, h)
    window.show()
    sys.exit(app.exec_())
