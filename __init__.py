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

def classFactory(iface):
    from .location_lab import LocationLab
    return LocationLab(iface)
