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
# Channel Manager Installer, install channel packages
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
import sublime_plugin

import os
import sys
import time
import shutil

import io
import json
import shlex
import threading

import configparser
from collections import OrderedDict


from .settings import CURRENT_DIRECTORY
from .settings import CURRENT_PACKAGE_NAME

g_is_already_running = False

from .channel_utilities import get_installed_packages
from .channel_utilities import unique_list_join
from .channel_utilities import unique_list_append
from .channel_utilities import write_data_file
from .channel_utilities import get_dictionary_key
from .channel_utilities import string_convert_list
from .channel_utilities import add_item_if_not_exists
from .channel_utilities import load_data_file
from .channel_utilities import remove_if_exists
from .channel_utilities import remove_item_if_exists
from .channel_utilities import convert_to_unix_path
from .channel_utilities import _delete_read_only_file
from .channel_utilities import wrap_text
from .channel_utilities import load_repository_file


# When there is an ImportError, means that Package Control is installed instead of PackagesManager,
# or vice-versa. Which means we cannot do nothing as this is only compatible with PackagesManager.
try:
    from package_control import cmd

    from package_control.package_manager import PackageManager
    from package_control.package_disabler import PackageDisabler

    from package_control.thread_progress import ThreadProgress
    from package_control.commands.satisfy_dependencies_command import SatisfyDependenciesThread
    from package_control.commands.advanced_install_package_command import AdvancedInstallPackageThread

except ImportError:
    pass


# How many packages to ignore and unignore in batch to fix the ignored packages bug error
g_is_installation_complete     = True
PACKAGES_COUNT_TO_IGNORE_AHEAD = 8


from python_debug_tools import Debugger
from estimated_time_left import sequence_timer
from estimated_time_left import progress_info
from estimated_time_left import CurrentUpdateProgress

# Debugger settings: 0 - disabled, 127 - enabled
log = Debugger( 127, os.path.basename( __file__ ) )

# log( 2, "..." )
# log( 2, "..." )
# log( 2, "Debugging" )
# log( 2, "CURRENT_DIRECTORY_:     " + CURRENT_DIRECTORY )


def main(channel_settings):
    """
        Before calling this installer, the `Package Control` user settings file, must have the
        Channel file set before the default channel key `channels`.

        Also the current `Package Control` cache must be cleaned, ensuring it is downloading and
        using the Channel repositories/channel list.
    """
    log( 2, "Entering on %s main(0)" % CURRENT_PACKAGE_NAME )

    installer_thread = StartInstallChannelThread(channel_settings)
    installer_thread.start()


def unpack_settings(channel_settings):
    global USER_SETTINGS_FILE
    global DEFAULT_PACKAGES_FILES
    global TEMPORARY_FOLDER_TO_USE

    global CHANNEL_ROOT_URL
    global CHANNEL_PACKAGE_NAME

    global CHANNEL_ROOT_DIRECTORY
    global IS_DEVELOPMENT_INSTALL
    global CHANNEL_INSTALLATION_SETTINGS
    global USER_FOLDER_PATH

    global CHANNEL_REPOSITORY_FILE
    global FORBIDDEN_PACKAGES
    global PACKAGES_TO_INSTALL_FIRST
    global PACKAGES_TO_INSTALL_LAST

    global PACKAGES_TO_NOT_INSTALL_STABLE
    global PACKAGES_TO_IGNORE_ON_DEVELOPMENT
    global PACKAGES_TO_NOT_INSTALL_DEVELOPMENT

    IS_DEVELOPMENT_INSTALL        = True if channel_settings['INSTALLATION_TYPE'] == "development" else False
    CHANNEL_INSTALLATION_SETTINGS = channel_settings['CHANNEL_INSTALLATION_SETTINGS']

    CHANNEL_ROOT_URL      = channel_settings['CHANNEL_ROOT_URL']
    CHANNEL_PACKAGE_NAME  = channel_settings['CHANNEL_PACKAGE_NAME']

    USER_SETTINGS_FILE      = channel_settings['USER_SETTINGS_FILE']
    DEFAULT_PACKAGES_FILES  = channel_settings['DEFAULT_PACKAGES_FILES']
    TEMPORARY_FOLDER_TO_USE = channel_settings['TEMPORARY_FOLDER_TO_USE']
    CHANNEL_REPOSITORY_FILE = channel_settings['CHANNEL_REPOSITORY_FILE']

    CHANNEL_ROOT_DIRECTORY  = channel_settings['CHANNEL_ROOT_DIRECTORY']
    USER_FOLDER_PATH        = channel_settings['USER_FOLDER_PATH']

    PACKAGES_TO_NOT_INSTALL_STABLE      = channel_settings['PACKAGES_TO_NOT_INSTALL_STABLE']
    PACKAGES_TO_NOT_INSTALL_DEVELOPMENT = channel_settings['PACKAGES_TO_NOT_INSTALL_DEVELOPMENT']
    PACKAGES_TO_IGNORE_ON_DEVELOPMENT   = channel_settings['PACKAGES_TO_IGNORE_ON_DEVELOPMENT']

    FORBIDDEN_PACKAGES        = channel_settings['FORBIDDEN_PACKAGES']
    PACKAGES_TO_INSTALL_FIRST = channel_settings['PACKAGES_TO_INSTALL_FIRST']
    PACKAGES_TO_INSTALL_LAST  = channel_settings['PACKAGES_TO_INSTALL_LAST']


