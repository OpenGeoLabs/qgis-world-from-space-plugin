from qgis.PyQt.QtCore import QThread, pyqtSignal
import urllib.request, urllib.error, urllib.parse
import socket, os
import requests, json

class ResponseOutput:
    def __init__(self, filepath, minetype):
        self.filepath = filepath
        self.minetype = minetype

class Response():
    status = 200
    data = []
    output = {}

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
            if self.type == 'POST':
                headers = {'Content-type': 'application/json'}
                r = requests.post(self.url, data=self.data, headers=headers)
                responseToReturn.status = r.status_code
                responseToReturn.data = r.text
                print("POST:" + self.url)
                print(r)
            if self.type == 'GET':
                response = urllib.request.urlopen(self.url, None, self.timeout)
                # response = response.read().decode('utf-8') # str(response.read())
                responseToReturn.data = response
                responseToReturn.status = response.status
                print('GET: ' + self.url)
                print(response)
        except urllib.error.URLError:
            responseToReturn.status = 500
            responseToReturn.data = ""
        except urllib.error.HTTPError:
            responseToReturn.status = 500
            responseToReturn.data = ""
        except socket.timeout:
            responseToReturn.status = 500
            responseToReturn.data = ""
        except Exception as e:
            responseToReturn.status = 500
            responseToReturn.data = ""
            print(e)

        self.statusChanged.emit(responseToReturn)
