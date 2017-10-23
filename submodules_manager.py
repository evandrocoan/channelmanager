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

import re
import os
import io
import sys
import imp
import shlex

import time
import argparse
import unittest
import importlib
import threading
import subprocess


CURRENT_DIRECTORY = os.path.dirname( os.path.realpath( __file__ ) )


# Relative imports in Python 3
# https://stackoverflow.com/questions/16981921/relative-imports-in-python-3
try:
    from .settings import *
    from .channel_utilities import get_main_directory
    from .channel_utilities import assert_path

except( ImportError, ValueError):
    from settings import *
    from channel_utilities import get_main_directory
    from channel_utilities import assert_path


# Allow using this file on the website where the sublime
# module is unavailable
try:
    import sublime
    import sublime_plugin

    # Import the debugger
    from PythonDebugTools.debug_tools import Debugger

except ImportError:
    sublime = None
    sublime_plugin = None

    # Import the debugger. It will fail when `PythonDebugTools` is inside a `.sublime-package`,
    # however, this is only meant to be used on the Development version, `PythonDebugTools` is
    # unpacked at the loose packages folder as a git submodule.
    assert_path( os.path.join( os.path.dirname( CURRENT_DIRECTORY ), 'PythonDebugTools' ) )
    from debug_tools import Debugger


# # https://stackoverflow.com/questions/9079036/detect-python-version-at-runtime
if sys.version_info[0] < 3:
    is_python_2 = True

    # https://github.com/noahcoad/google-spell-check/pull/26/files
    import urllib2 as urllib
    from urllib2 import HTTPError

else:
    is_python_2 = False

    # https://stackoverflow.com/questions/3969726/attributeerror-module-object-has-no-attribute-urlopen
    import urllib.request as urllib
    from urllib.error import HTTPError


# sys.tracebacklimit = 10; raise ValueError
def print_python_envinronment():
    index = 0;

    for path in sys.path:
        print(index, path);
        index += 1;


# https://stackoverflow.com/questions/14087598/python-3-importerror-no-module-named-configparser
try:
    import configparser
    from configparser import NoOptionError

except:
    from six.moves import configparser
    from six.moves.configparser import NoOptionError


# print_python_envinronment()
CHANNEL_SESSION_FILE = os.path.join( CURRENT_DIRECTORY, "last_session.channel-manager" )
FIND_FORKS_PATH      = os.path.join( CURRENT_DIRECTORY, "find_forks" )

# How many errors are acceptable when the GitHub API request fails
MAXIMUM_REQUEST_ERRORS = 10
g_is_already_running   = False


# When there is an ImportError, means that Package Control is installed instead of PackagesManager.
# Which means we cannot do nothing as this is only compatible with PackagesManager.
try:
    from PackagesManager.packagesmanager import cmd

except ImportError:
    pass


# Debugger settings: 0 - disabled, 127 - enabled
log = Debugger( 127, os.path.basename( __file__ ) )

#log.log_to_file( "Debug.txt" )
#log.clear_log_file()

# log( 1, "..." )
# log( 1, "..." )
# log( 1, "Debugging" )
# log( 1, "CURRENT_DIRECTORY: " + CURRENT_DIRECTORY )


