# acabspool - spooling daemon for the AllColoursAreBeautiful project
# Copyright (C) 2010 Raffael Mancini <raffael.mancini@hcl-club.lu>
#                    Franz Pletz <fpletz@fnordicwalking.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import time
import socket
import struct
import json
import threading 
import asyncore

sys.path = ['..','../acabed'] + sys.path
os.environ['DJANGO_SETTINGS_MODULE'] = 'acabed.settings'

from acabed.acab import models
from acabed.kiosk.models import History
import acabed.kiosk.models as kiosk

# klingon ack
ACK = '\xf8\xe2\xf8\xe6\xf8\xd6'
#ack_wait = False

spooler = None
spooler_exit = False

header = 0x00009000
op_duration = 0x0a
op_set_screen = 0x11
op_flip = 0x12

log = lambda s: sys.stdout.write(s + '\n')

MESSAGE_HELLO = 'Welcome to the acabspooler!'
MESSAGE_ALLOWED = 'MOAR\n'
MESSAGE_DENIED = 'GTFO\n'
MESSAGE_ERROR = "ERROR\n"
MESSAGE_NOT_ALLOWED = "NOT ALLWED\n"

GIGARGOYLE_IP = "127.0.0.1"
GIGARGOYLE_PORT = 43948

STREAMER_HOST = ''
STREAMER_PORT = 50023

def ntos(n):
    if n > 0:
        return chr(n % 256) + ntos(n/256)
    return ''




class Spooler(threading.Thread):
    def __init__(self):
        self.socket = None
        self._stopevent = threading.Event()
        self.ack_wait = False
        threading.Thread.__init__(self, name="spooler")
        
    def send_animation(self, s, a):
        #global ack_wait
        elapsed = 0
        duration = -1
        header = 0x00009000
        op_duration = 0x0a
        op_set_screen = 0x11
        op_flip = 0x12
        mask_ack = 0x00000100
    
        data = json.loads(a.data)
        last = data[-1]
        #while a.max_duration > elapsed:
        if True:
            for i in xrange(len(data)):
                if spooler_exit:
                    #print "stop spooler"
                    return
                frame = data[i]
                new_duration = int(frame['duration'])*750
                if new_duration != duration:
                    duration = new_duration
                    s.send(struct.pack('!III', header | op_duration, 8+4, duration))
                    #log(str(duration))
    
                mask = 0
                if i == len(data)-1:
                    mask = mask_ack
                    self.ack_wait = True
    
                d = struct.pack('!II', header | op_set_screen | mask,
                                8 + a.height * a.width * a.depth / 8 * a.channels)
                for r in frame['rows']:
                    for i in xrange(len(r)/2):
                        d += (chr(int(r[i*2:][:2], 16)))
                s.send(d)
                #s.send(struct.pack('!II', header | op_flip, 8))
                
                elapsed += duration    
                
    def run(self):
        #global ack_wait
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((GIGARGOYLE_IP, GIGARGOYLE_PORT))
        log('Spooler: Started')
        try:
            playlists = None
            while 0xacab:
                job = models.SpoolJob.current()
                if len(sys.argv) == 2 and sys.argv[1] == 'PATEN':
                    log('Spooler: PATEN')
                    playlist = models.Playlist.objects.get(title='PIXELPATEN')
                elif job == None:
                    #log('no job in spool, randomly picking a playlist')
                    if playlists is None or playlists == []:
                        playlists = list(models.Playlist.objects.order_by('?'))
                    playlist = playlists.pop()
                else:
                    log('Spooler: working on job: %s' % str(job))
                    playlist = job.playlist
    
                log('Spooler: playlist: %s' % str(playlist))
                for a in playlist.animations.all():
                    if spooler_exit:
                        #print "STOP"
                        raise
                    # wait for ack
                    if self.ack_wait:
                        response = ''
    
                        while len(response) < len(ACK):
                            response += self.socket.recv(len(ACK)-len(response))
                            #log(response)
    
                        log('Spooler: next')
    
                        self.ack_wait = False
    
                    a.playing = True
                    a.save()
                    
                    #get the animation instance and push it to the history
                    try:
                        ai = models.AnimationInstance.objects.get(playlist = playlist, animation = a)
                        History.objects.push_movie(ai)
                    except History.DoesNotExist:
                        pass
                        
                    
                    log('Spooler: Playing animaton %s' % str(a))
                    
                    self.send_animation(self.socket, a)
    
                    a.playing = False
                    a.save()
    
                if job != None:
                    log('Spooler: deleting playlist %s' % str(playlist))
                    job.delete()
    
        except KeyboardInterrupt:
            pass
        except:        
            pass
    
        self.socket.close()
        log('Spooler: Closing')
        
    def join(self,timeout=None):   
        #self._stopevent.set()
        global spooler_exit
        spooler_exit = True
        threading.Thread.join(self, timeout)

class Receiver(asyncore.dispatcher):
    def __init__(self,conn):
        asyncore.dispatcher.__init__(self,conn)
        self.from_remote_buffer=''
        self.to_remote_buffer=''
        self.sender=None
        self.send(MESSAGE_ALLOWED)
        
    def handle_connect(self):
        pass
    
    def handle_read(self):
        read = self.recv(4096)
        #print '%04i -->'%len(read)
        self.from_remote_buffer += read

    def writable(self):
        return (len(self.to_remote_buffer) > 0)

    def handle_write(self):
        sent = self.send(self.to_remote_buffer)
        #print '%04i <--'%sent
        self.to_remote_buffer = self.to_remote_buffer[sent:]

    def handle_close(self):
        #print "close"
        self.close()
        if self.sender:
            self.sender.close()
            
        #restart the spooler
        global spooler
        global spooler_exit 
        spooler_exit = False
        spooler = Spooler()
        spooler.start()

