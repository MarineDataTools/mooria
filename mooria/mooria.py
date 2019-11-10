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
        device_name = list(devices.keys())[0]
        device = devices[device_name]        
        mooring = self.create_mooring_widget(device_name,device) # device and device_name have to be removed, thats for the moment only
        self.moorings.append(mooring)        
        
        self.allmoorings = self.create_allmoorings_widget()
        self.loadsave = self.create_loadsave_widget()                
        # Tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self.allmoorings['widget'],'Moorings')        
        self.tabs.addTab(mooring['widget'],'Mooring')
        self.tabs.addTab(self.loadsave['widget'],'Load/Save')        
        self.layout = QtWidgets.QGridLayout(self)
        self.layout.addWidget(self.tabs,2,0,1,2)

    def create_loadsave_widget(self):
        mooring = {}
        mooring['widget']     = QtWidgets.QWidget()
        mooring['layout']     = QtWidgets.QVBoxLayout(mooring['widget'])
        mooring['load']    = QtWidgets.QPushButton('Load')
        mooring['load'].clicked.connect(self.load)
        mooring['save']    = QtWidgets.QPushButton('Save')
        mooring['save'].clicked.connect(self.save)
        mooring['csv']    = QtWidgets.QPushButton('Export csv')
        mooring['csv'].clicked.connect(self.save_csv)
        mooring['layout'].addWidget(mooring['load'])
        mooring['layout'].addWidget(mooring['save'])
        mooring['layout'].addWidget(mooring['csv'])
        mooring['layout'].addStretch()
        return mooring
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
        mooring['resize']    = QtWidgets.QPushButton('Resize to fit')
        mooring['resize'].clicked.connect(self._resize_to_fit)                        
        # Layout
        mooring['layout'].addWidget(mooring['table'],0,0,1,2)
        mooring['layout'].addWidget(mooring['addmoor'],1,0)
        mooring['layout'].addWidget(mooring['remmoor'],1,1)
        mooring['layout'].addWidget(mooring['edmoor'],2,0)
        mooring['layout'].addWidget(mooring['resize'],2,1)        

        # Creates the mooring table
        table = mooring['table']
        mooring['headers'] = {}
        mooring['headers']['Name'] = 0
        mooring['headers']['Long term mooring name'] = 1 # If the mooring is part of a sequential series of deployments
        mooring['headers']['Depth']     = 2        
        mooring['headers']['Deployed']  = 3
        mooring['headers']['Recovered'] = 4
        mooring['headers']['Longitude'] = 5
        mooring['headers']['Latitude']  = 6
        mooring['headers']['Campaign']  = 7        
        mooring['headers']['Comment']  = 8              
        table.setColumnCount(len(mooring['headers']))
        hlabels = list(mooring['headers'])
        mooring['header_labels'] = hlabels
        table.setHorizontalHeaderLabels(hlabels)
        table.resizeColumnsToContents()

        return mooring

    def create_mooring_widget(self, device_name,device):
        """
        """
        mooring = {}
        mooring['name']         = device_name
        mooring['widget']       = QtWidgets.QWidget()
        mooring['layout']       = QtWidgets.QGridLayout(mooring['widget'])
        mooring['devtable']     = QtWidgets.QTableWidget() # Table with all available devices to choose from
        mooring['devwidget']    = QtWidgets.QWidget() # Special widget to enter parameters for that device
        # Putting the widget into a scrollWidget
        mooring['scrollwidget'] = QtWidgets.QScrollArea()
        mooring['scrollwidget'].setWidgetResizable(True)
        mooring['scrolllayout'] = QtWidgets.QHBoxLayout(mooring['scrollwidget'])
        mooring['scrolllayout'].addWidget(mooring['scrollwidget'])
        mooring['scrollwidget'].setWidget(mooring['devwidget'])
        #mooring['scrollwidget'].setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        mooring['moortable']    = QtWidgets.QTableWidget() # Mooring table, here all devices of the mooring are listed
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.addWidget(mooring['moortable'])
        #splitter.addWidget(mooring['devwidget'])
        splitter.addWidget(mooring['scrollwidget'])
        splitter.addWidget(mooring['devtable'])
        mooring['splitter'] = splitter
        mooring['layout'].addWidget(splitter)
        #mooring['layout'].addWidget(mooring['moortable'],0,0)
        #mooring['layout'].addWidget(mooring['devwidget'],0,1)
        #mooring['layout'].addWidget(mooring['devtable'],0,2)
        
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

        # Create a blank mooring table
        table = mooring['moortable']
        table.setColumnCount(2)
        table.setRowCount(10)
        table.setHorizontalHeaderLabels(['Depth','Device'])
        table.resizeColumnsToContents()        

        mooring['devices'] = []        
        # Adding a test device
        device = self.create_device_widget(mooring, device_name,device)
        self.update_device_widget(mooring,device)
        return mooring

    def update_device_widget(self,mooring,device_new):
        """ updates the device widget with a new one
        """
        mooring['scrolllayout'].removeWidget(mooring['devwidget'])
        mooring['devwidget'] = device_new['widget']
        w = mooring['widget'].frameGeometry().width()
        h = mooring['widget'].frameGeometry().height()
        splitter_width = int(w/3)
        mooring['scrolllayout'].addWidget(mooring['devwidget'])
        mooring['splitter'].setSizes([splitter_width, splitter_width,splitter_width])
        #sizes = mooring['splitter'].sizes()
        #print(sizes)        
        #mooring['splitter'].setRubberBand(100)
    
    def create_device_widget(self,mooring,device_name,device_dict):
        """  Creates a device with all necessary widgets into the mooring dict
        """
        device = {}
        device['widget']    = QtWidgets.QWidget() # Special widget to enter parameters for that device        
        device['name'] = device_name        
        mooring['devices'].append(device)        
        device['widget_layout'] = QtWidgets.QFormLayout(device['widget'])
        lab = QtWidgets.QLabel(device_name)
        device['widget_layout'].addWidget(lab)
        # Serial number
        lab = QtWidgets.QLabel('Serial number')
        sered = QtWidgets.QLineEdit()
        device['widget_layout'].addRow(lab,sered)
        ## Depth
        #lab = QtWidgets.QLabel('Water Depth')
        #depthed = QtWidgets.QLineEdit()
        #device['widget_layout'].addRow(lab,depthed)        
        # Deployment location
        lab = QtWidgets.QLabel('Location')
        loced = QtWidgets.QLineEdit()
        locref = QtWidgets.QComboBox()
        locref.addItems(['Depth','Above bottom','Custom'])
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(loced)
        layout.addWidget(locref)        
        device['widget_layout'].addRow(lab,layout)        
        for i,k in enumerate(device_dict.keys()):
            if(k.lower() == 'parameter'):
                lab2 = QtWidgets.QLabel('Parameter')
                device['widget_layout'].addRow(lab2)                
                for par in device_dict[k]:
                    lab2 = QtWidgets.QLabel(par)
                    par = QtWidgets.QCheckBox()
                    device['widget_layout'].addRow(lab2,par)
            else:
                try:
                    device_dict[k]['options']
                    HAS_OPTION = True
                except:
                    HAS_OPTION = False

                print(device_dict[k],HAS_OPTION)
                if(HAS_OPTION):
                    optcombo = QtWidgets.QComboBox()
                    for op in device_dict[k]['options']:
                        optcombo.addItem(str(op))

                    lab2 = QtWidgets.QLabel(k)                        
                    device['widget_layout'].addRow(lab2,optcombo)
                else:
                    lab2 = QtWidgets.QLabel(k)
                    lineed = QtWidgets.QLineEdit(str(device_dict[k]))
                    device['widget_layout'].addRow(lab2,lineed)                    

        device['add']         = QtWidgets.QPushButton('Add to mooring')
        device['add'].mooring = mooring # This is a self reference to get the mooring by looking at the sender
        device['add'].device  = device  # This is a self reference to get the mooring by looking at the sender
        device['widget_layout'].addWidget(device['add'])                            
        device['add'].clicked.connect(self.add_device_to_mooring)
        return device

    def add_device_to_mooring(self):
        print('Add')
        # The mooring and device are references for convenience in create_device_widget
        mooring = self.sender().mooring
        device  = self.sender().mooring
        print(self.sender().mooring['name'])
        table = mooring['moortable']
        table.insertRow(0)
        item = QtWidgets.QTableWidgetItem( device['name'] )
        table.setItem(0,1,item)
        pass


    def create_mooring_dict(self):
        """Function that creates from all available information a dictionary

        """
        data = {}
        data['moorings'] = []
        table = self.allmoorings['table']        
        nrows = table.rowCount()
        ncols = table.columnCount()
        for i in range(nrows):
            mooring = {}
            try:
                mooring['name'] = table.item(i,self.allmoorings['headers']['Name']).text()
            except:
                mooring['name'] = ''
            try:
                mooring['depth'] = table.item(i,self.allmoorings['headers']['Depth']).text()
            except:
                mooring['depth'] = ''                
            try:
                mooring['longtermname'] = table.item(i,self.allmoorings['headers']['Long term mooring name']).text()
            except:
                mooring['longtermname'] = ''                
            try:                
                mooring['lon'] = table.item(i,self.allmoorings['headers']['Longitude']).text()
            except:
                mooring['lon'] = ''
            try:                
                mooring['lat'] = table.item(i,self.allmoorings['headers']['Latitude']).text()
            except:
                mooring['lat'] = ''                
            try:                
                mooring['deployed'] = table.item(i,self.allmoorings['headers']['Deployed']).text()
            except:
                mooring['deployed'] = ''                                
            try:                
                mooring['recovered'] = table.item(i,self.allmoorings['headers']['Recovered']).text()
            except:
                mooring['recovered'] = ''                                
            try:                
                mooring['comment'] = table.item(i,self.allmoorings['headers']['Comment']).text()
            except:
                mooring['comment'] = ''
                
            data['moorings'].append(mooring)

        return data

    def load_mooring_dict(self,data):
        table = self.allmoorings['table']        
        nrows = table.rowCount()
        ncols = table.columnCount()        
        for mooring in data['moorings']:
            table.insertRow(0)
            item = QtWidgets.QTableWidgetItem( mooring['name'] )            
            table.setItem(0,self.allmoorings['headers']['Name'],item)
            item = QtWidgets.QTableWidgetItem( mooring['longtermname'] )            
            table.setItem(0,self.allmoorings['headers']['Long term mooring name'],item)
            item = QtWidgets.QTableWidgetItem( mooring['depth'] )            
            table.setItem(0,self.allmoorings['headers']['Depth'],item)                        
            item = QtWidgets.QTableWidgetItem( mooring['deployed'] )            
            table.setItem(0,self.allmoorings['headers']['Deployed'],item)
            item = QtWidgets.QTableWidgetItem( mooring['recovered'] )            
            table.setItem(0,self.allmoorings['headers']['Recovered'],item)
            item = QtWidgets.QTableWidgetItem( mooring['lon'] )            
            table.setItem(0,self.allmoorings['headers']['Longitude'],item)
            item = QtWidgets.QTableWidgetItem( mooring['lat'] )            
            table.setItem(0,self.allmoorings['headers']['Latitude'],item)            
            item = QtWidgets.QTableWidgetItem( mooring['comment'] )            
            table.setItem(0,self.allmoorings['headers']['Comment'],item)
            pass

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
        table = self.allmoorings['table']
        lab = self.allmoorings['header_labels'][column] # Get the label
        item = table.item(row,column)
        print(item.text())
        # Check if the input is correct
        if(('longitude' in lab.lower()) or ('latitude' in lab.lower())):
            lonbad = 'dec. deg.'
            try:
                lon = float(item.text())
            except:
                lon = lonbad

            item_new = QtWidgets.QTableWidgetItem( str(lon) )
            # Check if we have already a change, otherwise it becomes recursive
            if(lonbad in item.text()):
                pass
            elif(str(lon) == item.text()):
                pass
            else:
                table.setItem(row,column,item_new)

        if(('deployed' in lab.lower()) or ('recovered' in lab.lower())):
            dbad = 'yyyy-mm-dd HH:MM:SS'
            try:
                date = datetime.datetime.strptime(item.text(),'%Y-%m-%d %H:%M:%S')
                item_new = QtWidgets.QTableWidgetItem( date.strftime('%Y-%m-%d %H:%M:%S'))
            except Exception as e:
                print(e)
                date = dbad
                item_new = QtWidgets.QTableWidgetItem( date)

            # Check if we have already a change, otherwise it becomes recursive
            if(dbad in item.text()):
                pass
            elif(str(date) == item.text()):
                pass
            else:
                table.setItem(row,column,item_new)

    def _resize_to_fit(self):
        table = self.allmoorings['table']        
        table.resizeColumnsToContents()

    def load(self):
        data = self.create_mooring_dict()        
        self.load_mooring_dict(data)
        print('Load')

    def save(self):
        print('Save')
        data = self.create_mooring_dict()
        print(data)

    def save_csv(self):
        print('Save csv')                


        

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
