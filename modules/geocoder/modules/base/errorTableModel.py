from qgis.PyQt.QtCore import QAbstractTableModel, Qt, QModelIndex, QCoreApplication

class ErrorTableModel(QAbstractTableModel):

    def __init__(self, parent=None):
        super(ErrorTableModel, self).__init__(parent)
        self.items = []

    def rowCount(self, parent=QModelIndex()):
        return len(self.items)

    def columnCount(self, parent=QModelIndex()):
        return 3

    def insertRows(self, rows, position=None, parent=QModelIndex()):
        if position is None:
            position = self.rowCount()
        self.beginInsertRows(parent, position, position + len(rows) - 1)
        for i, item in enumerate(rows):
            self.items.insert(position + i, item)
        self.endInsertRows()
        return True

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == 0:
                return 'ID'
            elif section == 1:
                return self.tr('Address')
            elif section == 2:
                return self.tr('Error message')

    def data(self, index, role):
        if not index.isValid():
            return
        item = self.items[index.row()]
        if role == Qt.DisplayRole:
            if index.column() == 0:
                return item['id']
            elif index.column() == 1:
                return item['address']
            elif index.column() == 2:
                return item['error']
        elif role == Qt.UserRole:
            return item
        return

    def clear(self, parent=QModelIndex()):
        self.beginRemoveRows(parent, 0, self.rowCount() - 1)
        self.items = []
        self.endRemoveRows()

    def tr(self, message):
        return QCoreApplication.translate(self.__class__.__name__, message)