class StartInstallChannelThread(threading.Thread):

    def __init__(self, channel_settings):
        threading.Thread.__init__(self)
        self.channel_settings = channel_settings

    def run(self):
        """
            Python thread exit code
            https://stackoverflow.com/questions/986616/python-thread-exit-code
        """

        if is_allowed_to_run():
            global g_failed_repositories
            global g_is_installation_complete
            global _uningored_packages_to_flush

            g_failed_repositories        = []
            g_is_installation_complete   = False
            _uningored_packages_to_flush = []

            unpack_settings( self.channel_settings )

            installer_thread  = InstallChannelFilesThread()
            installation_type = self.channel_settings['INSTALLATION_TYPE']

            global set_progress
            installer_thread.start()

            set_progress = CurrentUpdateProgress( 'Installing the %s packages...' % installation_type )
            ThreadProgress( installer_thread, set_progress, 'The %s was successfully installed.' % installation_type )

            installer_thread.join()
            save_default_settings(1)

            # Wait PackagesManager to load the found dependencies, before announcing it to the user
            sublime.set_timeout_async( check_installed_packages, 2000 )

        global g_is_already_running
        g_is_already_running = False


def print_failed_repositories():
    sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )

    if len( g_failed_repositories ) > 0:
        log.insert_empty_line( 1 )
        log.insert_empty_line( 1 )
        log( 1, "The following repositories failed their commands..." )

    for package_name in g_failed_repositories:
        log( 1, "Package: %s" % ( package_name ) )


def is_allowed_to_run():
    global g_is_already_running

    if g_is_already_running:
        print( "You are already running a command. Wait until it finishes or restart Sublime Text" )
        return False

    g_is_already_running = True
    return True


class InstallChannelFilesThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        log( 2, "Entering on run(1)" )
        load_installation_settings_file()

        command_line_interface = cmd.Cli( None, True )
        git_executable_path    = command_line_interface.find_binary( "git.exe" if os.name == 'nt' else "git" )

        log( 2, "run, git_executable_path: " + str( git_executable_path ) )

        install_modules( command_line_interface, git_executable_path)
        uninstall_package_control()


def load_installation_settings_file():
    global g_package_control_name
    global g_packagesmanager_name

    g_package_control_name = "Package Control.sublime-settings"
    g_packagesmanager_name = "PackagesManager.sublime-settings"

    global g_userSettings
    global g_channelSettings
    global g_default_ignored_packages

    g_userSettings    = sublime.load_settings( USER_SETTINGS_FILE )
    g_channelSettings = load_data_file( CHANNEL_INSTALLATION_SETTINGS )

    # `g_default_ignored_packages` contains the original user's ignored packages.
    g_default_ignored_packages = g_userSettings.get( 'ignored_packages', [] )

    global g_packages_to_uninstall
    global g_files_to_uninstall
    global g_folders_to_uninstall
    global g_packages_to_unignore
    global g_next_packages_to_ignore
    global g_packages_not_installed

    g_packages_to_uninstall   = get_dictionary_key( g_channelSettings, 'packages_to_uninstall', [] )
    g_packages_to_unignore    = get_dictionary_key( g_channelSettings, 'packages_to_unignore', [] )
    g_files_to_uninstall      = get_dictionary_key( g_channelSettings, 'files_to_uninstall', [] )
    g_folders_to_uninstall    = get_dictionary_key( g_channelSettings, 'folders_to_uninstall', [] )
    g_next_packages_to_ignore = get_dictionary_key( g_channelSettings, 'next_packages_to_ignore', [] )
    g_packages_not_installed  = get_dictionary_key( g_channelSettings, 'packages_not_installed', [] )

    unignore_installed_packages()

    log( 2, "load_installation_settings_file, PACKAGES_TO_IGNORE_ON_DEVELOPMENT: " + str( PACKAGES_TO_IGNORE_ON_DEVELOPMENT ) )
    log( 2, "load_installation_settings_file, g_default_ignored_packages:        " + str( g_default_ignored_packages ) )


def install_modules(command_line_interface, git_executable_path):
    log( 2, "install_modules_, git_executable_path: " + str( git_executable_path ) )

    if IS_DEVELOPMENT_INSTALL:
        packages_to_install = download_not_packages_submodules( command_line_interface, git_executable_path )
        log( 2, "install_modules, packages_to_install: " + str( packages_to_install ) )

        install_development_packages( packages_to_install, git_executable_path, command_line_interface )
        satisfy_dependencies()

    else:
        packages_to_install = get_stable_packages()
        log( 2, "install_modules, packages_to_install: " + str( packages_to_install ) )

        install_stable_packages( packages_to_install )
        accumulative_unignore_user_packages( flush_everything=True )


