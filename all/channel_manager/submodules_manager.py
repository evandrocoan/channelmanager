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
import contextlib


# Relative imports in Python 3
# https://stackoverflow.com/questions/16981921/relative-imports-in-python-3
try:
    from . import settings as g_settings

    from .channel_utilities import get_main_directory
    from .channel_utilities import load_data_file
    from .channel_utilities import write_data_file
    from .channel_utilities import get_section_option
    from .channel_utilities import assert_path

except( ImportError, ValueError ):
    import settings as g_settings

    from channel_utilities import get_main_directory
    from channel_utilities import load_data_file
    from channel_utilities import write_data_file
    from channel_utilities import get_section_option
    from channel_utilities import assert_path


# Allow using this file on the website where the sublime
# module is unavailable
try:
    import sublime
    import sublime_plugin

    # https://stackoverflow.com/questions/14087598/python-3-importerror-no-module-named-configparser
    import configparser

    from debug_tools import getLogger
    from debug_tools.utilities import join_path
    from debug_tools.estimated_time_left import sequence_timer
    from debug_tools.estimated_time_left import progress_info

    # When there is an ImportError, means that Package Control is installed instead of PackagesManager.
    # Which means we cannot do nothing as this is only compatible with PackagesManager.
    try:
        from PackagesManager.package_control import cmd

    except( ImportError, ValueError ):
        pass

except( ImportError, ValueError ):
    sublime = None
    sublime_plugin = None

    # Import the debugger. It will fail when `debug_tools` is inside a `.sublime-package`,
    # however, this is only meant to be used on the Development version, `debug_tools` is
    # unpacked at the loose packages folder as a git submodule.
    assert_path( g_settings.PACKAGE_ROOT_DIRECTORY, 'six' )
    assert_path( g_settings.PACKAGE_ROOT_DIRECTORY, 'all' )
    assert_path( os.path.dirname( g_settings.PACKAGE_ROOT_DIRECTORY ), 'PackagesManager' )
    assert_path( os.path.dirname( g_settings.PACKAGE_ROOT_DIRECTORY ), 'debugtools', 'all' )

    from six.moves import configparser
    from package_control import cmd
    from debug_tools import getLogger
    from debug_tools.utilities import join_path
    from debug_tools.estimated_time_left import sequence_timer


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


if is_python_2:
    try:
        from githubpullrequests import PullRequester

    except( ImportError, ValueError ):
        assert_path( g_settings.PACKAGE_ROOT_DIRECTORY, '..', '..', 'githubpullrequests', 'source' )
        from githubpullrequests import PullRequester


# sys.tracebacklimit = 10; raise ValueError
def print_python_envinronment():
    index = 0;

    for file_path in sys.path:
        print(index, file_path);
        index += 1;


# print_python_envinronment()
CHANNEL_LOG_FILE     = os.path.join( g_settings.PACKAGE_ROOT_DIRECTORY, "all", "commands.log" )
CHANNEL_SESSION_FILE = os.path.join( g_settings.PACKAGE_ROOT_DIRECTORY, "all", "last_session.json" )
FIND_FORKS_PATH      = os.path.join( g_settings.PACKAGE_ROOT_DIRECTORY, "find_forks" )

# How many errors are acceptable when the GitHub API request fails
MAXIMUM_REQUEST_ERRORS = 1
g_is_already_running   = False
command_line_interface = cmd.Cli( None, False )


# Debugger settings: 0 - disabled, 127 - enabled
# log = getLogger( 127, __name__, CHANNEL_LOG_FILE, rotation=10, mode=2, stdout=True)
log = getLogger( 127, __name__ )

#log.setup( "Debug.txt" )
#log.clear()

# log( 1, "..." )
# log( 1, "..." )
# log( 1, "Debugging" )
# log( 1, "PACKAGE_ROOT_DIRECTORY: " + g_settings.PACKAGE_ROOT_DIRECTORY )


