# acabspool - spooling daemon for the AllColoursAreBeautiful project
# Copyright (C) 2010 Raphael Mancini <sepisultrum@hcl-club.lu>
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

sys.path = ['..','../acabed'] + sys.path
os.environ['DJANGO_SETTINGS_MODULE'] = 'acabed.settings'

from acabed.acab import models

# klingon ack
ACK = u'\xf8\xe2\xf8\xe6\xf8\xd6'

log = lambda s: sys.stdout.write(s + '\n')


def ntos(n):
    if n > 0:
        return chr(n % 256) + ntos(n/256)
    return ''


def send_animation(s, a):
    duration = -1
    header = 0x00009000
    op_duration = 0x0a
    op_set_screen = 0x11
    op_flip = 0x12
    mask_ack = 0x00000100

    data = json.loads(a.data)
    last = data[-1]
    for frame in data:
        if frame['duration'] != duration:
            duration = int(frame['duration'])
            s.send(struct.pack('!III', header | op_duration, 8+4, duration))
            print duration

        mask = 0
        if frame == last:
            mask = mask_ack

        d = struct.pack('!II', header | op_set_screen | mask,
                        8 + a.height * a.width * a.depth / 8 * a.channels)
        for r in frame['rows']:
            for i in xrange(len(r)/2):
                d += (chr(int(r[i*2:][:2], 16)))

        s.send(d)
        s.send(struct.pack('!II', header | op_flip, 8))

    # wait for ack
    response = ''

    while len(response) <= 6:
        response += s.recv(6)

    if response != ACK:
        log('ERROR: no ack?!')


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('localhost', 43948))

    try:
        while 0xacab:
            job = models.SpoolJob.current()

            if job == None:
                log('no job in spool, randomly picking a playlist')
                playlist = models.Playlist.objects.order_by('?')[0]
            else:
                log('working on job: %s' % str(job))
                playlist = job.playlist

            log('playlist: %s' % str(playlist))
            
            for a in playlist.animations.all():
                a.playing = True
                a.save()

                log('playing %s' % str(a))

                send_animation(s, a)

                time.sleep(a.max_duration/1000.0)

                a.playing = False
                a.save()

            if job != None:
                log('deleting %s' % str(playlist))
                job.delete()

    except KeyboardInterrupt:
        pass

    s.close()


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

if __name__ == '__main__':
    main()