def main(command=None):
    log( 1, "Entering on main(1) " + str( command ) )
    global CHANNEL_ROOT_DIRECTORY

    argumentsNamespace    = None
    CHANNEL_ROOT_DIRECTORY = get_main_directory( CURRENT_DIRECTORY )

    # https://stackoverflow.com/questions/6382804/how-to-use-getopt-optarg-in-python-how-to-shift
    if not command:
        print_command_line_arguments()
        argumentParser = argparse.ArgumentParser( description='Update Sublime Text Channel' )

        argumentParser.add_argument( "-b", "--backstroke", action="store_true",
                help="Check all backstroke registered repositories updates with their upstream. "
                "The backstroke URLs are now in a separate file on: Local/Backstroke.gitmodules" )

        argumentParser.add_argument( "-f", "--find-forks", action="store_true",
                help="Find all repositories forks, fetch their branches and clean the duplicated branches. "
                "The upstream data in on the `.gitmodules` file on: Sublime Text `Data` folder" )

        argumentParser.add_argument( "-p", "--pull", action="store_true",
                help="Perform a git pull from the remote repositories" )

        argumentParser.add_argument( "-t", "--push-tags", action="store_true",
                help="Perform a git push for all submodules tags to their respective remote repository" )

        argumentsNamespace = argumentParser.parse_args()

    # print( argumentsNamespace )
    if argumentsNamespace and argumentsNamespace.find_forks:
        attempt_run_find_forks()

    elif command == "-t" or argumentsNamespace and argumentsNamespace.push_tags:
        RunGitForEachSubmodulesThread( "git push --tags" ).start()

    elif command == "-p" or argumentsNamespace and argumentsNamespace.pull:
        RunGitForEachSubmodulesThread( "git checkout master && git pull --rebase" ).start()

    elif command == "-b" or argumentsNamespace and argumentsNamespace.backstroke:
        RunBackstrokeThread(False).start()

    elif not command:
        argumentParser.print_help()

    # unittest.main()


def attempt_run_find_forks():
    if sublime:
        print( "The find forks command is only available running by the command line, while" )
        print( "using the Sublime Text Channel Development version." )

    else:
        RunBackstrokeThread(True).start()


def is_allowed_to_run():
    global g_is_already_running

    if g_is_already_running:
        print( "You are already running a command. Wait until it finishes or restart Sublime Text" )
        return False

    g_is_already_running = True
    return True


#
# Repositories which are a fork from outside the Github, which need manually checking.
#
# https://github.com/sublimehq/Packages
# https://github.com/evandrocoan/SublimeAMXX_Editor
# https://github.com/evandrocoan/SublimePreferencesEditor

class RunGitForEachSubmodulesThread(threading.Thread):

    def __init__(self, git_command):
        threading.Thread.__init__(self)
        self.git_command = git_command

    def run(self):

        if is_allowed_to_run():
            self.update_submodules( self.git_command )

        global g_is_already_running
        g_is_already_running = False

    def update_submodules(self, git_command):
        error_list = []
        log( 1, "update_submodules::Current directory: " + CHANNEL_ROOT_DIRECTORY )

        for _ in range(0, 100):
            error_list.append( "Error! " )

        # What is the most efficient string concatenation method in python?
        # https://stackoverflow.com/questions/1316887/what-is-the-most-efficient-string-concatenation-method-in-python
        error_string = ''.join( error_list )

        # git submodule foreach - Robust way to recursively commit a child module first?
        # https://stackoverflow.com/questions/14846967/git-submodule-foreach-robust-way-to-recursively-commit-a-child-module-first
        command  = "git submodule foreach --recursive "

        # Continue looping over submodules with the “git submodule foreach” command after a non-zero exit
        # https://stackoverflow.com/questions/19728933/continue-looping-over-submodules-with-the-git-submodule-foreach-command-after
        command += "'date && %s && printf \"\n\" || printf \"%s\n\n\n\n\n\"'" % ( git_command, error_string )

        if sublime:
            command_line_interface = cmd.Cli( None, False )
            run_command_line( command_line_interface, shlex.split( command ), CHANNEL_ROOT_DIRECTORY )

        else:
            # Python os.system() call runs in incorrect directory
            # https://stackoverflow.com/questions/18066278/python-os-system-call-runs-in-incorrect-directory
            os.chdir( CHANNEL_ROOT_DIRECTORY )

            # Calling an external command in Python
            # https://stackoverflow.com/questions/89228/calling-an-external-command-in-python
            os.system( command )

        log( 1, "Process finished! If there are any, review its log output looking for 'Error!' messages." )


