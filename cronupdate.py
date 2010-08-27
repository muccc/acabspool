#!/usr/bin/python
# cronupdate - cron updater for the AllColoursAreBeautiful project
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

import sys
import os
from subprocess import Popen, PIPE

ACABSPOOL_ROOT = '/home/fpletz/src/acab/acabspool'

os.chdir(ACABSPOOL_ROOT)
sys.path = ['..','../acabed'] + sys.path
os.environ['DJANGO_SETTINGS_MODULE'] = 'acabed.settings'

from acabed.acab import models

cronjobs = [
    'PYTHONPATH=/home/fpletz/src/django',
    '*/1 * * * * %s/cronupdate.py' % ACABSPOOL_ROOT
]

for cronjob in models.CronJob.objects.all():
    cronjobs.append(
        '%s %s %s %s %s %s/queue.py %s' %
        (cronjob.m, cronjob.h, cronjob.dom, cronjob.mon, cronjob.dow,
         ACABSPOOL_ROOT, cronjob.playlist.pk)
    )

ct = Popen(['crontab', '-'], stdin=PIPE, stdout=sys.stdout, stderr=sys.stderr, close_fds=True)
ct.stdin.write('\n'.join(cronjobs) + '\n')
ct.stdin.close()

