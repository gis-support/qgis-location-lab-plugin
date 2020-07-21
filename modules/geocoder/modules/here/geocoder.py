from ..base.geocoder import GeocoderAbstract
from .errorTableModel import HEREErrorTableModel

from qgis.core import Qgis, QgsField, QgsPointXY, QgsFeature, QgsGeometry, QgsApplication, QgsProject,\
    QgsNetworkAccessManager
from qgis.PyQt.QtCore import QVariant, QUrl, QEventLoop
from qgis.PyQt.QtNetwork import QNetworkRequest
from collections import defaultdict
from io import BytesIO
from zipfile import ZipFile
import csv
import json
import xml.etree.cElementTree as et

class GeocoderHERE(GeocoderAbstract):
    
    API_URL = 'https://batch.geocoder.ls.hereapi.com/6.2/jobs'
    NAME = 'HERE'
    SEPARATOR = '|'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.error_table_model = HEREErrorTableModel()

    def geocode(self, parent_layer):
        response = self.createApiRequest()
        request_id = response.get('id')
        error = response.get('error')
        if error:
            self.showMessage(self.tr('Error: ') + error, Qgis.Critical)
            return

        self.showMessage(self.tr('HERE batch geocode request is being created, it may take a while to complete.'), Qgis.Info)
        erorrs = 0
        invalid = 0
        while True:
            job_info = self.getJobInfo(request_id)
            status = job_info['status']
            progress = job_info['progress']
            self.parent.dlg.progressBar.setValue(progress - invalid)
            if status == 'completed':
                errors = job_info['errors']
                invalid = job_info['invalid']
                break

        self.error_table_model.insertRows([
            {'errors': errors, 'invalid': invalid}
        ])

        result = self.getJobResult(request_id)
        self.addFieldsToParentLayer(parent_layer)
        result_attributes = [row.split(self.SEPARATOR) for row in result.split('\n')]
        for fid, attr in enumerate(self.parent.feature_attributes):
            try:
                point = QgsPointXY(float(result_attributes[fid][4]), float(result_attributes[fid][3]))
            except (ValueError, IndexError):
                #Failed to geocode
                continue
            new_feature = QgsFeature()
            new_feature.setGeometry(QgsGeometry.fromPointXY(point))
            new_feature.setAttributes(attr + result_attributes[fid])
            parent_layer.dataProvider().addFeature(new_feature)

        QgsProject.instance().addMapLayer(parent_layer)
        parent_layer.updateExtents()
        self.showMessage(self.tr('Geocoding successful'), Qgis.Success)

    def createApiRequest(self):
        request_url = self.API_URL+f'?&apiKey={self.api_key}&action=run&header=false&inDelim={self.SEPARATOR}&outDelim={self.SEPARATOR}&outCols=latitude,longitude,locationLabel&outputCombined=True&language=pl-PL'

        params_keys = list(self.geocode_parameters.keys())
        params_string = self.SEPARATOR.join(params_keys) + '\n'
        count = len(self.geocode_parameters['recId'])
        for i in range(0, count):
            row = []
            for key in params_keys:
                row.append(str(self.geocode_parameters[key][i]))
            params_string += '|'.join(row) + '\n'

        response = self.request(request_url, params_string, 'post')
        if 'error' in response:
            response_data = json.loads(response)
            error_msg = response_data['error_description']
            return {'error': error_msg}
        else:
            return {'id': self.extractInfoFromXMLResponse(response, get_id=True)}

    def setParams(self, features):
        self.geocode_parameters = defaultdict(list)
        for fid, feature in enumerate(features):
            self.geocode_parameters['recId'].append(fid)
            self.geocode_parameters['street'].append(self.parent.getFeatureEncodedValue(feature, self.parent.dlg.streetComboBox.currentText()))
            self.geocode_parameters['houseNumber'].append(self.parent.getFeatureEncodedValue(feature, self.parent.dlg.houseNumberComboBox.currentText()))
            self.geocode_parameters['postalCode'].append(self.parent.getFeatureEncodedValue(feature, self.parent.dlg.zipComboBox.currentText()))
            self.geocode_parameters['city'].append(self.parent.getFeatureEncodedValue(feature, self.parent.dlg.cityComboBox.currentText()))
            self.parent.feature_attributes.append(feature.attributes())

    def getJobInfo(self, request_id):
        request_url = self.API_URL+f'/{request_id}?action=status&apiKey={self.api_key}'
        response = self.request(request_url)
        info = self.extractInfoFromXMLResponse(response)
        return {
            'status': info.find('Status').text,
            'progress': int(info.find('ProcessedCount').text),
            'errors': int(info.find('ErrorCount').text),
            'invalid': int(info.find('InvalidCount').text)
        }

    def getJobResult(self, request_id):
        request_url = self.API_URL+f'/{request_id.strip()}/result?apiKey={self.api_key}'
        response = self.request(request_url, decode=False)
        try:
            if 'error' in response.decode():
                response_data = json.loads(response)
                error_msg = response_data['error_description']
                return {'error': error_msg}
        except:
            pass
        response_bytes = BytesIO(response)
        zf = ZipFile(response_bytes)
        geocode_data = zf.read(zf.namelist()[0]).decode()
        return geocode_data

    def addFieldsToParentLayer(self, layer):
        here_fields = [
            QgsField('recId', QVariant.Int),
            QgsField('SeqNumber', QVariant.Int),
            QgsField('seqLength', QVariant.Int),
            QgsField('latitude', QVariant.Double),
            QgsField('longtitude', QVariant.Double),
            QgsField('locationLabel', QVariant.String)
        ]
        layer.dataProvider().addAttributes(self.parent.curLayer.dataProvider().fields().toList() + here_fields)
        layer.updateFields()

    def request(self, url, data=None, method='get', decode=True):
        request = QNetworkRequest(QUrl(url))
        if method == 'get':
            response = self.manager.get(request)
        else:
            request.setRawHeader(b'Content-Type', b'text/plain')
            response = self.manager.post(request, data.encode())
        loop = QEventLoop()
        response.finished.connect(loop.quit)
        loop.exec_()
        response_data = response.readAll().data()
        return response_data if not decode else response_data.decode()

    @staticmethod
    def extractInfoFromXMLResponse(resp, get_id=False):
        tree = et.fromstring(resp)
        info = tree.find('Response')
        if not get_id:
            return info
        else:
            return info.find('MetaInfo').find('RequestId').text
