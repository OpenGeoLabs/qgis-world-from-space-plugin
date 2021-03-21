# -*- coding: utf-8 -*-
"""
/***************************************************************************
                                 A QGIS WFS plugin

 This plugin connect to WPS via OWSLib.

 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2020-08-04
        git sha              : $Format:%H$
        copyright            : (C) 2020 by OpenGeoLabs
        email                : info@opengeolabs.cz
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
import webbrowser

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt import QtGui
from qgis.utils import iface
from qgis.core import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import *
from qgis.gui import *

from .ui_settings import Ui_Settings

import importlib, inspect
import time

from .connect import *

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
WIDGET_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'world_from_space_widget_base.ui'))


class WorldFromSpaceWidget(QDockWidget, WIDGET_CLASS):
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(WorldFromSpaceWidget, self).__init__(parent)
        # TODO put into plugin settings
        self.url_polygons = 'https://api-dynacrop.worldfromspace.cz/api/v2/polygons'
        self.url_processing_request = 'https://api-dynacrop.worldfromspace.cz/api/v2/processing_request'
        self.iface = iface
        self.pluginPath = os.path.dirname(__file__)
        self.settingsPath = self.pluginPath + "/../../../qgis_world_from_space_settings"
        QDockWidget.__init__(self, None)
        self.setupUi(self)
        self.settingsdlg = Ui_Settings(self.pluginPath, self)
        self.pushButtonSettings.clicked.connect(self.showSettings)
        self.pushButtonRegisterPolygons.clicked.connect(self.createPolygons)
        self.pushButtonGetIndex.clicked.connect(self.createProcessingRequests)
        self.polygons = []
        self.requests = []
        self.loadPolygons()
        self.loadIndexesList()
        self.loadTypesList()
        self.settings = {}
        # print("LOADING SETTINGS")
        self.loadSettings()
        self.polygons_to_register = []
        self.current_polygon_to_register_id = 0
        self.requests_to_register = []
        self.current_request_to_register_id = 0
        # self.pushButtonAbout.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons/cropped-opengeolabs-logo-small.png")))
        # self.pushButtonAbout.clicked.connect(self.showAbout)

    def loadSettings(self):
        # print(self.settingsPath + "/settings.json")
        if os.path.exists(self.settingsPath + "/settings.json"):
            with open(self.settingsPath + "/settings.json") as json_file:
                self.settings = json.load(json_file)
                # print(self.settings)

    def showSettings(self):
        self.settingsdlg.updateSettings()
        self.settingsdlg.show()

    def loadIndexesList(self):
        indexes = ["NDVI", "EVI", "NDWI", "NDMI", "LAI", "fAPAR", "CWC", "CCC"]
        for index in indexes:
            self.comboBoxIndexes.addItem(index)

    def loadTypesList(self):
        types = ["observation", "field_zonation", "time_series"]
        for type in types:
            self.comboBoxTypes.addItem(type)

    def loadPolygons(self):
        # TODO load form JSON
        # TODO Geometry?
        path = "/home/jencek/qgis3_profiles/profiles/default/python/plugins/qgis-world-from-space-plugin/data"
        self.polygons = [
            {"layer": path + "/ABC.gpkg|layername=ABC", "fid": 1, "id": 42982},
            {"layer": path + "/ABC.gpkg|layername=ABC", "fid": 2, "id": 42981},
            {"layer": path + "/ABC.gpkg|layername=ABC", "fid": 3, "id": 42987}
        ]

    def polygonIsRegistered(self, polygon):
        # We do not want to register polygon if it is already registered
        for pol in self.polygons:
            if pol['layer'] == polygon['layer'] and pol['fid'] == polygon['fid']:
                return pol['id']
        return None

    def createPolygons(self):
        self.listWidgetPolygons.clear()
        self.polygons_to_register = []
        self.current_polygon_to_register_id = 0
        selectedLayers = self.iface.layerTreeView().selectedLayers()
        if len(selectedLayers) != 1:
            QMessageBox.information(None, self.tr("ERROR"), self.tr("You have to select one layer."))
            return
        layer_source = selectedLayers[0].source()
        features = selectedLayers[0].selectedFeatures()
        if len(features) < 1:
            QMessageBox.information(None, self.tr("ERROR"), self.tr("You have to select at least one feature."))
            return
        for feature in features:
            geom = feature.geometry()
            geom_wkt = geom.asWkt()
            polygon = {"layer": layer_source, "fid": feature.id(), "geometry": geom_wkt}
            polid = self.polygonIsRegistered(polygon)
            if polid is not None:
                self.listWidgetPolygons.addItem(str(polid))
            else:
                self.polygons_to_register.append(polygon)

        if len(self.polygons_to_register) > 0:
            self.createPolygon()
        else:
            self.pushButtonGetIndex.setEnabled(True)

    def createPolygon(self):
        self.createpolygon = Connect()
        self.createpolygon.setType('POST')
        self.createpolygon.setUrl(self.url_polygons)
        # "POLYGON((16.609153599499933 49.20045317863389,16.61297306513714 49.199219336662225,16.61524757838177 49.19759286157719,16.616577954053156 49.195910244858794,16.61400303339886 49.195265226606885,16.6094540069096 49.197368515988586,16.608381123303644 49.19863044668781,16.609153599499933 49.20045317863389))"
        # "POLYGON ((16.56518693093434536 49.22676219888379023, 16.56425126852759178 49.22444226880676865, 16.56539200762623665 49.22282728985813094, 16.56810927379379095 49.22272475151218174, 16.5683784369518996 49.22462171091217442, 16.56854506176405906 49.22571118083784825, 16.56828871589919672 49.22681346805676128, 16.56767348582352284 49.2272620733202686, 16.56518693093434536 49.22676219888379023))"
        print(self.polygons_to_register[self.current_polygon_to_register_id]["geometry"])
        data = {
            "geometry": self.polygons_to_register[self.current_polygon_to_register_id]["geometry"],
            "api_key": self.settings['apikey'],
            "max_mean_cloud_cover": 0.1,
            "smi_enabled": False
        }
        self.createpolygon.setData(json.dumps(data))
        self.createpolygon.statusChanged.connect(self.onCreatePolygonResponse)
        self.createpolygon.start()

    def onCreatePolygonResponse(self, response):
        if response.status == 200:
            # QMessageBox.information(self.parent.iface.mainWindow(), self.tr("INFO"), self.tr("Polygon registered"))
            # print(response.data)
            response_json = json.loads(response.data)
            self.listWidgetPolygons.addItem(str(response_json["id"]))
        else:
            print("ERROR")
            # QMessageBox.information(self.parent.iface.mainWindow(), self.tr("ERROR"), self.tr("Polygon can not be registered"))
        self.current_polygon_to_register_id += 1
        if len(self.polygons_to_register) > self.current_polygon_to_register_id:
            self.createPolygon()
        else:
            time.sleep(15)
            self.pushButtonGetIndex.setEnabled(True)

    def createProcessingRequests(self):
        self.requests_to_register = []
        self.current_request_to_register_id = 0
        for index in range(self.listWidgetPolygons.count()):
            self.requests_to_register.append(self.listWidgetPolygons.item(index).text())
        if len(self.requests_to_register) > 0:
            self.createProcessingRequest()

    def createProcessingRequest(self):
        self.setCursor(Qt.WaitCursor)
        self.createprocessingrequest = Connect()
        self.createprocessingrequest.setType('POST')
        self.createprocessingrequest.setUrl(self.url_processing_request)
        data = {
            "rendering_type": self.comboBoxTypes.currentText(),
            "polygon_id": int(self.requests_to_register[self.current_request_to_register_id]),
            "date_from": self.mDateTimeEditStart.dateTime().toString("yyyy-MM-dd"),
            "date_to": self.mDateTimeEditEnd.dateTime().toString("yyyy-MM-dd"),
            "layer": self.comboBoxIndexes.currentText(),
            "number_of_zones": 16,
            "api_key": self.settings['apikey']
        }
        self.createprocessingrequest.setData(json.dumps(data))
        self.createprocessingrequest.statusChanged.connect(self.onCreateProcessingRequestResponse)
        self.createprocessingrequest.start()

    def onCreateProcessingRequestResponse(self, response):
        if response.status == 200:
            # QMessageBox.information(self.parent.iface.mainWindow(), self.tr("INFO"), self.tr("Polygon registered"))
            # print(response.data)
            response_json = json.loads(response.data)
            self.requests.append(response_json["id"])
            print("RESPONSE")
            print(self.requests)
            time.sleep(5)
            # TODO when the sleep is not sufficient
            self.getProcessingRequestInfo(response_json["id"])
        else:
            print("ERROR")
            self.requests.append(-1)
            # QMessageBox.information(self.parent.iface.mainWindow(), self.tr("ERROR"), self.tr("Polygon can not be registered"))
        self.setCursor(Qt.ArrowCursor)

    def getProcessingRequestInfo(self, id):
        self.setCursor(Qt.WaitCursor)
        self.getprocessingrequestinfo = Connect()
        self.getprocessingrequestinfo.setType('GET')
        self.getprocessingrequestinfo.setUrl(self.url_processing_request + "/" + str(id) + "?api_key=" + self.settings['apikey'])
        self.getprocessingrequestinfo.statusChanged.connect(self.onGetProcessingRequestInfoResponse)
        self.getprocessingrequestinfo.start()

    def onGetProcessingRequestInfoResponse(self, response):
        if response.status == 200:
            # QMessageBox.information(self.parent.iface.mainWindow(), self.tr("INFO"), self.tr("Polygon registered"))
            print("REQUEST INFO:")
            print(response.data)
            data = response.data.read().decode('utf-8')
            response_json = json.loads(data)
            if response_json["rendering_type"] == "time_series":
                self.showGraph(response_json)
            else:
                if response_json["result"]["tiles_color"] is not None:
                    url = "type=xyz&url=" + response_json["result"]["tiles_color"]
                    layer_name = response_json["layer"] + "_" + str(response_json["polygon_id"]) + "__" + str(response_json["date_from"]) + "_" + str(response_json["date_to"])
                    layer = QgsRasterLayer(url, layer_name, 'wms')
                    # TODO check if the layer is valid
                    QgsProject.instance().addMapLayer(layer)
                else:
                    print("ERROR")
                    QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),
                                            QApplication.translate("World from Space", "The response does not contain valid data to show.", None))
        else:
            print("ERROR")
            QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),
                                    QApplication.translate("World from Space", "The response does not contain valid data to show.", None))

        self.current_request_to_register_id += 1
        if len(self.requests_to_register) > self.current_request_to_register_id:
            self.createProcessingRequest()
        self.setCursor(Qt.ArrowCursor)

    def showGraph(self, response_json):
        if response_json["status"] == "completed" and response_json["result"]["time_series"] is not None:
            if response_json["result"]["time_series"]["dates"] is not None and len(response_json["result"]["time_series"]["dates"]) > 0:
                import matplotlib.pyplot as plt

                # "result": {
                #     "time_series": {
                #         "dates": [
                #             "2020-09-14",
                #             "2020-09-22",
                #             "2020-09-24"
                #         ],
                #         "values": [
                #             0.2860300894659764,
                #             0.28543065172559484,
                #             0.2525505356341188
                #         ]
                #     }
                # },

                # date = [ "2020-09-14", "2020-09-22", "2020-09-24" ]
                # values = [ 0.2860300894659764, 0.28543065172559484, 0.2525505356341188 ]

                plt.plot(response_json["result"]["time_series"]["dates"], response_json["result"]["time_series"]["values"])
                plt.show()
