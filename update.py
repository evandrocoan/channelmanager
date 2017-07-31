#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
# These lines allow to use UTF-8 encoding and run this file with `./update.py`, instead of `python update.py`
# https://stackoverflow.com/questions/7670303/purpose-of-usr-bin-python3
# https://stackoverflow.com/questions/728891/correct-way-to-define-python-source-code-encoding
#
#

#
# Licensing
#
#  This program is free software; you can redistribute it and/or modify it
#  under the terms of the GNU General Public License as published by the
#  Free Software Foundation; either version 3 of the License, or ( at
#  your option ) any later version.
#
#  This program is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import re
import os
import sys
import imp
import shlex
import urllib
import unittest
import importlib
import threading
import find_forks
import configparser

def assert_path(module):
    """
        Import a module from a relative path
        https://stackoverflow.com/questions/279237/import-a-module-from-a-relative-path
    """
    if module not in sys.path:
        sys.path.insert( 0, module )

def print_python_envinronment():
    index = 0;

    for path in sys.path:
        print(index, path);
        index += 1;

print_python_envinronment()
current_directory = os.path.dirname( os.path.realpath( __file__ ) )

# print( "current_directory: " + current_directory )
assert_path( os.path.join( current_directory, '../PythonDebugTools' ) )

# sys.tracebacklimit = 10; raise ValueError
find_forks_path = "StudioChannel/find_forks"

# https://stackoverflow.com/questions/9123517/how-do-you-import-a-file-in-python-with-spaces-in-the-name
cmd = importlib.import_module("Package Control.package_control.cmd")

# from find_forks import find_forks as find_forks_
import debug_tools
from debug_tools import log

debug_tools.g_debug_level = 127
log( 1, "..." )
log( 1, "..." )
log( 1, "Debugging" )

##
## Usage:
##   make <target>
##
## Targets:
##   all              generate all assets
##
##   forks            check all forks not supported by `backstroke` against their upstream
##   backstroke       check all backstroke registered repositories updates with their upstream
##   update           perform a git pull from the remote repositories
##
def main():
    log( 1, "Entering on main(0)" )
    ListPackagesThread().start()

    # https://github.com/sublimehq/Packages
    # "https://backstroke.us/",

    # unittest.main()


#
# Repositories which are a fork from outside the Github, which need manually checking.
#
# https://github.com/sublimehq/Packages
# https://github.com/evandrocoan/SublimeAMXX_Editor
# https://github.com/evandrocoan/SublimePreferencesEditor


#
# My forks upstreams
#
class ListPackagesThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        log( 1, "ListPackagesThread::run" )

        self.create_backstroke_pulls()
        log( 1, "Finished ListPackagesThread::run()" )

    def create_backstroke_pulls(self):
        log( 1, "ListPackagesThread::create_backstroke_pulls" )

        configParser   = configparser.RawConfigParser()
        configFilePath = os.path.join( current_directory, '..', '..', '.gitmodules' )

        log( 1, "ListPackagesThread::sections: " + configFilePath )
        configParser.read( configFilePath )

        # https://stackoverflow.com/questions/22068050/iterate-over-sections-in-a-config-file
        for section in configParser.sections():
            log( 1, section )
            # for (each_key, each_val) in configParser.items(section):
            #     log( 1, each_key + ': ' + each_val )

            # https://docs.python.org/3/library/configparser.html#configparser.ConfigParser.get
            upstream   = configParser.get( section, "upstream" )
            backstroke = configParser.get( section, "backstroke" )
            path       = configParser.get( section, "path" )

            # log( 1, upstream )
            # log( 1, backstroke )

            if len( upstream ) > 20:
                user, repository = parse_upstream( upstream )
                command = cmd.Cli( None, True )

                command.execute(
                    shlex.split( "python ../%s --user=%s --repo=%s" % ( find_forks_path, user, repository ) ),
                    os.path.join( current_directory, '..', '..', path ),
                    live_output=True
                )
                break

            # https://stackoverflow.com/questions/2018026/what-are-the-differences-between-the-urllib-urllib2-and-requests-module
            if len( backstroke ) > 20:
                continue
                # https://stackoverflow.com/questions/28396036/python-3-4-urllib-request-error-http-403
                req = urllib.request.Request( backstroke, headers={'User-Agent': 'Mozilla/5.0'} )
                res = urllib.request.urlopen( req )

                # https://stackoverflow.com/questions/2667509/curl-alternative-in-python
                print( res.read() )


    # Now loop through the above array
    # for current_url in backstroke_request_list:
    #     print( str( current_url ) )
        # curl -X POST current_url


def parse_upstream( upstream ):
    """
    How to extract a substring from inside a string in Python?
    https://stackoverflow.com/questions/4666973/how-to-extract-a-substring-from-inside-a-string-in-python
    """
    # https://regex101.com/r/TRxkI9/1/
    matches = re.search( 'github\.com\/(.+)\/(.+)', upstream )

    if matches:
        return matches.group(1), matches.group(2)

    return "", ""

# Here's our "unit".
def IsOdd(n):
    return n % 2 == 1

class IsOddTests(unittest.TestCase):

    def testOne(self):
        self.failUnless(IsOdd(1))


if __name__ == "__main__":
    main()

def plugin_loaded():
    main()