def main(command=None):
    log( 1, "Entering on main(1) " + str( command ) )
    global CHANNEL_ROOT_DIRECTORY

    maximum_repositories   = 0
    synced_repositories    = False
    argumentsNamespace     = None
    CHANNEL_ROOT_DIRECTORY = get_main_directory( g_settings.PACKAGE_ROOT_DIRECTORY )

    # https://stackoverflow.com/questions/6382804/how-to-use-getopt-optarg-in-python-how-to-shift
    if not command:
        print_command_line_arguments()
        argumentParser = argparse.ArgumentParser( description='Update Sublime Text Channel' )

        argumentParser.add_argument( "-m", "--merge-upstreams", action="store_true",
                help="Merges all registered repositories updates with their upstream. "
                "The upstrems URLs are in a separate file on: Local/Backstroke.gitmodules" )

        argumentParser.add_argument( "-mr", "--maximum-repositories", action="store", type=int,
                help="The maximum count of repositories/requests to process per file. "
                "Only valid when using `--merge-upstreams` option." )

        argumentParser.add_argument( "-s", "--synced-repositories", action="store_true",
                help="Reports which repositories not Synchronized with Pull Requests. "
                "Only valid when using `--merge-upstreams` option." )

        argumentParser.add_argument( "-f", "--find-forks", action="store_true",
                help="Find all repositories forks, fetch their branches and clean the duplicated branches. "
                "The upstream data in on the `.gitmodules` file on: Sublime Text `Data` folder" )

        argumentParser.add_argument( "-p", "--pull", action="store_true",
                help="Checkout on all submodules master branch and perform a git pull "
                "from the remote repositories" )

        argumentParser.add_argument( "-t", "--push-tags", action="store_true",
                help="Perform a git push for all submodules tags to their respective remote repository" )

        argumentParser.add_argument( "-u", "--create-upstreams", action="store_true",
                help="Find all repositories on the `.gitmodules` which has the key `upstream` and add"
                "it as a remote on the respective repository." )

        argumentParser.add_argument( "-d", "--delete-remotes", action="store_true",
                help="Find all repositories on the `.gitmodules` which has the key `upstream` and delete"
                "all its git remote repositories which are not the origin or the upstream user." )

        argumentParser.add_argument( "-c", "--cancel-operation", action="store_true",
                help="If there is some batch operation running, cancel it as soons as possible." )

        argumentParser.add_argument( "-pr", "--create-pullrequests", action="store_true",
                help="Call the command githubpullrequests for all registered git submodules. "
                "You need to create the file `Local/GITHUBPULLREQUESTS_TOKEN` "
                "or create the environment variable `GITHUBPULLREQUESTS_TOKEN` within a Github token "
                "with `public_repos` permission." )

        argumentParser.add_argument( "-o", "--pull-origins", action="store_true",
                help="Find all repositories on the `.gitmodules` and perform a git pull --rebase" )

        argumentParser.add_argument( "-fo", "--fetch-origins", action="store_true",
                help="Find all repositories on the `.gitmodules` and perform a git fetch origin" )

        argumentsNamespace = argumentParser.parse_args()

    # log( 1, argumentsNamespace )
    if argumentsNamespace and argumentsNamespace.maximum_repositories:
        maximum_repositories = argumentsNamespace.maximum_repositories

    if argumentsNamespace and argumentsNamespace.synced_repositories:
        synced_repositories = argumentsNamespace.synced_repositories

    if argumentsNamespace and argumentsNamespace.find_forks:
        if sublime:
            log( 1, "The find forks command is only available running by the command line, while" )
            log( 1, "using the Sublime Text Channel Development version." )

        else:
            RunBackstrokeThread("find_forks", maximum_repositories).start()

    elif command == "-t" or argumentsNamespace and argumentsNamespace.push_tags:
        RunGitForEachSubmodulesThread( "git push --tags" ).start()

    elif command == "-p" or argumentsNamespace and argumentsNamespace.pull:
        RunGitForEachSubmodulesThread( "git checkout master && "
                "git branch --set-upstream-to=origin/master master && git pull --rebase" ).start()

    elif command == "-o" or argumentsNamespace and argumentsNamespace.pull_origins:
        RunBackstrokeThread("pull_origins", maximum_repositories).start()

    elif command == "-fo" or argumentsNamespace and argumentsNamespace.fetch_origins:
        RunBackstrokeThread("fetch_origins", maximum_repositories).start()

    elif command == "-m" or argumentsNamespace and argumentsNamespace.merge_upstreams:
        RunBackstrokeThread("merge_upstreams", maximum_repositories).start()

    elif command == "-pr" or argumentsNamespace and argumentsNamespace.create_pullrequests:
        RunBackstrokeThread("create_pullrequests", maximum_repositories, synced_repositories).start()

    elif command == "-u" or argumentsNamespace and argumentsNamespace.create_upstreams:
        RunBackstrokeThread("create_upstreams", maximum_repositories).start()

    elif command == "-d" or argumentsNamespace and argumentsNamespace.delete_remotes:
        RunBackstrokeThread("delete_remotes", maximum_repositories).start()

    elif command == "cancel_operation" or argumentsNamespace and argumentsNamespace.cancel_operation:
        free_mutex_lock()

    elif not command:
        argumentParser.print_help()

    else:
        log( 1, "Invalid command: " + str( command ) )

    # unittest.main()


