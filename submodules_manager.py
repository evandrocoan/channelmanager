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
# Channel Manager Submodules, manage the channel repositories
# Copyright (C) 2017 Evandro Coan <https://github.com/evandrocoan>
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
    from .channel_utilities import progress_info
    from .channel_utilities import assert_path

except( ImportError, ValueError):
    from settings import *
    from channel_utilities import get_main_directory
    from channel_utilities import progress_info
    from channel_utilities import assert_path


# Allow using this file on the website where the sublime
# module is unavailable
try:
    import sublime
    import sublime_plugin

    from estimated_time_left import estimated_time_left
    from PythonDebugTools.debug_tools import Debugger

    # When there is an ImportError, means that Package Control is installed instead of PackagesManager.
    # Which means we cannot do nothing as this is only compatible with PackagesManager.
    try:
        from PackagesManager.packagesmanager import cmd

    except:
        pass

except ImportError:
    sublime = None
    sublime_plugin = None

    # Import the debugger. It will fail when `PythonDebugTools` is inside a `.sublime-package`,
    # however, this is only meant to be used on the Development version, `PythonDebugTools` is
    # unpacked at the loose packages folder as a git submodule.
    assert_path( os.path.join( os.path.dirname( CURRENT_DIRECTORY ), 'PythonDebugTools' ) )
    assert_path( os.path.join( os.path.dirname( CURRENT_DIRECTORY ), 'PackagesManager' ) )
    assert_path( os.path.join( os.path.dirname( CURRENT_DIRECTORY ), 'estimated_time_left' ) )

    import estimated_time_left
    from debug_tools import Debugger
    from packagesmanager import cmd


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

    for file_path in sys.path:
        print(index, file_path);
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

        argumentParser.add_argument( "-u", "--create-upstreams", action="store_true",
                help="Find all repositories on the `.gitmodules` which has the key `upstream` and add"
                "it as a remote on the respective repository." )

        argumentParser.add_argument( "-d", "--delete-remotes", action="store_true",
                help="Find all repositories on the `.gitmodules` which has the key `upstream` and delete"
                "all its git remote repositories which are not the origin or the upstream user." )

        argumentParser.add_argument( "-o", "--pull-origins", action="store_true",
                help="Find all repositories on the `.gitmodules` and perform a git pull --rebase" )

        argumentParser.add_argument( "-fo", "--fetch-origins", action="store_true",
                help="Find all repositories on the `.gitmodules` and perform a git fetch origin" )

        argumentsNamespace = argumentParser.parse_args()

    # print( argumentsNamespace )
    if argumentsNamespace and argumentsNamespace.find_forks:
        attempt_run_find_forks()

    elif command == "-t" or argumentsNamespace and argumentsNamespace.push_tags:
        RunGitForEachSubmodulesThread( "git push --tags" ).start()

    elif command == "-p" or argumentsNamespace and argumentsNamespace.pull:
        RunGitForEachSubmodulesThread( "git checkout master && git pull --rebase" ).start()

    elif command == "-o" or argumentsNamespace and argumentsNamespace.pull_origins:
        RunBackstrokeThread("pull_origins").start()

    elif command == "-fo" or argumentsNamespace and argumentsNamespace.fetch_origins:
        RunBackstrokeThread("fetch_origins").start()

    elif command == "-b" or argumentsNamespace and argumentsNamespace.backstroke:
        RunBackstrokeThread("backstroke").start()

    elif command == "-u" or argumentsNamespace and argumentsNamespace.create_upstreams:
        RunBackstrokeThread("create_upstreams").start()

    elif command == "-d" or argumentsNamespace and argumentsNamespace.delete_remotes:
        RunBackstrokeThread("delete_remotes").start()

    elif not command:
        argumentParser.print_help()

    else:
        log( 1, "Invalid command: " + str( command ) )

    # unittest.main()


def attempt_run_find_forks():
    if sublime:
        print( "The find forks command is only available running by the command line, while" )
        print( "using the Sublime Text Channel Development version." )

    else:
        RunBackstrokeThread("find_forks").start()


def is_allowed_to_run():
    global g_is_already_running

    if g_is_already_running:
        print( "You are already running a command. Wait until it finishes or restart Sublime Text" )
        return False

    g_is_already_running = True
    return True


