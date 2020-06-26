from builtins import str
from builtins import range
from builtins import object
from qgis.PyQt.QtCore import QSettings, QVariant, Qt, QCoreApplication
from qgis.PyQt.QtWidgets import QMessageBox, QWidget, QMenu, QFileDialog
# from . import resources
from .geocoder_dialog import GeocoderDialog
import os.path
import locale
import pickle
import urllib.request, urllib.parse, urllib.error
import json
from qgis.core import QgsFeature, QgsGeometry, QgsVectorLayer, \
    QgsProject, QgsField, QgsPointXY, Qgis, QgsWkbTypes, QgsVectorFileWriter
from qgis.gui import QgsMessageBar
from qgis.utils import iface


class Geocoder(object):

    def __init__(self, parent):
        self.parent = parent
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # Create the dialog (after translation) and keep reference
        self.dlg = GeocoderDialog()
        # Declare instance attributes
        self.dlg.startButton.clicked.connect(self.accept)
        self.chooseApi()
        self.dlg.apiCb.currentIndexChanged.connect(self.chooseApi)
        self.dlg.apiCb.currentIndexChanged.connect(self.updateFieldNames)
        #self.dlg.apiCb.currentIndexChanged.connect(self.enableGeocoding) #uncomment if the new api requires certain params to be met before enabling geocoding
        QgsProject.instance().layersAdded.connect(self.listLayers)
        QgsProject.instance().layersRemoved.connect(self.listLayers)
        QgsProject.instance().layersWillBeRemoved.connect(self.beforeRemove)
        self.dlg.inComboBox.currentIndexChanged.connect(self.updateFieldNames)
        self.dlg.sObjCheckBox.clicked.connect(self.countFeatures)
        self.dlg.keyLineEdit.textChanged.connect(self.saveKey)

        APIs = ['LocIt']
        self.dlg.apiCb.addItems(APIs)
        self.listLayers()
        self.loadKey()

    def tr(self, message):
        return QCoreApplication.translate('Geocoder', message)

    def show(self):
        self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.dlg)
        # self.dlg.show()

    def saveKey(self):
        apiKey = 'gissupport/location_lab/{}'.format(self.dlg.apiCb.currentText())
        QSettings().setValue(apiKey, self.dlg.keyLineEdit.text())
        try:
            self.enableGeocoding()
        except AttributeError:
            pass


    def loadKey(self):
        apiKey = 'gissupport/location_lab/{}'.format(self.dlg.apiCb.currentText())
        self.dlg.keyLineEdit.setText(QSettings().value(apiKey) or '')


    def chooseApi(self):
        if self.dlg.apiCb.currentText() == 'LocIt':
            self.dlg.locitWidget.setVisible(True)
        else:
            #another api
            self.dlg.locitWidget.setVisible(False)


    def listLayers(self):
        self.dlg.label_counter.setText('0')
        self.dlg.progressBar.setFormat(self.tr('no addresses provided'))
        self.dlg.inComboBox.clear()
        self.dlg.stComboBox.clear()
        self.dlg.nrComboBox.clear()
        self.dlg.zipComboBox.clear()
        self.dlg.citComboBox.clear()
        self.layerList = []
        for layer in QgsProject.instance().mapLayers().values():
            try:
                if layer.wkbType() == QgsWkbTypes.NoGeometry and layer.isValid():
                    self.layerList.append(layer.name())
            except:
                pass
        self.dlg.inComboBox.addItems(self.layerList)


    def beforeRemove(self):
        try:
            self.disconnectSignals(self.curLayer)
        except:
            pass
        self.curLayer = None


    def beforeLayerChanges(self, layer): #called just before the self.curLayer.committed... signal slots, prevents QGIS 3 from crashing
        self.disconnectSignals(layer)


    def disconnectSignals(self, layer):
        try:
            layer.committedAttributesAdded.disconnect()
            layer.committedAttributesDeleted.disconnect()
            layer.committedAttributeValuesChanges.disconnect()
            layer.committedFeaturesAdded.disconnect()
            layer.committedFeaturesRemoved.disconnect()
            layer.committedGeometriesChanges.disconnect()
            layer.selectionChanged.disconnect()
            layer.beforeCommitChanges.disconnect()
        except:
            pass


    def updateFieldNames(self):
        self.dlg.stComboBox.clear()
        self.dlg.nrComboBox.clear()
        self.dlg.zipComboBox.clear()
        self.dlg.citComboBox.clear()
        self.progressValue = 0
        self.dlg.progressBar.setValue(self.progressValue)
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == self.dlg.inComboBox.currentText():
                try:
                    self.disconnectSignals(self.curLayer)
                except:
                    pass
                self.curLayer = layer
                #signals for changes within the current layer- if changes commited, set a new self.curLayer
                self.curLayer.committedAttributesAdded.connect(self.updateFieldNames)
                self.curLayer.committedAttributesDeleted.connect(self.updateFieldNames)
                self.curLayer.committedAttributeValuesChanges.connect(self.updateFieldNames)
                self.curLayer.committedFeaturesAdded.connect(self.updateFieldNames)
                self.curLayer.committedFeaturesRemoved.connect(self.updateFieldNames)
                self.curLayer.committedGeometriesChanges.connect(self.updateFieldNames)
                self.curLayer.selectionChanged.connect(self.countFeatures)
                self.curLayer.beforeCommitChanges.connect(lambda: self.beforeLayerChanges(self.curLayer))
                break
        try:
            fieldNames = [field.name() for field in self.curLayer.dataProvider().fields()]
            if self.dlg.apiCb.currentText() == 'LocIt':
                self.dlg.stComboBox.addItems(fieldNames)
                self.dlg.nrComboBox.addItems(fieldNames)
                self.dlg.zipComboBox.addItems(fieldNames)
                self.dlg.citComboBox.addItems(fieldNames)
            else:
                #another api
                pass
            self.countFeatures()
        except AttributeError:
            pass


    def enableGeocoding(self):
        if (self.featureCounter != 0
        and self.dlg.keyLineEdit.text()
        ):
            self.dlg.startButton.setEnabled(True)
        else:
            self.dlg.startButton.setEnabled(False)


    def encoded(self,val):
        if isinstance(val,(int, float)):
            val = str(val)
        return val if val else ''


    def defineParams(self):
        self.attrList = []
        if self.dlg.apiCb.currentText() == 'LocIt': #locit params
            self.paramsLocit = {
                'zip' : [],
                'city' : [],
                'street' : [],
                'building' : []
            }
            if not self.dlg.sObjCheckBox.isChecked():
                for feature in self.curLayer.getFeatures():
                    self.paramsLocit['street'].append(self.encoded(feature.attributes()[self.curLayer.fields().indexFromName(self.dlg.stComboBox.currentText())]))
                    self.paramsLocit['building'].append(self.encoded(feature.attributes()[self.curLayer.fields().indexFromName(self.dlg.nrComboBox.currentText())]))
                    self.paramsLocit['zip'].append(self.encoded(feature.attributes()[self.curLayer.fields().indexFromName(self.dlg.zipComboBox.currentText())]))
                    self.paramsLocit['city'].append(self.encoded(feature.attributes()[self.curLayer.fields().indexFromName(self.dlg.citComboBox.currentText())]))
                    self.attrList.append(feature.attributes())
            else:
                for feature in self.curLayer.selectedFeatures():
                    self.paramsLocit['street'].append(self.encoded(feature.attributes()[self.curLayer.fields().indexFromName(self.dlg.stComboBox.currentText())]))
                    self.paramsLocit['building'].append(self.encoded(feature.attributes()[self.curLayer.fields().indexFromName(self.dlg.nrComboBox.currentText())]))
                    self.paramsLocit['zip'].append(self.encoded(feature.attributes()[self.curLayer.fields().indexFromName(self.dlg.zipComboBox.currentText())]))
                    self.paramsLocit['city'].append(self.encoded(feature.attributes()[self.curLayer.fields().indexFromName(self.dlg.citComboBox.currentText())]))
                    self.attrList.append(feature.attributes())
            return 2
        else:
            #another api
            #return 1
            pass 


    def drawPoints(self):
        try:
            api = self.defineParams()
        except:
            self.iface.messageBar().pushMessage(
                'Location Lab: Geocoder',
                self.tr(u'Unknown error occurred'),
                level=Qgis.Critical)
            return
        outlayer = QgsVectorLayer('Point?crs=EPSG:4326', 'tempLLGeocoder', 'memory')
        if self.dlg.saveChkb.isChecked():
            saveFile = QFileDialog.getSaveFileName(None, self.tr('Save to...'), filter='*.shp') #returns tuple (path, extension)
            fileName = '{}{}'.format(saveFile[0], saveFile[1][-4:])
            layerName = os.path.basename(fileName)[:-4]
            QgsVectorFileWriter.writeAsVectorFormat(
                outlayer, fileName, "utf-8", outlayer.crs(), "ESRI Shapefile")
            outlayer = QgsVectorLayer(fileName, layerName, 'ogr')
        dp = outlayer.dataProvider()
        dp.addAttributes([QgsField('ID', QVariant.Int)] + self.curLayer.dataProvider().fields().toList())
        outlayer.updateFields()

        self.progressValue = 0
        self.dlg.progressBar.setValue(self.progressValue)
        if api == 1: #another api
            return
        else: #locit api
            gcLocit = 'https://api.locit.pl/webservice/address-hygiene/v1.0.0/'
            failedAdr = 0
            id = 1
            for attr in self.attrList:
                r = urllib.request.urlopen(gcLocit, data=urllib.parse.urlencode(
                    {
                        'key' : self.dlg.keyLineEdit.text(),
                        'zip' : self.paramsLocit['zip'][id-1],
                        'city' : self.paramsLocit['city'][id-1],
                        'street' : self.paramsLocit['street'][id-1],
                        'building' : self.paramsLocit['building'][id-1],
                        'geocoding' : '1',
                        'country' : 'POL',
                        'format' : 'json',
                        'charset' : 'UTF-8'
                    }
                ).encode())
                resp = json.loads(r.read().decode())
                if resp['info']['message'] == 'Authorisation: invalid key':
                    self.iface.messageBar().pushMessage(
                        'Location Lab: Geocoder',
                        self.tr(u'Invalid API key. Provide a correct one and try again.'),
                        level=Qgis.Warning)
                    return
                if resp['info']['code'] != 200:
                    self.iface.messageBar().pushMessage(
                        'Location Lab: Geocoder',
                        '{} "{}"'.format(self.tr(u'An API request error occurred. Error message:'), resp['info']['message']),
                        level=Qgis.Critical)
                    return
                try:
                    data = resp['data']
                except:
                    failedAdr += 1
                    self.progressValue += 1
                    self.dlg.progressBar.setValue(self.progressValue)
                    continue
                point = QgsPointXY(float(data['x']),float(data['y']))
                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromPointXY(point))
                feature.setAttributes([id] + attr)
                dp.addFeatures([feature])
                outlayer.updateExtents()
                id += 1
                self.progressValue += 1
                self.dlg.progressBar.setValue(self.progressValue)

        QgsProject.instance().addMapLayer(outlayer)
        if not failedAdr:
            self.iface.messageBar().pushMessage(
                'Location Lab: Geocoder',
                self.tr(u'Geocoding successful'),
                level=Qgis.Success)
        else:
            self.iface.messageBar().pushMessage(
                'Location Lab: Geocoder',
                u'{} {} {}'.format(self.tr(u'Failed to geocode'),failedAdr,self.tr(u'addresses')),
                level=Qgis.Warning)
            self.iface.messageBar().pushMessage(
                'Location Lab: Geocoder',
                self.tr(u'Geocoding done'),
                level=Qgis.Info)


    def countFeatures(self):
        try:
            if not self.dlg.sObjCheckBox.isChecked():
                self.featureCounter = 0
                if self.layerList:
                    for feature in self.curLayer.getFeatures():
                        self.featureCounter += 1
            elif not self.layerList:
                self.featureCounter = 0
            else:
                self.featureCounter = self.curLayer.selectedFeatureCount()
            self.dlg.label_counter.setText(str(self.featureCounter))
            if self.featureCounter:
                self.dlg.progressBar.setFormat(u'%v/%m {}'.format(self.tr('addresses computed')))
                self.dlg.progressBar.setMaximum(self.featureCounter)
            else:
                self.dlg.progressBar.setFormat(self.tr('no addresses provided'))
            self.enableGeocoding()
        except AttributeError:
            pass


    def accept(self):
        if self.drawPoints():
            super(Geocoder, self).dlg.accept()