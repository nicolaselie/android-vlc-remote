#!/usr/bin/env python
#-*- coding:utf-8 -*-

import sys, os
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib
import urllib.request
import urllib.parse
import subprocess
import traceback
import time
import shutil
from xml.etree import ElementTree

DEBUG = True

VLC_PORT = 9090
RTSP_PORT = 8554
VLC_COMMAND = '--ttl 12 --qt-start-minimized --fullscreen --extraintf=luahttp --rtsp-host=0.0.0.0 --rtsp-port=%d --http-host=localhost --http-port=%d --sout-ffmpeg-strict=-2 --avi-index=2 --no-qt-error-dialogs --no-qt-privacy-ask' % (RTSP_PORT, VLC_PORT)

#Get command to launch VLC and to shutdown computer (platform specific)
if sys.platform.startswith('win32'): #Windows
    import winreg
    try:
        VLC_EXEC = winreg.QueryValue(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\VideoLAN\VLC')
    except WindowsError:
        VLC_EXEC = r'C:\Program Files\VideoLAN\VLC\vlc.exe',
    VLC_COMMAND += ' --no-qt-updates-notif'
    SHUTDOWN_COMMAND = 'shutdown -s -f -t 0'
if sys.platform.startswith('linux'): #Linux, try to detect Desktop Environment (https://groups.google.com/forum/#!topic/razor-qt/w5Ba2Elid_E)
    VLC_EXEC = 'vlc'
    de = os.environ.get('XDG_CURRENT_DESKTOP')
    if de == 'KDE' and shutil.which("qdbus-qt4") != None:
        SHUTDOWN_COMMAND = 'qdbus-qt4 org.kde.ksmserver /KSMServer org.kde.KSMServerInterface.logout 0 2 2'
    elif de == 'KDE' and shutil.which("qdbus") != None:   
        SHUTDOWN_COMMAND = 'qdbus org.kde.ksmserver /KSMServer org.kde.KSMServerInterface.logout 0 2 2' #KDE logout without user confirm: http://api.kde.org/4.4-api/kdebase-workspace-apidocs/libs/kworkspace/html/namespaceKWorkSpace.html#ebd506f19067a1ae1c00ae4b8f2d7c03
    elif de == 'GNOME':
        SHUTDOWN_COMMAND = 'dbus-send --session --type=method_call --print-reply --dest=org.gnome.SessionManager /org/gnome/SessionManager org.gnome.SessionManager.RequestShutdown'
    else: #LXDE, XFCE
        SHUTDOWN_COMMAND = 'dbus-send --system --print-reply --dest=org.freedesktop.ConsoleKit /org/freedesktop/ConsoleKit/Manager org.freedesktop.ConsoleKit.Manager.Stop' #Quite dirty shutdown

#Try to get VLC version
try:
    p = subprocess.Popen([VLC_EXEC, "--version"], stdout=subprocess.PIPE)
    version = p.communicate()[0].split(b'VLC version')[1].split()[0]
    VLC_VERSION = tuple([int(value) for value in version.split(b'.')])
except:
    VLC_VERSION = (0, 0, 0)

class RemoteControlServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        self.vlcp = None
        
        if server_address[0] == '':
            self.address = 'localhost'
        else:
            self.address = server_address[0]
        
        HTTPServer.__init__(self, server_address, RequestHandlerClass)
        
    def launchVLC(self):
        if self.vlcp is None \
          or (self.vlcp is not None and self.vlcp.poll() is not None):
            self.vlcp = subprocess.Popen([VLC_EXEC] + VLC_COMMAND.split(' '))
            time.sleep(1)

    def closeVLC(self):
        if self.vlcp is not None and self.vlcp.poll() is None:
            self.vlcp.terminate()
    
    def shutdown(self):
        self.closeVLC()
         
        HTTPServer.shutdown(self)

class RemoteControlHandler(BaseHTTPRequestHandler):   
    def __init__(self, request, client_address, parent):
        BaseHTTPRequestHandler.__init__(self, request, client_address, parent)

    def do_GET(self):
        try:
            if self.headers.get_content_type() == 'text/plain':
                
                p = urllib.parse.urlparse(self.path)
                params = {}
                if p.query != '':
                    params = urllib.parse.parse_qs(p.query, True, True)
                    if DEBUG:
                        print("Received command: %s (%s)" % (params, p.path))

                if (params.get('command') == ['key'] and params.get('val') == ['shutdown']) or params.get('command') == ['shutdown']:
                    self.server.closeVLC()
                    subprocess.Popen(SHUTDOWN_COMMAND.split(' '))
                else:
                    self.server.launchVLC()
                        
                    if self.server.vlcp is not None and self.server.vlcp.poll() is None:
                        r = urllib.request.urlopen("http://%s:%s%s" % (self.server.address, VLC_PORT, self.path))
                        data = r.read()
                        
                        if p.path == '/requests/status.xml':
                            container = ElementTree.fromstring(data)
                            ElementTree.SubElement(container, 'allowshutdown').text = "1"
                            data = ElementTree.tostring(container)
                        
                        self.send_response(r.getcode())
                        if r.getcode() == 200:
                            for header, value in r.getheaders():
                                if header == 'Content-Length':
                                    self.send_header(header, len(data))
                                else:
                                    self.send_header(header, value)
                            self.end_headers()
                            self.wfile.write(data)
                    
            return
        except:
            self.send_error(404, 'File Not Found: %s' % self.path)
            if DEBUG:
                print(traceback.print_exc())


if __name__ == '__main__':
    try:
        server = RemoteControlServer(('', 8080), RemoteControlHandler)
        print('Started httpserver...')
        server.serve_forever()
    except KeyboardInterrupt:
        print('^C received, shutting down server')
        server.shutdown()
    except:
        traceback.print_exc()