def install_stable_packages(packages_to_install):
    """
        python multithreading wait till all threads finished
        https://stackoverflow.com/questions/11968689/python-multithreading-wait-till-all-threads-finished

        There is a bug with the AdvancedInstallPackageThread thread which trigger several errors of:

        "It appears a package is trying to ignore itself, causing a loop.
        Please resolve by removing the offending ignored_packages setting."

        When trying to install several package at once, then here I am installing them one by one.
    """
    log( 2, "install_stable_packages, PACKAGES_TO_NOT_INSTALL_STABLE: " + str( PACKAGES_TO_NOT_INSTALL_STABLE ) )
    set_default_settings( packages_to_install )

    # Package Control: Advanced Install Package
    # https://github.com/wbond/package_control/issues/1191
    # thread = AdvancedInstallPackageThread( packages_to_install )
    # thread.start()
    # thread.join()

    package_manager  = PackageManager()
    package_disabler = PackageDisabler()

    current_index      = 0
    git_packages_count = len( packages_to_install )

    for package_name, pi in sequence_timer( packages_to_install, info_frequency=0 ):
        current_index += 1
        progress = progress_info( pi, set_progress )

        # # For quick testing
        # if current_index > 3:
        #     break

        log.insert_empty_line( 1 )
        log.insert_empty_line( 1 )

        log( 1, "%s Installing %d of %d: %s" % ( progress, current_index, git_packages_count, str( package_name ) ) )
        ignore_next_packages( package_disabler, package_name, packages_to_install )

        if package_manager.install_package( package_name, False ) is False:
            g_failed_repositories.append( package_name )

        add_package_to_installation_list( package_name )
        accumulative_unignore_user_packages( package_name )


def ignore_next_packages(package_disabler, package_name, packages_list):
    """
        There is a bug with the uninstalling several packages, which trigger several errors of:

        "It appears a package is trying to ignore itself, causing a loop.
        Please resolve by removing the offending ignored_packages setting."

        When trying to uninstall several package at once, then here I am ignoring them all at once.

        Package Control: Advanced Install Package
        https://github.com/wbond/package_control/issues/1191

        This fixes it by ignoring several next packages, then later unignoring them after uninstalled.
    """
    if len( _uningored_packages_to_flush ) < 1:
        global g_next_packages_to_ignore

        last_ignored_packges      = packages_list.index( package_name )
        g_next_packages_to_ignore = packages_list[ last_ignored_packges : last_ignored_packges + PACKAGES_COUNT_TO_IGNORE_AHEAD + 1 ]

        log( 1, "Adding %d packages to be uninstalled to the `ignored_packages` setting list." % len( g_next_packages_to_ignore ) )
        log( 1, "g_next_packages_to_ignore: " + str( g_next_packages_to_ignore ) )

        # We never can ignore the Default package, otherwise several errors/anomalies show up
        if "Default" in g_next_packages_to_ignore:
            g_next_packages_to_ignore.remove( "Default" )

        # Add them to the in_process list
        package_disabler.disable_packages( g_next_packages_to_ignore, "remove" )
        unique_list_append( g_default_ignored_packages, g_next_packages_to_ignore )

        # Let the package be unloaded by Sublime Text while ensuring anyone is putting them back in
        add_packages_to_ignored_list( g_next_packages_to_ignore )


def accumulative_unignore_user_packages(package_name="", flush_everything=False):
    """
        There is a bug with the uninstalling several packages, which trigger several errors of:

        "It appears a package is trying to ignore itself, causing a loop.
        Please resolve by removing the offending ignored_packages setting."

        When trying to uninstall several package at once, then here I am unignoring them all at once.

        Package Control: Advanced Install Package
        https://github.com/wbond/package_control/issues/1191

        @param flush_everything     set all remaining packages as unignored
    """

    if flush_everything:
        unignore_some_packages( _uningored_packages_to_flush )

    else:
        log( 1, "Adding package to unignore list: %s" % str( package_name ) )
        _uningored_packages_to_flush.append( package_name )

        if len( _uningored_packages_to_flush ) > PACKAGES_COUNT_TO_IGNORE_AHEAD:
            unignore_some_packages( _uningored_packages_to_flush )
            del _uningored_packages_to_flush[:]


def unignore_some_packages(packages_list):
    """
        Flush just a few items each time
    """

    for package_name in packages_list:

        if package_name in g_default_ignored_packages:
            log( 1, "Unignoring the package: %s" % package_name )
            g_default_ignored_packages.remove( package_name )

    g_userSettings.set( "ignored_packages", g_default_ignored_packages )
    sublime.save_settings( USER_SETTINGS_FILE )


def get_stable_packages():
    """
        python ConfigParser: read configuration from string
        https://stackoverflow.com/questions/27744058/python-configparser-read-configuration-from-string
    """
    index    = 0
    packages = []

    installed_packages = get_installed_packages( exclusion_list=[CHANNEL_PACKAGE_NAME] )
    log( 2, "get_stable_packages, installed_packages: " + str( installed_packages ) )

    # Do not try to install this own package and the Package Control, as they are currently running
    currently_running = [ "Package Control", CURRENT_PACKAGE_NAME, CHANNEL_PACKAGE_NAME ]

    packages_tonot_install = unique_list_join( PACKAGES_TO_NOT_INSTALL_STABLE, installed_packages, PACKAGES_TO_IGNORE_ON_DEVELOPMENT, currently_running )

    repositories_loaded = load_repository_file( CHANNEL_REPOSITORY_FILE, False )
    log( 2, "get_stable_packages, packages_tonot_install: " + str( packages_tonot_install ) )

    for package_name in repositories_loaded:
        # # For quick testing
        # index += 1
        # if index > 7:
        #     break

        if package_name not in packages_tonot_install \
                and not is_dependency( package_name, repositories_loaded ):

            packages.append( package_name )

        if package_name in installed_packages:
            g_packages_not_installed.append( package_name )

    # return \
    # [
    #     ('Active View Jump Back', False),
    #     ('amxmodx', False),
    #     ('Amxx Pawn', False),
    #     ('Clear Cursors Carets', False),
    #     ('Indent and braces', False),
    #     ('Invert Selection', False),
    #     ('PackagesManager', False),
    #     ('Toggle Words', False),
    #     # ('BBCode', False),
    #     ('DocBlockr', False),
    #     ('Gist', False),
    #     ('FileManager', False),
    #     ('FuzzyFileNav', False),
    #     ('ExportHtml', False),
    #     ('ExtendedTabSwitcher', False),
    #     ('BufferScroll', False),
    #     ('ChannelRepositoryTools', False),
    #     ('Better CoffeeScript', False),
    # ]

    return packages