# My forks upstreams
#
class RunBackstrokeThread(threading.Thread):

    def __init__(self, is_find_forks):
        threading.Thread.__init__(self)
        self._is_find_forks = is_find_forks

    def run(self):
        log( 1, "RunBackstrokeThread::run" )

        if is_allowed_to_run():

            if self._is_find_forks:

                if self.run_find_forks(True):
                    self.run_find_forks()

            else:
                self.create_backstroke()

        global g_is_already_running
        g_is_already_running = False

        log( 1, "Finished RunBackstrokeThread::run()" )

    def open_last_session_data(self):
        lastSection = configparser.ConfigParser( allow_no_value=True )

        if os.path.exists( CHANNEL_SESSION_FILE ):
            lastSection.read( CHANNEL_SESSION_FILE )

        else:
            lastSection.add_section( 'last_backstroke_session' )
            lastSection.set( 'last_backstroke_session', 'index', '0' )

            lastSection.add_section( 'last_findforks_session' )
            lastSection.set( 'last_findforks_session', 'index', '0' )

        return lastSection

    def create_backstroke(self):
        log( 1, "RunBackstrokeThread::create_backstroke" )
        backstrokeFilePath = os.path.join( CHANNEL_ROOT_DIRECTORY, 'Local', 'Backstroke.gitmodules' )

        request_index        = 0
        successful_resquests = 0

        # https://pymotw.com/3/configparser/
        lastSection    = self.open_last_session_data()
        maximum_errors = MAXIMUM_REQUEST_ERRORS

        start_index       = lastSection.getint( 'last_backstroke_session', 'index' )
        backstrokeConfigs = configparser.RawConfigParser()

        log( 1, "RunBackstrokeThread::sections: " + backstrokeFilePath )
        backstrokeConfigs.read( backstrokeFilePath )

        index          = 0
        sections       = backstrokeConfigs.sections()
        sections_count = len( sections )

        # https://stackoverflow.com/questions/22068050/iterate-over-sections-in-a-config-file
        for section in sections:
            request_index += 1

            # Walk until the last processed index, skipping everything else
            if start_index > 0:
                start_index -= 1
                continue

            # # For quick testing
            # index += 1
            # if index > 30:
            #     break

            # The GitHub API only allows about 30 requests per second for the backstroke call,
            # then we make it take a little longer so all the requests can be performed in a row.
            time.sleep(2)

            log( 1, "Index: ", successful_resquests, "/", request_index, " of ", sections_count, ", ", section )
            # for (each_key, each_val) in backstrokeConfigs.items(section):
            #     log( 1, each_key + ': ' + each_val )

            # https://docs.python.org/3/library/configparser.html#configparser.ConfigParser.get
            upstream   = self.get_stream_section( section, backstrokeConfigs )
            backstroke = backstrokeConfigs.get( section, "backstroke" )

            # log( 1, upstream )
            # log( 1, backstroke )

            # https://stackoverflow.com/questions/2018026/what-are-the-differences-between-the-urllib-urllib2-and-requests-module
            if len( backstroke ) > 20:
                successful_resquests += 1

                # https://stackoverflow.com/questions/28396036/python-3-4-urllib-request-error-http-403
                req = urllib.Request( backstroke, headers={'User-Agent': 'Mozilla/5.0'} )

                try:
                    # https://stackoverflow.com/questions/2667509/curl-alternative-in-python
                    res = urllib.urlopen( req )
                    print( res.read() )

                except HTTPError as error:
                    maximum_errors -= 1
                    print( "\n\n\nERROR! ", error.read() )

                    # Save only where the first error happened
                    if maximum_errors == MAXIMUM_REQUEST_ERRORS - 1:
                        lastSection.set( 'last_backstroke_session', 'index', str( request_index - 1 ) )

                    if maximum_errors < 1:
                        break

                    else:
                        continue

            else:
                print( "\n\n\nMissing backstroke key for upstream: " + upstream )

        self.save_session_data( maximum_errors, 'last_backstroke_session', lastSection )

    def get_stream_section(self, section, backstrokeConfigs):

        if backstrokeConfigs.has_option( section, "upstream" ):
            return backstrokeConfigs.get( section, "upstream" )

        return ""

    def save_session_data(self, maximum_errors, session_key, lastSection):

        with open( CHANNEL_SESSION_FILE, 'wt' ) as configfile:

            if maximum_errors == MAXIMUM_REQUEST_ERRORS:
                print( "\n\nCongratulations! It was a successful execution." )

                lastSection.set( session_key, 'index', "0" )
                lastSection.write( configfile )

            else:
                print( "\n\nAttention! There were errors on execution, please review its output." )
                lastSection.write( configfile )

    # Now loop through the above array
    # for current_url in backstroke_request_list:
    #     print( str( current_url ) )
        # curl -X POST current_url

    def run_find_forks(self, isKeyErrorChecking=False):
        log( 1, "RunBackstrokeThread::run_find_forks" )
        maximum_errors = MAXIMUM_REQUEST_ERRORS

        # https://pymotw.com/3/configparser/
        lastSection = self.open_last_session_data()
        start_index = lastSection.getint( 'last_findforks_session', 'index' )

        request_index        = 0
        successful_resquests = 0

        gitFilePath      = os.path.join( CHANNEL_ROOT_DIRECTORY, '.gitmodules' )
        upstreamsConfigs = configparser.RawConfigParser()

        # https://stackoverflow.com/questions/45415684/how-to-stop-tabs-on-python-2-7-rawconfigparser-throwing-parsingerror/
        with open( gitFilePath ) as fakeFile:
            # https://stackoverflow.com/questions/22316333/how-can-i-resolve-typeerror-with-stringio-in-python-2-7
            fakefile = io.StringIO( fakeFile.read().replace( u"\t", u"" ) )

        log( 1, "RunBackstrokeThread::sections: " + gitFilePath )
        upstreamsConfigs._read( fakefile, gitFilePath )

        index          = 0
        sections       = upstreamsConfigs.sections()
        sections_count = len( sections )

        # https://stackoverflow.com/questions/22068050/iterate-over-sections-in-a-config-file
        for section in sections:
            request_index += 1

            # Walk until the last processed index, skipping everything else
            if start_index > 0:
                start_index -= 1
                continue

            # # For quick testing
            # index += 1
            # if index > 30:
            #     break

            log( 1, "Index: ", successful_resquests, "/", request_index, " of ", sections_count,", ", section )
            # for (each_key, each_val) in upstreamsConfigs.items(section):
            #     log( 1, each_key + ': ' + each_val )

            try:

                # https://docs.python.org/3/library/configparser.html#configparser.ConfigParser.get
                path     = upstreamsConfigs.get( section, "path" )
                forkUrl  = upstreamsConfigs.get( section, "url" )
                upstream = self.get_stream_section( section, upstreamsConfigs )

            except( NoOptionError, KeyError ) as error:
                maximum_errors -= 1

                print( "\n\n\nERROR! " + str( error ) )
                lastSection.set( 'last_findforks_session', 'index', str( request_index - 1 ) )

                self.save_session_data( maximum_errors, 'last_findforks_session', lastSection )
                return False

            # log( 1, "path: " + path )
            # log( 1, "upstream: " + upstream )

            if isKeyErrorChecking:
                pass

            elif len( upstream ) > 20:
                successful_resquests  += 1
                forkUser, _            = parse_upstream( forkUrl )
                user, repository       = parse_upstream( upstream )
                command_line_interface = cmd.Cli( None, True )

                # Find all forks, add them as remote and fetch them
                run_command_line(
                    command_line_interface,
                    shlex.split( "python %s --user=%s --repo=%s" % ( FIND_FORKS_PATH, user, repository ) ),
                    os.path.join( CHANNEL_ROOT_DIRECTORY, path ),
                )

                # Clean duplicate branches
                run_command_line(
                    command_line_interface,
                    shlex.split( "sh %s/remove_duplicate_branches.sh %s" % ( FIND_FORKS_PATH, forkUser ) ),
                    os.path.join( CHANNEL_ROOT_DIRECTORY, path ),
                )

            else:
                # print( "Missing upstream key for package path: " + path )
                pass


        self.save_session_data( maximum_errors, 'last_findforks_session', lastSection )
        return True


def run_command_line(command_line_interface, commad, initial_folder):
    print( "" )
    output = command_line_interface.execute( commad, initial_folder, live_output=True )

    if is_python_2:
        print( output )


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


def print_command_line_arguments():

    try:
        log( 1, "( print_command_line_arguments ) len(sys.argv): " + str( len( sys.argv ) ) )

        for arg in sys.argv:
            log( 1, "( print_command_line_arguments ) arg: " + str( arg ) )

    except AttributeError:
        pass


if __name__ == "__main__":
    main()


