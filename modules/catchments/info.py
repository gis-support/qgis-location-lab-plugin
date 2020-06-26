# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Location Lab
                                 A QGIS plugin
 Perform Location Intelligence analysis in QGIS environment
                             -------------------
        begin                : 2017-07-10
        copyright            : (C) 2017 by Sebastian Schulz / GIS Support
        email                : sebastian.schulz@gis-support.pl
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog
import os.path

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'info.ui'))

class Info(QDialog, FORM_CLASS):
    def __init__(self, parent, parents=None):
        super(Info, self).__init__(parents)
        self.setupUi(self)
        self.parent = parent
        self.iface = parent.iface

    def accept(self):
        super(Info, self).accept()
