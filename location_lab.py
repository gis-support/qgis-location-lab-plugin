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
from builtins import object
from qgis.PyQt.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QMenu
from qgis.PyQt.QtGui import QIcon
from qgis.gui import QgsMessageBar
from .resources import resources
import os.path
from .modules.catchments.main import Catchments
from .modules.catchments.info import Info
from .modules.geocoder.main import Geocoder

class LocationLab(object):

    def __init__(self, iface):
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.plugin_dir = os.path.dirname(__file__)
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'location_lab_{}.qm'.format(locale))
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)
        self.actions = []
        # Init modules
        self.catchmentsModule = Catchments(self)
        self.infoModule = Info(self)
        self.geocoderModule = Geocoder(self)
        

    def tr(self, message):
        return QCoreApplication.translate('LocationLab', message)

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
        menuBar = self.iface.mainWindow().menuBar()
        self.menu = menuBar.findChild(QMenu,'locationLab')

        if self.menu is None:
            self.menu = QMenu(menuBar)
            self.menu.setObjectName('locationLab')
            self.menu.setTitle(u'&Location Lab')

            menuBar.insertMenu(
                self.iface.firstRightStandardMenu().menuAction(),
                self.menu)

        self.add_action(
            ':/plugins/LocationLab/catchments/catchments.png',
            text=self.tr(u'Catchments'),
            callback=self.catchmentsModule.show)
        self.add_action(
            ':/plugins/LocationLab/geocoder/geocoder.png',
            text=self.tr(u'Geocoder'),
            callback=self.geocoderModule.show)
        self.menu.addSeparator()
        self.add_action(
           ':/plugins/LocationLab/catchments/info.png',
           text=self.tr(u'Info'),
           callback=self.infoModule.show)


    def unload(self):
        try:
            for action in self.actions:
                self.menu.removeAction(action)
            if self.menu.isEmpty():
                self.menu.deleteLater()
        except RuntimeError:
            pass