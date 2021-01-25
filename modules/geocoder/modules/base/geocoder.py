from qgis.PyQt.QtCore import QObject, QCoreApplication
from qgis.core import QgsNetworkAccessManager
from .errorTableModel import ErrorTableModel
from collections import defaultdict

class GeocoderAbstract(QObject):

    API_URL = ''
    NAME = ''

    def __init__(self, parent=None):
        self.parent = parent
        self.error_table_model = ErrorTableModel()
        self.geocode_parameters = defaultdict(list)
        self.manager = QgsNetworkAccessManager.instance()

    def saveKey(self, api_key):
        self.api_key = api_key

    def createApiRequest(self):
        pass

    def geocode(self, parent_layer):
        pass

    def tr(self, message):
        return QCoreApplication.translate(self.__class__.__name__, message)

    def showMessage(self, message, level):
        self.parent.iface.messageBar().pushMessage(
            self.parent.name,
            message,
            level=level
        )