class Sender(asyncore.dispatcher):
    def __init__(self, receiver, remoteaddr,remoteport, request):
        asyncore.dispatcher.__init__(self)
        self.receiver=receiver
        receiver.sender=self
        self.request = request
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((remoteaddr, remoteport))
        self.request.state = kiosk.STREAM_PLAYING
        self.request.save()
        log("Forwarder: Streaming %s by %s"%(self.request.title,self.request.author))
        
    def handle_connect(self):
        pass

    def handle_read(self):
        read = self.recv(4096)
        #print '<-- %04i'%len(read)
        self.receiver.to_remote_buffer += read

    def writable(self):
        return (len(self.receiver.from_remote_buffer) > 0)

    def handle_write(self):
        sent = self.send(self.receiver.from_remote_buffer)
        #print '--> %04i'%sent
        self.receiver.from_remote_buffer = self.receiver.from_remote_buffer[sent:]

    def handle_close(self):
        self.close()
        if self.receiver():
            self.receiver.close()

class RequestListener(asyncore.dispatcher):
    def __init__(self, ip, port):
        asyncore.dispatcher.__init__(self)
        
        self.create_socket(socket.AF_INET,socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((ip,port))
        self.listen(5)
        log("RequestListener: started")
    def handle_accept(self):
        conn, addr = self.accept()
        log("RequestListener: Incoming from %s:%s"%(addr[0],addr[1]))
        RequestHandler(conn)
        
class RequestHandler(asyncore.dispatcher):
    def __init__(self, conn):
        asyncore.dispatcher.__init__(self,conn)
        self.rx_buffer = ""
        self.tx_buffer = ""
        self.request = None
        self.args = {}
        self.conn = None
        self.addr = None
        self.done = False
        self.request = kiosk.StreamRequest.push_new_request()
        log("RequestHandler: started")
        
    def handle_close(self):
        if self.request:
            self.request.state = kiosk.STREAM_FINISHED
            self.request.save()
        self.close()
        log ("RequestHandler: closed")
    
    def handle_connect(self):
        pass
    
    def handle_read(self):
        # Read to the buffer
        self.rx_buffer += self.recv(4096)
        
        #Parse the buffer
        lines = self.rx_buffer.split('\n') #splitlines() behaves differently, ignores trailing newline.
        self.rx_buffer = lines.pop() #empty, if trailing newline.
        
        #Parse the args
        for line in lines:
            log("RequestHandler <-- %s"%line)
            if line.count("=")==1:
                key, val = line.split("=")
                self.args[key]=val
            if line =="DONE":
                self.done = True
                
    def handle_write(self):
        log ("RequestHandler --> %s"%self.tx_buffer)
        sent = self.send(self.tx_buffer)
        self.tx_buffer = self.tx_buffer[sent:]
        
  
    def writable(self):
        #evil hack :)
        self._check_state()
        
        return (len(self.tx_buffer) > 0)
    
    def _check_state(self):
        #kind of a state machine
        
        
        if not self.request:
            self.send(MESSAGE_NOT_ALLOWED)
            self.close()
            return
        
        try:
            self.request = kiosk.StreamRequest.objects.get(id = self.request.id)
        except kiosk.StreamRequest.DoesNotExist:
            self.send(MESSAGE_ERROR)
            self.close()
            return
         
        if self.done:
            self.request.title = self.args["TITLE"]
            self.request.author = self.args["AUTHOR"]
            self.request.save()
            self.done = False
        
        if self.request.state == kiosk.STREAM_ALLOWED:
            log ("RequestHandler: Initiating stream %s by %s"%(self.args["TITLE"],self.args["AUTHOR"]))
            #kill the spooler
            global spooler
            spooler.join()
            
            #Forward to gigargoyle
            Sender(Receiver(self),GIGARGOYLE_IP,GIGARGOYLE_PORT, self.request)   
        
        if self.request.state == kiosk.STREAM_DENIED:
            log ("RequestHandler: Denied stream %s by %s"%(self.args["TITLE"],self.args["AUTHOR"]))
            self.send("MESSAGE_DENIED")
            self.close()
            return

               
def daemonize():
    try:
        pid = os.fork()
    except OSError:
        sys.exit(42)
    
    if pid == 0:
        sys.stdin.close()
        sys.stdout.close()
        sys.stderr.close()
        os.setsid()

        sys.stdin = sys.stdout = sys.stder = logfile = file('acabspool.log', 'w')
        def _log(s):
            logfile.write(s + '\n')
        log = _log
        
        try:   
            main()
        except:
            import traceback
            traceback.print_exc(file=logfile)

    else:
        file('acabspool.pid', 'w').write(str(pid))


def main():
    try:
        global spooler
        spooler = Spooler()
        spooler.start()
    
        #Forwarder("", 50023, "127.0.0.1", 43948)
        kiosk.StreamRequest.objects.restore()
        RequestListener("", 50023)
        asyncore.loop(5,use_poll = True)
    except KeyboardInterrupt:
        exit()
        
if __name__ == '__main__':
    main()

