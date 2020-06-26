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
from builtins import zip
from builtins import str
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSettings, Qt, QVariant, QCoreApplication
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QDockWidget
from qgis.gui import QgsMapLayerComboBox, QgsMessageBar
from qgis.core import QgsCoordinateTransform, QgsCoordinateReferenceSystem, \
    QgsGeometry, QgsField, QgsProject, QgsVectorLayer, QgsFeature, \
    QgsPointXY, Qgis, QgsWkbTypes, QgsMapLayerProxyModel, QgsFieldProxyModel
import os.path
import locale
import urllib.request, urllib.parse, urllib.error
import json
import requests

locale.setlocale(locale.LC_ALL, '')
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'catchments.ui'))

class Catchments(QDockWidget, FORM_CLASS):
    def __init__(self, parent, parents=None):
        super(Catchments, self).__init__(parents)
        self.setupUi(self)
        self.parent = parent
        self.iface = parent.iface
        self.HERE_PARAMS = {
            self.tr('Car'): 'car',
            self.tr('Pedestrian'): 'pedestrian',
            self.tr('Truck'): 'truck'
        }
        self.OPENROUTE_PARAMS = {
            self.tr('Bike'): 'cycling-regular',
            self.tr('Car'): 'driving-car',
            self.tr('Pedestrian'): 'foot-walking',
            self.tr('Truck'): 'driving-hgv'
        }
        self.fillDialog()

    def tr(self, message):
        return QCoreApplication.translate('Catchments', message)

    def fillDialog(self):
        self.layerComboBox = QgsMapLayerComboBox(self)
        self.layerComboBox.setObjectName('layerComboBox')
        self.layerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.fieldsComboBox.setFilters(QgsFieldProxyModel.Int | QgsFieldProxyModel.LongLong)
        self.layersLayout.addWidget(self.layerComboBox)
        self.providersComboBox.addItems(['HERE', 'OpenRouteService'])
        self.modesComboBox.addItems([self.tr('Car'), self.tr('Pedestrian'), self.tr('Truck')])
        self.trafficCheckBox.setEnabled(True)
        self.unitsComboBox.addItems([self.tr('Minutes'), self.tr('Meters')])
        self.valueSpinBox.setMinimum(1)
        self.valueSpinBox.setMaximum(99999)
        self.valueSpinBox.setValue(10)
        self.getCatchments.setEnabled(False)
        self.getKeyLabel.setText('<html><head/><body><p>\
            <a href="https://developer.here.com/?create=Evaluation&keepState=true&step=account">\
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
        if self.modesComboBox.currentText() == self.tr('Pedestrian'):
            self.trafficCheckBox.setEnabled(False)
            self.trafficCheckBox.setChecked(False)
        elif self.providersComboBox.currentText() == 'HERE':
            self.trafficCheckBox.setEnabled(True)

    def changeProvider(self):
        self.modesComboBox.clear()
        if self.providersComboBox.currentText() == 'HERE':
            self.getCatchments.setToolTip('')
            items = [self.tr('Car'), self.tr('Pedestrian'), self.tr('Truck')]
            self.trafficCheckBox.setEnabled(True)
            self.getKeyLabel.setText('<html><head/><body><p>\
                <a href="https://developer.here.com/?create=Evaluation&keepState=true&step=account">\
                <span style=" text-decoration: underline; color:#0000ff;">Get key</span></a></p></body></html>'
            )
            self.keyLineEdit.setPlaceholderText(self.tr('Insert App ID:App Code or apiKey'))
        elif self.providersComboBox.currentText() == 'OpenRouteService':
            self.getCatchments.setToolTip(
                self.tr('Free Plan Directions (2.000 requests per day @40 requests per minute)')
            )
            items = [self.tr('Bike'), self.tr('Car'), self.tr('Pedestrian'), self.tr('Truck')]
            self.trafficCheckBox.setEnabled(False)
            self.getKeyLabel.setText('<html><head/><body><p>\
                <a href="https://openrouteservice.org/plans/">\
                <span style=" text-decoration: underline; color:#0000ff;">Get key</span></a></p></body></html>'
            )
            self.keyLineEdit.setPlaceholderText(self.tr('Insert API key'))
        self.updateFeaturesQuantity()
        self.modesComboBox.addItems(items)
        self.loadKey()

    def saveKey(self):
        value = 'gissupport/location_lab/{}'.format(self.providersComboBox.currentText())
        QSettings().setValue(value, self.keyLineEdit.text())

    def loadKey(self):
        value = 'gissupport/location_lab/{}'.format(self.providersComboBox.currentText())
        self.keyLineEdit.setText(QSettings().value(value) or '')

    def getPoints(self, vl, features):
        trans = QgsCoordinateTransform(vl.crs(), QgsCoordinateReferenceSystem(4326), QgsProject().instance())
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
        if self.providersComboBox.currentText() == 'HERE':
            """
            HERE options:
            start           string      lat and lng
            mode            string      car, pedestrian or truck
            range           int         range for calculations
            rangetype       string      distance, time, consumption
            traffic         boolean     takes traffic
            """

            key = self.keyLineEdit.text().strip().split(':')
            with_id = False
            if len(key) == 1:
                url = 'https://isoline.route.ls.hereapi.com/routing/7.2/calculateisoline.json'
            else:
                url = 'https://isoline.route.cit.api.here.com/routing/7.2/calculateisoline.json'
                with_id = True
            for p in points:
                params = {
                    'source': self.providersComboBox.currentText(),
                    'url': url,
                    'key': key,
                    'coords': '{x},{y}'.format(x=p[1], y=p[0]),
                    'transport': self.HERE_PARAMS[self.modesComboBox.currentText()],
                    'range': self.valueSpinBox.value() if self.unitsComboBox.currentText() == self.tr('Meters') else self.valueSpinBox.value() * 60,
                    'units': 'distance' if self.unitsComboBox.currentText() == self.tr('Meters') else 'time',
                    'traffic': 'enabled' if self.trafficCheckBox.isChecked() else 'disabled'
                }
                if not with_id:
                    link = '{url}\
                        ?apiKey={key[0]}\
                        &mode=fastest;{transport};traffic:{traffic}\
                        &range={range}\
                        &rangetype={units}'.replace(' ', '').format(**params)
                else:
                    link = '{url}\
                        ?app_id={key[0]}\
                        &app_code={key[1]}\
                        &mode=fastest;{transport};traffic:{traffic}\
                        &range={range}\
                        &rangetype={units}'.replace(' ', '').format(**params)
                coords = params['coords']
                if self.pointsRouteStartCheckBox.isChecked():
                    link += f'&start=geo!{coords}'
                else:
                    link += f'&destination=geo!{coords}'
                try:
                    r = urllib.request.urlopen(link)
                except urllib.error.HTTPError as e:
                    if e.code == 401:
                        return 'invalid key'
                    elif e.code == 403:
                        return 'forbidden'
                    else:
                        continue
                params['coordinates'] = json.loads(r.read().decode())['response']['isoline'][0]['component'][0]['shape']
                polygons.append(params)
        elif self.providersComboBox.currentText() == 'OpenRouteService':
            """
            OpenRouteService options:
            locations      array       lng
            range          array(int)  seconds for time, meters for distance
            range_type     string      time/distance
            profile        string      driving-car/driving-hgv/foot-walking (query parameter)
            """
            source = self.providersComboBox.currentText()
            url = 'https://api.openrouteservice.org/v2/isochrones'

            mode = self.OPENROUTE_PARAMS[self.modesComboBox.currentText()]
            location_coords = [[p[0], p[1]] for p in points]
            data = {
                'locations': location_coords,
                'range': [self.valueSpinBox.value()] if self.unitsComboBox.currentText() == self.tr('Meters')\
                    else [self.valueSpinBox.value() * 60],
                'range_type': 'distance' if self.unitsComboBox.currentText() == self.tr('Meters') else 'time',
                'attributes': ['reachfactor']
            }
            if self.pointsRouteStartCheckBox.isChecked():
                data['location_type'] = 'destination'
            r = requests.post(
                f'{url}/{mode}',
                json=data,
                headers={'Authorization': self.keyLineEdit.text().strip()}
            )
            if r.status_code == 403:
                polygons = r.json()['error']
            elif r.status_code == 200:
                data.update({
                    'source': source,
                    'url': url
                })
                features = r.json()['features']
                for index, feature in enumerate(features):
                    feature_coords = feature['geometry']['coordinates'][0]
                    feature_data = dict(data)
                    feature_data.update({'coords': f'{location_coords[index][0]}, {location_coords[index][1]}'})
                    feature_data['coordinates'] = [str(c[1])+ ',' + str(c[0]) for c in feature_coords]
                    polygons.append(feature_data)

        if polygons and not_found:
            self.iface.messageBar().pushMessage(
                u'Catchments',
                u'{} {}'.format(not_found, self.tr('catchments not found')),
                level=Qgis.Info)
        return polygons

    def addPolygonsToMap(self, polygons):
        if not QgsProject.instance().mapLayersByName('Location Lab - catchments'):
            vl = QgsVectorLayer('Polygon?crs=EPSG:4326', 'Location Lab - catchments', 'memory')
            pr = vl.dataProvider()
            vl.startEditing()
            pr.addAttributes(
                [
                    QgsField('id', QVariant.Int),
                    QgsField(self.tr('provider'), QVariant.String),
                    QgsField(self.tr('mode'), QVariant.String),
                    QgsField(self.tr('value'), QVariant.Int),
                    QgsField(self.tr('units'), QVariant.String),
                    QgsField(self.tr('lat'), QVariant.Double),
                    QgsField(self.tr('lon'), QVariant.Double),
                    QgsField('params', QVariant.String)
                ]
            )
            vl.commitChanges()
            QgsProject.instance().addMapLayer(vl)
        vl = QgsProject.instance().mapLayersByName('Location Lab - catchments')[0]
        pr = vl.dataProvider()
        next_id = len(vl.allFeatureIds()) + 1
        id_field = self.fieldsComboBox.currentField()
        if id_field:
            layer = self.layerComboBox.currentLayer()
            new_ids = [feature.attribute(id_field) for feature in list(layer.getFeatures())]
        for index, p in enumerate(polygons):
            feature = QgsFeature()
            points = []
            if p['source'] == 'HERE' or p['source'] == 'OpenRouteService':
                coordinates = [c.split(',') for c in p['coordinates']]
                for xy in coordinates:
                    points.append(QgsPointXY(float(xy[1]), float(xy[0])))
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPolygonXY([points]))
            lat, lon = p['coords'].split(',')
            for key in ['key', 'url', 'coordinates', 'start']: #unnecessary params
                if key in p.keys():
                    p.pop(key)
            feature.setAttributes([
                next_id if not id_field else new_ids[index],
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
                mapSettings().
                destinationCrs(),
                QgsProject().instance()).
            transform(vl.extent()))
        self.iface.mapCanvas().refresh()

    def changeLayerEvent(self):
        vl = self.layerComboBox.currentLayer()
        self.fieldsComboBox.setLayer(vl)
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
        self.pointsLabel.setText('{} {}'.format(self.tr('Number of points:'), len(features)))
        if len(features) > 5 and self.providersComboBox.currentText() == 'OpenRouteService':
            self.getCatchments.setEnabled(False)
            self.pointsLabel.setText('{} {} {}'.format(self.tr('Number of points:'), len(features), self.tr('(limit is 5)')))
        elif len(features) == 0:
            self.getCatchments.setEnabled(False)
        else:
            self.getCatchments.setEnabled(True)

    def show(self):
        self.changeLayerEvent()
        self.iface.addDockWidget(Qt.LeftDockWidgetArea, self)
        super(Catchments, self).show()

    def run(self):
        vl = self.layerComboBox.currentLayer()
        if self.selectCheckBox.isChecked():
            features = [f for f in vl.selectedFeatures()]
        else:
            features = [f for f in vl.getFeatures()]
        if not features:
            self.iface.messageBar().pushMessage(
                u'Catchments',
                self.tr(u'No geometry'),
                level=Qgis.Warning)
            return
        points = self.getPoints(vl, features)
        polygons = self.requestApi(points)
        if not polygons:
            self.iface.messageBar().pushMessage(
                u'Catchments',
                self.tr(u'Catchments not found'),
                level=Qgis.Warning)
            return
        elif polygons == 'invalid key':
            self.iface.messageBar().pushMessage(
                u'Catchments',
                self.tr(u'Invalid API key'),
                level=Qgis.Warning)
            return 
        elif polygons == 'forbidden':
            self.iface.messageBar().pushMessage(
                u'Catchments',
                self.tr(u'These credentials do not authorize access'),
                level=Qgis.Warning)
            return 
        elif polygons == 'Daily quota reached or API key unauthorized':
            self.iface.messageBar().pushMessage(
                u'Catchments',
                self.tr(u'Openservice API daily quota reached or API key unauthorized'),
                level=Qgis.Warning)
            return
        self.addPolygonsToMap(polygons)