import sys, os, json
sys.path = ['..','../acabed'] + sys.path
os.environ['DJANGO_SETTINGS_MODULE'] = 'acabed.settings'

from acab.models import *
rows = "ABCD"

data = []
for y in range(4):
    tmp = []
    for x in range(1,25):
        pixel = rows[y] + "%02i" % x
        do = Pixeldonor.objects.get(pixel=pixel)
        
        '''i = 0
        colors = []
        tmpc = ''
        for c in do.color:
            if i == 0:
                i = 1
                tmpc = c
            else:
                i = 0
                colors.append(tmpc + c)
        print colors'''

        tmp.append(do.color.lower())
    data.append(''.join(tmp))

data = [{'duration': 5000, 'rows': data}]

print json.dumps(data)
