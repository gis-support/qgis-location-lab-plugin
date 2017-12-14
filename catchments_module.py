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
from PyQt4 import uic
from PyQt4.QtCore import QSettings, Qt, QVariant
from PyQt4.QtGui import QDialog, QDialogButtonBox, QDockWidget
from qgis.gui import QgsMapLayerComboBox, QgsMapLayerProxyModel, QgsMessageBar
from qgis.core import QgsCoordinateTransform, QgsCoordinateReferenceSystem, \
    QgsGeometry, QgsField, QgsMapLayerRegistry, QgsVectorLayer, QgsFeature, \
    QgsPoint
import os.path
import locale
import urllib
import json

locale.setlocale(locale.LC_ALL, '')
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'catchments_module.ui'))

HERE_PARAMS = {
    'Car': 'car',
    'Pedestrian': 'pedestrian',
    'Truck': 'truck'
}

class CatchmentsModule(QDockWidget, FORM_CLASS):
    def __init__(self, parent, parents=None):
        super(CatchmentsModule, self).__init__(parents)
        self.setupUi(self)
        self.parent = parent
        self.iface = parent.iface
        self.fillDialog()

    def fillDialog(self):
        self.layerComboBox = QgsMapLayerComboBox(self)
        self.layerComboBox.setObjectName('layerComboBox')
        self.layerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.layersLayout.addWidget(self.layerComboBox)
        self.providersComboBox.addItems(['Skobbler', 'HERE'])
        self.modesComboBox.addItems(['Car', 'Bike', 'Pedestrian'])
        self.unitsComboBox.addItems(['Minutes', 'Meters'])
        self.valueSpinBox.setValue(10)
        self.valueSpinBox.setMinimum(1)
        self.getCatchments.setEnabled(False)
        self.getKeyLabel.setText('<html><head/><body><p>\
            <a href="https://developer.skobbler.com/getting-started/web#sec3">\
            <span style=" text-decoration: underline; color:#0000ff;">Get key</span></a></p></body></html>'
        )
        self.connectFunctions()
        self.loadKey()

    def connectFunctions(self):
        self.providersComboBox.currentIndexChanged.connect(self.changeProvider)
        self.keyLineEdit.textChanged.connect(self.saveKey)
        self.layerComboBox.currentIndexChanged.connect(self.changeLayerEvent)
        self.modesComboBox.currentIndexChanged.connect(self.disableUnnecessaryParams)
        self.selectCheckBox.stateChanged.connect(self.updateFeaturesQuantity)
        self.getCatchments.clicked.connect(self.run)

    def disableUnnecessaryParams(self):
        if self.modesComboBox.currentText() == 'Pedestrian':
            self.trafficCheckBox.setEnabled(False)
            self.highwaysCheckBox.setEnabled(False)
            self.tollsCheckBox.setEnabled(False)
            self.highwaysCheckBox.setChecked(False)
            self.tollsCheckBox.setChecked(False)
            self.trafficCheckBox.setChecked(False)
        elif self.providersComboBox.currentText() == 'Skobbler':
            self.trafficCheckBox.setEnabled(False)
            self.highwaysCheckBox.setEnabled(True)
            self.tollsCheckBox.setEnabled(True)
        elif self.providersComboBox.currentText() == 'HERE':
            self.trafficCheckBox.setEnabled(True)
            self.highwaysCheckBox.setEnabled(False)
            self.tollsCheckBox.setEnabled(False)

    def changeProvider(self):
        self.modesComboBox.clear()
        if self.providersComboBox.currentText() == 'Skobbler':
            items = ['Car', 'Bike', 'Pedestrian']
            self.highwaysCheckBox.setEnabled(True)
            self.tollsCheckBox.setEnabled(True)
            self.trafficCheckBox.setEnabled(False)
            self.trafficCheckBox.setChecked(False)
            self.getKeyLabel.setText('<html><head/><body><p>\
                <a href="https://developer.skobbler.com/apikeys">\
                <span style=" text-decoration: underline; color:#0000ff;">Get key</span></a></p></body></html>'
            )
            self.keyLineEdit.setPlaceholderText('Insert Api Code')
        elif self.providersComboBox.currentText() == 'HERE':
            items = ['Car', 'Pedestrian', 'Truck']
            self.trafficCheckBox.setEnabled(True)
            self.highwaysCheckBox.setEnabled(False)
            self.highwaysCheckBox.setChecked(False)
            self.tollsCheckBox.setChecked(False)
            self.tollsCheckBox.setEnabled(False)
            self.getKeyLabel.setText('<html><head/><body><p>\
                <a href="https://developer.here.com/?create=Evaluation&keepState=true&step=account">\
                <span style=" text-decoration: underline; color:#0000ff;">Get key</span></a></p></body></html>'
            )
            self.keyLineEdit.setPlaceholderText('Insert App ID and App Code separated by \':\'')
        self.modesComboBox.addItems(items)
        self.loadKey()

    def saveKey(self):
        value = 'gissupport/location_lab/{}'.format(self.providersComboBox.currentText())
        QSettings().setValue(value, self.keyLineEdit.text())

    def loadKey(self):
        value = 'gissupport/location_lab/{}'.format(self.providersComboBox.currentText())
        self.keyLineEdit.setText(QSettings().value(value) or '')

    def getPoints(self, vl, features):
        trans = QgsCoordinateTransform(vl.crs(), QgsCoordinateReferenceSystem(4326))
        points = []
        for f in features:
            geom = f.geometry()
            geom.transform(trans)
            if geom.isMultipart():
                points.append(geom.asMultiPoint()[0])
            else:
                points.append(geom.asPoint())
        return points

    def requestApi(self, points):
        polygons = []
        not_found = 0
        if self.providersComboBox.currentText() == 'Skobbler':
            """
            Skobbler options:
            start           string      Center of RealReach™ in GPS coordinates: Latitude, Longitude
            transport       string      You can pick one of the transport options: pedestrian, bike, car
            range           int         The range for which we calculate RealReach™
            units           string      You can choose between sec and meter. 'Sec' is for time and 'Meter' is for distance
            toll            boolean     You can specify whether to avoid or not the use of toll roads in route calculation
            highways        boolean     Specifies whether to avoid or not the use of highways in route calculation
            """
            for p in points:
                params = {
                    'source': self.providersComboBox.currentText(),
                    'url': 'tor.skobbler.net/tor/RSngx/RealReach/json/20_5/en',
                    'key': self.keyLineEdit.text(),
                    'start': '{x},{y}'.format(x=p[1], y=p[0]),
                    'transport': self.modesComboBox.currentText().lower(),
                    'range': self.valueSpinBox.value() if self.unitsComboBox.currentText() == 'Meters' else self.valueSpinBox.value() * 60,
                    'units': 'meter' if self.unitsComboBox.currentText() == 'Meters' else 'sec',
                    'nonReachable': '0',
                    'toll': '1' if self.tollsCheckBox.isChecked() else '0',
                    'highways': '1' if self.highwaysCheckBox.isChecked() else '0',
                    'response_type': 'gps'
                }
                link = 'http://{key}.{url}/{key}\
                    ?start={start}\
                    &transport={transport}\
                    &range={range}\
                    &units={units}\
                    &nonReachable={nonReachable}\
                    &toll={toll}\
                    &highways={highways}\
                    &response_type={response_type}'.replace(' ', '').format(**params)
                try:
                    r = urllib.urlopen(link)
                except IOError as e:
                    if e[1] == 401:
                        return 'invalid key'
                    continue
                data = json.loads(r.read())
                if data['status']['apiMessage'] == 'Route cannot be calculated.':
                    not_found += 1
                    continue
                params['coordinates'] = data['realReach']['gpsPoints']
                polygons.append(params)
        elif self.providersComboBox.currentText() == 'HERE':
            """
            HERE options:
            start           string      lat and lng
            mode            string      car, pedestrian or truck
            range           int         range for calculations
            rangetype       string      distance, time, consumption
            traffic         boolean     takes traffic
            """
            for p in points:
                params = {
                    'source': self.providersComboBox.currentText(),
                    'url': 'https://isoline.route.cit.api.here.com/routing/7.2/calculateisoline.json',
                    'key': self.keyLineEdit.text().split(':'),
                    'start': '{x},{y}'.format(x=p[1], y=p[0]),
                    'transport': HERE_PARAMS[self.modesComboBox.currentText()],
                    'range': self.valueSpinBox.value() if self.unitsComboBox.currentText() == 'Meters' else self.valueSpinBox.value() * 60,
                    'units': 'distance' if self.unitsComboBox.currentText() == 'Meters' else 'time',
                    'traffic': 'enabled' if self.trafficCheckBox.isChecked() else 'disabled'
                }
                link = '{url}\
                    ?app_id={key[0]}\
                    &app_code={key[1]}\
                    &mode=fastest;{transport};traffic:{traffic}\
                    &start=geo!{start}\
                    &range={range}\
                    &rangetype={units}'.replace(' ', '').format(**params)
                try:
                    r = urllib.urlopen(link)
                except IOError as e:
                    if e[1] == 401:
                        return 'invalid key'
                    continue
                if r.getcode() == 403:
                    return 'forbidden'
                params['coordinates'] = json.loads(r.read())['response']['isoline'][0]['component'][0]['shape']
                polygons.append(params)
        if polygons and not_found:
            self.iface.messageBar().pushMessage(
                u'Catchments',
                u'{} catchments not found'.format(not_found),
                level=QgsMessageBar.INFO)
        return polygons

    def addPolygonsToMap(self, polygons):
        if not QgsMapLayerRegistry.instance().mapLayersByName('Location Lab - catchments'):
            vl = QgsVectorLayer('Polygon?crs=EPSG:4326', 'Location Lab - catchments', 'memory')
            pr = vl.dataProvider()
            vl.startEditing()
            pr.addAttributes(
                [
                    QgsField('id', QVariant.Int),
                    QgsField('provider', QVariant.String),
                    QgsField('mode', QVariant.String),
                    QgsField('value', QVariant.Int),
                    QgsField('units', QVariant.String),
                    QgsField('lat', QVariant.Double),
                    QgsField('lon', QVariant.Double),
                    QgsField('params', QVariant.String)
                ]
            )
            vl.commitChanges()
            QgsMapLayerRegistry.instance().addMapLayer(vl)
        vl = QgsMapLayerRegistry.instance().mapLayersByName('Location Lab - catchments')[0]
        pr = vl.dataProvider()
        next_id = len(vl.allFeatureIds()) + 1
        for p in polygons:
            feature = QgsFeature()
            points = []
            if p['source'] == 'Skobbler':
                coordinates_x = [c for c in p['coordinates'][8::2]]
                coordinates_y = [c for c in p['coordinates'][9::2]]
                for x, y in zip(coordinates_x, coordinates_y):
                    points.append(QgsPoint(x, y))
            elif p['source'] == 'HERE':
                coordinates = [c.split(',') for c in p['coordinates']]
                for xy in coordinates:
                    points.append(QgsPoint(float(xy[1]), float(xy[0])))
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPolygon([points]))
            lat, lon = p['start'].split(',')
            for key in ['key', 'url', 'coordinates', 'start']: #unnecessary params
                p.pop(key)
            feature.setAttributes([
                next_id,
                self.providersComboBox.currentText(),
                self.modesComboBox.currentText().lower(),
                self.valueSpinBox.value(),
                self.unitsComboBox.currentText(),
                float(lat),
                float(lon),
                str(p)
            ])
            pr.addFeatures([feature])
            next_id += 1
        vl.updateExtents()
        self.iface.mapCanvas().setExtent(
            QgsCoordinateTransform(
                vl.crs(),
                self.iface.
                mapCanvas().
                mapRenderer().
                destinationCrs()).
            transform(vl.extent()))
        self.iface.mapCanvas().refresh()

    def changeLayerEvent(self):
        vl = self.layerComboBox.currentLayer()
        if not vl:
            return
        self.updateFeaturesQuantity()
        vl.selectionChanged.connect(self.updateFeaturesQuantity)

    def updateFeaturesQuantity(self):
        vl = self.layerComboBox.currentLayer()
        if not vl:
            return
        if self.selectCheckBox.isChecked():
            features = [f for f in vl.selectedFeatures()]
        else:
            features = [f for f in vl.getFeatures()]
        self.pointsLabel.setText('Number of points: {}'.format(len(features)))
        if len(features) > 5:
            self.getCatchments.setEnabled(False)
            self.pointsLabel.setText('Number of points: {} (limit is 5)'.format(len(features)))
        elif len(features) == 0:
            self.getCatchments.setEnabled(False)
        else:
            self.getCatchments.setEnabled(True)

    def show(self):
        self.changeLayerEvent()
        self.iface.addDockWidget(Qt.LeftDockWidgetArea, self)
        super(CatchmentsModule, self).show()

    def checkApiKey(self):
        if self.providersComboBox.currentText() == 'HERE':
            if len(self.keyLineEdit.text().split(':')) != 2:
                self.iface.messageBar().pushMessage(
                    u'Catchments',
                    u'Invalid api key format, required app_id:app_code',
                    level=QgsMessageBar.WARNING)
                return False
        return True

    def run(self):
        vl = self.layerComboBox.currentLayer()
        if self.selectCheckBox.isChecked():
            features = [f for f in vl.selectedFeatures()]
        else:
            features = [f for f in vl.getFeatures()]
        if not features:
            self.iface.messageBar().pushMessage(
                u'Catchments',
                u'No geometry',
                level=QgsMessageBar.WARNING)
            return
        points = self.getPoints(vl, features)
        if not self.checkApiKey():
            return
        polygons = self.requestApi(points)
        if not polygons:
            self.iface.messageBar().pushMessage(
                u'Catchments',
                u'Catchments not found',
                level=QgsMessageBar.WARNING)
            return
        elif polygons == 'invalid key':
            self.iface.messageBar().pushMessage(
                u'Catchments',
                u'Invalid API key',
                level=QgsMessageBar.WARNING)
            return 
        elif polygons == 'forbidden':
            self.iface.messageBar().pushMessage(
                u'Catchments',
                u'These credentials do not authorize access',
                level=QgsMessageBar.WARNING)
            return 
        self.addPolygonsToMap(polygons)