@contextlib.contextmanager
def lock_context_manager():
    """
        https://stackoverflow.com/questions/12594148/skipping-execution-of-with-block
        https://stackoverflow.com/questions/27071524/python-context-manager-not-cleaning-up
        https://stackoverflow.com/questions/10447818/python-context-manager-conditionally-executing-body
        https://stackoverflow.com/questions/34775099/why-does-contextmanager-throws-a-runtime-error-generator-didnt-stop-after-thro
    """
    try:
        yield is_allowed_to_run()

    finally:
        free_mutex_lock()


def free_mutex_lock():
    global g_is_already_running
    g_is_already_running = False


def is_allowed_to_run():
    global g_is_already_running

    if g_is_already_running:
        log( 1, "You are already running a command. Wait until it finishes or restart Sublime Text" )
        return False

    g_is_already_running = True
    return True


# My forks upstreams
#
class RunBackstrokeThread(threading.Thread):

    def __init__(self, command, maximum_repositories=0, synced_repositories=False):
        threading.Thread.__init__(self)
        self.command = command
        self.maximum_repositories = maximum_repositories
        self.synced_repositories = synced_repositories

    def run(self):
        log( 1, "RunBackstrokeThread::run" )

        with lock_context_manager() as is_allowed:
            if not is_allowed: return

            if self.command == "find_forks":
                git_file_path = os.path.join( CHANNEL_ROOT_DIRECTORY, '.gitmodules' )
                self.run_general_command( CHANNEL_ROOT_DIRECTORY, git_file_path, self.command )

            elif self.command in (
                      "create_upstreams",
                      "delete_remotes",
                      "fetch_origins",
                      "pull_origins",
                      "merge_upstreams",
                    ):
                gitmodules_directory = get_channel_root_from_project()
                log( 1, "gitmodules_directory: %s", gitmodules_directory )

                git_file_path = os.path.join( gitmodules_directory, '.gitmodules' )
                self.run_general_command( CHANNEL_ROOT_DIRECTORY, git_file_path, self.command )

            elif self.command == "create_pullrequests":
                self.run_githubpullrequests()

            else:
                log( 1, "RunBackstrokeThread::run, Invalid command: " + str( self.command ) )

        free_mutex_lock()
        log.newline()
        log( 1, "Finished RunBackstrokeThread::run()" )

    def run_githubpullrequests(self):
        token_file = join_path( CHANNEL_ROOT_DIRECTORY, 'Local', 'GITHUBPULLREQUESTS_TOKEN' )
        gitmodules_file = join_path( CHANNEL_ROOT_DIRECTORY, '.gitmodules' )
        backstroke_file = join_path( CHANNEL_ROOT_DIRECTORY, 'Local', 'Backstroke.gitmodules' )

        if is_python_2:

            if os.path.exists( token_file ):
                github_token = token_file

            else:
                github_token = os.environ.get( 'GITHUBPULLREQUESTS_TOKEN', "" )

            pull_requester = PullRequester( github_token, self.maximum_repositories, self.synced_repositories )
            pull_requester.parse_gitmodules( [gitmodules_file, backstroke_file] )
            pull_requester.publish_report()

        else:
            sync = "-s" if self.synced_repositories else ""

            if os.path.exists( token_file ):
                run( "githubpullrequests -f '%s' -f '%s' -t '%s' %s" % (
                        gitmodules_file, backstroke_file, token_file, sync ), CHANNEL_ROOT_DIRECTORY )

            else:
                run( "githubpullrequests -f '%s -f '%s' %s" % (
                        gitmodules_file, backstroke_file, sync ), CHANNEL_ROOT_DIRECTORY )

    def run_general_command(self, base_root_directory, git_file_path, command):
        """
            @param function_command   a function pointer to be called on each `.gitmodules` section.
        """
        log( 1, "RunBackstrokeThread::run_general_command" )
        maximum_errors = MAXIMUM_REQUEST_ERRORS

        lastSection = load_data_file( CHANNEL_SESSION_FILE )
        start_index = lastSection.get( command, 0 )

        request_index = 0
        successful_resquests = 0

        # https://pymotw.com/3/configparser/
        generalSettingsConfigs = configparser.RawConfigParser()

        # https://stackoverflow.com/questions/45415684/how-to-stop-tabs-on-python-2-7-rawconfigparser-throwing-parsingerror/
        with open( git_file_path ) as fakeFile:
            # https://stackoverflow.com/questions/22316333/how-can-i-resolve-typeerror-with-stringio-in-python-2-7
            fakefile = io.StringIO( fakeFile.read().replace( u"\t", u"" ) )

        log( 1, "RunBackstrokeThread::sections: " + git_file_path )
        generalSettingsConfigs._read( fakefile, git_file_path )

        sections       = generalSettingsConfigs.sections()
        sections_count = len( sections )

        # https://stackoverflow.com/questions/22068050/iterate-over-sections-in-a-config-file
        for section, pi in sequence_timer( sections, info_frequency=0 ):
            request_index += 1
            progress       = progress_info( pi )

            if not g_is_already_running:
                raise ImportError( "Stopping the process as this Python module was reloaded!" )

            # Walk until the last processed index, skipping everything else
            if start_index > 0:
                start_index -= 1
                continue

            # For quick testing
            if self.maximum_repositories and request_index > self.maximum_repositories:
                break

            self.save_session_file(base_root_directory, lastSection, command, request_index)

            log( 1, "{:s}, {:3d}({:d}) of {:d}... {:s}".format(
                    progress, request_index, successful_resquests, sections_count, section ) )

            if command == "find_forks":
                # https://docs.python.org/3/library/configparser.html#configparser.ConfigParser.get
                forkUrl  = get_section_option( section, "url", generalSettingsConfigs )
                forkpath = get_section_option( section, "path", generalSettingsConfigs )
                upstream = get_section_option( section, "upstream", generalSettingsConfigs )

                # log( 1, "forkpath: " + forkpath )
                # log( 1, "upstream: " + upstream )
                if len( upstream ) > 20:
                    successful_resquests += 1
                    forkUser, _           = parse_upstream( forkUrl )
                    user, repository      = parse_upstream( upstream )

                    # Find all forks, add them as remote and fetch them
                    run( "python %s --user=%s --repo=%s" % ( FIND_FORKS_PATH, user, repository ),
                        base_root_directory, forkpath )

                    # Clean duplicate branches
                    run( "sh %s/remove_duplicate_branches.sh %s" % ( FIND_FORKS_PATH, forkUser ),
                        base_root_directory, forkpath )

                else:
                    log.newline( count=3 )
                    log( 1, "Error, invalid/missing upstream: " + str( upstream ) )

            elif command == "merge_upstreams":
                # The GitHub API only allows about 30 requests per second for the merge_upstreams call,
                # then we make it take a little longer so all the requests can be performed in a row.
                time.sleep(2)

                # https://docs.python.org/3/library/configparser.html#configparser.ConfigParser.get
                forkpath = get_section_option( section, "path", generalSettingsConfigs )
                downstream = get_section_option( section, "url", generalSettingsConfigs )

                upstream = get_section_option( section, "upstream", generalSettingsConfigs )
                branches = get_section_option( section, "branches", generalSettingsConfigs )
                local_branch, upstream_branch = parser_branches( branches )

                if not upstream:
                    log( 1, "Skipping %s because there is not upstream defined...", section )
                    continue

                log( 1, branches )
                log( 1, downstream )
                log( 1, upstream )
                if not local_branch or not upstream_branch:
                    maximum_errors -= 1

                    log.newline( count=3 )
                    log( 1, "ERROR! Invalid branches `%s`", branches )

                    if maximum_errors < 1:
                        break

                    continue

                successful_resquests += 1
                run( "git checkout %s" % local_branch, base_root_directory, forkpath )
                run( "git fetch", base_root_directory, forkpath )
                run( "git pull --rebase", base_root_directory, forkpath )

                upstream_user, upstream_repository = parse_upstream( upstream )
                remotes = command_line_interface.execute(
                    shlex.split( "git remote" ),
                    os.path.join( base_root_directory, forkpath ),
                    short_errors=True
                )

                if upstream_user not in remotes:
                    run( "git remote add %s %s" % ( upstream_user, upstream ), base_root_directory, forkpath )

                run( "git fetch %s" % ( upstream_user ), base_root_directory, forkpath )
                run( "git merge %s/%s" % ( upstream_user, upstream_branch ), base_root_directory, forkpath )

            elif command == "create_upstreams" or command == "delete_remotes":
                forkpath = get_section_option( section, "path", generalSettingsConfigs )
                upstream = get_section_option( section, "upstream", generalSettingsConfigs )

                if len( upstream ) > 20:
                    successful_resquests += 1
                    user, repository     = parse_upstream( upstream )

                    remotes = command_line_interface.execute(
                        shlex.split( "git remote" ),
                        os.path.join( base_root_directory, forkpath ),
                        short_errors=True
                    )

                    if command == "create_upstreams":

                        if user not in remotes:
                            run( "git remote add %s %s" % ( user, upstream ), base_root_directory, forkpath )
                            run( "git fetch %s" % ( user ), base_root_directory, forkpath )

                    else:
                        remote_index = 0
                        remotes_list = remotes.split( "\n" )

                        # -2 because I am discarding myself and my upstream
                        remotes_count = len( remotes_list ) - 2

                        for remote, pi in sequence_timer( remotes_list, info_frequency=0 ):

                            if remote not in ( "origin", user ):
                                progress      = progress_info( pi )
                                remote_index += 1

                                log( 1, "Cleaning remote {:3d} of {:d} ({:s}): {:<20s} {:s}".format(
                                        remote_index, remotes_count, progress, remote, forkpath ) )

                                run( "git remote rm %s" % ( remote ), base_root_directory, forkpath )

            elif command == "pull_origins":
                successful_resquests += 1
                forkpath = get_section_option( section, "path", generalSettingsConfigs )

                run( "git pull --rebase", base_root_directory, forkpath )
                self.recursiveily_process_submodules( base_root_directory, command, forkpath )

            elif command == "fetch_origins":
                successful_resquests += 1
                forkpath = get_section_option( section, "path", generalSettingsConfigs )

                run( "git fetch origin", base_root_directory, forkpath )
                self.recursiveily_process_submodules( base_root_directory, command, forkpath )

            else:
                log( 1, "RunBackstrokeThread::run_general_command, Invalid command: " + str( command ) )

        # Only save the session file when finishing the main thread
        if base_root_directory == CHANNEL_ROOT_DIRECTORY:
            log.newline( count=2 )

            if maximum_errors == MAXIMUM_REQUEST_ERRORS:
                self.save_session_file(base_root_directory, lastSection, command, 1)
                log( 1, "Congratulations! It was a successful execution." )

            else:
                log( 1, "Attention! There were errors on execution, please review its output." )

        return True

    @staticmethod
    def save_session_file(base_root_directory, lastSection, command, request_index):
        """ Only saves the session file when working on the main project submodules
            instead overriding it with the nested submodules contents. """

        if base_root_directory == CHANNEL_ROOT_DIRECTORY:
            lastSection[command] = request_index - 1
            write_data_file( CHANNEL_SESSION_FILE, lastSection )

    def recursiveily_process_submodules(self, base_root_directory, command, forkpath):
        base_root_directory    = os.path.join( base_root_directory, forkpath )
        nested_submodules_file = os.path.join( base_root_directory, ".gitmodules" )

        if os.path.exists( nested_submodules_file ):
            self.run_general_command( base_root_directory, nested_submodules_file, command )