def clone_sublime_text_channel(command_line_interface, git_executable_path):
    """
        Clone the main repository as `https://github.com/evandrocoan/SublimeTextStudio` and install
        it on the Sublime Text Data folder.
    """
    main_git_folder = os.path.join( CHANNEL_ROOT_DIRECTORY, ".git" )

    if os.path.exists( main_git_folder ):
        log.insert_empty_line( 1 )
        log.insert_empty_line( 1 )

        log( 1, "Error: The folder '%s' already exists.\nYou already has some custom channel git installation." % main_git_folder )
        log.insert_empty_line( 1 )

    else:
        channel_temporary_folder = os.path.join( CHANNEL_ROOT_DIRECTORY, TEMPORARY_FOLDER_TO_USE )
        download_main_repository( command_line_interface, git_executable_path, channel_temporary_folder )

        copy_overrides( channel_temporary_folder, CHANNEL_ROOT_DIRECTORY )
        shutil.rmtree( channel_temporary_folder, onerror=_delete_read_only_file )

        # Progressively saves the installation data, in case the user closes Sublime Text
        save_default_settings()


def copy_overrides(root_source_folder, root_destine_folder, move_files=False):
    """
        Python How To Copy Or Move Folders Recursively
        http://techs.studyhorror.com/python-copy-move-sub-folders-recursively-i-92

        Python script recursively rename all files in folder and subfolders
        https://stackoverflow.com/questions/41861238/python-script-recursively-rename-all-files-in-folder-and-subfolders

        Force Overwrite in Os.Rename
        https://stackoverflow.com/questions/8107352/force-overwrite-in-os-rename
    """
    installed_files = []

    # Call this if operation only one time, instead of calling the for every file.
    if move_files:
        def copy_file(source_file, destine_folder):
            shutil.move( source_file, destine_folder )
            add_path_if_not_exists( installed_files, relative_file_path )
    else:

        def copy_file(source_file, destine_folder):
            shutil.copy( source_file, destine_folder )
            add_path_if_not_exists( installed_files, relative_file_path )

    for source_folder, directories, files in os.walk( root_source_folder ):
        destine_folder = source_folder.replace( root_source_folder, root_destine_folder)

        if not os.path.exists( destine_folder ):
            os.mkdir( destine_folder )

        for file in files:
            source_file  = os.path.join( source_folder, file )
            destine_file = os.path.join( destine_folder, file )

            # print( ( "Moving" if move_files else "Coping" ), "file:", source_file, "to", destine_file )
            if os.path.exists( destine_file ):
                os.remove( destine_file )

            # Python: Get relative path from comparing two absolute paths
            # https://stackoverflow.com/questions/7287996/python-get-relative-path-from-comparing-two-absolute-paths
            relative_file_path   = convert_absolute_path_to_relative( destine_file )
            relative_folder_path = convert_absolute_path_to_relative( destine_folder )

            copy_file(source_file, destine_folder)

            add_path_if_not_exists( g_files_to_uninstall, relative_file_path )
            add_path_if_not_exists( g_folders_to_uninstall, relative_folder_path )

    log( 1, "installed_files: " + str( installed_files ) )


def add_path_if_not_exists(list_to_add, path):

    if path != "." and path != "..":
        add_item_if_not_exists( list_to_add, path )


def convert_absolute_path_to_relative(file_path):
    relative_path = os.path.commonprefix( [ CHANNEL_ROOT_DIRECTORY, file_path ] )
    relative_path = os.path.normpath( file_path.replace( relative_path, "" ) )

    return convert_to_unix_path(relative_path)


def add_folders_and_files_for_removal(root_source_folder, relative_path):
    add_path_if_not_exists( g_folders_to_uninstall, relative_path )

    for source_folder, directories, files in os.walk( root_source_folder ):

        for folder in directories:
            source_file   = os.path.join( source_folder, folder )
            relative_path = convert_absolute_path_to_relative( source_file )

            add_path_if_not_exists( g_folders_to_uninstall, relative_path )

        for file in files:
            source_file   = os.path.join( source_folder, file )
            relative_path = convert_absolute_path_to_relative( source_file )

            add_path_if_not_exists( g_files_to_uninstall, relative_path )


