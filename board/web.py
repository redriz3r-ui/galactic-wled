"""Single-client, bounded nonblocking HTTP server and asynchronous Wi-Fi lifecycle."""
import socket
import json
import config
from utils import ticks_ms,ticks_diff
from api import API

class Server:
    def __init__(self,engine,port=None):
        self.api=API(engine);self.listener=socket.socket()
        try:
            self.listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            self.listener.bind(('0.0.0.0',config.WEB_PORT if port is None else port))
            self.listener.listen(2);self.listener.setblocking(False)
        except OSError:
            self.listener.close()
            raise
        self.client=None;self.file=None;self.rx=bytearray();self.tx=b'';self.offset=0
        self.started=self.activity=0;self.responding=False
    def close_client(self):
        if self.file:
            self.file.close();self.file=None
        if self.client:
            self.client.close();self.client=None
        self.rx=bytearray();self.tx=b'';self.offset=0;self.responding=False
    def close(self):
        self.close_client();self.listener.close()
    def reply(self,status,value=None,html=False):
        data=b''
        if html:
            try:
                self.file=open('www/index.html','rb')
                self.file.seek(0,2);size=self.file.tell();self.file.seek(0)
            except OSError:
                html=False;status=503;value={'error':'Upload www/index.html'}
        if not html:
            data=json.dumps(value).encode();size=len(data)
        kind='text/html; charset=utf-8' if html else 'application/json'
        self.tx=('HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n\r\n' %
                 (status,'OK' if status==200 else 'Error',kind,size)).encode()+data
        self.offset=0;self.responding=True;self.rx=bytearray()
    def request(self):
        boundary=self.rx.find(b'\r\n\r\n')
        if boundary<0:
            if len(self.rx)>1024: self.reply(413,{'error':'Headers too large'})
            return
        if boundary>1024: self.reply(413,{'error':'Headers too large'});return
        try:
            lines=bytes(self.rx[:boundary]).decode().split('\r\n')
            method,path,version=lines[0].split()
            if version not in ('HTTP/1.0','HTTP/1.1'): raise ValueError('Bad HTTP version')
            headers={}
            for line in lines[1:]:
                key,val=line.split(':',1);key=key.strip().lower()
                if key in headers: raise ValueError('Duplicate header')
                headers[key]=val.strip()
            if 'transfer-encoding' in headers: raise ValueError('Chunked requests unsupported')
            length=int(headers.get('content-length','0'))
            if not 0<=length<=4096: self.reply(413,{'error':'Body too large'});return
            if method=='POST' and 'content-length' not in headers: raise ValueError('Content-Length required')
            # Reject browser cross-origin writes; local scripts need no Origin header.
            origin=headers.get('origin')
            if method=='POST' and origin and origin!='http://'+headers.get('host',''):
                self.reply(403,{'error':'Cross-origin write rejected'});return
            if method=='POST' and path!='/api/frame' and not headers.get('content-type','').startswith('application/json'):
                self.reply(415,{'error':'Use application/json'});return
            if len(self.rx)<boundary+4+length: return
            body=bytes(self.rx[boundary+4:boundary+4+length])
            if method=='GET' and path=='/': self.reply(200,html=True)
            else:
                status,value=self.api.handle(method,path,body);self.reply(status,value)
        except (ValueError,UnicodeError): self.reply(400,{'error':'Malformed HTTP request'})
    def poll(self):
        now=ticks_ms()
        if self.client is None:
            try: self.client,_=self.listener.accept()
            except OSError: return
            self.client.setblocking(False);self.started=self.activity=now
        if ticks_diff(now,self.activity)>2500 or ticks_diff(now,self.started)>10000:
            self.close_client();return
        try:
            if self.responding:
                if self.offset<len(self.tx):
                    sent=self.client.send(memoryview(self.tx)[self.offset:self.offset+1024])
                    if sent==0: self.close_client();return
                    self.offset+=sent;self.activity=now
                elif self.file:
                    self.tx=self.file.read(1024);self.offset=0
                    if not self.tx: self.close_client()
                else: self.close_client()
            else:
                data=self.client.recv(512)
                if not data: self.close_client();return
                self.activity=now;self.rx.extend(data)
                if len(self.rx)>5124: self.reply(413,{'error':'Request too large'})
                else: self.request()
        except OSError as error:
            if error.args and error.args[0] in (11,35,10035,115): return
            self.close_client()
        except Exception:
            self.close_client()

class WiFi:
    def __init__(self,engine):
        self.engine=engine;self.wlan=None;self.server=None
        self.attempt=None;self.retry=None;self.ready=False
        if config.WEB_ENABLED and config.WIFI_SSID:
            try:
                import network
                self.wlan=network.WLAN(network.STA_IF)
                try: network.hostname(config.HOSTNAME)
                except AttributeError: pass
            except (ImportError,OSError) as error: engine.error='Wi-Fi unavailable: '+str(error)
    def poll(self):
        if self.wlan is None: return
        now=ticks_ms()
        try:
            if self.wlan.isconnected():
                if self.server is None:
                    self.server=Server(self.engine);self.engine.ip=self.wlan.ifconfig()[0]
                    print('Galactic WLED: http://'+self.engine.ip)
                self.attempt=None;self.server.poll();return
            if self.server:
                self.server.close();self.server=None;self.engine.ip=None
            if self.attempt is not None:
                if ticks_diff(now,self.attempt)>config.WIFI_TIMEOUT_MS:
                    self.wlan.disconnect();self.wlan.active(False);self.attempt=None;self.retry=now
                return
            if self.retry is None or ticks_diff(now,self.retry)>config.WIFI_RETRY_MS:
                self.wlan.active(True);self.wlan.connect(config.WIFI_SSID,config.WIFI_PASSWORD);self.attempt=now
        except Exception as error:
            self.engine.error='Wi-Fi: '+str(error)
            if self.server:
                self.server.close();self.server=None
            self.engine.ip=None;self.retry=now;self.attempt=None
            try: self.wlan.active(False)
            except OSError: pass
