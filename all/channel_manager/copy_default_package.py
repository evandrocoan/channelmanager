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
# Channel Manager Copier, Unpack the Default.sublime-package and configure it
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

import sublime
import configparser

import os
import re
import sys
import shlex

import zipfile
import threading
import contextlib

from . import settings as g_settings
from .channel_manager import get_git_latest_tag

from .channel_utilities import load_data_file
from .channel_utilities import write_data_file
from .channel_utilities import is_sublime_text_upgraded

try:
    from PackagesManager.package_control import cmd
    command_line_interface = cmd.Cli( None, True )


except ImportError:
    pass

from debug_tools import getLogger

# Debugger settings: 0 - disabled, 127 - enabled
log = getLogger( 127, __name__ )

# log( 2, "..." )
# log( 2, "..." )
# log( 2, "Debugging" )
# log( 2, "PACKAGE_ROOT_DIRECTORY: " + g_settings.PACKAGE_ROOT_DIRECTORY )
packages_file_name = "Default.sublime-package"


def main(is_forced=False):

    # We can only run this when we are using the development version of the channel. And when there
    # is a `.git` folder, we are running the `Development Version` of the channel.
    main_git_path = os.path.join( g_settings.PACKAGE_ROOT_DIRECTORY, ".git" )

    # Not attempt to run when we are running from inside a `.sublime-package` because this is only
    # available for the `Development Version` as there is not need to unpack the `Default Package`
    # on the `Stable Version` of the channel.
    if is_forced or os.path.exists( main_git_path ) and is_sublime_text_upgraded( "copy_default_package" ):
        log( 1, "Entering on CopyFilesThread(1)" )
        CopyFilesThread().start()


class CopyFilesThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        log( 2, "Entering on run(1)" )

        package_path = os.path.join( os.path.dirname( sublime.executable_path() ), "Packages", packages_file_name )
        output_directory = os.path.join( os.path.dirname( sublime.packages_path() ), packages_file_name )

        log( 2, "run, package_path:  " + package_path )
        log( 2, "run, output_directory: " + output_directory )

        extract_package( package_path, output_directory )
        create_git_ignore_file( output_directory )
        create_version_setting_file( output_directory )


def run_command(command, output_directory):
    command = shlex.split( command )
    output = command_line_interface.execute( command, output_directory, short_errors=True )
    return output


def create_version_setting_file(output_directory):
    latest_git_tag = get_git_latest_tag( output_directory, command_line_interface )

    # https://stackoverflow.com/questions/10345182/log-first-10-in-git
    output = run_command( "git log -10 --pretty=oneline", output_directory )

    # log( 1, 'Fetched the latest git history: \n%s', output )
    version_found = 0

    latest_git_tag = int( latest_git_tag )
    version_regex = re.compile( r'(?:version|build)\s*(\d\d\d\d)', re.IGNORECASE )

    for line in output.split('\n'):
        version_match = version_regex.search(line)

        if version_match:
            version_match = int( version_match.group(1) )

            if version_match > latest_git_tag:
                version_found = version_match
                break

    log( 1, 'version_found: %s', version_found )
    log( 1, 'latest_git_tag: %s', latest_git_tag )

    if version_found:
        output = run_command( "git tag %s" % ( version_found ), output_directory )
        cloned_package_path = os.path.join( sublime.packages_path(), 'Default' )
        log( 1, 'Created git tag `%s`:\n%s', version_found, output )

        local_packages_fork = "%s/../../%s" % ( cloned_package_path, packages_file_name )
        local_packages_fork_name = "local_packages_fork"

        remotes = run_command( "git remote", cloned_package_path )

        if local_packages_fork_name in remotes:
            log( 1, "Skipping `%s` remote creation as it already exists: \n%s", local_packages_fork_name, remotes )

        else:
            output = run_command( "git remote add %s %s" % ( local_packages_fork_name, local_packages_fork ), cloned_package_path )
            log( 1, 'Created local remote on: \n%s\n%s', os.path.abspath( local_packages_fork ), output )

        output = run_command( "git fetch %s --tags --force" % ( local_packages_fork_name ), cloned_package_path )
        log( 1, 'Fetched local remote: \n%s', output )

        version_found = str( version_found )
        version_settings_path = os.path.join( output_directory, 'settings.json' )
        version_settings_file = load_data_file( version_settings_path )

        if version_found not in version_settings_file['tags']:
            version_settings_file['tags'].append( str( version_found ) )
            write_data_file(version_settings_path, version_settings_file)

        else:
            log( 1, 'Warning: The version `%s` was already found on: %s', version_found, version_settings_path )

    else:
        log( 1, 'No new Sublime Text version was found.' )


def create_git_ignore_file(output_directory):

    gitignore_file = os.path.join( output_directory, ".gitignore" )
    lines_to_write = \
    [
        "",
        "# Do not edit this file manually, otherwise your changes will be lost on the next update!",
        "# To change this file contents, edit the package `%s/%s`" % ( g_settings.CURRENT_PACKAGE_NAME, os.path.basename( __file__ ) ),
        "",
        "",
        "*.png",
    ]

    lines_to_write.append("\n")
    log( 1, "Writing to gitignore_file: " + str( gitignore_file ) )

    with open( gitignore_file, "w" ) as text_file:
        text_file.write( "\n".join( lines_to_write ) )


def extract_package(package_path, destine_folder):
    """
        If the files already exists on the destine, they will be overridden.
    """

    try:
        package_file = zipfile.ZipFile( package_path )

    except zipfile.BadZipfile as error:
        log( 1, " The package file '%s is invalid! Error: %s" % ( package_path, error ) )

    with contextlib.closing( package_file ):

        try:
            os.mkdir( destine_folder )

        except OSError as error:

            if os.path.isdir( destine_folder ):
                pass

            else:
                log( 1, "The directory '%s' could not be created! Error: %s" % ( destine_folder, error ) )
                return

        try:
            package_file.extractall( destine_folder )

        except Exception as error:
            log( 1, "Extracting '%s' failed. Error: %s" % ( package_path, error ) )
            return

        log( 1, "The file '%s' was successfully extracted." % package_path )


if __name__ == "__main__":
    main()