def download_main_repository(command_line_interface, git_executable_path, channel_temporary_folder):
    log( 1, "download_main_repository..." )
    log.insert_empty_line( 1 )
    log.insert_empty_line( 1 )
    log( 1, "Installing: %s" % ( str( CHANNEL_ROOT_URL ) ) )

    if os.path.isdir( channel_temporary_folder ):
        shutil.rmtree( channel_temporary_folder )

    command = shlex.split( '"%s" clone "%s" "%s"' % ( git_executable_path, CHANNEL_ROOT_URL, TEMPORARY_FOLDER_TO_USE ) )
    output  = str( command_line_interface.execute( command, cwd=CHANNEL_ROOT_DIRECTORY ) )

    log( 1, "download_main_repository, output: " + str( output ) )
    channel_temporary_packages_folder = os.path.join( channel_temporary_folder, "Packages" )

    shutil.rmtree( channel_temporary_packages_folder )


def download_not_packages_submodules(command_line_interface, git_executable_path):
    log( 1, "download_not_packages_submodules" )
    clone_sublime_text_channel( command_line_interface, git_executable_path )

    gitFilePath    = os.path.join( CHANNEL_ROOT_DIRECTORY, '.gitmodules' )
    gitModulesFile = configparser.RawConfigParser()

    index = 0
    gitModulesFile.read( gitFilePath )

    for section in gitModulesFile.sections():
        url  = gitModulesFile.get( section, "url" )
        path = gitModulesFile.get( section, "path" )

        # # For quick testing
        # index += 1
        # if index > 3:
        #     break

        if 'Packages' != path[0:8]:
            package_name            = os.path.basename( path )
            submodule_absolute_path = os.path.join( CHANNEL_ROOT_DIRECTORY, path )

            # How to check to see if a folder contains files using python 3
            # https://stackoverflow.com/questions/25675352/how-to-check-to-see-if-a-folder-contains-files-using-python-3
            try:
                os.rmdir( submodule_absolute_path )
                is_empty = True

            except OSError:
                is_empty = False

            if is_empty:
                log( 1, "download_not_packages_submodules..." )
                log.insert_empty_line( 1 )
                log.insert_empty_line( 1 )
                log( 1, "Installing: %s" % ( str( url ) ) )

                command = shlex.split( '"%s" clone "%s" "%s"' % ( git_executable_path, url, path ) )
                output  = str( command_line_interface.execute( command, cwd=CHANNEL_ROOT_DIRECTORY ) )

                add_folders_and_files_for_removal( submodule_absolute_path, path )
                log( 1, "download_not_packages_submodules, output: " + str( output ) )

                # Progressively saves the installation data, in case the user closes Sublime Text
                save_default_settings()

    return get_development_packages()


def install_development_packages(packages_to_install, git_executable_path, command_line_interface):
    set_default_settings( packages_to_install )
    log( 2, "install_submodules_packages, PACKAGES_TO_NOT_INSTALL_DEVELOPMENT: " + str( PACKAGES_TO_NOT_INSTALL_DEVELOPMENT ) )

    current_index      = 0
    git_packages_count = len( packages_to_install )

    for package_info, pi in sequence_timer( packages_to_install, info_frequency=0 ):
        current_index += 1

        progress = progress_info( pi, set_progress )
        package_name, url, path = package_info

        # # For quick testing
        # if current_index > 3:
        #     break

        log.insert_empty_line( 1 )
        log.insert_empty_line( 1 )
        log( 1, "%s Installing %d of %d: %s" % ( progress, current_index, git_packages_count, str( package_name ) ) )

        command = shlex.split( '"%s" clone --recursive "%s" "%s"' % ( git_executable_path, url, path) )
        output  = str( command_line_interface.execute( command, cwd=CHANNEL_ROOT_DIRECTORY ) )

        command = shlex.split( '"%s" checkout master' % ( git_executable_path ) )
        output += "\n" + str( command_line_interface.execute( command, cwd=os.path.join( CHANNEL_ROOT_DIRECTORY, path ) ) )

        log( 1, "install_development_packages, output: " + str( output ) )
        add_package_to_installation_list( package_name )


def get_development_packages():
    gitFilePath    = os.path.join( CHANNEL_ROOT_DIRECTORY, '.gitmodules' )
    gitModulesFile = configparser.RawConfigParser()

    index = 0
    installed_packages = get_installed_packages()

    # Do not try to install `Package Control` as they are currently running, and must be uninstalled
    # on the end, if `PackagesManager` was installed.
    currently_running = [ "Package Control" ]

    packages_tonot_install = unique_list_join( PACKAGES_TO_NOT_INSTALL_DEVELOPMENT, installed_packages, currently_running )
    log( 2, "get_development_packages, packages_tonot_install: " + str( packages_tonot_install ) )

    packages = []
    gitModulesFile.read( gitFilePath )

    for section in gitModulesFile.sections():
        # # For quick testing
        # index += 1
        # if index > 3:
        #     break

        url  = gitModulesFile.get( section, "url" )
        path = gitModulesFile.get( section, "path" )

        log( 2, "get_development_packages, path: " + path )

        if 'Packages' == path[0:8]:
            package_name            = os.path.basename( path )
            submodule_absolute_path = os.path.join( CHANNEL_ROOT_DIRECTORY, path )

            if not os.path.isdir( submodule_absolute_path ) \
                    and package_name not in packages_tonot_install :

                packages.append( ( package_name, url, path ) )

    # return \
    # [
    #     ('Active View Jump Back', 'https://github.com/evandrocoan/SublimeActiveViewJumpBack', 'Packages/Active View Jump Back'),
    #     ('amxmodx', 'https://github.com/evandrocoan/SublimeAMXX_Editor', 'Packages/amxmodx'),
    #     ('All Autocomplete', 'https://github.com/evandrocoan/SublimeAllAutocomplete', 'Packages/All Autocomplete'),
    #     ('Amxx Pawn', 'https://github.com/evandrocoan/SublimeAmxxPawn', 'Packages/Amxx Pawn'),
    #     ('Clear Cursors Carets', 'https://github.com/evandrocoan/ClearCursorsCarets', 'Packages/Clear Cursors Carets'),
    #     ('Notepad++ Color Scheme', 'https://github.com/evandrocoan/SublimeNotepadPlusPlusTheme', 'Packages/Notepad++ Color Scheme'),
    #     ('PackagesManager', 'https://github.com/evandrocoan/package_control', 'Packages/PackagesManager'),
    #     ('Toggle Words', 'https://github.com/evandrocoan/ToggleWords', 'Packages/Toggle Words'),
    #     ('Default', 'https://github.com/evandrocoan/SublimeDefault', 'Packages/Default'),
    # ]

    return packages


