from builtins import str
from builtins import range
from qgis.PyQt.QtCore import QSettings, QVariant, Qt, QCoreApplication, QObject
from qgis.PyQt.QtWidgets import QMessageBox, QWidget, QMenu, QFileDialog, QTableWidget, QHeaderView, QTableWidgetItem

from .modules.openrouteservice.geocoder import GeocoderORS
from .geocoder_dialog import GeocoderDialog
import os.path
import locale
import pickle
import urllib.request, urllib.parse, urllib.error
import json
from collections import defaultdict
from qgis.core import QgsFeature, QgsGeometry, QgsVectorLayer, \
    QgsProject, QgsField, QgsPointXY, Qgis, QgsWkbTypes, QgsVectorFileWriter, QgsRasterLayer
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
        self.dlg.apiComboBox.currentIndexChanged.connect(self.chooseApi)
        #self.dlg.apiComboBox.currentIndexChanged.connect(self.enableGeocoding) #uncomment if the new api requires certain params to be met before enabling geocoding
        QgsProject.instance().layersAdded.connect(self.listLayers)
        QgsProject.instance().layersRemoved.connect(self.listLayers)
        QgsProject.instance().layersWillBeRemoved.connect(self.beforeRemove)
        self.dlg.inComboBox.currentIndexChanged.connect(self.updateFieldNames)
        self.dlg.sObjCheckBox.clicked.connect(self.countFeatures)
        self.dlg.keyLineEdit.textChanged.connect(self.saveKey)
        self.geocoder = GeocoderORS(self)
        APIs = ['OpenRouteService']
        self.dlg.apiComboBox.addItems(APIs)
        self.listLayers()


    def tr(self, message):
        return QCoreApplication.translate('Geocoder', message)

    def show(self):
        self.chooseApi()
        self.updateFieldNames()
        self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.dlg)

    def saveKey(self):
        api = self.dlg.apiComboBox.currentText()
        api_key = self.dlg.keyLineEdit.text()
        QSettings().setValue('gissupport/location_lab/{}'.format(api), api_key)
        self.geocoder.saveKey(api_key)
        try:
            self.enableGeocoding()
        except AttributeError:
            pass


    def loadKey(self):
        api = 'gissupport/location_lab/{}'.format(self.dlg.apiComboBox.currentText())
        api_key = QSettings().value(api) or ''
        self.dlg.keyLineEdit.setText(api_key)
        self.geocoder.saveKey(api_key)


    def chooseApi(self):
        if self.dlg.apiComboBox.currentText() == 'OpenRouteService':
            self.dlg.parametersWidget.setVisible(True)
            self.geocoder = GeocoderORS(self)
            self.loadKey()
            self.dlg.failedRequestsTableView.setModel(self.geocoder.error_table_model)
        else:
            #another api
            self.dlg.parametersWidget.setVisible(False)

    def listLayers(self, layers=None):
        if not layers:
            self.dlg.label_counter.setText('0')
            self.dlg.progressBar.setFormat(self.tr('no addresses provided'))
            self.dlg.inComboBox.clear()
            self.dlg.streetComboBox.clear()
            self.dlg.houseNumberComboBox.clear()
            self.dlg.zipComboBox.clear()
            self.dlg.cityComboBox.clear()
            self.layers = set()
            for layer in QgsProject.instance().mapLayers().values():
                if self._checkLayerGeometry(layer):
                    self.layers.add(layer.name())
            self.dlg.inComboBox.addItems(self.layers)
        else:
            for layer in layers:
                if not isinstance(layer, str):
                    if layer.name() == 'tempGeocoderLayer':
                        #skip layer created by geocoder plugin
                        continue
                    if self._checkLayerGeometry(layer):
                        self.layers.add(layer.name())
                        self.dlg.inComboBox.addItem(layer.name())
                else:
                    layer_name = layer.split('_')[0]
                    if layer_name in self.layers:
                        self.layers.remove(layer_name)
                        layer_index = self.dlg.inComboBox.findText(layer_name)
                        if layer_index != -1:
                            self.dlg.inComboBox.removeItem(layer_index)


    def beforeRemove(self, layers):
        if self.curLayer is None:
            return
        for layer in layers:
            if self.curLayer.name() in layer:
                self.dlg.label_counter.setText('0')
                self.dlg.progressBar.setFormat(self.tr('no addresses provided'))
                try:
                    self.curLayer.layerModified.disconnect()
                    self.curLayer.featureAdded.disconnect()
                    self.curLayer.featureDeleted.disconnect()
                    self.curLayer.geometryChanged.disconnect()
                except:
                    pass
                self.curLayer = None
                break


    def updateFieldNames(self):
        self.dlg.streetComboBox.clear()
        self.dlg.houseNumberComboBox.clear()
        self.dlg.zipComboBox.clear()
        self.dlg.cityComboBox.clear()
        self.progressValue = 0
        self.dlg.progressBar.setValue(self.progressValue)
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == self.dlg.inComboBox.currentText():
                try:
                    self.disconnectSignals(self.curLayer)
                except:
                    pass
                self.curLayer = layer
                self.curLayer.layerModified.connect(self.countFeatures)
                self.curLayer.featureAdded.connect(self.countFeatures)
                self.curLayer.featureDeleted.connect(self.countFeatures)
                self.curLayer.geometryChanged.connect(self.countFeatures)
                break
        try:
            fieldNames = [field.name() for field in self.curLayer.dataProvider().fields()]
            if self.dlg.apiComboBox.currentText() == 'OpenRouteService':
                self.dlg.streetComboBox.addItems(fieldNames)
                self.dlg.houseNumberComboBox.addItems(fieldNames)
                self.dlg.zipComboBox.addItems(fieldNames)
                self.dlg.cityComboBox.addItems(fieldNames)
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


    def getFeatureEncodedValue(self, ft, name):
        fields = self.curLayer.fields()
        return self._encode(ft.attributes()[fields.indexFromName(name)])


    def defineParams(self):
        self.feature_attributes = []

        if not self.dlg.sObjCheckBox.isChecked():
            features = self.curLayer.getFeatures()
        else:
            features = self.curLayer.getSelectedFeatures()
        if self.geocoder.NAME == 'OpenRouteService':
            self.geocode_parameters = defaultdict(list)
            for feature in features:
                address = ' '.join([
                    self.getFeatureEncodedValue(feature, self.dlg.streetComboBox.currentText()),
                    self.getFeatureEncodedValue(feature, self.dlg.houseNumberComboBox.currentText())
                ])
                self.geocode_parameters['address'].append(address)
                self.geocode_parameters['postalcode'].append(self.getFeatureEncodedValue(feature, self.dlg.zipComboBox.currentText()))
                self.geocode_parameters['locality'].append(self.getFeatureEncodedValue(feature, self.dlg.cityComboBox.currentText()))
                self.feature_attributes.append(feature.attributes())


    def drawPoints(self):
        try:
            self.defineParams()
        except:
            self.iface.messageBar().pushMessage(
                'Location Lab: Geocoder',
                self.tr(u'Unknown error occurred'),
                level=Qgis.Critical)
            return
        outlayer = QgsVectorLayer('Point?crs=EPSG:4326', 'tempGeocoderLayer', 'memory')
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

        progress = 0
        self.dlg.progressBar.setValue(progress)
        for id, attr in enumerate(self.feature_attributes):
            address = self.geocode_parameters['address'][id]
            request_params = {
                'address': urllib.parse.quote(address),
                'postalcode': self.geocode_parameters['postalcode'][id],
                'locality': urllib.parse.quote(self.geocode_parameters['locality'][id]),
            }

            geocoder_response = self.geocoder.createApiRequest(request_params)

            error = geocoder_response.get('error')
            if error == 'Invalid API Key':
                self.iface.messageBar().pushMessage(
                    'Location Lab: Geocoder',
                    error,
                    level=Qgis.Critical
                )
                return
            elif error:
                full_address = ', '.join([self.geocode_parameters['locality'][id], address])
                self.geocoder.error_table_model.insertRows([
                    {'id': id + 1, 'address': full_address, 'error': error}
                ])
            else:
                new_features = []
                for resp_feature in geocoder_response.get('features'):
                    coords = resp_feature['geometry']['coordinates']
                    point = QgsPointXY(float(coords[0]), float(coords[1]))
                    new_feature = QgsFeature()
                    new_feature.setGeometry(QgsGeometry.fromPointXY(point))
                    new_feature.setAttributes([id + 1] + attr)
                    new_features.append(new_feature)
                dp.addFeatures(new_features)
                outlayer.updateExtents()
            progress += 1
            self.dlg.progressBar.setValue(progress)
            QgsProject.instance().addMapLayer(outlayer)

        self.iface.messageBar().pushMessage(
            'Location Lab: Geocoder',
            self.tr(u'Geocoding successful'),
            level=Qgis.Success)


    def countFeatures(self):
        self.dlg.progressBar.setValue(0)
        try:
            if not self.dlg.sObjCheckBox.isChecked():
                self.featureCounter = 0
                if self.layers:
                    for feature in self.curLayer.getFeatures():
                        self.featureCounter += 1
            elif not self.layers:
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
        self.geocoder.error_table_model.clear()
        if self.drawPoints():
            super(Geocoder, self).dlg.accept()

    def _encode(self, val):
        if isinstance(val,(int, float)):
            val = str(val)
        return val if val else ''

    def _checkLayerGeometry(self, lyr):
        if isinstance(lyr, QgsRasterLayer):
            return False
        return True if lyr.wkbType() == QgsWkbTypes.NoGeometry and lyr.isValid() else False