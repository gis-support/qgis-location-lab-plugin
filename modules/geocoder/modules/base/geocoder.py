from qgis.PyQt.QtCore import QObject
from .errorTableModel import ErrorTableModel
from collections import defaultdict

class GeocoderAbstract(QObject):

    API_URL = ''
    NAME = ''

    def __init__(self, parent=None):
        self.parent = parent
        self.error_table_model = ErrorTableModel()
        self.geocode_parameters = defaultdict(list)

    def saveKey(self, api_key):
        self.api_key = api_key

    def createApiRequest(self):
        pass

    def geocode(self, parent_layer):
        return True