def set_default_settings(packages_to_install):
    """
        Set some package to be enabled at last due their settings being dependent on other packages
        which need to be installed first.

        This also disables all development disabled packages, when installing the development
        version. It sets the current user's `ignored_packages` settings including all packages
        already disabled and the new packages to be installed and must be disabled before attempting
        to install them.
    """
    set_first_and_last_packages_to_install( packages_to_install )
    ask_user_for_which_packages_to_install( packages_to_install )

    if "PackagesManager" in packages_to_install:
        sync_package_control_and_manager()

    else:
        global g_package_control_settings
        g_package_control_settings = None

    # The development version does not need to ignore all installed packages before starting the
    # installation process as it is not affected by the Sublime Text bug.
    if IS_DEVELOPMENT_INSTALL:
        set_development_ignored_packages( packages_to_install )


def set_development_ignored_packages(packages_to_install):

    for package_name in PACKAGES_TO_IGNORE_ON_DEVELOPMENT:

        # Only ignore the packages which are being installed
        if package_name in packages_to_install and package_name not in g_default_ignored_packages:
            g_default_ignored_packages.append( package_name )
            add_item_if_not_exists( g_packages_to_unignore, package_name )

    add_packages_to_ignored_list( g_default_ignored_packages )


def set_first_and_last_packages_to_install(packages_to_install):
    """
        Set the packages to be installed first and last. The `PACKAGES_TO_INSTALL_LAST` has priority
        when some package is on both lists.
    """
    set_first_packages_to_install( packages_to_install )
    last_packages = {}

    for package_name in packages_to_install:

        if package_name[0] in PACKAGES_TO_INSTALL_LAST:
            last_packages[package_name[0]] = package_name
            packages_to_install.remove( package_name )

    for package_name in PACKAGES_TO_INSTALL_LAST:

        if package_name in last_packages:
            packages_to_install.append( last_packages[package_name] )


def set_first_packages_to_install(packages_to_install):
    first_packages = {}

    for package_name in packages_to_install:

        if package_name[0] in PACKAGES_TO_INSTALL_FIRST:
            first_packages[package_name[0]] = package_name
            packages_to_install.remove( package_name )

    for package_name in reversed( PACKAGES_TO_INSTALL_FIRST ):

        if package_name in first_packages:
            packages_to_install.insert( 0, first_packages[package_name] )


def save_default_settings(is_installation_completed=0):
    """
        When uninstalling this channel we can only remove our packages, keeping the user's original
        ignored packages intact.
    """
    global g_channelSettings

    if 'Default' in g_packages_to_uninstall:
        g_channelSettings['default_packages_files'] = DEFAULT_PACKAGES_FILES

    # `packages_to_uninstall` and `packages_to_unignore` are to uninstall and unignore they when uninstalling the channel
    g_channelSettings['packages_to_uninstall']   = g_packages_to_uninstall
    g_channelSettings['packages_to_unignore']    = g_packages_to_unignore
    g_channelSettings['files_to_uninstall']      = g_files_to_uninstall
    g_channelSettings['folders_to_uninstall']    = g_folders_to_uninstall
    g_channelSettings['next_packages_to_ignore'] = g_next_packages_to_ignore
    g_channelSettings['packages_not_installed']  = g_packages_not_installed

    g_channelSettings = sort_dictionary( g_channelSettings )
    log( 1 & is_installation_completed, "save_default_settings, g_channelSettings: " + json.dumps( g_channelSettings, indent=4 ) )

    write_data_file( CHANNEL_INSTALLATION_SETTINGS, g_channelSettings )


def sort_dictionary(dictionary):
    return OrderedDict( sorted( dictionary.items() ) )


