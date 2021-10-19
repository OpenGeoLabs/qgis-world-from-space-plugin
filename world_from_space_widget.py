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

from qgis.PyQt import uic
from qgis.core import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import *
from qgis.gui import *

from .ui_settings import Ui_Settings

import json, webbrowser

from .connect import *

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
WIDGET_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'world_from_space_widget_base.ui'))


class WorldFromSpaceWidget(QDockWidget, WIDGET_CLASS):
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(WorldFromSpaceWidget, self).__init__(parent)

        # TODO put into plugin settings
        # Paths
        self.url_polygons = 'https://api-dynacrop.worldfromspace.cz/api/v2/polygons'
        self.url_processing_request = 'https://api-dynacrop.worldfromspace.cz/api/v2/processing_request'
        self.url_layers = 'https://api-dynacrop.worldfromspace.cz/api/v2/available_layers'
        self.iface = iface
        self.pluginPath = os.path.dirname(__file__)
        self.settingsPath = self.pluginPath + "/../../../qgis_world_from_space_settings"
        QDockWidget.__init__(self, None)

        # Dialogs
        self.setupUi(self)
        self.settingsdlg = Ui_Settings(self.pluginPath, self)

        # Settings
        self.settings = {}
        # print("LOADING SETTINGS")
        self.loadSettings()

        # Buttons
        self.pushButtonSettings.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons/settings.png")))
        self.pushButtonSettings.clicked.connect(self.showSettings)
        self.pushButtonSave.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons/save.png")))
        self.pushButtonSave.clicked.connect(self.saveRasters)
        self.pushButtonHelp.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons/help.png")))
        self.pushButtonHelp.clicked.connect(self.showHelp)
        self.pushButtonGetIndex.clicked.connect(self.createPolygons)
        self.pushButtonCancel.clicked.connect(self.cancelRequest)

        # Lists
        self.comboBoxTypes.currentIndexChanged.connect(self.changedType)

        # Global variables
        self.polygons = []
        self.requests = []
        self.loadPolygons()
        self.loadTypesList()
        self.polygons_to_process = []
        self.polygons_to_register = []
        self.current_polygon_to_register_id = 0
        self.requests_to_register = []
        self.current_request_to_register_id = 0
        self.number_of_polygons_to_process = 0

        # Zones
        self.zones = [3, 5, 10, 20, 255]
        self.zones_labels = ['3', '5', '10', '20', '255']
        self.zones_median = [3, 3, 5, 5, 5, 10, 255]
        self.zones_median_labels = ['3 zones - low variability', '3 zones', '5 zones - implicit', '5 zones - low variability', '5 zones - high variability', '10 zones', '255 zones']
        self.zones_median_thresholds = [[0.45, 0.55],
                                        [0.4, 0.6],
                                        [0.45, 0.475, 0.525, 0.55],
                                        [0.48, 0.49, 0.51, 0.52],
                                        [0.4, 0.45, 0.55, 0.6],
                                        [0.325, 0.375, 0.425, 0.475, 0.525, 0.575, 0.625, 0.675, 0.675],
                                        [0.004, 0.008, 0.012, 0.016, 0.02, 0.024, 0.027, 0.031, 0.035, 0.039, 0.043, 0.047, 0.051, 0.055, 0.059, 0.063, 0.067, 0.071, 0.075, 0.078, 0.082, 0.086, 0.09, 0.094, 0.098, 0.102, 0.106, 0.11, 0.114, 0.118, 0.122, 0.125, 0.129, 0.133, 0.137, 0.141, 0.145, 0.149, 0.153, 0.157, 0.161, 0.165, 0.169, 0.173, 0.176, 0.18, 0.184, 0.188, 0.192, 0.196, 0.2, 0.204, 0.208, 0.212, 0.216, 0.22, 0.224, 0.227, 0.231, 0.235, 0.239, 0.243, 0.247, 0.251, 0.255, 0.259, 0.263, 0.267, 0.271, 0.275, 0.278, 0.282, 0.286, 0.29, 0.294, 0.298, 0.302, 0.306, 0.31, 0.314, 0.318, 0.322, 0.325, 0.329, 0.333, 0.337, 0.341, 0.345, 0.349, 0.353, 0.357, 0.361, 0.365, 0.369, 0.373, 0.376, 0.38, 0.384, 0.388, 0.392, 0.396, 0.4, 0.404, 0.408, 0.412, 0.416, 0.42, 0.424, 0.427, 0.431, 0.435, 0.439, 0.443, 0.447, 0.451, 0.455, 0.459, 0.463, 0.467, 0.471, 0.475, 0.478, 0.482, 0.486, 0.49, 0.494, 0.498, 0.502, 0.506, 0.51, 0.514, 0.518, 0.522, 0.525, 0.529, 0.533, 0.537, 0.541, 0.545, 0.549, 0.553, 0.557, 0.561, 0.565, 0.569, 0.573, 0.576, 0.58, 0.584, 0.588, 0.592, 0.596, 0.6, 0.604, 0.608, 0.612, 0.616, 0.62, 0.624, 0.627, 0.631, 0.635, 0.639, 0.643, 0.647, 0.651, 0.655, 0.659, 0.663, 0.667, 0.671, 0.675, 0.678, 0.682, 0.686, 0.69, 0.694, 0.698, 0.702, 0.706, 0.71, 0.714, 0.718, 0.722, 0.725, 0.729, 0.733, 0.737, 0.741, 0.745, 0.749, 0.753, 0.757, 0.761, 0.765, 0.769, 0.773, 0.776, 0.78, 0.784, 0.788, 0.792, 0.796, 0.8, 0.804, 0.808, 0.812, 0.816, 0.82, 0.824, 0.827, 0.831, 0.835, 0.839, 0.843, 0.847, 0.851, 0.855, 0.859, 0.863, 0.867, 0.871, 0.875, 0.878, 0.882, 0.886, 0.89, 0.894, 0.898, 0.902, 0.906, 0.91, 0.914, 0.918, 0.922, 0.925, 0.929, 0.933, 0.937, 0.941, 0.945, 0.949, 0.953, 0.957, 0.961, 0.965, 0.969, 0.973, 0.976, 0.98, 0.984, 0.988, 0.992, 0.996]
                                        ]

        self.setDefaults()

    def setDefaults(self):
        now = QDateTime.currentDateTime()
        self.mDateTimeEditStart.setDateTime(now.addMonths(-1))

    def showHelp(self):
        try:
            webbrowser.get().open(
                "https://github.com/OpenGeoLabs/qgis-world-from-space-plugin/wiki")
        except (webbrowser.Error):
            self.iface.messageBar().pushMessage(QApplication.translate("World from Space", "Error", None), QApplication.translate("World from Space", "Can not find web browser to open help", None), level=Qgis.Critical)

    def get_form_of_output(self, index):
        """
        Returns parameter for API according to the selected items from the list.
        :param index:
        :return:
        """
        if index == 0:
            return "observation"
        if index == 1:
            return "field_zonation"
        if index == 2:
            return "field_zonation_by_median"
        if index == 3:
            return "time_series"

    def loadSettings(self):
        """
        Loads the settings from the file.
        :return:
        """
        if os.path.exists(self.settingsPath + "/settings.json"):
            with open(self.settingsPath + "/settings.json") as json_file:
                self.settings = json.load(json_file)
                self.loadIndexesList()

    def showSettings(self):
        """
        Opens the dialog for the settings.
        :return:
        """
        # First we loads the settings from the file.
        self.settingsdlg.updateSettings()
        self.settingsdlg.show()

    def loadIndexesList(self):
        """
        Loads list of indexes.
        :return:
        """
        self.getIndexes()

    def getIndexes(self):
        self.loadindexes = Connect()
        self.loadindexes.setType('GET')
        self.loadindexes.setUrl(self.url_layers + "?api_key=" + self.settings['apikey'])
        self.loadindexes.statusChanged.connect(self.onLoadIndexesResponse)
        self.loadindexes.start()

    def onLoadIndexesResponse(self, response):
        """
        Loads list of indexes.
        :return:
        """
        if response.status in (200, 201):
            data = response.data.read().decode('utf-8')
            response_json = json.loads(data)
            if "log_level" in self.settings and self.settings["log_level"] == 'ALL':
                QgsMessageLog.logMessage("onLoadIndexesResponse " + data, "DynaCrop")
            # indexes = ["NDVI", "EVI", "NDWI", "NDMI", "LAI", "fAPAR", "CWC", "CCC","SMI"]
            self.comboBoxIndexes.clear()
            for index in response_json:
                self.comboBoxIndexes.addItem(index)
            self.pushButtonGetIndex.setEnabled(True)
        else:
            QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),
                                    QApplication.translate("World from Space", "Can not load layers. Check if you set the API key.", None))

    def loadTypesList(self):
        """
        Loads the list of options in human readable form.
        :return:
        """
        types = ["Observation", "Field zonation", "Field zonation by median", "Time series"]
        for type in types:
            self.comboBoxTypes.addItem(type)

    def changedType(self):
        """
        Checks if type if zone based and adequately loads the zones
        :return:
        """
        if self.comboBoxTypes.currentIndex() == 1:
            self.loadZones()
            self.comboBoxZones.setEnabled(True)
        if self.comboBoxTypes.currentIndex() == 2:
            self.loadZonesMedian()
            self.comboBoxZones.setEnabled(True)
        if self.comboBoxTypes.currentIndex() == 0 or self.comboBoxTypes.currentIndex() == 3:
            self.comboBoxZones.clear()
            self.comboBoxZones.setEnabled(False)

    def loadZones(self):
        self.comboBoxZones.clear()
        for zone in self.zones_labels:
            self.comboBoxZones.addItem(zone)

    def loadZonesMedian(self):
        self.comboBoxZones.clear()
        for zone in self.zones_median_labels:
            self.comboBoxZones.addItem(zone)
        self.comboBoxZones.setCurrentIndex(2)

    def loadPolygons(self):
        """
        Loads locally stored polygons from previous sessions.
        :return:
        """
        path = self.settingsPath + "/registered_polygons.gpkg|layername=registered_polygons"
        # print(path)
        self.registered_polygons = QgsVectorLayer(path, "Registered polygons", "ogr")

    def polygonIsRegistered(self, polygon):
        """
        Checks if the polygons is already registerd in the DynaCrop system.
        :param polygon: input polygon
        :return: Id if we have its id in local storage None if not.
        """
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

    def transformToWgs84(self, geom):
        """
        Transforms geometry into EPSG:4326
        :param geom:
        :return:
        """
        source_crs = self.iface.layerTreeView().selectedLayers()[0].crs().authid()
        if source_crs != "EPSG:4326":
            crs_src = QgsCoordinateReferenceSystem(source_crs)
            crs_dest = QgsCoordinateReferenceSystem(4326)
            xform = QgsCoordinateTransform(crs_src, crs_dest, QgsProject.instance())
            geom.transform(xform)
            return geom
        else:
            return geom

    def getSelectedParts(self, geometry):
        """
        Returns one or more geometries.
        If the geometry is multigeometry it splits it into list of sigle geometries.
        :param geometry: geometry to split
        :return: list of geometries, if the geometry is single then the list has just one item
        """
        geometries = []
        if geometry.isMultipart():
            multi_geometry = geometry.asMultiPolygon()
            for single_geom in multi_geometry:
                single_geom_wpsg4326 = self.transformToWgs84(QgsGeometry.fromPolygonXY(single_geom))
                geometries.append(single_geom_wpsg4326)
        else:
            single_geom_wpsg4326 = self.transformToWgs84(geometry)
            geometries.append(single_geom_wpsg4326)
        return geometries

    def savePolygonsJob(self, polid):
        """
        Writes polygon check into the queue
        :param polid: polygon id to check
        :return:
        """
        with open(self.settingsPath + "/requests/polygons/" + str(polid), "w") as f:
            f.write(str(polid))

    def saveProcessingRequest(self):
        """
        Saves request into JSON to use it from connect thread
        :return:
        """
        number_of_zones = 10
        data = {
            "rendering_type": self.get_form_of_output(self.comboBoxTypes.currentIndex()),
            "polygon_id": 0,
            "date_from": self.mDateTimeEditStart.dateTime().toString("yyyy-MM-dd"),
            "date_to": self.mDateTimeEditEnd.dateTime().toString("yyyy-MM-dd"),
            "layer": self.comboBoxIndexes.currentText(),
            "number_of_zones": number_of_zones,
            "api_key": self.settings['apikey']
        }

        if self.comboBoxTypes.currentIndex() == 1:
            number_of_zones = self.zones[self.comboBoxZones.currentIndex()]
            data["number_of_zones"] = number_of_zones

        if self.comboBoxTypes.currentIndex() == 2:
            number_of_zones = self.zones_median[self.comboBoxZones.currentIndex()]
            data["number_of_zones"] = number_of_zones
            data["thresholds"] = self.zones_median_thresholds[self.comboBoxZones.currentIndex()]

        with open(self.settingsPath + "/requests/request.json", "w") as outfile:
            json.dump(data, outfile)

    def createPolygons(self):
        """
        Main function where all starts.
        :return:
        """
        self.progressBar.setValue(0)
        self.polygons_to_process = []
        self.polygons_to_register = []
        self.current_polygon_to_register_id = 0
        selectedLayers = self.iface.layerTreeView().selectedLayers()

        # Check if all inputs are ready
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

        if self.mDateTimeEditStart.dateTime() >= self.mDateTimeEditEnd.dateTime():
            QMessageBox.information(None, self.tr("ERROR"), self.tr("Please enter valid time range."))
            return

        # Saves the request into JSOn for further usage
        self.saveProcessingRequest()
        self.pushButtonGetIndex.setEnabled(False)
        # Inform user that something happend
        self.progressBar.setValue(5)

        # Check if the index is SMI
        smi_enabled = False
        if self.comboBoxIndexes.currentText() == 'SMI':
            smi_enabled = True

        # Close plot
        if self.comboBoxTypes.currentIndex() == 2:
            import matplotlib.pyplot as plt
            plt.close('all')

        # Loop all selected geometries
        for feature in features:
            geom = feature.geometry()
            geometries = self.getSelectedParts(geom)
            for single_geometry in geometries:
                stripped_z = QgsGeometry.fromPolygonXY(single_geometry.asPolygon())
                geom_wkt = stripped_z.asWkt()
                polygon = {"layer": layer_source, "fid": feature.id(), "geometry": geom_wkt, "smi_enabled": smi_enabled}
                polid = self.polygonIsRegistered(single_geometry)
                self.number_of_polygons_to_process += 1

                # If the polygon is already registered we just save it
                if polid is not None:
                    self.polygons_to_process.append(str(polid))
                    self.savePolygonsJob(polid)
                else:
                    # If the polygon is not registered we add it into the list and then save into the queue
                    self.polygons_to_register.append(polygon)

        if len(self.polygons_to_register) > 0:
            # If there are polygons to register we register them
            self.createPolygon()

    def cancelRequest(self):
        """
        Allows to remove all jobs from the queues and returns back to the starting position.
        :return:
        """

        directory = os.fsencode(self.settingsPath + "/requests/polygons")
        for file in os.listdir(directory):
            filename = os.fsdecode(file)
            os.remove(self.settingsPath + "/requests/polygons/" + str(filename))

        directory = os.fsencode(self.settingsPath + "/requests/jobs")
        for file in os.listdir(directory):
            filename = os.fsdecode(file)
            os.remove(self.settingsPath + "/requests/jobs/" + str(filename))

        self.progressBar.setValue(0)
        self.pushButtonGetIndex.setEnabled(True)

    def onProgressStatusChanged(self, count):
        """
        This is slot where jobs thread sends ifnormation about the progress
        :param count: number of not processed jobs
        :return:
        """
        # If all is done we return to the first state
        if count == 0:
            self.progressBar.setValue(100)
            self.pushButtonGetIndex.setEnabled(True)
        else:
            # We had used already the 5% so the have just 95% for the rest
            one_request_percent = 95 / self.number_of_polygons_to_process / 2
            self.progressBar.setValue(int(105 - (one_request_percent * count)))

    def createPolygon(self):
        """
        Creates thread that registers the polygon
        :return:
        """
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
            "smi_enabled": self.polygons_to_register[self.current_polygon_to_register_id]["smi_enabled"]
        }
        self.createpolygon.setData(json.dumps(data))
        self.createpolygon.statusChanged.connect(self.onCreatePolygonResponse)
        self.createpolygon.start()

    def onCreatePolygonResponse(self, response):
        """
        If the thrtead registers the polygon we move to the other polygon.
        :param response:
        :return:
        """
        if response.status in (200, 201):
            response_json = json.loads(response.data)
            if "log_level" in self.settings and self.settings["log_level"] == 'ALL':
                QgsMessageLog.logMessage("onCreatePolygonResponse " + response.data, "DynaCrop")
            self.polygons_to_process.append(str(response_json["id"]))
            self.savePolygon(self.current_polygon_to_register_id, response_json["id"])
            self.savePolygonsJob(response_json["id"])
        else:
            QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),
                                    QApplication.translate("World from Space", "Can not register selected polygons. Check if the polygon in single geometry.", None))

        # Move to the another polygon if there is any
        self.current_polygon_to_register_id += 1
        if len(self.polygons_to_register) > self.current_polygon_to_register_id:
            self.createPolygon()

    def savePolygon(self, pos, id):
        """
        Saves the polygon into local GPKG file.
        :param pos: where is the polygon in the list
        :param id: id of the polygon from DynaCrop database
        :return:
        """
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

    def saveRasters(self):
        """
        Saves selected raster layers to the local directory and replaces its original with local.
        :return:
        """
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
        """
        Saves one raster to he local directory.
        :param layer:
        :return:
        """
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
