
from ..base.geocoder import GeocoderAbstract

from qgis.core import Qgis, QgsPointXY, QgsFeature, QgsGeometry, QgsField, QgsProject
from qgis.PyQt.QtCore import QVariant
import json
import urllib
from collections import defaultdict

class GeocoderORS(GeocoderAbstract):

    API_URL = 'https://api.openrouteservice.org/geocode/search/structured'
    NAME = 'OpenRouteService'

    def geocode(self, parent_layer):
        progress = 0
        self.parent.dlg.progressBar.setValue(progress)

        provider = parent_layer.dataProvider()
        self.addFieldsToParentLayer(parent_layer)
        parent_layer.reload()

        for fid, base_attrs in enumerate(self.parent.feature_attributes):

            request_data = self.getFeatureRequestData(fid)
            response = self.createApiRequest(request_data)

            error = response.get('error')
            if error == 'Invalid API Key':
                self.showMessage(error, Qgis.Critical)
                return
            elif error:
                full_address = self.getFeatureFullAddress(fid)
                self.error_table_model.insertRows([
                    {'id': fid + 1, 'address': full_address, 'error': error}
                ])
            else:
                all_features = response.get('features')
                if all_features:
                    attrs_to_get = [
                        'continent', 'country',
                        'region', 'county',
                        'confidence', 'match_type',
                        'layer', 'accuracy'
                    ]
                    feature = max(all_features, key=lambda item: item['properties']['confidence'])
                    coords = feature['geometry']['coordinates']
                    point = QgsPointXY(float(coords[0]), float(coords[1]))
                    new_feature = QgsFeature()
                    new_feature.setGeometry(QgsGeometry.fromPointXY(point))
                    attributes = [fid + 1]
                    for attr_to_get in attrs_to_get:
                        attributes.append(feature['properties'].get(attr_to_get, ''))

                    new_feature.setAttributes(attributes + base_attrs)
                    provider.addFeature(new_feature)
                    parent_layer.updateExtents()
            progress += 1
            self.parent.dlg.progressBar.setValue(progress)
        self.showMessage(self.tr('Geocoding succesful'), Qgis.Success)
        QgsProject.instance().addMapLayer(parent_layer)

    def createApiRequest(self, parameters):
        try:
            request = urllib.request.urlopen(self._buildRequestUrl(parameters))
            response = json.loads(request.read().decode())
            return response
        except urllib.error.HTTPError as error:
            if error.code == 403:
                return {'error': self.tr('Invalid API Key')}
            else:
                return {'error': error.msg}

    def setParams(self, features):
        self.geocode_parameters = defaultdict(list)
        for feature in features:
            address = ' '.join([
                self.parent.getFeatureEncodedValue(feature, self.parent.dlg.streetComboBox.currentText()),
                self.parent.getFeatureEncodedValue(feature, self.parent.dlg.houseNumberComboBox.currentText())
            ])
            self.geocode_parameters['address'].append(address)
            self.geocode_parameters['postalcode'].append(self.parent.getFeatureEncodedValue(feature, self.parent.dlg.zipComboBox.currentText()))
            self.geocode_parameters['locality'].append(self.parent.getFeatureEncodedValue(feature, self.parent.dlg.cityComboBox.currentText()))
            self.parent.feature_attributes.append(feature.attributes())

    def getFeatureRequestData(self, fid):
        address = self.geocode_parameters['address'][fid]
        return {
            'address': urllib.parse.quote(address),
            'postalcode': self.geocode_parameters['postalcode'][fid],
            'locality': urllib.parse.quote(self.geocode_parameters['locality'][fid]),
        }

    def getFeatureFullAddress(self, fid):
        try:
            address = self.geocode_parameters['address'][id]
            return ', '.join([self.geocode_parameters['locality'][id], address])
        except IndexError:
            return ''

    def addFieldsToParentLayer(self, layer):
        fields = [
            QgsField('ID', QVariant.Int),
            QgsField('Continent', QVariant.String),
            QgsField('Country', QVariant.String),
            QgsField('Region', QVariant.String),
            QgsField('County', QVariant.String),
            QgsField('Confidence', QVariant.Int),
            QgsField('Match type', QVariant.String),
            QgsField('Layer', QVariant.String),
            QgsField('Accuracy', QVariant.String)
        ]
        layer.dataProvider().addAttributes(fields + self.parent.curLayer.dataProvider().fields().toList())
        layer.updateFields()

    def _buildRequestUrl(self, request_params):
        return self.API_URL + '?api_key=' + str(self.api_key)\
            + '&address={address}&locality={locality}&postalcode={postalcode}'.format(**request_params)

