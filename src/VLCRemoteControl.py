#!/usr/bin/env python
#-*- coding:utf-8 -*-

import sys, os
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request, urllib
import subprocess
import traceback
import time
from xml.etree import ElementTree

DEBUG = True

VLC_PORT = 9090
VLC_COMMAND = 'vlc --qt-start-minimized --fullscreen --extraintf=luahttp --http-host=localhost --http-port=%s --sout-ffmpeg-strict=-2 --avi-index=2 --no-qt-error-dialogs' % VLC_PORT

if sys.platform.startswith('win32'): #Windows
    SHUTDOWN_COMMAND = 'shutdown -i -s -f'
if sys.platform.startswith('linux'): #Linux, try to detect Desktop Environment (https://groups.google.com/forum/#!topic/razor-qt/w5Ba2Elid_E)
    de = os.environ.get('XDG_CURRENT_DESKTOP')
    if de == 'KDE':
        SHUTDOWN_COMMAND = 'qdbus org.kde.ksmserver /KSMServer org.kde.KSMServerInterface.logout 0 2 2' #KDE logout without user confirm: http://api.kde.org/4.4-api/kdebase-workspace-apidocs/libs/kworkspace/html/namespaceKWorkSpace.html#ebd506f19067a1ae1c00ae4b8f2d7c03
    elif de == 'GNOME':
        SHUTDOWN_COMMAND = 'dbus-send --session --type=method_call --print-reply --dest=org.gnome.SessionManager /org/gnome/SessionManager org.gnome.SessionManager.RequestShutdown'
    else: #LXDE, XFCE
        SHUTDOWN_COMMAND = 'dbus-send --system --print-reply --dest=org.freedesktop.ConsoleKit /org/freedesktop/ConsoleKit/Manager org.freedesktop.ConsoleKit.Manager.Stop' #Quite dirty shutdown

class RemoteControlServer(HTTPServer):    
    def __init__(self, server_address, RequestHandlerClass):
        self.vlcp = None
        
        HTTPServer.__init__(self, server_address, RequestHandlerClass)
        
    def launchVLC(self):
        if self.vlcp is None \
          or (self.vlcp is not None and self.vlcp.poll() is not None):
            self.vlcp = subprocess.Popen(VLC_COMMAND.split(' '))
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
                        print("Received command: ", params)

                if (params.get('command') == ['key'] and params.get('val') == ['shutdown']) \
                  or params.get('command') == ['shutdown']:
                    self.server.closeVLC()
                    subprocess.Popen(SHUTDOWN_COMMAND.split(' '))
                else:
                    self.server.launchVLC()
                        
                    #if params.get('input') != None:
                    #    params['options'] = [':sout=#transcode{soverlay,acodec=mp4a,aenc=avcodec{strict=-2},fps=25,ab=128,channels=1,vcodec=h264,vb=1024,aenc=ffmpeg{aac-profile=low},venc=x264{no-cabac,trellis=0,profile=baseline,keyint=50,no-interlaced,ref=1,vbv-maxrate=1024,vbv-bufsize=512,aq-mode=0,partitions=none,weightp=0,me=dia,subme=0,no-8x8dct,level=1.3,no-weightb,bframes=0,no-mixed-refs,no-mbtree},vfilter=canvas{width=960,aspect=4:3,padd},audio-sync}:rtp{sdp=rtsp://0.0.0.0:5554/stream.sdp,no-sap,no-mp4a-latm,caching=2000}', 'audio-desync=-50', 'sout-keep', 'file-caching=500', 'rtsp-timeout=0', 'rtsp-session-timeout=0', 'rtp-timeout=0']
                    #    self.path = p.path + '?' + urllib.parse.urlencode(params, doseq=True)
                    
                    if self.server.vlcp is not None and self.server.vlcp.poll() is None:                        
                        r = urllib.request.urlopen("http://%s:%s%s" % (self.server.server_address[0], VLC_PORT, self.path))                  
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