# My forks upstreams
#
class RunBackstrokeThread(threading.Thread):

    def __init__(self, command):
        threading.Thread.__init__(self)
        self.command = command

    def run(self):
        log( 1, "RunBackstrokeThread::run" )

        if is_allowed_to_run():

            if self.command == "find_forks":
                settings = \
                {
                    'section_name': "last_find_forks_session",
                    'git_file_path': os.path.join( CHANNEL_ROOT_DIRECTORY, '.gitmodules' ),
                }

                self.run_general_command( CHANNEL_ROOT_DIRECTORY, settings, self.command )

            elif self.command == "backstroke":
                settings = \
                {
                    'section_name': "last_backstroke_session",
                    'git_file_path': os.path.join( CHANNEL_ROOT_DIRECTORY, 'Local', 'Backstroke.gitmodules' ),
                }

                self.run_general_command( CHANNEL_ROOT_DIRECTORY, settings, self.command )

            elif self.command == "create_upstreams" \
                    or self.command == "delete_remotes" \
                    or self.command == "fetch_origins" \
                    or self.command == "pull_origins":

                settings = \
                {
                    'section_name': "last_create_upstreams_session",
                    'git_file_path': os.path.join( CHANNEL_ROOT_DIRECTORY, '.gitmodules' ),
                }

                self.run_general_command( CHANNEL_ROOT_DIRECTORY, settings, self.command )

            else:
                log( 1, "RunBackstrokeThread::run, Invalid command: " + str( self.command ) )

        global g_is_already_running
        g_is_already_running = False

        log( 1, "Finished RunBackstrokeThread::run()" )

    def open_last_session_data(self):
        lastSection = configparser.ConfigParser( allow_no_value=True )
        default_sections = \
        [
            "last_backstroke_session",
            "last_find_forks_session",
            "last_create_upstreams_session",
        ]

        def create_sections():

            for section in default_sections:

                if not lastSection.has_section( section ):
                    lastSection.add_section( section )
                    lastSection.set( section, 'index', '0' )

                if not lastSection.has_option( section, 'index' ):
                    lastSection.set( section, 'index', '0' )

        if os.path.exists( CHANNEL_SESSION_FILE ):
            lastSection.read( CHANNEL_SESSION_FILE )
            create_sections()

        else:
            create_sections()

        return lastSection

    def get_section_option(self, section, option, configSettings):

        if configSettings.has_option( section, option ):
            return configSettings.get( section, option )

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

    def run_general_command(self, base_root_directory, settings, command):
        """
            @param function_command   a function pointer to be called on each `.gitmodules` section.
        """
        log( 1, "RunBackstrokeThread::run_general_command" )
        maximum_errors = MAXIMUM_REQUEST_ERRORS

        # https://pymotw.com/3/configparser/
        lastSection = self.open_last_session_data()
        start_index = lastSection.getint( settings['section_name'], 'index' )

        request_index        = 0
        successful_resquests = 0

        gitFilePath            = settings['git_file_path']
        generalSettingsConfigs = configparser.RawConfigParser()

        # https://stackoverflow.com/questions/45415684/how-to-stop-tabs-on-python-2-7-rawconfigparser-throwing-parsingerror/
        with open( gitFilePath ) as fakeFile:
            # https://stackoverflow.com/questions/22316333/how-can-i-resolve-typeerror-with-stringio-in-python-2-7
            fakefile = io.StringIO( fakeFile.read().replace( u"\t", u"" ) )

        log( 1, "RunBackstrokeThread::sections: " + gitFilePath )
        generalSettingsConfigs._read( fakefile, gitFilePath )

        index          = 0
        sections       = generalSettingsConfigs.sections()
        sections_count = len( sections )

        command_line_interface = cmd.Cli( None, False )

        # https://stackoverflow.com/questions/22068050/iterate-over-sections-in-a-config-file
        for section, pi in estimated_time_left.sequence_timer( sections, info_frequency=0 ):
            request_index += 1
            progress       = progress_info( pi )

            # Walk until the last processed index, skipping everything else
            if start_index > 0:
                start_index -= 1
                continue

            # # For quick testing
            # if request_index > 3:
            #     break

            log( 1, "{:s}, {:3d}({:d}) of {:d}... {:s}".format(
                    progress, request_index, successful_resquests, sections_count, section ) )

            if command == "find_forks":
                # https://docs.python.org/3/library/configparser.html#configparser.ConfigParser.get
                forkUrl  = self.get_section_option( section, "url", generalSettingsConfigs )
                forkPath = self.get_section_option( section, "path", generalSettingsConfigs )
                upstream = self.get_section_option( section, "upstream", generalSettingsConfigs )

                # log( 1, "forkPath: " + forkPath )
                # log( 1, "upstream: " + upstream )
                if len( upstream ) > 20:
                    successful_resquests += 1
                    forkUser, _           = parse_upstream( forkUrl )
                    user, repository      = parse_upstream( upstream )

                    # Find all forks, add them as remote and fetch them
                    run_command_line(
                        command_line_interface,
                        shlex.split( "python %s --user=%s --repo=%s" % ( FIND_FORKS_PATH, user, repository ) ),
                        os.path.join( base_root_directory, forkPath ),
                    )

                    # Clean duplicate branches
                    run_command_line(
                        command_line_interface,
                        shlex.split( "sh %s/remove_duplicate_branches.sh %s" % ( FIND_FORKS_PATH, forkUser ) ),
                        os.path.join( base_root_directory, forkPath ),
                    )

                else:
                    print( "\n\n\nError, invalid/missing upstream: " + str( upstream ) )

            elif command == "backstroke":
                # The GitHub API only allows about 30 requests per second for the backstroke call,
                # then we make it take a little longer so all the requests can be performed in a row.
                time.sleep(2)

                # https://docs.python.org/3/library/configparser.html#configparser.ConfigParser.get
                upstream   = self.get_section_option( section, "upstream", generalSettingsConfigs )
                backstroke = self.get_section_option( section, "backstroke", generalSettingsConfigs )

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
                            lastSection.set( settings['section_name'], 'index', str( request_index - 1 ) )

                        if maximum_errors < 1:
                            break

                else:
                    print( "\n\n\nMissing backstroke key for upstream: " + upstream )

            elif command == "create_upstreams" or command == "delete_remotes":
                forkPath = self.get_section_option( section, "path", generalSettingsConfigs )
                upstream = self.get_section_option( section, "upstream", generalSettingsConfigs )

                if len( upstream ) > 20:
                    successful_resquests += 1
                    user, repository     = parse_upstream( upstream )

                    remotes = command_line_interface.execute(
                        shlex.split( "git remote" ),
                        os.path.join( base_root_directory, forkPath ),
                        short_errors=True
                    )

                    if command == "create_upstreams":

                        if user not in remotes:

                            run_command_line(
                                command_line_interface,
                                shlex.split( "git remote add %s %s" % ( user, upstream ) ),
                                os.path.join( base_root_directory, forkPath )
                            )

                            run_command_line(
                                command_line_interface,
                                shlex.split( "git fetch %s" % ( user ) ),
                                os.path.join( base_root_directory, forkPath )
                            )

                    else:
                        remote_index = 0
                        remotes_list = remotes.split( "\n" )

                        # -2 because I am discarding myself and my upstream
                        remotes_count = len( remotes_list ) - 2

                        for remote, pi in estimated_time_left.sequence_timer( remotes_list, info_frequency=0 ):

                            if remote not in ( "origin", user ):
                                progress      = progress_info( pi )
                                remote_index += 1

                                log( 1, "Cleaning remote {:3d} of {:d} ({:s}): {:<20s} {:s}".format(
                                        remote_index, remotes_count, progress, remote, forkPath ) )

                                run_command_line(
                                    command_line_interface,
                                    shlex.split( "git remote rm %s" % ( remote ) ),
                                    os.path.join( base_root_directory, forkPath )
                                )

            elif command == "pull_origins":
                successful_resquests += 1
                forkPath = self.get_section_option( section, "path", generalSettingsConfigs )

                run_command_line(
                    command_line_interface,
                    shlex.split( "git pull --rebase" ),
                    os.path.join( base_root_directory, forkPath )
                )

                self.recursiveily_process_submodules( base_root_directory, command, settings, forkPath )

            elif command == "fetch_origins":
                successful_resquests += 1
                forkPath = self.get_section_option( section, "path", generalSettingsConfigs )

                run_command_line(
                    command_line_interface,
                    shlex.split( "git fetch origin" ),
                    os.path.join( base_root_directory, forkPath )
                )

                self.recursiveily_process_submodules( base_root_directory, command, settings, forkPath )

            else:
                log( 1, "RunBackstrokeThread::run_general_command, Invalid command: " + str( command ) )

        # Only save the session file when finishing the main thread
        if base_root_directory == CHANNEL_ROOT_DIRECTORY:
            self.save_session_data( maximum_errors, settings['section_name'], lastSection )

        return True

    def recursiveily_process_submodules(self, base_root_directory, command, settings, forkPath):
        base_root_directory    = os.path.join( base_root_directory, forkPath )
        nested_submodules_file = os.path.join( base_root_directory, ".gitmodules" )

        if os.path.exists( nested_submodules_file ):
            settings['git_file_path'] = nested_submodules_file
            self.run_general_command( base_root_directory, settings, command )


def run_command_line(command_line_interface, commad, initial_folder):
    output = command_line_interface.execute( commad, initial_folder, live_output=True, short_errors=True )

    if is_python_2:
        log.clean( 1, output )

    return output


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


if __name__ == "__main__":
    main()


