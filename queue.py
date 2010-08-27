#!/usr/bin/python
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

import sys, os, json

ACABSPOOL_ROOT = '/home/fpletz/src/acab/acabspool'

os.chdir(ACABSPOOL_ROOT)
sys.path = ['..','../acabed'] + sys.path
os.environ['DJANGO_SETTINGS_MODULE'] = 'acabed.settings'

from acab.models import *

for p in Playlist.objects.filter(pk=int(sys.argv[1])):
    print p
    SpoolJob.objects.create(
            playlist=p,
            priority=0, added="2008-01-01 11:11")

