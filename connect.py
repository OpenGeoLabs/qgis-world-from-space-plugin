from qgis.PyQt.QtCore import QThread, pyqtSignal
import urllib.request, urllib.error, urllib.parse
import socket, os
import requests, json

from qgis.core import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import *
from qgis.gui import *

class Response():
    status = 200
    data = []
    output = {}

class CheckRequests(QThread):
    statusChanged = pyqtSignal(object)
    def __init__(self, path):
        self.settingsPath = path
        super(CheckRequests, self).__init__()
        self.settings = {}
        self.request = None
        self.loadSettings()
        self.url_polygons = 'https://api-dynacrop.worldfromspace.cz/api/v2/polygons'
        self.url_processing_request = 'https://api-dynacrop.worldfromspace.cz/api/v2/processing_request'
        self.threadPool = []
        self.stop = False

    def loadSettings(self):
        if os.path.exists(self.settingsPath + "/settings.json"):
            with open(self.settingsPath + "/settings.json") as json_file:
                self.settings = json.load(json_file)

    def loadProcessingRequest(self):
        if os.path.exists(self.settingsPath + "/requests/request.json"):
            with open(self.settingsPath + "/requests/request.json") as json_file:
                self.request = json.load(json_file)

    def setFileContent(self, file, content):
        with open(file, 'w') as f:
            f.write(content)

    def getFileContent(self, file):
        with open(file) as f:
            return f.read()

    def stopMe(self):
        self.stop = True

    def run(self):
        while True and not self.stop:
            try:
                self.threadPool = []
                self.request = None
                self.loadProcessingRequest()
                if self.request is not None:
                    directory = os.fsencode(self.settingsPath + "/requests/polygons")
                    for file in os.listdir(directory):
                        filename = os.fsdecode(file)
                        # print(filename)
                        content = self.getFileContent(self.settingsPath + "/requests/polygons/" + filename)
                        # print(content)
                        if content != 'CHECKING':
                            simpleGet = Connect()
                            simpleGet.setUrl(self.url_polygons + "/" + filename + "?api_key=" + self.settings['apikey'])
                            simpleGet.setType("GET")
                            simpleGet.statusChanged.connect(self.onPolygonResponse)
                            self.setFileContent(self.settingsPath + "/requests/polygons/" + filename, 'CHECKING')
                            simpleGet.start()
                            self.threadPool.append(simpleGet)
                    directory = os.fsencode(self.settingsPath + "/requests/jobs")
                    for file in os.listdir(directory):
                        filename = os.fsdecode(file)
                        # print(filename)
                        content = self.getFileContent(self.settingsPath + "/requests/jobs/" + filename)
                        # print(content)
                        if content != 'CHECKING':
                            getprocessingrequestinfo = Connect()
                            getprocessingrequestinfo.setType('GET')
                            getprocessingrequestinfo.setUrl(self.url_processing_request + "/" + filename + "?api_key=" + self.settings['apikey'])
                            getprocessingrequestinfo.statusChanged.connect(self.onGetProcessingRequestInfoResponse)
                            self.setFileContent(self.settingsPath + "/requests/jobs/" + filename, 'CHECKING')
                            getprocessingrequestinfo.start()
                            self.threadPool.append(getprocessingrequestinfo)

            except Error as e:
                QgsMessageLog.logMessage(self.tr("ERROR reading thread pool"), "DynaCrop")

            self.sleep(10)

    def onPolygonResponse(self, response):
        if response.status in (200, 201):
            data = response.data.read().decode('utf-8')
            response_json = json.loads(data)
            if response_json["status"] == "completed":
                if os.path.exists(self.settingsPath + "/requests/polygons/" + str(response_json["id"])):
                    os.remove(self.settingsPath + "/requests/polygons/" + str(response_json["id"]))
                # print("CREATE REQUEST:" + str(response_json["id"]))
                self.createProcessingRequest(response_json["id"])
            else:
                self.setFileContent(self.settingsPath + "/requests/polygons/" + str(response_json["id"]), 'CREATED')
        else:
            QgsMessageLog.logMessage(self.tr("ERROR reading registered polygon information"), "DynaCrop")

    def checkCountOfTheRequests(self):
        currentCount = 0
        directory = os.fsencode(self.settingsPath + "/requests/polygons")
        for file in os.listdir(directory):
            currentCount += 1
        directory = os.fsencode(self.settingsPath + "/requests/jobs")
        for file in os.listdir(directory):
            currentCount += 1
        responseToReturn = Response()
        responseToReturn.data = currentCount
        self.statusChanged.emit(responseToReturn)

    def onGetProcessingRequestInfoResponse(self, response):
        if response.status in (200, 201):
            data = response.data.read().decode('utf-8')
            response_json = json.loads(data)
            if response_json["status"] == "completed":
                if os.path.exists(self.settingsPath + "/requests/jobs/" + str(response_json["id"])):
                    os.remove(self.settingsPath + "/requests/jobs/" + str(response_json["id"]))
                if response_json["rendering_type"] == "time_series":
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
                        QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),

                                                QApplication.translate("World from Space", "The response does not contain valid data to show.", None))
            else:
                self.setFileContent(self.settingsPath + "/requests/jobs/" + str(response_json["id"]), 'CREATED')
        else:
            QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),
                                    QApplication.translate("World from Space", "Some error occured during getting information about request status.", None))

        self.checkCountOfTheRequests()

    def showGraph(self, response_json):
        if response_json["status"] == "completed" and response_json["result"]["time_series"] is not None:
            if response_json["result"]["time_series"]["dates"] is not None and len(response_json["result"]["time_series"]["dates"]) > 0:
                import matplotlib.pyplot as plt
                import matplotlib.dates as mdates
                import datetime as dt

                dates_list = [dt.datetime.strptime(date, '%Y-%m-%d').date() for date in response_json["result"]["time_series"]["dates"]]
                plt.xticks(rotation=90)
                plt.title(response_json["layer"])
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                plt.gca().xaxis.set_major_locator(mdates.DayLocator())
                plt.plot(dates_list,response_json["result"]["time_series"]["values"],marker='o',label=response_json["polygon"]["id"])
                plt.legend(loc="upper left")
                # print(str(len(self.requests_to_register)))
                # print(str(self.current_request_to_register_id))
                if len(self.requests_to_register) == (self.current_request_to_register_id + 1):
                    mng = plt.get_current_fig_manager()
                    mng.window.showMaximized()
                    plt.show()

    def createProcessingRequest(self, polid):
        # self.setCursor(Qt.WaitCursor)
        self.request["polygon_id"] = polid
        createprocessingrequest = Connect()
        createprocessingrequest.setType('POST')
        createprocessingrequest.setUrl(self.url_processing_request)
        createprocessingrequest.setData(json.dumps(self.request))
        createprocessingrequest.statusChanged.connect(self.onCreateProcessingRequestResponse)
        createprocessingrequest.start()
        self.threadPool.append(createprocessingrequest)

    def onCreateProcessingRequestResponse(self, response):
        if response.status in (200, 201):
            response_json = json.loads(response.data)
            # print("onCreateProcessingRequestResponse" + str(response_json["id"]))
            self.saveRequestJob(response_json["id"])
        else:
            QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),
                                    QApplication.translate("World from Space", "Creating reuest failed", None))

    def saveRequestJob(self, requestid):
        with open(self.settingsPath + "/requests/jobs/" + str(requestid), "w") as f:
            f.write(str(requestid))

