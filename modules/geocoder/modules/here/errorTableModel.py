from qgis.PyQt.QtCore import Qt, QModelIndex, QCoreApplication
from ..base.errorTableModel import ErrorTableModel

class HEREErrorTableModel(ErrorTableModel):

    def columnCount(self, parent=QModelIndex()):
        return 2

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == 0:
                return self.tr('Errors')
            elif section == 1:
                return self.tr('Invalid objects')

    def data(self, index, role):
        if not index.isValid():
            return
        item = self.items[index.row()]
        if role == Qt.DisplayRole:
            if index.column() == 0:
                return item['errors']
            elif index.column() == 1:
                return item['invalid']
        elif role == Qt.UserRole:
            return item
        return

