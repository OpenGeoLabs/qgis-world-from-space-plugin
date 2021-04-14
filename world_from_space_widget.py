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
        self.pushButtonSettings.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons/settings.png")))
        self.pushButtonSettings.clicked.connect(self.showSettings)
        self.pushButtonSave.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons/save.png")))
        self.pushButtonSave.clicked.connect(self.saveRasters)
        self.pushButtonGetIndex.clicked.connect(self.createPolygons)
        self.polygons = []
        self.requests = []
        self.loadPolygons()
        self.loadIndexesList()
        self.loadTypesList()
        self.settings = {}
        # print("LOADING SETTINGS")
        self.loadSettings()
        self.polygons_to_process = []
        self.polygons_to_register = []
        self.current_polygon_to_register_id = 0
        self.requests_to_register = []
        self.current_request_to_register_id = 0

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
        types = ["Observation", "Field zonation", "Time series"]
        for type in types:
            self.comboBoxTypes.addItem(type)

    def loadPolygons(self):
        path = self.settingsPath + "/registered_polygons.gpkg|layername=registered_polygons"
        # print(path)
        self.registered_polygons = QgsVectorLayer(path, "Registered polygons", "ogr")

    def polygonIsRegistered(self, polygon):
        if self.registered_polygons.isValid():
            # print("GETTING REGISTERED")
            provider = self.registered_polygons.dataProvider()
            features = provider.getFeatures()
            # print(features)
            for feature in features:
                # print("COMPARE:")
                registered_geometry = feature.geometry()
                # print(registered_geometry)
                # print(polygon)
                if registered_geometry.equals(polygon):
                    # print("SAME")
                    return feature['polygon_id']
            return None
        else:
            QgsMessageLog.logMessage(self.tr("File for storing registered polygons is not available"), "DynaCrop")
            return None

    def createPolygons(self):
        self.polygons_to_process = []
        self.polygons_to_register = []
        self.current_polygon_to_register_id = 0
        selectedLayers = self.iface.layerTreeView().selectedLayers()
        if len(selectedLayers) != 1:
            QMessageBox.information(None, self.tr("ERROR"), self.tr("You have to select one layer."))
            return
        if selectedLayers[0].type() != QgsMapLayer.VectorLayer:
            QMessageBox.information(None, self.tr("ERROR"), self.tr("You have to select vector layer."))
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
            polid = self.polygonIsRegistered(geom)
            if polid is not None:
                self.polygons_to_process.append(str(polid))
            else:
                self.polygons_to_register.append(polygon)

        if len(self.polygons_to_register) > 0:
            self.createPolygon()
        else:
            self.createProcessingRequests()

    def createPolygon(self):
        self.createpolygon = Connect()
        self.createpolygon.setType('POST')
        self.createpolygon.setUrl(self.url_polygons)
        # "POLYGON((16.609153599499933 49.20045317863389,16.61297306513714 49.199219336662225,16.61524757838177 49.19759286157719,16.616577954053156 49.195910244858794,16.61400303339886 49.195265226606885,16.6094540069096 49.197368515988586,16.608381123303644 49.19863044668781,16.609153599499933 49.20045317863389))"
        # "POLYGON ((16.56518693093434536 49.22676219888379023, 16.56425126852759178 49.22444226880676865, 16.56539200762623665 49.22282728985813094, 16.56810927379379095 49.22272475151218174, 16.5683784369518996 49.22462171091217442, 16.56854506176405906 49.22571118083784825, 16.56828871589919672 49.22681346805676128, 16.56767348582352284 49.2272620733202686, 16.56518693093434536 49.22676219888379023))"
        # print(self.polygons_to_register[self.current_polygon_to_register_id]["geometry"])
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
        if response.status in (200, 201):
            # QMessageBox.information(self.parent.iface.mainWindow(), self.tr("INFO"), self.tr("Polygon registered"))
            # print(response.data)
            response_json = json.loads(response.data)
            self.polygons_to_process.append(str(response_json["id"]))
            self.savePolygon(self.current_polygon_to_register_id, response_json["id"])
        else:
            # print("ERROR")
            QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),
                                    QApplication.translate("World from Space", "Can not register selected polygons. Check if the polygon in single geometry.", None))
            # QMessageBox.information(self.parent.iface.mainWindow(), self.tr("ERROR"), self.tr("Polygon can not be registered"))
        self.current_polygon_to_register_id += 1
        if len(self.polygons_to_register) > self.current_polygon_to_register_id:
            self.createPolygon()
        else:
            time.sleep(15)
            self.createProcessingRequests()
            # self.pushButtonGetIndex.setEnabled(True)

    def savePolygon(self, pos, id):
        if not self.registered_polygons.isValid():
            QgsMessageLog.logMessage(self.tr("File for storing registered polygons is not available"), "DynaCrop")
        else:
            next_fid = self.registered_polygons.featureCount()
            self.registered_polygons.startEditing()
            fet = QgsFeature()
            fet.setGeometry(QgsGeometry.fromWkt(self.polygons_to_register[pos]["geometry"]))
            fet.setAttributes([next_fid, id])
            self.registered_polygons.addFeature(fet)
            # provider.addFeatures([fet])
            self.registered_polygons.commitChanges()

    def createProcessingRequests(self):
        self.requests_to_register = []
        self.current_request_to_register_id = 0
        for index in range(len(self.polygons_to_process)):
            self.requests_to_register.append(self.polygons_to_process[index])
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
        if response.status in (200, 201):
            # QMessageBox.information(self.parent.iface.mainWindow(), self.tr("INFO"), self.tr("Polygon registered"))
            # print(response.data)
            response_json = json.loads(response.data)
            self.requests.append(response_json["id"])
            # print("RESPONSE")
            # print(self.requests)
            time.sleep(1)
            # TODO when the sleep is not sufficient
            self.getProcessingRequestInfo(response_json["id"])
        else:
            # print("ERROR")
            QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),
                                    QApplication.translate("World from Space", "The response does not contain valid data to show.", None))
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
        if response.status in (200, 201):
            # QMessageBox.information(self.parent.iface.mainWindow(), self.tr("INFO"), self.tr("Polygon registered"))
            # print("REQUEST INFO:")
            # print(response.data)
            data = response.data.read().decode('utf-8')
            response_json = json.loads(data)
            if response_json["rendering_type"] == "Time series":
                self.showGraph(response_json)
            else:
                if response_json["result"]["tiles_color"] is not None:
                    # url = "type=xyz&url=" + response_json["result"]["tiles_color"]
                    layer_name = response_json["layer"] + "_" + str(response_json["polygon_id"]) + "__" + str(response_json["date_from"]) + "_" + str(response_json["date_to"])
                    # layer = QgsRasterLayer(url, layer_name, 'wms')
                    url = "/vsicurl/" + response_json["result"]["raw"]
                    layer = QgsRasterLayer(url, layer_name, 'gdal')
                    provider = layer.dataProvider()
                    provider.setNoDataValue(1, -999)
                    provider.setUserNoDataValue(1, [QgsRasterRange(-998,-998)])
                    provider.histogram(1)
                    extent = layer.extent()
                    ver = provider.hasStatistics(1, QgsRasterBandStats.All)
                    stats = provider.bandStatistics(1, QgsRasterBandStats.All,extent, 0)
                    renderer = QgsSingleBandGrayRenderer(layer.dataProvider(), 1)
                    ce = QgsContrastEnhancement(layer.dataProvider().dataType(0))
                    ce.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
                    ce.setMinimumValue(stats.minimumValue)
                    ce.setMaximumValue(stats.maximumValue)
                    renderer.setContrastEnhancement(ce)
                    layer.setRenderer(renderer)
                    # TODO check if the layer is valid
                    QgsProject.instance().addMapLayer(layer)
                else:
                    # print("ERROR")
                    QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),
                                            QApplication.translate("World from Space", "The response does not contain valid data to show.", None))
        else:
            # print("ERROR")
            QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),
                                    QApplication.translate("World from Space", "The response does not contain valid data to show.", None))

        self.current_request_to_register_id += 1
        if len(self.requests_to_register) > self.current_request_to_register_id:
            self.createProcessingRequest()
        self.setCursor(Qt.ArrowCursor)

    def showGraph(self, response_json):
        if response_json["status"] == "completed" and response_json["result"]["Time series"] is not None:
            if response_json["result"]["Time series"]["dates"] is not None and len(response_json["result"]["Time series"]["dates"]) > 0:
                import matplotlib.pyplot as plt
                import matplotlib.dates as mdates
                import datetime as dt

                # "result": {
                #     "Time series": {
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
                dates_list = [dt.datetime.strptime(date, '%Y-%m-%d').date() for date in response_json["result"]["Time series"]["dates"]]
                plt.xticks(rotation=90)
                plt.title(response_json["layer"])
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                plt.gca().xaxis.set_major_locator(mdates.DayLocator())
                plt.plot(dates_list,response_json["result"]["Time series"]["values"],marker='o',label=response_json["polygon"]["id"])
                plt.legend(loc="upper left")
                # print(str(len(self.requests_to_register)))
                # print(str(self.current_request_to_register_id))
                if len(self.requests_to_register) == (self.current_request_to_register_id + 1):
                    mng = plt.get_current_fig_manager()
                    mng.window.showMaximized()
                    plt.show()

    def saveRasters(self):
        selectedLayers = self.iface.layerTreeView().selectedLayers()
        if len(selectedLayers) < 1:
            QMessageBox.information(None, self.tr("ERROR"), self.tr("You have to select at least one layer."))
            return
        for layer in selectedLayers:
            if layer.type() != QgsMapLayer.RasterLayer:
                QgsMessageLog.logMessage(self.tr("Selected layer is not raster. Skipping"), "DynaCrop")
            else:
                self.saveRaster(layer)
                if layer.isValid():
                    url = os.path.join(self.settings['layers_directory'], layer.name() + ".tif")
                    layer2 = QgsRasterLayer(url, layer.name(), 'gdal')
                    if layer2.isValid():
                        QgsProject.instance().addMapLayer(layer2)
                        QgsProject.instance().removeMapLayer(layer)

        QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),
                                QApplication.translate("World from Space", "Selected raster layers were saved localy.", None))

    def saveRaster(self, layer):
        extent = layer.extent()
        width, height = layer.width(), layer.height()
        renderer = layer.renderer()
        provider = layer.dataProvider()
        # crs = layer.crs().toWkt()
        pipe = QgsRasterPipe()
        pipe.set(provider.clone())
        pipe.set(renderer.clone())
        # pa_name, file_name = os.path.split(fileName)
        # save_raster = os.path.join(save_path, file_name)
        p = os.path.join(self.settings['layers_directory'], layer.name() + ".tif")
        file_writer = QgsRasterFileWriter(p)
        file_writer.writeRaster(pipe,
                            width,
                            height,
                            extent,
                            layer.crs())
