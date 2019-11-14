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


class mainWidget(QtWidgets.QWidget):
    def __init__(self,logging_level=logging.INFO,within_qgis = False):
        QtWidgets.QWidget.__init__(self)        
        self.moorings = []
        device_name = list(devices.keys())[0]
        device = devices[device_name]        
        mooring = self.create_mooring_widget('Test') # device and device_name have to be removed, thats for the moment only
        self.moorings.append(mooring) 
        
        self.allmoorings = self.create_allmoorings_widget()
        self.loadsave = self.create_loadsave_widget()                
        # Tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.remove_tab)
        self.tabs.addTab(self.allmoorings['widget'],'Moorings')        
        self.tabs.addTab(self.loadsave['widget'],'Load/Save')
        self.tabs.addTab(mooring['widget'],'Mooring')
        tabbar = self.tabs.tabBar()
        tabbar.setTabButton(0, QtWidgets.QTabBar.RightSide,None)
        tabbar.setTabButton(1, QtWidgets.QTabBar.RightSide,None)        

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
        item_depth = QtWidgets.QTableWidgetItem( dstr )
        item_mab = QtWidgets.QTableWidgetItem( '{:3.3f}'.format(0) )        
        table.setRowCount(1)
        table.setItem(0,mooring['moortable_headers']['Device'],item)
        table.setItem(0,mooring['moortable_headers']['Depth'],item_depth)
        table.setItem(0,mooring['moortable_headers']['MAB'],item_mab)        
        table.setHorizontalHeaderLabels(mooring['moortable_header_labels'])
        table.resizeColumnsToContents()        

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
        mooring['devices'].append(device)        
        device['widget_layout'] = QtWidgets.QFormLayout(device['widget'])
        lab = QtWidgets.QLabel(device_name)
        device['widget_layout'].addWidget(lab)
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
        # All other dicts without special treatment
        for i,k in enumerate(device_dict.keys()):
            if(k.lower() == 'parameter'):
                lab2 = QtWidgets.QLabel('Parameter')
                device['widget_layout'].addRow(lab2)
                device['device_widgets']['parameter'] = {}                
                for par in device_dict[k]:
                    lab2 = QtWidgets.QLabel(par)
                    par = QtWidgets.QCheckBox()
                    device['device_widgets']['parameter'][par] = par 
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
                    device['device_widgets'][k] = optcombo
                    device['widget_layout'].addRow(lab2,optcombo)
                else:
                    lab2 = QtWidgets.QLabel(k)
                    lineed = QtWidgets.QLineEdit(str(device_dict[k]))
                    device['device_widgets'][k] = lineed
                    device['widget_layout'].addRow(lab2,lineed)                    

        device['add']          = QtWidgets.QPushButton('Add to mooring')
        device['add'].mooring  = mooring # This is a self reference to get the mooring by looking at the sender
        device['add'].device   = device  # This is a self reference to get the device by looking at the sender
        device['widget_layout'].addWidget(device['add'])                            
        device['add'].clicked.connect(self.add_device_to_mooring)
        return device

    def create_dict_from_device(self,device):
        """This is a major function, as it collects all the information in the
        widgets and crates a dictionary out of it, which can be saved
        or used to create a new device widget

        """
        pass

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
                # TODO, could save the removed devices
                
    def add_device_to_mooring(self):
        print('Add')
        # The mooring and device are references for convenience in create_device_widget
        mooring      = self.sender().mooring
        device       = self.sender().device
        device_blank = self.create_device_widget(mooring,device['name'],device['device_dict'].copy()) # Create a blank device to replace the original one
        #device_orig = self.sender().device        
        #device_dict = self.create_dict_from_device(device_orig)
        #device      = self.create_device_widget(mooring,device_dict['name'],device_dict)
        print(self.sender().mooring['name'])
        table = mooring['moortable']
        # Calculate depth/MAB of all devices listed
        rows = table.rowCount()
        depth = []
        MAB = []
        for i in range(rows):
            depthitem = table.item(i,mooring['moortable_headers']['Depth'])
            mabitem = table.item(i,mooring['moortable_headers']['MAB'])
            try:
                depth.append(float(depthitem.text()))
            except Exception as e:
                print(e)
                depth.append(np.NaN)

            try:
                MAB.append(float(mabitem.text()))
            except:
                MAB.append(np.NaN)                


        ## MAB = mooring['depth'] - depth
        ## depth = mooring['depth'] - MAB
        #for i in range(len
        print('MAB',MAB)
        print('Depth',depth)
        row = 0
        table.insertRow(row)
        print('Depth new device',device['device_widgets']['location'][0].text())
        print('Depth new device',device['device_widgets']['location'][1].currentText())
        refsystem = device['device_widgets']['location'][1].currentText()
        if('depth' in refsystem.lower()):
            item = QtWidgets.QTableWidgetItem( device['device_widgets']['location'][0].text() )
            table.setItem(row,mooring['moortable_headers']['Depth'],item)
        else:
            item = QtWidgets.QTableWidgetItem( device['device_widgets']['location'][0].text() )
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
                item = dtable.takeItem(i,0)
                item.device = device_blank
                dtable.setItem(i,0,item)
                self.update_device_widget(mooring, device_blank)


    def calc_MAB_depth_of_mooring(self,mooring):
        """ Calculates MAB (Meters above bottom) and depth vectors of the
        given devices and returns a dictionary containing both

        """

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
                mooring['longtermseries'] = table.item(i,self.allmoorings['headers']['Long term series']).text()
            except:
                mooring['longtermseries'] = ''                
            try:                
                mooring['lon'] = float(table.item(i,self.allmoorings['headers']['Longitude']).text())
            except:
                mooring['lon'] = ''
            try:                
                mooring['lat'] = float(table.item(i,self.allmoorings['headers']['Latitude']).text())
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
            try:                
                mooring['campaign'] = table.item(i,self.allmoorings['headers']['Campaign']).text()
            except:
                mooring['campaign'] = ''
                
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

    def add_mooring(self):
        table = self.allmoorings['table']
        nrows = table.rowCount()
        table.insertRow(nrows)

    def rem_mooring(self):
        print('rem')        
        pass

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
                    item.mooring
                    print('Has mooring')
                    HAS_MOORING=True
                except Exception as e:
                    print('No mooring',e)
                    
                if(HAS_MOORING): # Enter the new depth
                    rowcnt  = item.mooring['moortable'].rowCount()
                    botitem = item.mooring['moortable'].takeItem(rowcnt,mooring['moortable_headers']['Depth'])
                    botitem_new = QtWidgets.QTableWidgetItem( '{:3.3f}'.format(depth) )
                    print('Setting depth',rowcnt)
                    item.mooring['moortable'].setItem(rowcnt-1,mooring['moortable_headers']['Depth'],botitem_new)
                    
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
                device = item.device
                if(item.text() == 'bottom'): # Clicked at the bottom cell
                    return                

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
        data = self.create_mooring_dict()
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
