#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
# A minimal example to run external command using the `Package Control` CLI (Command Line Intercace).
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

import os
import sys
import shlex
import subprocess
import importlib
import threading

# print( "current_directory: " + current_directory )
current_directory = os.path.dirname( os.path.realpath( __file__ ) )

# https://stackoverflow.com/questions/9123517/how-do-you-import-a-file-in-python-with-spaces-in-the-name
cmd = importlib.import_module("Package Control.package_control.cmd")

# sys.tracebacklimit = 10; raise ValueError
find_forks_path = "StudioChannel/find_forks"

def main():
    ListPackagesThread().start()

class ListPackagesThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        self.create_backstroke_pulls()

    def create_backstroke_pulls(self):
        print( "here" )

        user       = "aziz"
        path       = "Packages/ANSIescape"
        repository = "SublimeANSI"

        command = cmd.Cli( None, True )

        command.execute(
            shlex.split( "python ../%s --user=%s --repo=%s" % ( find_forks_path, user, repository ) ),
            os.path.join( current_directory, '..', '..', path ),
            live_output=True
        )

        # startupinfo = subprocess.STARTUPINFO()
        # startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # proc = subprocess.Popen(
        #     shlex.split("python ../%s --user=%s --repo=%s" % ( find_forks_path, user, repository ) ),
        #     stdin=subprocess.PIPE,
        #     stdout=subprocess.PIPE,
        #     stderr=subprocess.STDOUT,
        #     startupinfo=startupinfo,
        #     cwd=os.path.join( current_directory, '..', '..', path ),
        #     env=os.environ
        # )
        # output, _ = proc.communicate()
        # print( output )


if __name__ == "__main__":
    main()

def plugin_loaded():
    main()

