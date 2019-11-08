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


class mainWidget(QtWidgets.QWidget):
    def __init__(self,logging_level=logging.INFO,within_qgis = False):
        QtWidgets.QWidget.__init__(self)        
        self.moorings = []
        mooring = self.create_mooring_widget()
        self.allmoorings = self.create_allmoorings_widget()        
        # Tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self.allmoorings['widget'],'Moorings')        
        self.tabs.addTab(mooring['widget'],'Mooring')
        self.layout = QtWidgets.QGridLayout(self)
        self.layout.addWidget(self.tabs,2,0,1,2)        
        
    def create_allmoorings_widget(self):
        mooring = {}
        mooring['widget']     = QtWidgets.QWidget()
        mooring['layout']     = QtWidgets.QGridLayout(mooring['widget'])
        mooring['table']  = QtWidgets.QTableWidget()
        mooring['table'].cellChanged.connect(self._allmoorings_cell_changed)
        mooring['edmoor']    = QtWidgets.QPushButton('Edit')
        mooring['edmoor'].clicked.connect(self.edit_mooring)                
        mooring['addmoor']    = QtWidgets.QPushButton('Add')
        mooring['addmoor'].clicked.connect(self.add_mooring)
        mooring['remmoor']    = QtWidgets.QPushButton('Rem')
        mooring['remmoor'].clicked.connect(self.rem_mooring)        
        # Layout
        mooring['layout'].addWidget(mooring['table'],0,0,1,2)
        mooring['layout'].addWidget(mooring['edmoor'],1,0,1,2)        
        mooring['layout'].addWidget(mooring['addmoor'],2,0)
        mooring['layout'].addWidget(mooring['remmoor'],2,1)                

        # Creates the mooring table
        table = mooring['table']
        mooring['headers'] = {}
        mooring['headers']['Name'] = 0
        mooring['headers']['Long term mooring name'] = 1 # If the mooring is part of a sequential series of deployments
        mooring['headers']['Deployed']  = 2
        mooring['headers']['Recovered'] = 3
        mooring['headers']['Longitude'] = 4
        mooring['headers']['Latitude']  = 5
        mooring['headers']['Campaign']  = 6        
        mooring['headers']['Comments']  = 7               
        table.setColumnCount(len(mooring['headers']))
        hlabels = list(mooring['headers'])
        mooring['header_labels'] = hlabels
        table.setHorizontalHeaderLabels(hlabels)
        table.resizeColumnsToContents()

        return mooring

        
    def create_mooring_widget(self):
        """
        """
        mooring = {}
        mooring['widget']     = QtWidgets.QWidget()
        mooring['layout']     = QtWidgets.QGridLayout(mooring['widget'])
        mooring['devtable']   = QtWidgets.QTableWidget() # Table with all available devices to choose from
        mooring['devwidget']  = QtWidgets.QWidget() # Special widget to enter parameters for that device
        mooring['moortable']  = QtWidgets.QTableWidget()
        mooring['layout'].addWidget(mooring['moortable'],0,0)
        mooring['layout'].addWidget(mooring['devwidget'],0,1)
        mooring['layout'].addWidget(mooring['devtable'],0,2)
        
        # Fill the devices table
        table = mooring['devtable']
        table.setColumnCount(1)
        table.setHorizontalHeaderLabels(['Name'])
        nrows = len(devices)
        for row,dev in enumerate(devices):
            item = QtWidgets.QTableWidgetItem( dev )            
            table.insertRow(row)
            table.setItem(row,0,item)
            
        table.resizeColumnsToContents()
        device_name = list(devices.keys())[0]
        device = devices[device_name]
        self.update_device_widget(mooring, device_name,device)
        
        self.moorings.append(mooring)
        return mooring
    
    def update_device_widget(self,mooring,device_name,device):
        mooring['devwidget_layout'] = QtWidgets.QVBoxLayout(mooring['devwidget'])
        lab = QtWidgets.QLabel(device_name)
        mooring['devwidget_layout'].addWidget(lab)        
        lab2 = QtWidgets.QLabel('Test')
        print(device)
        for i,k in enumerate(device.keys()):
            lab2 = QtWidgets.QLabel(k)
            mooring['devwidget_layout'].addWidget(lab2)

        #mooring['devwidget_layout'].insertWidget(1,lab2)
        mooring['devwidget_layout'].addStretch()

    def add_mooring(self):
        table = self.allmoorings['table']        
        table.insertRow(0)
        print('add')

    def rem_mooring(self):
        print('rem')        
        pass

    def edit_mooring(self):
        print('edit')        
        pass

    def _allmoorings_cell_changed(self,row,column):
        print(row,column)
        lab = self.allmoorings['header_labels'][column] # Get the label
        if('longitude' in lab.lower()):
            print('Longitude')
        if('latitude' in lab.lower()):
            print('Latitude')
        if('deployed' in lab.lower()):
            print('deployed')
        if('recovered' in lab.lower()):
            print('recovered')                                    
        

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

    screen = app.primaryScreen()
    print('Screen: %s' % screen.name())
    size = screen.size()
    print('Size: %d x %d' % (size.width(), size.height()))
    rect = screen.availableGeometry()
    print('Available: %d x %d' % (rect.width(), rect.height()))
    w = int(rect.width() * 2/3)
    h = int(rect.height() * 2/3)
    window.resize(w, h)
    window.show()
    sys.exit(app.exec_())
