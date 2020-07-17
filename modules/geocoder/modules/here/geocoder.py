from ..base.geocoder import GeocoderAbstract
from .errorTableModel import HEREErrorTableModel

from qgis.core import Qgis, QgsField, QgsPointXY, QgsFeature, QgsGeometry, QgsTask, QgsApplication, QgsProject
from qgis.PyQt.QtCore import QVariant
from collections import defaultdict
from io import BytesIO
from zipfile import ZipFile
import csv
import json
import xml.etree.cElementTree as et
import urllib.request


class GeocoderHERE(GeocoderAbstract):
    
    API_URL = 'https://batch.geocoder.ls.hereapi.com/6.2/jobs'
    NAME = 'HERE'
    SEPARATOR = '|'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.error_table_model = HEREErrorTableModel()

    def geocode(self, parent_layer):

        def work(task):
            erorrs = 0
            invalid = 0
            while True:
                job_info = self.getJobInfo(self.request_id)
                status = job_info['status']
                progress = job_info['progress']
                if status == 'completed':
                    self.parent.dlg.progressBar.setValue(progress)
                    #progress temporarly set once at the end not to cause QGIS crash
                    errors = job_info['errors']
                    invalid = job_info['invalid']
                    break

            self.error_table_model.insertRows([
                {'errors': errors, 'invalid': invalid}
            ])

            result = self.getJobResult(self.request_id)
            self.addFieldsToParentLayer(self.layer)
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
                self.layer.dataProvider().addFeature(new_feature)
            try:
                self.parent.dlg.progressBar.setValue(len(self.parent.feature_attributes - invalid))
            except:
                pass

        def handle_task_completed():
            QgsProject.instance().addMapLayer(self.layer)
            self.layer.updateExtents()
            self.showMessage(self.tr('Geocoding successful'), Qgis.Success)

        def handle_task_terminated():
            self.showMessage(self.tr('Unknown error occured while fetching HERE API response.'), Qgis.Critical)

        try:
            self.showMessage(self.tr('HERE batch geocode request is being created, it may take a while to complete.'), Qgis.Info)
        except:
            pass
        response = self.createApiRequest()
        self.request_id = response.get('id')
        error = response.get('error')
        if error:
            self.showMessage(self.tr('Error') + error, Qgis.Critical)
            return
        self.layer = parent_layer

        manager = QgsApplication.taskManager()
        geocode_task = QgsTask.fromFunction('Location Lab', work)
        geocode_task.taskCompleted.connect(handle_task_completed)
        geocode_task.taskTerminated.connect(handle_task_terminated)
        manager.addTask(geocode_task)

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

        headers = {'Content-type': 'text/plain', 'Content-length': len(params_string)}
        request = urllib.request.Request(request_url, params_string.encode(), headers=headers)
        try:
            response = urllib.request.urlopen(request)
            return {'id': self._extractInfoFromXMLResponse(response, get_id=True)}
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

    def getJobInfo(self, request_id):
        request_url = self.API_URL+f'/{request_id}?action=status&apiKey={self.api_key}'
        response = urllib.request.urlopen(request_url)
        info = self._extractInfoFromXMLResponse(response)
        return {
            'status': info.find('Status').text,
            'progress': int(info.find('ProcessedCount').text),
            'errors': int(info.find('ErrorCount').text),
            'invalid': int(info.find('InvalidCount').text)
        }

    def getJobResult(self, request_id):
        request_url = self.API_URL+f'/{request_id.strip()}/result?apiKey={self.api_key}'
        try:
            response_bytes = BytesIO(urllib.request.urlopen(request_url).read())
            zf = ZipFile(response_bytes)
            geocode_data = zf.read(zf.namelist()[0]).decode('utf-8')
            return geocode_data
        except urllib.error.HTTPError as error:
            return {'error': error.msg}

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

    def _extractInfoFromXMLResponse(self, resp, get_id=False):
        tree = et.fromstring(resp.read().decode())
        info = tree.find('Response')
        if not get_id:
            return info
        else:
            return info.find('MetaInfo').find('RequestId').text
