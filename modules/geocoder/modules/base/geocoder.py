from qgis.PyQt.QtCore import QObject
from .errorTableModel import ErrorTableModel

class GeocoderAbstract(QObject):

    API_URL = ''
    NAME = ''

    def __init__(self, parent=None):
        self.parent = parent
        self.error_table_model = ErrorTableModel()

    def saveKey(self, api_key):
        self.api_key = api_key

    def createApiRequest(self):
        pass
