import os
import sys
import time
os.environ['DJANGO_SETTINGS_MODULE'] = 'acabed.settings'

from acabed.animations import models

log = lambda s: sys.stdout.write(s + '\n')

def main():
    while 1:
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
            # TODO: send

            time.sleep(a.max_duration)

            a.playing = False
            a.save()

        if job != None:
            log('deleting %s' % str(playlist))
            job.delete()

        
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

