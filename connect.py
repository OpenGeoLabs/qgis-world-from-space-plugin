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
    """
    Thread that runs in infinite loop and checks if there are any requests in the queues to process
    """
    statusChanged = pyqtSignal(object)
    def __init__(self, path):
        self.settingsPath = path
        super(CheckRequests, self).__init__()
        self.settings = {}
        self.request = None
        self.loadSettings()
        # Paths
        self.url_polygons = 'https://api-dynacrop.worldfromspace.cz/api/v2/polygons'
        self.url_processing_request = 'https://api-dynacrop.worldfromspace.cz/api/v2/processing_request'
        # Pool where the threads are stured
        self.threadPool = []
        self.stop = False

    def loadSettings(self):
        """
        Loads settings from the file
        :return:
        """
        if os.path.exists(self.settingsPath + "/settings.json"):
            with open(self.settingsPath + "/settings.json") as json_file:
                self.settings = json.load(json_file)

    def loadProcessingRequest(self):
        """
        Loads processing request from the file.
        :return:
        """
        if os.path.exists(self.settingsPath + "/requests/request.json"):
            with open(self.settingsPath + "/requests/request.json") as json_file:
                self.request = json.load(json_file)

    def setFileContent(self, file, content):
        """
        Writes content into the file
        :param file:
        :param content:
        :return:
        """
        with open(file, 'w') as f:
            f.write(content)

    def getFileContent(self, file):
        """
        Reads files content
        :param file:
        :return:
        """
        with open(file) as f:
            return f.read()

    def stopMe(self):
        """
        indicates that the thread should be stopped. It is used when the plugin is reloaded.
        :return:
        """
        self.stop = True

    def run(self):
        """
        Main infinite loop
        :return:
        """
        self.threadPool = []
        while True and not self.stop:
            try:
                self.request = None
                # Reads the processing request JSON
                self.loadProcessingRequest()

                if "log_level" in self.settings and self.settings["log_level"] == 'ALL':
                    QgsMessageLog.logMessage("Checking jobs", "DynaCrop")

                if self.request is not None:
                    # Loops polygons queue
                    directory = os.fsencode(self.settingsPath + "/requests/polygons")
                    for file in os.listdir(directory):
                        filename = os.fsdecode(file)
                        # print(filename)
                        content = self.getFileContent(self.settingsPath + "/requests/polygons/" + filename)
                        if "log_level" in self.settings and self.settings["log_level"] == 'ALL':
                            QgsMessageLog.logMessage("File " + self.settingsPath + "/requests/polygons/" + filename + ": " + content, "DynaCrop")
                        # print(content)
                        # If the file is now taken by another thread we wait until the thread finished it
                        if content != 'CHECKING':
                            # If the file is new or last check did not get nay result we create new thread to check it
                            simpleGet = Connect()
                            simpleGet.setUrl(self.url_polygons + "/" + filename + "?api_key=" + self.settings['apikey'])
                            simpleGet.setType("GET")
                            simpleGet.statusChanged.connect(self.onPolygonResponse)
                            # We indicate for another thread that this one is taken writing CHECKING string into the file
                            self.setFileContent(self.settingsPath + "/requests/polygons/" + filename, 'CHECKING')
                            simpleGet.start()
                            self.threadPool.append(simpleGet)
                    directory = os.fsencode(self.settingsPath + "/requests/jobs")
                    # loop for processing jobs, works similar as polygon loop
                    # TODO we may probably simplify this code (DRY)
                    for file in os.listdir(directory):
                        filename = os.fsdecode(file)
                        # print(filename)
                        content = self.getFileContent(self.settingsPath + "/requests/jobs/" + filename)
                        if "log_level" in self.settings and self.settings["log_level"] == 'ALL':
                            QgsMessageLog.logMessage("File " + self.settingsPath + "/requests/jobs/" + filename + ": " + content, "DynaCrop")
                        # print(content)
                        if content != 'CHECKING':
                            getprocessingrequestinfo = Connect()
                            getprocessingrequestinfo.setType('GET')
                            getprocessingrequestinfo.setUrl(self.url_processing_request + "/" + filename + "?api_key=" + self.settings['apikey'])
                            getprocessingrequestinfo.statusChanged.connect(self.onGetProcessingRequestInfoResponse)
                            self.setFileContent(self.settingsPath + "/requests/jobs/" + filename, 'CHECKING')
                            getprocessingrequestinfo.start()
                            self.threadPool.append(getprocessingrequestinfo)

            except Exception as e:
                QgsMessageLog.logMessage(self.tr("ERROR reading thread pool"), "DynaCrop")
                QgsMessageLog.logMessage(e, "DynaCrop")

            self.sleep(1)

    def onPolygonResponse(self, response):
        """
        It is called when the thread of checking polygon status is finished.
        :param response:
        :return:
        """
        # If the checking thread for polygons is finished we look inside the response
        if response.status in (200, 201):
            data = response.data.read().decode('utf-8')
            response_json = json.loads(data)
            if "log_level" in self.settings and self.settings["log_level"] == 'ALL':
                QgsMessageLog.logMessage("onPolygonResponse " + data, "DynaCrop")
            # If the polygon is completed
            if response_json["status"] == "completed":
                # We remove the polygon from the queue
                if os.path.exists(self.settingsPath + "/requests/polygons/" + str(response_json["id"])):
                    os.remove(self.settingsPath + "/requests/polygons/" + str(response_json["id"]))
                # print("CREATE REQUEST:" + str(response_json["id"]))
                # We create new processing request for this polygons that is ready
                self.createProcessingRequest(response_json["id"])
            else:
                # if the polygon is not completed we change indicator in the job file to say check it again (CREATED status)
                self.setFileContent(self.settingsPath + "/requests/polygons/" + str(response_json["id"]), 'CREATED')
        else:
            QgsMessageLog.logMessage(self.tr("ERROR reading registered polygon information"), "DynaCrop")

    def checkCountOfTheRequests(self):
        """
        Checks the number of jobas that are still in the queue
        It emits the signal for main class that subsequently informs the widget
        :return:
        """
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
        return currentCount

    def onGetProcessingRequestInfoResponse(self, response):
        """
        It is called when check of the processing request is finished.
        :param response:
        :return:
        """

        # TODO remove Message boxes from here and put hem into widget
        if response.status in (200, 201):
            data = response.data.read().decode('utf-8')
            response_json = json.loads(data)
            if "log_level" in self.settings and self.settings["log_level"] == 'ALL':
                QgsMessageLog.logMessage("onGetProcessingRequestInfoResponse " + data, "DynaCrop")
            # If the processing request is completed we do the jobas such as load rastre file or sho wgraph
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
                        # Reads raster output directly from the URL
                        url = "/vsicurl/" + response_json["result"]["raw"]
                        layer = QgsRasterLayer(url, layer_name, 'gdal')
                        provider = layer.dataProvider()
                        provider.setNoDataValue(1, -999)
                        provider.setUserNoDataValue(1, [QgsRasterRange(-998,-998)])
                        provider.histogram(1)
                        extent = layer.extent()
                        # Sets the renderer parametesr tho have the raster nice
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

            elif response_json["status"] == "no_data":
                if os.path.exists(self.settingsPath + "/requests/jobs/" + str(response_json["id"])):
                    os.remove(self.settingsPath + "/requests/jobs/" + str(response_json["id"]))
                QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),
                                        QApplication.translate("World from Space", "The response does not contain valid data to show.", None))
            else:
                # if the processing request is not completed we change its status bakc to CREATED in the queue to chekc it next time again
                self.setFileContent(self.settingsPath + "/requests/jobs/" + str(response_json["id"]), 'CREATED')
        else:
            QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),
                                    QApplication.translate("World from Space", "Some error occured during getting information about request status.", None))

        # When this s finished we want ot inform widget to update progress bar
        self.checkCountOfTheRequests()

    def showGraph(self, response_json):
        """
        Shows the graph according to the data in the JSON
        :param response_json:
        :return:
        """
        if response_json["status"] == "completed" and response_json["result"]["time_series"] is not None:
            if response_json["result"]["time_series"]["dates"] is not None and len(response_json["result"]["time_series"]["dates"]) > 0:
                import matplotlib.pyplot as plt
                import matplotlib.dates as mdates
                import datetime as dt

                plt.close('all')

                dates_list = [dt.datetime.strptime(date, '%Y-%m-%d').date() for date in response_json["result"]["time_series"]["dates"]]
                plt.xticks(rotation=90)
                plt.title(response_json["layer"])
                plt.plot(dates_list,response_json["result"]["time_series"]["values"],marker='o',label=response_json["polygon"]["id"])
                plt.legend(loc="upper left")
                # print(str(self.checkCountOfTheRequests()))
                if self.checkCountOfTheRequests() == 0:
                    mng = plt.get_current_fig_manager()
                    mng.window.showMaximized()
                    plt.show()

    def createProcessingRequest(self, polid):
        """
        Creates the processing request based on the JSON and polygonid form the system.
        :param polid:
        :return:
        """
        # We change the polygon id (there is 0 in the originaly stored file just as placeholder.
        # TODO maybe remove polygon:id form the stored JSON file
        self.request["polygon_id"] = polid
        createprocessingrequest = Connect()
        createprocessingrequest.setType('POST')
        createprocessingrequest.setUrl(self.url_processing_request)
        createprocessingrequest.setData(json.dumps(self.request))
        createprocessingrequest.statusChanged.connect(self.onCreateProcessingRequestResponse)
        createprocessingrequest.start()
        self.threadPool.append(createprocessingrequest)

    def onCreateProcessingRequestResponse(self, response):
        """
        It is called when the processing request is created.
        :param response:
        :return:
        """
        if response.status in (200, 201):
            if "log_level" in self.settings and self.settings["log_level"] == 'ALL':
                QgsMessageLog.logMessage("onCreateProcessingRequestResponse " + response.data, "DynaCrop")
            response_json = json.loads(response.data)
            # print("onCreateProcessingRequestResponse" + str(response_json["id"]))
            self.saveRequestJob(response_json["id"])
        else:
            if response.status == 400:
                try:
                    response_json = json.loads(response.data)
                    message = response_json['user']
                    QMessageBox.information(None, QApplication.translate("World from Space", "Error", None), message)
                except:
                    self.generalErrorOnRequest()
            else:
                self.generalErrorOnRequest()

    def generalErrorOnRequest(self):
        QMessageBox.information(None, QApplication.translate("World from Space", "Error", None),
                                            QApplication.translate("World from Space", "Creating reuest failed", None))

    def saveRequestJob(self, requestid):
        """
        Writes the processing request id into the queue
        :param requestid:
        :return:
        """
        with open(self.settingsPath + "/requests/jobs/" + str(requestid), "w") as f:
            f.write(str(requestid))

class Connect(QThread):
    """
    Basic thread for calling POST or GET requests.
    """
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
            QgsMessageLog.logMessage(e, "DynaCrop")

        self.statusChanged.emit(responseToReturn)