def add_package_to_installation_list(package_name):
    """
        When the installation is going on the PackagesManager will be installed. If the user restart
        Sublime Text after doing it, on the next time Sublime Text starts, the Package Control and
        the PackagesManager will kill each other and probably end up uninstalling all the packages
        installed.

        So, here we try to keep thing nice by syncing both `Package Control` and `PackagesManager`
        settings files.
    """

    if g_package_control_settings and not IS_DEVELOPMENT_INSTALL:
        installed_packages = get_dictionary_key( g_package_control_settings, 'installed_packages', [] )
        add_item_if_not_exists( installed_packages, package_name )

        packagesmanager = os.path.join( USER_FOLDER_PATH, g_packagesmanager_name )
        write_data_file( packagesmanager, sort_dictionary( g_package_control_settings ) )

    add_item_if_not_exists( g_packages_to_uninstall, package_name )

    # Progressively saves the installation data, in case the user closes Sublime Text
    save_default_settings()


def uninstall_package_control():
    """
        Uninstals package control only if PackagesManager was installed, otherwise the user will end
        up with no package manager.
    """
    log( 2, "uninstall_package_control, g_packages_to_uninstall: " + str( g_packages_to_uninstall ) )

    if "PackagesManager" in g_packages_to_uninstall:
        # Sublime Text is waiting the current thread to finish before loading the just installed
        # PackagesManager, therefore run a new thread delayed which finishes the job
        sublime.set_timeout_async( complete_package_control_uninstalltion, 2000 )

    else:
        log.insert_empty_line( 1 )
        log.insert_empty_line( 1 )
        log( 1, "Warning: PackagesManager is was not installed on the system!" )

        global g_is_installation_complete
        g_is_installation_complete = True


def complete_package_control_uninstalltion(maximum_attempts=3):
    log.insert_empty_line( 1 )
    log.insert_empty_line( 1 )
    log(1, "Finishing Package Control Uninstallation... maximum_attempts: " + str( maximum_attempts ) )

    # Import the recent installed PackagesManager
    try:
        from PackagesManager.packagesmanager.show_error import silence_error_message_box
        from PackagesManager.packagesmanager.package_manager import PackageManager
        from PackagesManager.packagesmanager.package_disabler import PackageDisabler

    except ImportError:

        if maximum_attempts > 0:
            maximum_attempts -= 1

            sublime.set_timeout_async( lambda: complete_package_control_uninstalltion( maximum_attempts ), 2000 )
            return

        else:
            log( 1, "Error! Could not complete the Package Control uninstalling, missing import for `PackagesManager`." )

    silence_error_message_box(300.0)

    package_manager    = PackageManager()
    packages_to_remove = [ ("Package Control", False), ("0_package_control_loader", None) ]
    packages_names     = [ package_name[0] for package_name in packages_to_remove ]

    add_packages_to_ignored_list( packages_names )
    unique_list_append( _uningored_packages_to_flush, packages_names )

    for package_name, is_dependency in packages_to_remove:
        log.insert_empty_line( 1 )
        log.insert_empty_line( 1 )

        log( 1, "Uninstalling: %s..." % str( package_name ) )
        package_manager.remove_package( package_name, is_dependency )

    delete_package_control_settings()

    # Flush off the `_uningored_packages_to_flush` just appended
    accumulative_unignore_user_packages( flush_everything=True )


def add_packages_to_ignored_list(packages_list):
    """
        Something, somewhere is setting the ignored_packages list to `["Vintage"]`. Then ensure we
        override this.
    """
    log( 1, "add_packages_to_ignored_list, Adding packages to unignore list: %s" % str( packages_list ) )

    global g_next_packages_to_ignore
    g_next_packages_to_ignore = packages_list

    save_default_settings()

    ignored_packages = g_userSettings.get( "ignored_packages", [] )
    unique_list_append( ignored_packages, packages_list )

    for interval in range( 0, 27 ):
        g_userSettings.set( "ignored_packages", ignored_packages )
        sublime.save_settings( USER_SETTINGS_FILE )

        time.sleep(0.1)


def delete_package_control_settings():
    """
        Clean it a few times because Package Control is kinda running and still flushing stuff down
        to its settings file.
    """
    log( 1, "Calling delete_package_control_settings..." )
    global g_is_installation_complete

    clean_settings       = {}
    package_control_file = os.path.join( USER_FOLDER_PATH, g_package_control_name )

    clean_settings['bootstrapped']    = False
    clean_settings['remove_orphaned'] = False

    if "remove_orphaned_backup" in g_package_control_settings:
        clean_settings['remove_orphaned_backup'] = get_dictionary_key( g_package_control_settings, 'remove_orphaned_backup', True )

    else:
        clean_settings['remove_orphaned_backup'] = get_dictionary_key( g_package_control_settings, 'remove_orphaned', True )

    write_data_file( package_control_file, clean_settings )
    g_is_installation_complete = True


def sync_package_control_and_manager():
    """
        When the installation is going on the PackagesManager will be installed. If the user restart
        Sublime Text after doing it, on the next time Sublime Text starts, the Package Control and
        the PackagesManager will kill each other and probably end up uninstalling all the packages
        installed.

        This happens due their configurations files list different sets of packages. So to fix this
        we need to keep both files synced while the installation process is going on.
    """
    log( 1, "Calling sync_package_control_and_manager..." )
    global g_package_control_settings

    package_control_file       = os.path.join( USER_FOLDER_PATH, g_package_control_name )
    g_package_control_settings = load_data_file( package_control_file )

    log( 2, "sync_package_control_and_manager, package_control: " + str( g_package_control_settings ) )
    ensure_installed_packages_name( g_package_control_settings )

    packagesmanager = os.path.join( USER_FOLDER_PATH, g_packagesmanager_name )
    write_data_file( packagesmanager, g_package_control_settings )


