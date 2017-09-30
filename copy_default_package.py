#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

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

import sublime

import os
import sys
import zipfile
import threading
import contextlib


# https://stackoverflow.com/questions/14087598/python-3-importerror-no-module-named-configparser
try:
    import configparser
    from configparser import NoOptionError

except:
    from six.moves import configparser
    from six.moves.configparser import NoOptionError


def assert_path(module):
    """
        Import a module from a relative path
        https://stackoverflow.com/questions/279237/import-a-module-from-a-relative-path
    """
    if module not in sys.path:
        sys.path.append( module )


CURRENT_DIRECTORY    = os.path.dirname( os.path.realpath( __file__ ) )
UPGRADE_SESSION_FILE = os.path.join( CURRENT_DIRECTORY, 'last_sublime_upgrade.studio-channel' )

# print( "CURRENT_DIRECTORY: " + CURRENT_DIRECTORY )
assert_path( os.path.join( os.path.dirname( CURRENT_DIRECTORY ), 'PythonDebugTools' ) )

# Import the debugger
from debug_tools import Debugger

# Debugger settings: 0 - disabled, 127 - enabled
log = Debugger( 1, os.path.basename( __file__ ) )

log( 2, "..." )
log( 2, "..." )
log( 2, "Debugging" )
log( 2, "CURRENT_DIRECTORY: " + CURRENT_DIRECTORY )


def main():
    log( 2, "Entering on main(0)" )
    CopyFilesThread().start()


class CopyFilesThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        log( 2, "Entering on run(1)" )

        package_path  = os.path.join( os.path.dirname(sublime.executable_path()), "Packages", "Default.sublime-package" )
        output_folder = os.path.join( os.path.dirname( os.path.dirname( CURRENT_DIRECTORY ) ), "Default.sublime-package" )

        log( 2, "run, package_path:  " + package_path )
        log( 2, "run, output_folder: " + output_folder )

        extract_package( package_path, output_folder )


def extract_package(package_path, destine_folder):
    """
        If the files already exists on the destine, they will be overridden.
    """

    try:
        package_file = zipfile.ZipFile(package_path)

    except zipfile.BadZipfile:
        log( 1, " The package file '%s is invalid!" % package_path)

    with contextlib.closing(package_file):

        try:
            os.mkdir(destine_folder)

        except OSError:

            if os.path.isdir(destine_folder):
                pass

            else:
                log( 1, "The directory '%s' could not be created!" % destine_folder)
                return

        try:
            package_file.extractall(destine_folder)

        except:
            log( 1, "Extracting '%s' failed." % package_path)
            return

        log( 2, "The file '%s' was successfully extracted." % package_path)


def is_sublime_text_upgraded():
    """
        @return True   when it is the fist time this function is called or there is a sublime text
                       upgrade, False otherwise.
    """

    current_version = int( sublime.version() )

    last_section = open_last_session_data( UPGRADE_SESSION_FILE )
    last_version = int( last_section.getint( 'last_sublime_text_version', 'integer_value' ) )

    last_section.set( 'last_sublime_text_version', 'integer_value', str( current_version ) )
    save_session_data( last_section, UPGRADE_SESSION_FILE )

    if last_version < current_version:
        return True

    else:
        return False


def open_last_session_data(session_file):
    last_section = configparser.ConfigParser( allow_no_value=True )

    if os.path.exists( session_file ):
        last_section.read( session_file )

    else:
        last_section.add_section( 'last_sublime_text_version' )
        last_section.set( 'last_sublime_text_version', 'integer_value', '0' )

    return last_section


def save_session_data(last_section, session_file):

    with open( session_file, 'wt' ) as configfile:
        last_section.write( configfile )


if __name__ == "__main__":
    main()


def plugin_loaded():

    if is_sublime_text_upgraded():
        main()

