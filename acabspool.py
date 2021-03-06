# acabspool - spooling daemon for the AllColoursAreBeautiful project
# Copyright (C) 2010 Raffael Mancini <raffael.mancini@hcl-club.lu>
#                    Franz Pletz <fpletz@fnordicwalking.de>
#                    Sebastian Steuer <iggy@zxzy.de>
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
MESSAGE_NOT_ALLOWED = "BUSY\n"
MESSAGE_ABORT = "ABORT\n"

GIGARGOYLE_IP = "127.0.0.1"
GIGARGOYLE_SPOOLER_PORT = 43948
GIGARGOYLE_STREAMER_PORT = 44203
STREAMER_HOST = ''
STREAMER_PORT = 50023

def ntos(n):
    if n > 0:
        return chr(n % 256) + ntos(n/256)
    return ''




class Spooler(asyncore.dispatcher):
    def __init__(self,addr, port):
        asyncore.dispatcher.__init__(self)
        
        self.ack_wait = False
        self.ack_received = True
        self.tx_buffer = ''
        self.rx_buffer = ''
        self.playlists = None
        self.playlist = None
        
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((addr, port))
        log('Spooler: Started')
        
        
    def handle_read(self):
        read = self.recv(4096)
        print "read:"+read
        #log("Forwarder: %04i -->"%read)
        self.rx_buffer += read
        if len(self.rx_buffer) >= len(ACK):
            self.ack_received = True
            self.rx_buffer = ''

    def writable(self):
        self._check_state()
        
        return (len(self.tx_buffer) > 0)

    def handle_write(self):
        sent = self.send(self.tx_buffer)
        #log("Forwarder: %04i <--"%sent)
        self.tx_buffer = self.tx_buffer[sent:]
    
    def handle_close(self):
        self.close()
        log('Spooler: Closing')
        
    def send_animation(self, a):
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

        for i in xrange(len(data)):
            if spooler_exit:
                #print "stop spooler"
                return
            frame = data[i]
            new_duration = int(frame['duration'])*750
            if new_duration != duration:
                duration = new_duration
                self.tx_buffer+=(struct.pack('!III', header | op_duration, 8+4, duration))
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
            self.tx_buffer += d
            #s.send(struct.pack('!II', header | op_flip, 8))
            
            elapsed += duration    
                
    def _check_state(self):
        
        #Setup job, playlist
        job = models.SpoolJob.current()
        if len(sys.argv) == 2 and sys.argv[1] == 'PATEN':
            log('Spooler: PATEN')
            self.playlist = models.Playlist.objects.get(title='PIXELPATEN')
            
        elif job == None:
            #log('no job in spool, randomly picking a playlist')
            if self.playlists is None or self.playlists == []:
                self.playlists = list(models.Playlist.objects.order_by('?'))
            if self.playlist is None:
                self.playlist = self.playlists.pop()
        else:
            log('Spooler: working on job: %s' % str(job))
            self.playlist = job.playlist

        log('Spooler: playlist: %s' % str(self.playlist))
        for a in self.playlist.animations.all():
            
            # wait for ack
            if self.ack_wait:
                log ("Spooler: waiting for ack")
                if self.ack_received:
                    log('Spooler: ack received')
                    self.ack_wait = False
                    self.ack_received = False
                else:
                    log('Spooler: ack not received')
                    return
                
            a.playing = True
            a.save()
            
            #get the animation instance and push it to the history
            try:
                ai = models.AnimationInstance.objects.get(playlist = self.playlist, animation = a)
                History.objects.push_movie(ai)
            except History.DoesNotExist:
                pass
                
            
            log('Spooler: Playing animaton %s' % str(a))
            
            self.send_animation(a)

            a.playing = False
            a.save()
        
        if job != None:
            log('Spooler: deleting playlist %s' % str(self.playlist))
            job.delete()
        else:
            self.playlist = self.playlists.pop()
    
        
        

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
        #log("Forwarder: %04i -->"%read)
        self.from_remote_buffer += read

    def writable(self):
        return (len(self.to_remote_buffer) > 0)

    def handle_write(self):
        sent = self.send(self.to_remote_buffer)
        #log("Forwarder: %04i <--"%sent)
        self.to_remote_buffer = self.to_remote_buffer[sent:]

    def handle_close(self):
        log("Receiver: handle close")
        if self.sender:
            self.sender.handle_close()
            self.sender = None
        self.close()

class Sender(asyncore.dispatcher):
    def __init__(self, receiver, remoteaddr,remoteport, handler):
        asyncore.dispatcher.__init__(self)
        self.receiver=receiver
        receiver.sender=self
        self.handler = handler
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((remoteaddr, remoteport))
        self.handler.request.state = kiosk.STREAM_PLAYING
        self.handler.request.save()
        
        History.objects.push_stream(self.handler.request)
        log("Forwarder: Streaming %s by %s"%(self.handler.request.title,self.handler.request.author))
        
    def handle_connect(self):
        pass

    def handle_read(self):
        #try:
        read = self.recv(4096)
        self.receiver.to_remote_buffer += read
        #except socket.error:
        #    log("Forwarder (sender) socket error during read")
        #print '<-- %04i'%len(read)
        

    def writable(self):
        try:
            self.handler.request = kiosk.StreamRequest.objects.get(id = self.handler.request.id)
        except kiosk.StreamRequest.DoesNotExist:
            log("Forwarder: Stream Does not exist!")
            #self.send(MESSAGE_ERROR)
            
            self.handle_close()
            return
        
        if self.handler.request.state == kiosk.STREAM_ABORT:
            log ("Forwarder: Aborted stream %s by %s"%(self.handler.request.title,self.handler.request.author))
            #self.send("MESSAGE_ABORT")
            self.handle_close()
            return
        
        return (len(self.receiver.from_remote_buffer) > 0)

    def handle_write(self):
        sent = self.send(self.receiver.from_remote_buffer)
        #print '--> %04i'%sent
        self.receiver.from_remote_buffer = self.receiver.from_remote_buffer[sent:]

    def handle_close(self):
        log("Sender : handle close")
        if self.handler:
            self.handler.forwarder = None
            self.handler.handle_close()
            self.handler = None
        if self.receiver:
            self.receiver.sender = None
            self.receiver.handle_close()
            self.receiver = None
        self.close()
        
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
        self.forwarder = None
        self.done = False
        self.request = kiosk.StreamRequest.push_new_request()
        log("RequestHandler: started")
        
    def handle_close(self):
        if self.request:
            self.request.state = kiosk.STREAM_FINISHED
            self.request.save()
        if self.forwarder:
            self.forwarder.handle_close()
            self.forwarder = None
        self.close()
        spooler.ack_wait = False
        
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
        #from guppy import hpy
        #h = hpy()
        #print h.heap()
        
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
            self.forwarder = Sender(Receiver(self),GIGARGOYLE_IP,GIGARGOYLE_STREAMER_PORT, self)   
        
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
    #Setup the spooler and streamer
    global spooler
    spooler = Spooler(GIGARGOYLE_IP, GIGARGOYLE_SPOOLER_PORT)
    streamer = RequestListener(STREAMER_HOST, STREAMER_PORT)
    
    #Clean the db from old requests
    kiosk.StreamRequest.objects.restore()
    
    #loop through all the dispatchers
    try:
        asyncore.loop(1,use_poll = True)
    except KeyboardInterrupt:
        spooler.handle_close()
        streamer.handle_close()
        exit()
        
if __name__ == '__main__':
    main()

