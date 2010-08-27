import sys, os, json
sys.path = ['..','../acabed'] + sys.path
os.environ['DJANGO_SETTINGS_MODULE'] = 'acabed.settings'

from acab.models import *

for a in Animation.objects.filter(author=sys.argv[1]):
    print a
    SpoolJob.objects.create(
            playlist=
                AnimationInstance.objects.filter(animation=a.pk)[0].playlist,
            priority=0, added="2008-01-01 11:11")