class Connect(QThread):
    statusChanged = pyqtSignal(object)
    url = None
    timeout = 5
    data = None

    def setType(self, type):
        self.type = type

    def setUrl(self, url):
        self.url = url

    def setTimeout(self, timeout):
        self.timeout = timeout

    def setData(self, data):
        self.data = data

    def run(self):
        responseToReturn = Response()
        try:
            # print(self.url)
            if self.type == 'POST':
                headers = {'Content-type': 'application/json'}
                r = requests.post(self.url, data=self.data, headers=headers)
                responseToReturn.status = r.status_code
                responseToReturn.data = r.text
                # print("POST:" + self.url)
                # print(r)
            if self.type == 'GET':
                response = urllib.request.urlopen(self.url, None, self.timeout)
                # response = response.read().decode('utf-8') # str(response.read())
                responseToReturn.data = response
                responseToReturn.status = response.status
                # print('GET: ' + self.url)
                # print(response)
        except urllib.error.URLError:
            QgsMessageLog.logMessage(self.tr("URL Error: ") + str(self.url), "DynaCrop")
            responseToReturn.status = 500
            responseToReturn.data = ""
        except urllib.error.HTTPError:
            QgsMessageLog.logMessage(self.tr("HTTP Error: ") + str(self.url), "DynaCrop")
            responseToReturn.status = 500
            responseToReturn.data = ""
        except socket.timeout:
            QgsMessageLog.logMessage(self.tr("Socket Error: ") + str(self.url), "DynaCrop")
            responseToReturn.status = 500
            responseToReturn.data = ""
        except Exception as e:
            responseToReturn.status = 500
            responseToReturn.data = ""
            QgsMessageLog.logMessage(self.tr("Other URL Error: ") + str(self.url), "DynaCrop")

        self.statusChanged.emit(responseToReturn)
