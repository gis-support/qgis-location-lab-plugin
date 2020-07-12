from ..base.geocoder import GeocoderAbstract

from qgis.core import Qgis
from collections import defaultdict
import csv
import json
import xml.etree.cElementTree as et
import urllib.request

class GeocoderHERE(GeocoderAbstract):
    
    API_URL = 'https://batch.geocoder.ls.hereapi.com/6.2/jobs'
    NAME = 'HERE'

    def geocode(self, parent_layer):
        self.parent.dlg.progressBar.setValue(0)
        self.parent.iface.messageBar().pushMessage(
            self.parent.name,
            'HERE geocoding not yet supported',
            level=Qgis.Warning
        )
        return
        """
        response = self.createApiRequest()
        request_id = response.get('id')
        error = response.get('error')
        if error:
            self.parent.iface.messageBar().pushMessage(
                self.parent.name,
                error,
                level=Qgis.Critical
            )
            return
        result = self.getJobResult(request_id)
        return True
        """

    def createApiRequest(self):
        request_url = self.API_URL+f'?&apiKey={self.api_key}&action=run&header=true&inDelim=|&outDelim=|&outCols=recId,street,houseNumber,postalCode,city&outputCombined=True&language=pl-PL'

        params_keys = list(self.geocode_parameters.keys())
        params_string = '|'.join(params_keys) + '\n'
        count = len(self.geocode_parameters['recId'])
        for i in range(0, count):
            row = []
            for key in params_keys:
                row.append(str(self.geocode_parameters[key][i]))
            params_string += '|'.join(row) + '\n'

        headers = {'Content-type': 'text/plain', 'Content-length': len(params_string)}
        request = urllib.request.Request(request_url, params_string.encode(), headers=headers)
        try:
            response = urllib.request.urlopen(request)
            return {'id': et.fromstring(response.read().decode())\
                .find('Response').find('MetaInfo').find('RequestId').text}
        except urllib.error.HTTPError as error:
            return {'error': error.msg}

    def setParams(self, features):
        self.geocode_parameters = defaultdict(list)
        for fid, feature in enumerate(features):
            self.geocode_parameters['recId'].append(fid)
            self.geocode_parameters['street'].append(self.parent.getFeatureEncodedValue(feature, self.parent.dlg.streetComboBox.currentText()))
            self.geocode_parameters['houseNumber'].append(self.parent.getFeatureEncodedValue(feature, self.parent.dlg.houseNumberComboBox.currentText()))
            self.geocode_parameters['postalCode'].append(self.parent.getFeatureEncodedValue(feature, self.parent.dlg.zipComboBox.currentText()))
            self.geocode_parameters['city'].append(self.parent.getFeatureEncodedValue(feature, self.parent.dlg.cityComboBox.currentText()))
            self.parent.feature_attributes.append(feature.attributes())

    # def checkJobStatus(self, id):
    #     request_url = self.API_URL+f'/{id}?action=status&apiKey={self.api_key}'
    #     request = urllib.request.urlopen(request_url)
    #     return request.read().decode()

    def getJobResult(self, id):
        request_url = self.API_URL+f'/{id}/result?apiKey={self.api_key}'
        try:
            response = urllib.request.urlopen(request_url)
        except urllib.error.HTTPError as error:
            return {'error': error.msg}
        return response.status_code, response.read()

