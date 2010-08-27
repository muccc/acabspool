import sys, os, json
sys.path = ['..','../acabed'] + sys.path
os.environ['DJANGO_SETTINGS_MODULE'] = 'acabed.settings'

from acab.models import *

for a in Animation.objects.using('sqlite').all():
    a.title = a.title + ' (oldphidias)'
    a.pk = None
    a.save(using='default')

    p = Playlist(
        title = 'stub \'%s\' playlist (oldphidias)' % a.title,
        user = User.objects.all()[0]
    )
    p.save(using='default')
    
    ai = AnimationInstance(
        playlist = p,
        animation = a
    )
    ai.save(using='default')

