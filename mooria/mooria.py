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
import numpy as np

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

#https://gis.stackexchange.com/questions/208881/qtableview-qtablewidget-alternative-for-floats
# Need this, otherwise sorting is done as strings and not as numbers
class QCustomTableWidgetItem (QtWidgets.QTableWidgetItem):
    def __init__ (self, value):
        super(QCustomTableWidgetItem, self).__init__('%s' % value)

    def __lt__ (self, other):
        if (isinstance(other, QCustomTableWidgetItem)):
            selfDataValue  = float(self.data(QtCore.Qt.EditRole))
            otherDataValue = float(other.data(QtCore.Qt.EditRole))
            return selfDataValue < otherDataValue
        else:
            return QtWidgets.QTableWidgetItem.__lt__(self, other)

class mainWidget(QtWidgets.QWidget):
    def __init__(self,logging_level=logging.INFO,within_qgis = False):
        QtWidgets.QWidget.__init__(self)        
        self.moorings = []
        device_name = list(devices.keys())[0]
        device = devices[device_name]        

        self.allmoorings = self.create_allmoorings_widget()
        self.loadsave = self.create_loadsave_widget()                
        # Tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.remove_tab)
        self.tabs.addTab(self.allmoorings['widget'],'Moorings')        
        self.tabs.addTab(self.loadsave['widget'],'Load/Save')
        tabbar = self.tabs.tabBar()
        tabbar.setTabButton(0, QtWidgets.QTabBar.RightSide,None) # Make them not closable
        tabbar.setTabButton(1, QtWidgets.QTabBar.RightSide,None) # Make them not closable

        self.layout = QtWidgets.QGridLayout(self)
        self.layout.addWidget(self.tabs,2,0,1,2)

        self.add_new_mooring(name='Test',depth=100) # device and device_name have to be removed, thats for the moment only
        mooring_dict = self.create_mooring_dict()
        self.plot_mooring_dict(mooring_dict['moorings'][0],dpi=300)

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
        mooring['geojson']    = QtWidgets.QPushButton('Export as geojson')
        mooring['geojson'].clicked.connect(self.save_geojson)        
        mooring['layout'].addWidget(mooring['load'])
        mooring['layout'].addWidget(mooring['save'])
        mooring['layout'].addWidget(mooring['csv'])
        mooring['layout'].addWidget(mooring['geojson'])        
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
        mooring['headers']['Long term series'] = 1 # If the mooring is part of a sequential series of deployments
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

    def create_mooring_widget(self, mooring_name,depth = 0):
        """
        """
        mooring                 = {}
        mooring['depth']        = depth
        mooring['devices']      = []        
        mooring['name']         = mooring_name
        mooring['widget']       = QtWidgets.QWidget()
        mooring['layout']       = QtWidgets.QGridLayout(mooring['widget'])
        mooring['devtable']     = QtWidgets.QTableWidget() # Table with all available devices to choose from
        mooring['devtable'].cellClicked.connect(self._table_cell_was_clicked)
        mooring['devwidget']    = QtWidgets.QWidget() # Special widget to enter parameters for that device, this is a dummy
        # Putting the widget into a scrollWidget
        mooring['scrollwidget'] = QtWidgets.QScrollArea()
        mooring['scrollwidget'].setWidgetResizable(True)
        mooring['scrolllayout'] = QtWidgets.QHBoxLayout(mooring['scrollwidget'])
        mooring['scrolllayout'].addWidget(mooring['scrollwidget'])
        mooring['scrollwidget'].setWidget(mooring['devwidget'])        
        #mooring['scrollwidget'].setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        mooring['moortable']    = QtWidgets.QTableWidget() # Mooring table, here all devices of the mooring are listed
        mooring['moortable'].cellClicked.connect(self._table_cell_was_clicked)        
        mooring['moortable'].mooring = mooring # Self reference for easy use later
        mooring['moortable'].setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers) # Not editable

        moortablewidget      = QtWidgets.QTableWidget() # Table with all available devices to choose from
        moortablelayout      = QtWidgets.QGridLayout(moortablewidget)

        mooring['moorplotbutton'] = QtWidgets.QPushButton('Plot')
        mooring['moorplotbutton'].clicked.connect(self.plot_mooring)
        mooring['moorplotbutton'].mooring = mooring
        moortablelayout.addWidget(mooring['moortable'],0,0)
        moortablelayout.addWidget(mooring['moorplotbutton'],1,0)        
        
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.addWidget(moortablewidget)
        #splitter.addWidget(mooring['devwidget'])
        splitter.addWidget(mooring['scrollwidget'])
        splitter.addWidget(mooring['devtable'])
        mooring['splitter'] = splitter
        mooring['layout'].addWidget(splitter)
        #mooring['layout'].addWidget(mooring['moortable'],0,0)
        #mooring['layout'].addWidget(mooring['devwidget'],0,1)
        #mooring['layout'].addWidget(mooring['devtable'],0,2)
        
        # Fill the devices table
        mooring['devtable'].mooring = mooring # Self reference for easy use later      
        table = mooring['devtable']
        table.setColumnCount(1)
        table.setHorizontalHeaderLabels(['Name'])
        nrows = len(devices)
        for row,dev in enumerate(devices):
            item = QtWidgets.QTableWidgetItem( dev )
            # Add the device dictionary to the item, easy for referencing later
            item.device_dict = devices[dev]
            item.device_name = dev
            item.device = self.create_device_widget(mooring, item.device_name, item.device_dict)            
            table.insertRow(row)
            table.setItem(row,0,item)


        # Adding a test device        
        self.update_device_widget(mooring, item.device)
        table.resizeColumnsToContents()

        # Create a blank mooring table
        table = mooring['moortable']
        mooring['moortable_header_labels'] = ['Depth','MAB','Device','Serial Nr.','Parameter']
        mooring['moortable_headers']= {}
        for i in range(len(mooring['moortable_header_labels'])):
            mooring['moortable_headers'][mooring['moortable_header_labels'][i]] = i
            
        table.setColumnCount(len(mooring['moortable_header_labels']))
        # Create the seafloor (bottom)
        item = QtWidgets.QTableWidgetItem( 'bottom' )
        dstr = '{:3.3f}'.format(depth)
        #item_depth = QtWidgets.QTableWidgetItem( dstr )
        item_depth = QCustomTableWidgetItem( depth )
        item_mab = QtWidgets.QTableWidgetItem( '{:3.3f}'.format(0) )        
        table.setRowCount(1)
        table.setItem(0,mooring['moortable_headers']['Device'],item)
        table.setItem(0,mooring['moortable_headers']['Depth'],item_depth)
        table.setItem(0,mooring['moortable_headers']['MAB'],item_mab)        
        table.setHorizontalHeaderLabels(mooring['moortable_header_labels'])


        return mooring

    def update_device_widget(self,mooring,device_new):
        """ updates the device widget with a new one
        """
        mooring['devwidget'].hide()
        mooring['devwidget'] = device_new['widget']        
        w = mooring['widget'].frameGeometry().width()
        h = mooring['widget'].frameGeometry().height()
        splitter_width = int(w/3)
        ## Putting the widget into a scrollWidget
        mooring['scrollwidget'].takeWidget()        
        mooring['scrollwidget'].setWidget(mooring['devwidget'])
        mooring['devwidget'].show()
        mooring['splitter'].setSizes([splitter_width, splitter_width,splitter_width])
    
    def create_device_widget(self,mooring,device_name,device_dict):
        """  Creates a device with all necessary widgets into the mooring dict
        """
        device = {}
        device['widget']    = QtWidgets.QWidget() # Special widget to enter parameters for that device        
        device['name'] = device_name
        device['device_dict'] = device_dict.copy()
        device['device_widgets'] = {} # A dictionary with the same form as device_dict but with the responsible widgets in it
        # Name of the device and add button
        mooring['devices'].append(device)        
        device['widget_layout'] = QtWidgets.QFormLayout(device['widget'])
        lab = QtWidgets.QLabel(device_name)

        device['add']          = QtWidgets.QPushButton('Add to mooring')
        device['add'].mooring  = mooring # This is a self reference to get the mooring by looking at the sender
        device['add'].device   = device  # This is a self reference to get the device by looking at the sender
        #device['widget_layout'].addWidget(device['add'])                            
        device['add'].clicked.connect(self.add_device_to_mooring)
        
        device['widget_layout'].addRow(lab,device['add'])
        # Label
        lab = QtWidgets.QLabel('Label')
        lab.setToolTip('A custom name or description of the device')  
        labed = QtWidgets.QLineEdit()
        if('label' in device['device_dict']):
            sered.setText(str(device['device_dict']['label']))
        else:
            device['device_dict']['label'] = ''

        device['device_widgets']['label'] = labed # A list with the relevant widgets            
        device['widget_layout'].addRow(lab,labed)        
        # Serial number
        lab = QtWidgets.QLabel('Serial number')
        sered = QtWidgets.QLineEdit()
        if('Serial Number' in device['device_dict']):
            sered.setText(str(device['device_dict']['Serial Number']))
        else:
            device['device_dict']['Serial Number'] = ''
            device['device_widgets']['Serial Number'] = sered
            
        device['widget_layout'].addRow(lab,sered)
        # Depth
        lab = QtWidgets.QLabel('Location')
        loced = QtWidgets.QLineEdit()
        locref = QtWidgets.QComboBox()
        locref.addItems(['Depth','Above bottom'])
        layout = QtWidgets.QHBoxLayout()
        if('location' in device['device_dict']):
            sered.setText(str(device['device_dict']['location']))
        else:
            device['device_dict']['location'] = ''

        device['device_widgets']['location'] = [loced,locref] # A list with the relevant widgets
        layout.addWidget(loced)
        layout.addWidget(locref)        
        device['widget_layout'].addRow(lab,layout)

        # Add raw data files
        if('raw_data' in device['device_dict']):
            sered.setText(str(device['device_dict']['raw_data']))
        else:
            device['device_dict']['raw_data'] = ''

        lab = QtWidgets.QLabel('Raw data')
        dataed = QtWidgets.QLineEdit()
        dataref = QtWidgets.QPushButton('File(s)')
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(dataed)
        layout.addWidget(dataref)                
        device['widget_layout'].addRow(lab,layout)
        device['device_widgets']['raw_data'] = dataed
        # Add processed data files
        if('processed_data' in device['device_dict']):
            sered.setText(str(device['device_dict']['processed_data']))
        else:
            device['device_dict']['processed_data'] = ''

        lab = QtWidgets.QLabel('Processed data')
        dataed = QtWidgets.QLineEdit()
        dataref = QtWidgets.QPushButton('File(s)')
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(dataed)
        layout.addWidget(dataref)                
        device['widget_layout'].addRow(lab,layout)
        device['device_widgets']['processed_data'] = dataed        
        # All other dicts without special treatment
        for i,k in enumerate(device_dict.keys()):
            if(k.lower() == 'parameter'):
                lab2 = QtWidgets.QLabel('Parameter')
                device['widget_layout'].addRow(lab2)
                device['device_widgets']['parameter'] = {}                
                for par in device_dict[k]:
                    lab2 = QtWidgets.QLabel(par)
                    parcheck = QtWidgets.QCheckBox()
                    parcheck.setCheckState(True)
                    parcheck.setTristate(False)
                    device['device_widgets']['parameter'][par] = parcheck 
                    device['widget_layout'].addRow(lab2,parcheck)
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
                    device['device_widgets'][k] = optcombo
                    device['widget_layout'].addRow(lab2,optcombo)
                else:
                    lab2 = QtWidgets.QLabel(k)
                    lineed = QtWidgets.QLineEdit(str(device_dict[k]))
                    device['device_widgets'][k] = lineed
                    device['widget_layout'].addRow(lab2,lineed)                    

        return device


    def create_empty_device_widget(self):
        """  Creates a device with all necessary widgets into the mooring dict
        """
        device = {}
        device['widget']    = QtWidgets.QWidget() # Special widget to enter parameters for that device
        return device        

    def create_dict_from_device(self,device):
        """ This function collects all the information in the
        widgets and creates a dictionary out of it, which can be saved
        or used to create a new device widget

        """
        devdict = {}
        for i,k in enumerate(device['device_dict'].keys()):
            d = device['device_widgets'][k]
            #print('D:',d)
            #print(i,k)
            if(k == 'parameter'): # Parameter, check the checkboxes
               devdict['parameter'] = []        
               for j,kd in enumerate(d.keys()):
                   if(d[kd].isChecked()):
                       devdict['parameter'].append(kd)

            elif(isinstance(d,list)):
                print('List')
                data = d[0].text()
                data += ' ' + d[1].currentText() # A Qcombobox
                devdict[k] = data                
            else: # a Lineedit
                data = ''
                if(isinstance(d,QtWidgets.QComboBox)):
                    data = d.currentText()
                elif(isinstance(d,QtWidgets.QLineEdit)):
                    data = d.text()
                    
                devdict[k] = data
               
            
            
        return devdict

    def rem_device_to_mooring(self):
        print('Remove device from mooring')
        mooring = self.sender().mooring
        device  = self.sender().device
        # Check if the device is referenced in the devtable, if so replace it with None
        dtable = mooring['moortable']
        for i in range(dtable.rowCount()):
            print(i)
            try:
                dev = dtable.item(i,mooring['moortable_headers']['Device']).device
            except:
                dev = None

            # Found a device, will replace it with None
            if(dev == device):
                print('Found device! Will remove it',i)
                dtable.removeRow(i)
                device_blank = self.create_empty_device_widget()
                self.update_device_widget(mooring, device_blank)                
                # TODO, could save the removed devices

    def sort_devices_in_mooring(self,mooring):
        """
        """
        print('Updating')
                
    def add_device_to_mooring(self):
        print('Add')

        # The mooring and device are references for convenience in create_device_widget
        mooring      = self.sender().mooring
        device       = self.sender().device
        depth        = mooring['depth']
        #device_orig = self.sender().device        
        #device_dict = self.create_dict_from_device(device_orig)
        #device      = self.create_device_widget(mooring,device_dict['name'],device_dict)
        print(self.sender().mooring['name'])
        table = mooring['moortable']
        table.setSortingEnabled(False)        
        # Add new device (later a sorting will be done)
        row = 0
        table.insertRow(row)
        refsystem = device['device_widgets']['location'][1].currentText()
        try:
            depthtmp = float(device['device_widgets']['location'][0].text())
        except Exception as e:
            print('hgfhghj',e)
            depthtmp = np.NaN
            
        if('depth' in refsystem.lower()):
            depthdev = depthtmp
            MABdev   = depth - depthdev            

        else:
            MABdev   = depthtmp
            depthdev = depth - depthtmp

        print('hallo!',MABdev,depthdev,depth)
        #item = QtWidgets.QTableWidgetItem( '{:3.3f}'.format(depthdev) )
        item = QCustomTableWidgetItem(depthdev)
        #item = QtWidgets.QTableWidgetItem()
        #item.setData(QtCore.Qt.DisplayRole,depthdev)
        #item.setData(QtCore.Qt.EditRole,depthdev)
        table.setItem(row,mooring['moortable_headers']['Depth'],item)            
        item = QtWidgets.QTableWidgetItem( '{:3.3f}'.format(MABdev) ) 
        table.setItem(row,mooring['moortable_headers']['MAB'],item)

        item = QtWidgets.QTableWidgetItem( device['name'] )
        item.device = device
        table.setItem(row,mooring['moortable_headers']['Device'],item)
        # Change the add button
        device['add'].setText('Remove from mooring')
        device['add'].clicked.disconnect(self.add_device_to_mooring)
        device['add'].clicked.connect(self.rem_device_to_mooring)
        # Check if the device is referenced in the devtable, if so replace it with None
        dtable = mooring['devtable']
        for i in range(dtable.rowCount()):
            print(i)
            try:
                dev = dtable.item(i,0).device
            except:
                dev = None

            # Found a device, will replace it with None
            if(dev == device):
                print('Found device! Will replace it')
                #device_blank = self.create_device_widget(mooring,device['name'],device['device_dict'].copy()) # Create a blank device to replace the original one                
                device_blank = self.create_empty_device_widget()                                                
                item = dtable.takeItem(i,0)
                item.device = None
                dtable.setItem(i,0,item)
                self.update_device_widget(mooring, device_blank)        
        
        table.setSortingEnabled(True)
        table.sortByColumn(0,0)
        #table.sortItems(0, QtCore.Qt.AscendingOrder)
        if False:
            # Calculate depth/MAB of all devices listed
            rows = table.rowCount()        
            depths = []
            MABs = []
            for i in range(rows-1): # The last one is the bottom
                devitem = table.item(i,mooring['moortable_headers']['Device'])
                print('i',i,devitem.text())
                devtmp  = devitem.device
                try:
                    depthtmp = float(devtmp['device_widgets']['location'][0].text())
                except:
                    depthtmp = np.NaN


                # Check if we have depth or MAB
                refsystem = device['device_widgets']['location'][1].currentText()
                if('depth' in refsystem.lower()):
                    depthdev = depthtmp
                    MABdev   = depth - depthdev
                else:
                    MABdev   = depthtmp
                    depthdev = depth - depthtmp

                depths.append(depthdev)
                MABs.append(MABdev)            



    def calc_MAB_depth_of_mooring(self,mooring):
        """ Calculates MAB (Meters above bottom) and depth vectors of the
        given devices and returns a dictionary containing both

        """
        pass
    
    def plot_mooring(self):
        """
        """
        # This is a bit clumsy, we first create a dict of all mooring
        # and search then for the correct one 
        mooring_plot = self.sender().mooring
        mooring_dict_all = self.create_mooring_dict()
        table = self.allmoorings['table']        
        nrows = table.rowCount()
        ncols = table.columnCount()

        for i in range(nrows):
            mooring_dict = {}
            # Devices
            if True:
                try:
                   mooring = table.item(i,self.allmoorings['headers']['Name']).mooring
                   HAS_MOORING = True
                except Exception as e:
                   HAS_MOORING = False
                   print('mooring save',e)

                if HAS_MOORING:
                   print('Has mooring')
                   if(mooring_plot == mooring):
                       print('Plotting mooring')
                       mooring_dict = mooring_dict_all['moorings'][i]
                       self.plot_mooring_dict(mooring_dict)


    def plot_mooring_dict(self,mooring_dict,dpi=300):
        """ Plots a mooring dictionary using matplotlib
        """
        name  = mooring_dict['name']
        depth = float(mooring_dict['depth'])
        surface = 0
        if(depth < surface):
            surface = depth - 10
            
        fig       = Figure(dpi=dpi)
        fig.set_size_inches(10,10)
        figwidget = QtWidgets.QWidget()
        figwidget.setWindowTitle(name)
        canvas    = FigureCanvas(fig)
        canvas.setParent(figwidget)
        plotLayout = QtWidgets.QVBoxLayout()
        plotLayout.addWidget(canvas)
        figwidget.setLayout(plotLayout)
        #canvas.setMinimumSize(canvas.size()) # Prevent to make it smaller than the original size
        mpl_toolbar = NavigationToolbar(canvas, figwidget)
        plotLayout.addWidget(mpl_toolbar)

        # Plot the mooring
        ax = fig.add_axes([.1,.1,.8,.8])
        ax.plot([-.5,.5],[depth,depth],'-',color='grey',lw=4)
        ax.plot([-.5,.5],[surface,surface],'-',color='b',lw=4)
        YL = surface - depth
        print([-1,1],[depth-YL/10,surface+YL/10])
        ax.set_xlim([-1,1])
        ax.set_ylim([depth-YL/10,surface+YL/10])
        ax.set_ylabel('Depth [m]')
        
        canvas.draw()        
        figwidget.show()        
        

    def create_mooring_dict(self,with_devices=True):
        """Function that creates from all available information a dictionary

        """
        data = {}
        data['moorings'] = []
        table = self.allmoorings['table']        
        nrows = table.rowCount()
        ncols = table.columnCount()
        for i in range(nrows):
            mooring_dict = {}
            try:
                mooring_dict['name'] = table.item(i,self.allmoorings['headers']['Name']).text()
            except:
                mooring_dict['name'] = ''
            try:
                mooring_dict['depth'] = table.item(i,self.allmoorings['headers']['Depth']).text()
            except:
                mooring_dict['depth'] = ''                
            try:
                mooring_dict['longtermseries'] = table.item(i,self.allmoorings['headers']['Long term series']).text()
            except:
                mooring_dict['longtermseries'] = ''                
            try:                
                mooring_dict['lon'] = float(table.item(i,self.allmoorings['headers']['Longitude']).text())
            except:
                mooring_dict['lon'] = ''
            try:                
                mooring_dict['lat'] = float(table.item(i,self.allmoorings['headers']['Latitude']).text())
            except:
                mooring_dict['lat'] = ''                
            try:                
                mooring_dict['deployed'] = table.item(i,self.allmoorings['headers']['Deployed']).text()
            except:
                mooring_dict['deployed'] = ''                                
            try:                
                mooring_dict['recovered'] = table.item(i,self.allmoorings['headers']['Recovered']).text()
            except:
                mooring_dict['recovered'] = ''                                
            try:                
                mooring_dict['comment'] = table.item(i,self.allmoorings['headers']['Comment']).text()
            except:
                mooring_dict['comment'] = ''
            try:                
                mooring_dict['campaign'] = table.item(i,self.allmoorings['headers']['Campaign']).text()
            except:
                mooring_dict['campaign'] = ''

            # Devices
            if(with_devices):
                mooring_dict['devices'] = []
                try:
                   mooring = table.item(i,self.allmoorings['headers']['Name']).mooring
                   HAS_MOORING = True
                except Exception as e:
                   HAS_MOORING = False
                   print('mooring save',e)

                if HAS_MOORING:
                   print('Has mooring')
                   dtable = mooring['moortable']
                   # Loop over all devices and make a dict of them
                   for i in range(dtable.rowCount()):
                       try:
                           dev = dtable.item(i,mooring['moortable_headers']['Device']).device
                       except Exception as e:
                           print('Device exception:',str(e))
                           dev = None

                       if dev is not None: 
                           devdict = self.create_dict_from_device(dev)
                           mooring_dict['devices'].append(devdict)

            print(mooring_dict)
            data['moorings'].append(mooring_dict)

        return data

    def load_mooring_dict(self,data):
        table = self.allmoorings['table']        
        nrows = table.rowCount()
        ncols = table.columnCount()        
        for mooring in data['moorings']:
            table.insertRow(0)
            item = QtWidgets.QTableWidgetItem( mooring['name'] )            
            table.setItem(0,self.allmoorings['headers']['Name'],item)
            item = QtWidgets.QTableWidgetItem( mooring['longtermseries'] )            
            table.setItem(0,self.allmoorings['headers']['Long term series'],item)
            item = QtWidgets.QTableWidgetItem( mooring['depth'] )            
            table.setItem(0,self.allmoorings['headers']['Depth'],item)                        
            item = QtWidgets.QTableWidgetItem( mooring['deployed'] )            
            table.setItem(0,self.allmoorings['headers']['Deployed'],item)
            item = QtWidgets.QTableWidgetItem( mooring['recovered'] )            
            table.setItem(0,self.allmoorings['headers']['Recovered'],item)
            item = QtWidgets.QTableWidgetItem( '{:3.5f}'.format(mooring['lon']) )

            table.setItem(0,self.allmoorings['headers']['Longitude'],item)
            item = QtWidgets.QTableWidgetItem( '{:3.5f}'.format(mooring['lat']) )
            table.setItem(0,self.allmoorings['headers']['Latitude'],item)            
            item = QtWidgets.QTableWidgetItem( mooring['comment'] )            
            table.setItem(0,self.allmoorings['headers']['Comment'],item)
            try:
                item = QtWidgets.QTableWidgetItem( mooring['campaign'] )            
                table.setItem(0,self.allmoorings['headers']['Campaign'],item)
            except:
                pass

    def add_new_mooring(self,name=None,depth=None):
        """ Adds a new mooring
        """
        table = self.allmoorings['table']
        nrows = table.rowCount()
        table.insertRow(nrows)
        if(name is not None):
            item = QtWidgets.QTableWidgetItem( name )            
            table.setItem(nrows,self.allmoorings['headers']['Name'],item)

        if(depth is not None):
            item = QtWidgets.QTableWidgetItem( str(depth) )            
            table.setItem(nrows,self.allmoorings['headers']['Depth'],item)


        mooring = self.create_mooring_widget(name,depth=depth) 
        self.tabs.addTab(mooring['widget'],name)
        self.moorings.append(mooring)
        item = table.takeItem(nrows,self.allmoorings['headers']['Name'])
        item.mooring = mooring
        table.setItem(nrows,self.allmoorings['headers']['Name'],item)

    def add_mooring(self):
        table = self.allmoorings['table']
        nrows = table.rowCount()
        table.insertRow(nrows)

    def rem_mooring(self):
        print('rem')
        table = self.allmoorings['table']        
        #for items in table.selectedItems():
        rows = sorted(set(index.row() for index in
                          table.selectedIndexes()),reverse=True)
        for row in rows:
            item = table.item(row,0)
            name = item.text()
            print('row',row,'name',name)
            for i in range(self.tabs.count()):
                w = self.tabs.widget(i)
                try:
                    item.mooring['widget']
                    HAS_MOORING = True
                except Exception as e:
                    HAS_MOORING = False                    
                    pass
                if(HAS_MOORING and (w == item.mooring['widget'])):
                    self.remove_tab(i)                    
            
            table.removeRow(row)
            
    def edit_mooring(self):
        print('edit')
        table = self.allmoorings['table']        
        for item in table.selectedItems():
            row = item.row()            
            try:
                tmp = table.item(row,self.allmoorings['headers']['Name']).mooring
            except Exception as e:
                #print('Exception',e)
                tmp = None

            if(tmp == None):
                if(table.item(row,self.allmoorings['headers']['Name']) == None):
                    msg = QtWidgets.QMessageBox()
                    msg.setIcon(QtWidgets.QMessageBox.Warning)
                    msg.setInformativeText('Name the mooring first')
                    retval = msg.exec_()
                    return
                name = table.item(row,self.allmoorings['headers']['Name']).text()
                try:
                    depth = float(table.item(row,self.allmoorings['headers']['Depth']).text())
                except Exception as e:
                    print('Depth edit',e)
                    depth = ''
                    
                mooring = self.create_mooring_widget(name,depth=depth) 
                self.tabs.addTab(mooring['widget'],name)
                self.moorings.append(mooring)
                item = table.takeItem(row,self.allmoorings['headers']['Name'])
                item.mooring = mooring
                table.setItem(row,self.allmoorings['headers']['Name'],item)
                
            break


    def _allmoorings_cell_changed(self,row,column):
        """ 
        """
        print(row,column)
        table = self.allmoorings['table']
        lab = self.allmoorings['header_labels'][column] # Get the label
        item = table.item(row,column)

        # Check if the name has changed and rename the tab as well
        if(('name' == lab.lower())):
            for i in range(self.tabs.count()):
                w = self.tabs.widget(i)
                try:
                    item.mooring['widget']
                    HAS_MOORING = True
                except Exception as e:
                    HAS_MOORING = False                    
                    pass
                if(HAS_MOORING and (w == item.mooring['widget'])):
                    self.tabs.setTabText(i,item.text())

        # Check if the input is correct                
        if(('depth' in lab.lower())):
            depthbad = ''
            depth = item.text()
            if(item.text() == depthbad):
                return

            try:
                depth = float(depth)
                item_new = QtWidgets.QTableWidgetItem( '{:3.3f}'.format(depth) )                
            except:
                depth = depthbad
                item_new = QtWidgets.QTableWidgetItem( depthbad )
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setInformativeText('Enter depth as a number e.g. 200.4 (unit is m)')
                retval = msg.exec_()

            print('Depth',depth)
            # Check if we have already a change, otherwise it becomes recursive
            if(depthbad == item.text()):
                pass
            elif(depth == depthbad):
                table.setItem(row,column,item_new)
            elif('{:3.3f}'.format(depth) == item.text()): # If everything is fine, update the mooring, if existing
                item = table.item(row,self.allmoorings['headers']['Name'])
                HAS_MOORING = False
                try:
                    item.mooring['moortable']
                    print('Has mooring')
                    HAS_MOORING=True
                except Exception as e:
                    print('No mooring',e)
                    
                if(HAS_MOORING): # Enter the new depth
                    rowcnt  = item.mooring['moortable'].rowCount()
                    botitem = item.mooring['moortable'].takeItem(rowcnt,item.mooring['moortable_headers']['Depth'])
                    botitem_new = QtWidgets.QTableWidgetItem( '{:3.3f}'.format(depth) )
                    print('Setting depth',rowcnt)
                    item.mooring['moortable'].setItem(rowcnt-1,item.mooring['moortable_headers']['Depth'],botitem_new)
                    
            else:
                table.setItem(row,column,item_new)            
            


        if(('longitude' in lab.lower()) or ('latitude' in lab.lower())):
            print('Position')
            lonbad = ''
            pos = item.text()
            if(item.text() == lonbad):
                return
            
            sign = None
            # Check if different format and convert to float
            if(('E' in pos) or ('N' in pos)):
                sign = 1
                pos = pos.replace('E',' ')
                pos = pos.replace('N',' ')                
            if(('W' in pos) or ('S' in pos)):
                sign = -1
                pos = pos.replace('W',' ')
                pos = pos.replace('S',' ')

            if(sign is not None): # If we have a decimal degree format
                try:
                    pos = sign  * (float(pos.split(' ')[0]) + float(pos.split(' ')[1])/60)
                except Exception as e:
                    pass

            try:
                lon = float(pos)
                item_new = QtWidgets.QTableWidgetItem( '{:3.5f}'.format(lon) )                
            except:
                lon = lonbad
                item_new = QtWidgets.QTableWidgetItem( lonbad )
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setInformativeText('Enter position in decimal degrees e.g. 20.2, -20.2 or in degree and decimal minutes, e.g. 57N32.3, 40S32.0')
                retval = msg.exec_()


            # Check if we have already a change, otherwise it becomes recursive
            if(lonbad == item.text()):
                pass
            elif(lon == lonbad):
                table.setItem(row,column,item_new)            
            elif('{:3.5f}'.format(lon) == item.text()):
                pass
            else:
                table.setItem(row,column,item_new)

        if(('deployed' in lab.lower()) or ('recovered' in lab.lower())):
            dbad = ''
            if(len(item.text()) > 0):
                print('Date')
                try:
                    try:
                        date = datetime.datetime.strptime(item.text(),'%Y-%m-%d %H:%M:%S')
                    except:
                        date = datetime.datetime.strptime(item.text(),'%Y-%m-%d %H:%M')

                    item_new = QtWidgets.QTableWidgetItem( date.strftime('%Y-%m-%d %H:%M:%S'))
                except Exception as e:
                    date = dbad
                    msg = QtWidgets.QMessageBox()
                    msg.setIcon(QtWidgets.QMessageBox.Warning)
                    msg.setInformativeText('Enter date in format yyyy-mm-dd HH:MM(:SS)')
                    retval = msg.exec_()                
                    item_new = QtWidgets.QTableWidgetItem( date)

            # Check if we have already a change, otherwise it becomes recursive
            if(dbad == item.text()):
                pass
            elif(str(date) == item.text()):
                pass
            else:
                table.setItem(row,column,item_new)

    def _resize_to_fit(self):
        table = self.allmoorings['table']        
        table.resizeColumnsToContents()

    def _table_cell_was_clicked(self, row, column):
        """ Function for the table displaying all devices
        """
        print("Row %d and Column %d was clicked" % (row, column))
        print(self.sender())
        table = self.sender()
        item = table.item(row, column)
        mooring = table.mooring
        DEVTABLE=False
        if(item == None):
            return
        if(table == mooring['moortable']):
            if(column == mooring['moortable_headers']['Device']): # The device name column, here the items have all the information
                print('moortable')
                if(item.text() == 'bottom'): # Clicked at the bottom cell
                    return
                
                device = item.device
                self.update_device_widget(mooring,device)

            else:
                return
                    
        elif(table == mooring['devtable']):
            print('devtable')
            device_dict = item.device_dict
            device_name = item.device_name
            print(item.device_dict)            
            DEVTABLE=True
            
        #print(item.text())
        if(DEVTABLE):
            try:
                device = item.device # can be a device dict or None
            except:
                device = None

            if device == None:
                device = self.create_device_widget(mooring,device_name,device_dict)
                item.device = device
                table.setItem(row,column,item)
            
            self.update_device_widget(mooring,device)        

    def load(self):
        filename,extension  = QtWidgets.QFileDialog.getOpenFileName(self,"Choose file for summary","","All Files (*)")

        # Opening the yaml file
        try:
            stream = open(filename, 'r')
            data_yaml = yaml.safe_load(stream)
        except Exception as e:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setInformativeText('No valid or not existing yaml file (' + str(e) + ')')
            retval = msg.exec_()            
            return
        
        self.load_mooring_dict(data_yaml)
        print('Load')

    def save(self):
        print('Save')
        data = self.create_mooring_dict()
        filename,extension  = QtWidgets.QFileDialog.getSaveFileName(self,"Choose file for summary","","All Files (*)")
        self.save_yaml_summary(data,filename)

    def save_yaml_summary(self,summary,filename):
        """ Save a yaml summary
        """
        if ('.yaml' not in filename):
            filename += '.yaml'
        
        print('Create yaml summary in file:' + filename)
        with open(filename, 'w') as outfile:
            yaml.dump(summary, outfile, default_flow_style=False)

    def save_geojson(self):
        data = self.create_mooring_dict(with_devices = False) # Only the metainformation, not the devices of the mooring
        filename,extension  = QtWidgets.QFileDialog.getSaveFileName(self,"Choose file for summary","","All Files (*)")
        self.save_geojson_summary(data,filename)

    def save_geojson_summary(self,summary,filename):
        """ Save a geojson summary
        """
        if ('.geojson' not in filename):
            filename += '.geojson'

        print('Create geojson summary in file:' + filename)
        crs = { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } } # Reference coordinate system

        #['date','lon','lat','station','campaign','file','comment']
        if True:
            try:
                properties = summary['moorings'][0].keys()
            except:
                properties = []


        if(len(properties) > 0):
            features = []
            for i,d in enumerate(summary['moorings']):
                csv_line = ''
                try:
                    lon = float(d['lon'])
                    lat = float(d['lat'])
                except Exception as e:
                    print('No valid positions in mooring:' + d['name'] +  ' will not export it.' )
                    continue
                p = geojson.Point((lon, lat))
                prop = {}
                for o in properties:
                    prop[o] = d[o]

                feature = geojson.Feature(geometry=p, properties=prop)
                features.append(feature)

            featurecol = geojson.FeatureCollection(features,name='moorings',crs=crs)
            with open(filename, 'w') as outfile:
                geojson.dump(featurecol, outfile)

            outfile.close()


    def save_csv(self,delimiter=';'):
        filename,extension  = QtWidgets.QFileDialog.getSaveFileName(self,"Choose file for csv summary","","All Files (*)")
        self.create_csv(filename)
        
    def create_csv(self,filename,delimiter=';',header=None):
        if(header == None):
            header = ['Name','Depth','Longitude','Latitude','Deployed','Recovered']

        if ('.csv' not in filename):
            filename += '.csv'

        print('Opening',filename)
        f = open(filename,'w')
        table = self.allmoorings['table']        
        nrows = table.rowCount()
        ncols = table.columnCount()
        header = ['Name','Depth','Longitude','Latitude','Deployed','Recovered']
        # Write the header
        lstr = ''        
        for head in header:
            lstr += head + delimiter

        lstr = lstr[:lstr.rfind(delimiter)] + '\n' # Get rid of the last delimiter
        f.write(lstr)        
        # Write the data
        for i in range(nrows):
            lstr = ''
            for head in header:
                lstr += table.item(i,self.allmoorings['headers'][head]).text() + delimiter
                
            lstr = lstr[:lstr.rfind(delimiter)] + '\n' # Get rid of the last delimiter
            f.write(lstr)

        f.close()

    def remove_tab(self,index):
        print('Remove tab',index)
        widget = self.tabs.widget(index)
        if widget is not None:
            widget.hide()
        self.tabs.removeTab(index)



        

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
    w = int(rect.width() * 3/4)
    h = int(rect.height() * 2/3)
    window.resize(w, h)
    window.show()
    sys.exit(app.exec_())