def satisfy_dependencies():
    manager = PackageManager()
    thread  = SatisfyDependenciesThread(manager)

    thread.start()
    thread.join()


def unignore_installed_packages():
    """
        When the installation was interrupted, there will be ignored packages which are pending to
        uningored.
    """
    packages_to_unignore = []

    for package_name in g_next_packages_to_ignore:

        if package_name in g_packages_to_uninstall:
            packages_to_unignore.append( package_name )

    log( 1, "unignore_installed_packages: " + str( packages_to_unignore ) )
    unignore_some_packages( packages_to_unignore )


def is_dependency(package_name, repositories_dictionary):
    package_dicitonary = repositories_dictionary[package_name]
    return "load_order" in package_dicitonary


def ensure_installed_packages_name(package_control_settings):
    """
        Ensure the installed packages names are on the settings files.
    """

    if "installed_packages" in package_control_settings:
        installed_packages = get_dictionary_key( package_control_settings, 'installed_packages', [] )

        remove_item_if_exists( installed_packages, "Package Control" )

        add_item_if_not_exists( installed_packages, "PackagesManager" )
        add_item_if_not_exists( installed_packages, CHANNEL_PACKAGE_NAME )

    else:
        package_control_settings['installed_packages'] = [ "PackagesManager", CHANNEL_PACKAGE_NAME ]

    # The `remove_orphaned_backup` is used to save the default user value for the overridden key
    # `remove_orphaned` by the `PackagesManager` when configuring
    if "remove_orphaned_backup" in package_control_settings:
        package_control_settings['remove_orphaned'] = package_control_settings['remove_orphaned_backup']
        del package_control_settings['remove_orphaned_backup']


def ask_user_for_which_packages_to_install(packages_to_install):
    can_continue  = [False]
    active_window = sublime.active_window()

    install_message    = "Select this to not install it."
    uninstall_message  = "Select this to install it."

    selected_packages_to_not_install = []
    packages_informations            = \
    [
        [ "Cancel the Installation Process", "Select this to cancel the installation process." ],
        [ "Continue the Installation Process...", "Select this when you are finished selections packages." ]
    ]

    for package_name in packages_to_install:

        if package_name in FORBIDDEN_PACKAGES:
            packages_informations.append( [ package_name, "You must install it or cancel the installation." ] )

        else:
            packages_informations.append( [ package_name, install_message ] )

    def on_done(item_index):

        if item_index < 1:
            global g_is_already_running
            g_is_already_running = False

            log.insert_empty_line( 1 )
            raise RuntimeError( "The user closed the installer's packages pick up list." )

        if item_index == 1:
            log.insert_empty_line( 1 )
            log( 1, "Continuing the installation after the packages pick up..." )

            can_continue[0] = True
            return

        package_information = packages_informations[item_index]
        package_name        = package_information[0]

        if package_name not in FORBIDDEN_PACKAGES:

            if package_information[1] == install_message:
                log( 1, "Removing the package: %s" % package_name )

                package_information[1] = uninstall_message
                selected_packages_to_not_install.append( package_name )

            else:
                log( 1, "Adding the package: %s" % package_name )

                package_information[1] = install_message
                selected_packages_to_not_install.remove( package_name )

        else:
            log( 1, "The package %s must be installed. " % package_name +
                    "If you do not want to install this package, cancel the installation process." )

        show_quick_panel( item_index )

    def show_quick_panel(selected_index=0):
        active_window.show_quick_panel( packages_informations, on_done, sublime.KEEP_OPEN_ON_FOCUS_LOST, selected_index )

    show_quick_panel()

    # show_quick_panel is a non-blocking function, but we can only continue after on_done being called
    while not can_continue[0]:
        time.sleep(1)

    # Show up the console, so the user can follow the process.
    sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )

    for package_name in selected_packages_to_not_install:
        g_packages_not_installed.append( package_name )

        target_index = packages_to_install.index( package_name )
        del packages_to_install[target_index]


def check_installed_packages(maximum_attempts=10):
    """
        Display warning when the installation process is finished or ask the user to restart
        Sublime Text to finish the installation.

        Compare the current installed packages list with required packages to install, and if they
        differ, attempt to install they again for some times. If not successful, stop trying and
        warn the user.
    """
    log( 1, "Finishing installation... maximum_attempts: " + str( maximum_attempts ) )
    maximum_attempts -= 1

    if g_is_installation_complete:
        sublime.message_dialog( wrap_text( """\
                The %s installation was successfully completed.

                You need to restart Sublime Text to load the installed packages and finish
                installing their missing dependencies.

                Check you Sublime Text Console for more information.
                """ % CHANNEL_PACKAGE_NAME ) )

        print_failed_repositories()
        return

    if maximum_attempts > 0:
        sublime.set_timeout_async( lambda: check_installed_packages( maximum_attempts ), 2000 )

    else:
        sublime.error_message( wrap_text( """\
                The %s installation could not be successfully completed.

                Check you Sublime Text Console for more information.

                If you want help fixing the problem, please, save your Sublime Text Console output
                so later others can see what happened try to fix it.
                """ % CHANNEL_PACKAGE_NAME ) )

        print_failed_repositories()