def run(command, *args):
    command = shlex.split( command )
    output = command_line_interface.execute( command, os.path.join( *args ), live_output=True, short_errors=True )

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


def parser_branches( branches ):
    matches = re.search( r'(.+)\-\>(.+),', branches )

    if matches:
        return matches.group(2), matches.group(1)

    return "", ""


def print_command_line_arguments():

    try:
        log( 1, "( print_command_line_arguments ) len(sys.argv): " + str( len( sys.argv ) ) )

        for arg in sys.argv:
            log( 1, "( print_command_line_arguments ) arg: " + str( arg ) )

    except AttributeError:
        pass


def get_channel_root_from_project():

    if sublime:
        active_window = sublime.active_window()

        def is_valid_folder(folder):

            for file_name in ['.gitmodules', '.gitignore']:
                if not os.path.exists( os.path.join( folder, file_name ) ):
                    break

            # This is only run if all files were found
            else:
                return True

            return False

        for folder in active_window.folders():

            if is_valid_folder( folder ):

                for root, dirs, files in os.walk( folder ):

                    for file in files:

                        if file.endswith( ".sublime-project" ):
                            return os.path.abspath( folder )

    return CHANNEL_ROOT_DIRECTORY


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

        with lock_context_manager() as is_allowed:
            if not is_allowed: return
            self.update_submodules( self.git_command )

        free_mutex_lock()

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
        command += "\"date && %s && printf '\\n' || printf '%s\\n\\n\\n\\n\\n'\"" % ( git_command, error_string )

        log( 1, "Command: %s", [command] )

        if sublime:
            run(command, CHANNEL_ROOT_DIRECTORY )

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

