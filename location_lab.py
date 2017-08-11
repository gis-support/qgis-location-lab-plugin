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
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt4.QtGui import QAction, QIcon, QMessageBox, QMenu
from qgis.gui import QgsMessageBar
import resources
import os.path
from catchments_module import CatchmentsModule
from info_module import InfoModule

class LocationLab:

    def __init__(self, iface):
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.plugin_dir = os.path.dirname(__file__)
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'LocationLab{}.qm'.format(locale))
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)
        self.actions = []
        self.menu = QMenu(self.iface.mainWindow())
        self.menu.setObjectName('locationLab')
        self.menu.setTitle(u'&Location Lab')
        # Init modules
        self.catchmentsModule = CatchmentsModule(self)
        self.infoModule = InfoModule(self)
        

    def tr(self, message):
        return QCoreApplication.translate('Catchments', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        checkable=False
            ):

        icon = QIcon(icon_path)
        action = QAction(icon, text, self.iface.mainWindow())
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        action.setCheckable(checkable)
        self.menu.addAction(action)
        self.actions.append(action)
        return action

    def initGui(self):
        self.add_action(
            ':/plugins/LocationLab/catchments.png',
            text=self.tr(u'Catchments'),
            callback=self.catchmentsModule.show)
        self.add_action(
           ':/plugins/LocationLab/info.png',
           text=self.tr(u'Info'),
           callback=self.infoModule.show)
        menuBar = self.iface.mainWindow().menuBar()
        menuBar.insertMenu(self.iface.firstRightStandardMenu().menuAction(), self.menu)

    def unload(self):
        self.menu.deleteLater()
