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


from . import settings
g_is_running = False

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
from .channel_utilities import delete_read_only_file
from .channel_utilities import _delete_read_only_file
from .channel_utilities import wrap_text
from .channel_utilities import load_repository_file
from .channel_utilities import InstallationCancelled
from .channel_utilities import NoPackagesAvailable
from .channel_utilities import is_channel_upgraded
from .channel_utilities import print_failed_repositories
from .channel_utilities import sort_dictionary
from .channel_utilities import recursively_delete_empty_folders


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
    from PackagesManager.packagesmanager import cmd

    from PackagesManager.packagesmanager.package_manager import PackageManager
    from PackagesManager.packagesmanager.package_disabler import PackageDisabler

    from PackagesManager.packagesmanager.thread_progress import ThreadProgress
    from PackagesManager.packagesmanager.commands.satisfy_dependencies_command import SatisfyDependenciesThread
    from PackagesManager.packagesmanager.commands.advanced_install_package_command import AdvancedInstallPackageThread


# How many packages to ignore and unignore in batch to fix the ignored packages bug error
PACKAGES_COUNT_TO_IGNORE_AHEAD = 8


from python_debug_tools import Debugger
from estimated_time_left import sequence_timer
from estimated_time_left import progress_info
from estimated_time_left import CurrentUpdateProgress

# Debugger settings: 0 - disabled, 127 - enabled
log = Debugger( 127, os.path.basename( __file__ ) )

def _grade():
    return 1 & ( not IS_UPGRADE_INSTALLATION )

# log( 2, "..." )
# log( 2, "..." )
# log( 2, "Debugging" )
# log( 2, "CURRENT_PACKAGE_ROOT_DIRECTORY:     " + settings.CURRENT_PACKAGE_ROOT_DIRECTORY )


def main(channel_settings, is_forced=False):
    """
        Before calling this installer, the `Package Control` user settings file, must have the
        Channel file set before the default channel key `channels`.

        Also the current `Package Control` cache must be cleaned, ensuring it is downloading and
        using the Channel repositories/channel list.
    """
    # We can only run this when we are using the stable version of the channel. And when there is
    # not a `.git` folder, we are running the `Development Version` of the channel.
    main_git_path = os.path.join( settings.CURRENT_PACKAGE_ROOT_DIRECTORY, ".git" )

    # Not attempt to run when we are running from outside a `.sublime-package` as the upgrader is
    # only available for the `Stable Version` of the channel. The `Development Version` must use
    # git itself to install or remove packages.
    if is_forced or not os.path.exists( main_git_path ) and is_channel_upgraded( channel_settings ):
        log( 1, "Entering on %s main(0)" % settings.CURRENT_PACKAGE_NAME )

        installer_thread = StartInstallChannelThread( channel_settings )
        installer_thread.start()


class StartInstallChannelThread(threading.Thread):

    def __init__(self, channel_settings):
        threading.Thread.__init__(self)
        self.channel_settings = channel_settings

    def run(self):
        """
            The installation is not complete when the user cancelled the installation process or
            there are no packages available for an upgrade.

            Python thread exit code
            https://stackoverflow.com/questions/986616/python-thread-exit-code
        """

        if is_allowed_to_run():
            unpack_settings( self.channel_settings )
            installation_type = self.channel_settings['INSTALLATION_TYPE']

            installer_thread = InstallChannelFilesThread()
            installer_thread.start()

            global set_progress
            set_progress = CurrentUpdateProgress( 'Installing the %s packages...' % installation_type )

            ThreadProgress( installer_thread, set_progress, 'The %s was successfully installed.' % installation_type )
            installer_thread.join()

            save_default_settings()

            if not IS_UPGRADE_INSTALLATION:
                sublime.set_timeout_async( check_installed_packages_alert, 1000 )
                sublime.set_timeout_async( check_installed_packages, 10000 )


class InstallChannelFilesThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        log( _grade(), "Entering on run(1)" )

        load_installation_settings_file()
        command_line_interface = cmd.Cli( None, True )

        git_executable_path = command_line_interface.find_binary( "git.exe" if os.name == 'nt' else "git" )
        log( _grade(), "run, git_executable_path: " + str( git_executable_path ) )

        try:
            install_modules( command_line_interface, git_executable_path )

        except ( InstallationCancelled, NoPackagesAvailable ) as error:
            log( 1, str( error ) )

            # Set the flag as completed, to signalize the installation has ended
            global g_is_running
            g_is_running = False

        if not IS_UPGRADE_INSTALLATION:
            uninstall_package_control()


def install_modules(command_line_interface, git_executable_path):
    log( _grade(), "install_modules_, git_executable_path: " + str( git_executable_path ) )

    if IS_DEVELOPMENT_INSTALLATION:
        packages_to_install = download_not_packages_submodules( command_line_interface, git_executable_path )

        log( 2, "install_modules, packages_to_install: " + str( packages_to_install ) )
        install_development_packages( packages_to_install, git_executable_path, command_line_interface )

    else:
        packages_to_install = get_stable_packages( IS_UPGRADE_INSTALLATION )

        log( _grade(), "install_modules, packages_to_install: " + str( packages_to_install ) )
        install_stable_packages( packages_to_install )


def install_stable_packages(packages_to_install):
    """
        python multithreading wait till all threads finished
        https://stackoverflow.com/questions/11968689/python-multithreading-wait-till-all-threads-finished

        There is a bug with the AdvancedInstallPackageThread thread which trigger several errors of:

        "It appears a package is trying to ignore itself, causing a loop.
        Please resolve by removing the offending ignored_packages setting."

        When trying to install several package at once, then here I am installing them one by one.
    """
    log( 2, "install_stable_packages, g_channelSettings['PACKAGES_TO_NOT_INSTALL_STABLE']: "
            + str( g_channelSettings['PACKAGES_TO_NOT_INSTALL_STABLE'] ) )

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

        log.insert_empty_line()
        log.insert_empty_line()

        log( 1, "%s Installing %d of %d: %s" % ( progress, current_index, git_packages_count, str( package_name ) ) )
        ignore_next_packages( package_disabler, package_name, packages_to_install )

        if package_manager.install_package( package_name, False ) is False:
            log( 1, "Error: Failed to install the repository `%s`!" % package_name )
            g_failed_repositories.append( package_name )

        else:
            add_package_to_installation_list( package_name )

        accumulative_unignore_user_packages( package_name )

    accumulative_unignore_user_packages( flush_everything=True )


def get_stable_packages(is_upgrade):
    """
        python ConfigParser: read configuration from string
        https://stackoverflow.com/questions/27744058/python-configparser-read-configuration-from-string
    """
    channel_name = g_channelSettings['CHANNEL_PACKAGE_NAME']

    current_index     = 0
    filtered_packages = []

    installed_packages = get_installed_packages( list_default_packages=True, exclusion_list=[channel_name] )
    log( _grade(), "get_stable_packages, installed_packages: " + str( installed_packages ) )

    # Do not try to install this own package and the Package Control, as they are currently running
    currently_running = [ "Package Control", settings.CURRENT_PACKAGE_NAME, channel_name ]

    packages_tonot_install = unique_list_join \
    (
        currently_running,
        installed_packages,
        g_packages_to_uninstall,
        g_packages_not_installed if is_upgrade else [],
        g_channelSettings['PACKAGES_TO_NOT_INSTALL_STABLE'],
        g_channelSettings['PACKAGES_TO_IGNORE_ON_DEVELOPMENT'],
    )

    packages_to_install    = {}
    install_exclusively    = g_channelSettings['PACKAGES_TO_INSTALL_EXCLUSIVELY']
    is_exclusively_install = not not len( install_exclusively )

    repositories_loaded = load_repository_file( g_channelSettings['CHANNEL_REPOSITORY_FILE'], {} )
    log( _grade(), "get_stable_packages, packages_tonot_install: " + str( packages_tonot_install ) )

    if is_exclusively_install:
        log( _grade(), "Performing exclusively installation of the packages: " + str( install_exclusively ) )

        for package_name in repositories_loaded:

            if package_name in install_exclusively:
                packages_to_install[package_name] = repositories_loaded[package_name]

    else:
        packages_to_install = repositories_loaded

    for package_name in packages_to_install:
        # # For quick testing
        # current_index += 1
        # if current_index > 7:
        #     break

        if package_name not in packages_tonot_install \
                and not is_dependency( package_name, packages_to_install ):

            filtered_packages.append( package_name )

        # When installing the channel, we must mark the packages already installed as packages which
        # where not installed, so they are not uninstalled when the channel is uninstalled.
        if not is_upgrade \
                and package_name in installed_packages:

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

    if len( filtered_packages ) < 1:
        raise NoPackagesAvailable( "There are 0 packages available to install!" )

    if is_upgrade:
        log( 1, "New packages packages to install found... " + str( filtered_packages ) )

    return filtered_packages


def download_not_packages_submodules(command_line_interface, git_executable_path):
    log( 1, "download_not_packages_submodules" )

    root = g_channelSettings['CHANNEL_ROOT_DIRECTORY']
    clone_sublime_text_channel( command_line_interface, git_executable_path )

    gitFilePath    = os.path.join( root, '.gitmodules' )
    gitModulesFile = configparser.RawConfigParser()

    current_index = 0
    gitModulesFile.read( gitFilePath )

    for section in gitModulesFile.sections():
        url  = gitModulesFile.get( section, "url" )
        path = gitModulesFile.get( section, "path" )

        # # For quick testing
        # current_index += 1
        # if current_index > 3:
        #     break

        if 'Packages' != path[0:8]:
            package_name            = os.path.basename( path )
            submodule_absolute_path = os.path.join( root, path )

            # How to check to see if a folder contains files using python 3
            # https://stackoverflow.com/questions/25675352/how-to-check-to-see-if-a-folder-contains-files-using-python-3
            try:
                os.rmdir( submodule_absolute_path )
                is_empty = True

            except OSError:
                is_empty = False

            if is_empty:
                log( 1, "download_not_packages_submodules..." )
                log.insert_empty_line()
                log.insert_empty_line()
                log( 1, "Installing: %s" % ( str( url ) ) )

                command = shlex.split( '"%s" clone "%s" "%s"' % ( git_executable_path, url, path ) )
                output  = str( command_line_interface.execute( command, cwd=root ) )

                add_folders_and_files_for_removal( submodule_absolute_path, path )
                log( 1, "download_not_packages_submodules, output: " + str( output ) )

                # Progressively saves the installation data, in case the user closes Sublime Text
                save_default_settings()

    return get_development_packages()


def clone_sublime_text_channel(command_line_interface, git_executable_path):
    """
        Clone the main repository as `https://github.com/evandrocoan/SublimeTextStudio` and install
        it on the Sublime Text Data folder.
    """
    root = g_channelSettings['CHANNEL_ROOT_DIRECTORY']
    main_git_folder = os.path.join( root, ".git" )

    if os.path.exists( main_git_folder ):
        log.insert_empty_line()
        log.insert_empty_line()

        log( 1, "Error: The folder '%s' already exists.\nYou already has some custom channel git installation." % main_git_folder )
        log.insert_empty_line()

    else:
        root = g_channelSettings['CHANNEL_ROOT_DIRECTORY']
        temp = g_channelSettings['TEMPORARY_FOLDER_TO_USE']

        channel_temporary_folder = os.path.join( root, temp )
        download_main_repository( root, temp, command_line_interface, git_executable_path )

        files, folders = copy_overrides( channel_temporary_folder, root )
        shutil.rmtree( channel_temporary_folder, onerror=_delete_read_only_file )

        unique_list_append( g_files_to_uninstall, files )
        unique_list_append( g_folders_to_uninstall, folders )

        # Progressively saves the installation data, in case the user closes Sublime Text
        save_default_settings()


def download_main_repository(root, temp, command_line_interface, git_executable_path):
    log( 1, "download_main_repository..." )
    url = g_channelSettings['CHANNEL_ROOT_URL']

    log.insert_empty_line()
    log.insert_empty_line()

    log( 1, "Installing: %s" % ( str( g_channelSettings['CHANNEL_ROOT_URL'] ) ) )
    download_repository_to_folder( url, root, temp, command_line_interface, git_executable_path )

    # Delete the empty folders created by git while cloning the main repository
    channel_temporary_folder = os.path.join( root, temp )
    recursively_delete_empty_folders( channel_temporary_folder )


def download_repository_to_folder(url, root, temp, command_line_interface, git_executable_path):
    channel_temporary_folder = os.path.join( root, temp )

    if os.path.isdir( channel_temporary_folder ):
        shutil.rmtree( channel_temporary_folder, onerror=_delete_read_only_file )

    command = shlex.split( '"%s" clone "%s" "%s"' % ( git_executable_path, url, temp ) )
    output  = str( command_line_interface.execute( command, cwd=root ) )

    log( 1, "download_repository_to_folder, output: " + str( output ) )


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


def install_development_packages(packages_to_install, git_executable_path, command_line_interface):
    root = g_channelSettings['CHANNEL_ROOT_DIRECTORY']
    temp = g_channelSettings['TEMPORARY_FOLDER_TO_USE']
    channel_temporary_folder = os.path.join( root, temp )

    packages_names = [ package_info[0] for package_info in packages_to_install ]
    set_default_settings( packages_names, packages_to_install )

    package_disabler = PackageDisabler()
    package_manager  = PackageManager()

    current_index      = 0
    git_packages_count = len( packages_to_install )

    for package_info, pi in sequence_timer( packages_to_install, info_frequency=0 ):
        current_index += 1
        package_name, url, path = package_info

        progress = progress_info( pi, set_progress )
        submodule_absolute_path = os.path.join( root, path )

        # # For quick testing
        # if current_index > 3:
        #     break

        log.insert_empty_line()
        log.insert_empty_line()

        log( 1, "%s Installing %d of %d: %s" % ( progress, current_index, git_packages_count, str( package_name ) ) )
        ignore_next_packages( package_disabler, package_name, packages_names )

        if os.path.exists( submodule_absolute_path ):

            # Add the missing packages file into the existent packages folder, including the `.git` folder.
            if package_manager.backup_package_dir( package_name ):
                download_repository_to_folder( url, root, temp, command_line_interface, git_executable_path )
                copy_overrides( channel_temporary_folder, submodule_absolute_path, move_files=True, is_to_replace=False )

            else:
                g_failed_repositories.append( package_name )

                log( 1, "Error: Failed to backup and install the repository `%s`!" % package_name )
                continue

        else:
            command = shlex.split( '"%s" clone --recursive "%s" "%s"' % ( git_executable_path, url, path) )
            result  = command_line_interface.execute( command, cwd=root )

            if result is False:
                g_failed_repositories.append( package_name )
                log( 1, "Error: Failed to download the repository `%s`!" % package_name )
                continue

        command = shlex.split( '"%s" checkout master' % ( git_executable_path ) )
        output  = str( result ) + "\n" + str( command_line_interface.execute( command, cwd=os.path.join( root, path ) ) )

        log( 1, "install_development_packages, output: " + str( output ) )

        add_package_to_installation_list( package_name )
        accumulative_unignore_user_packages( package_name )

    accumulative_unignore_user_packages( flush_everything=True )
    satisfy_dependencies()

    # Clean the temporary folder after the process has ended
    shutil.rmtree( channel_temporary_folder, onerror=_delete_read_only_file )


def get_development_packages():
    development_ignored = g_channelSettings['PACKAGES_TO_NOT_INSTALL_DEVELOPMENT']
    log( 2, "install_submodules_packages, PACKAGES_TO_NOT_INSTALL_DEVELOPMENT: " + str( development_ignored ) )

    gitFilePath    = os.path.join( g_channelSettings['CHANNEL_ROOT_DIRECTORY'], '.gitmodules' )
    gitModulesFile = configparser.RawConfigParser()

    current_index      = 0
    installed_packages = get_installed_packages()

    # Do not try to install `Package Control` as they are currently running, and must be uninstalled
    # on the end, if `PackagesManager` was installed.
    currently_running = [ "Package Control" ]

    packages_tonot_install = unique_list_join( development_ignored, installed_packages, currently_running )
    log( 2, "get_development_packages, packages_tonot_install: " + str( packages_tonot_install ) )

    packages = []
    gitModulesFile.read( gitFilePath )

    for section in gitModulesFile.sections():
        # # For quick testing
        # current_index += 1
        # if current_index > 3:
        #     break

        url  = gitModulesFile.get( section, "url" )
        path = gitModulesFile.get( section, "path" )

        log( 2, "get_development_packages, path: " + path )

        if 'Packages' == path[0:8]:
            package_name = os.path.basename( path )

            if package_name not in packages_tonot_install :
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


def copy_overrides(root_source_folder, root_destine_folder, move_files=False, is_to_replace=True):
    """
        Python How To Copy Or Move Folders Recursively
        http://techs.studyhorror.com/python-copy-move-sub-folders-recursively-i-92

        Python script recursively rename all files in folder and subfolders
        https://stackoverflow.com/questions/41861238/python-script-recursively-rename-all-files-in-folder-and-subfolders

        Force Overwrite in Os.Rename
        https://stackoverflow.com/questions/8107352/force-overwrite-in-os-rename
    """
    installed_files   = []
    installed_folders = []

    # Call this if operation only one time, instead of calling the for every file.
    if move_files:

        def operate_file(source_file, destine_folder):
            shutil.move( source_file, destine_folder )

    else:

        def operate_file(source_file, destine_folder):
            shutil.copy( source_file, destine_folder )

    for source_folder, directories, files in os.walk( root_source_folder ):
        destine_folder = source_folder.replace( root_source_folder, root_destine_folder)

        if not os.path.exists( destine_folder ):
            os.mkdir( destine_folder )

        for file in files:
            source_file  = os.path.join( source_folder, file )
            destine_file = os.path.join( destine_folder, file )

            # print( ( "Moving" if move_files else "Coping" ), "file:", source_file, "to", destine_file )
            if os.path.exists( destine_file ):

                if is_to_replace:
                    delete_read_only_file( destine_file )

                else:
                    continue

            # Python: Get relative path from comparing two absolute paths
            # https://stackoverflow.com/questions/7287996/python-get-relative-path-from-comparing-two-absolute-paths
            relative_file_path   = convert_absolute_path_to_relative( destine_file )
            relative_folder_path = convert_absolute_path_to_relative( destine_folder )

            operate_file(source_file, destine_folder)

            add_path_if_not_exists( installed_files, relative_file_path )
            add_path_if_not_exists( installed_folders, relative_folder_path )

    log( 1, "copy_overrides, installed_files:   " + str( installed_files ) )
    log( 1, "copy_overrides, installed_folders: " + str( installed_folders ) )
    return installed_files, installed_folders


def add_path_if_not_exists(list_to_add, path):

    if path != "." and path != "..":
        add_item_if_not_exists( list_to_add, path )


def convert_absolute_path_to_relative(file_path):
    relative_path = os.path.commonprefix( [ g_channelSettings['CHANNEL_ROOT_DIRECTORY'], file_path ] )
    relative_path = os.path.normpath( file_path.replace( relative_path, "" ) )

    return convert_to_unix_path(relative_path)


def set_default_settings(packages_names, packages_to_install=[]):
    """
        Set some package to be enabled at last due their settings being dependent on other packages
        which need to be installed first.

        This also disables all development disabled packages, when installing the development
        version. It sets the current user's `ignored_packages` settings including all packages
        already disabled and the new packages to be installed and must be disabled before attempting
        to install them.
    """
    set_first_and_last_packages_to_install( packages_names )
    ask_user_for_which_packages_to_install( packages_names, packages_to_install )

    if "PackagesManager" in packages_names:
        sync_package_control_and_manager()

    else:
        global g_package_control_settings
        g_package_control_settings = None

    # The development version does not need to ignore all installed packages before starting the
    # installation process as it is not affected by the Sublime Text bug.
    if IS_DEVELOPMENT_INSTALLATION:
        set_development_ignored_packages( packages_names )


def set_development_ignored_packages(packages_to_install):

    for package_name in g_channelSettings['PACKAGES_TO_IGNORE_ON_DEVELOPMENT']:

        # Only ignore the packages which are being installed
        if package_name in packages_to_install and package_name not in g_default_ignored_packages:
            g_default_ignored_packages.append( package_name )
            add_item_if_not_exists( g_packages_to_unignore, package_name )

    add_packages_to_ignored_list( g_default_ignored_packages )


def set_first_and_last_packages_to_install(packages_to_install):
    """
        Set the packages to be installed first and last. The `g_channelSettings['PACKAGES_TO_INSTALL_LAST']` has priority
        when some package is on both lists.
    """
    set_first_packages_to_install( packages_to_install )
    last_packages = {}

    for package_name in packages_to_install:

        if package_name[0] in g_channelSettings['PACKAGES_TO_INSTALL_LAST']:
            last_packages[package_name[0]] = package_name
            packages_to_install.remove( package_name )

    for package_name in g_channelSettings['PACKAGES_TO_INSTALL_LAST']:

        if package_name in last_packages:
            packages_to_install.append( last_packages[package_name] )


def set_first_packages_to_install(packages_to_install):
    first_packages = {}

    for package_name in packages_to_install:

        if package_name[0] in g_channelSettings['PACKAGES_TO_INSTALL_FIRST']:
            first_packages[package_name[0]] = package_name
            packages_to_install.remove( package_name )

    for package_name in reversed( g_channelSettings['PACKAGES_TO_INSTALL_FIRST'] ):

        if package_name in first_packages:
            packages_to_install.insert( 0, first_packages[package_name] )


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

    if g_uningored_packages_to_flush < 1:
        global g_next_packages_to_ignore

        last_ignored_packages     = packages_list.index( package_name )
        g_next_packages_to_ignore = packages_list[last_ignored_packages : last_ignored_packages+PACKAGES_COUNT_TO_IGNORE_AHEAD+1]

        # We never can ignore the Default package, otherwise several errors/anomalies show up
        if "Default" in g_next_packages_to_ignore:
            g_next_packages_to_ignore.remove( "Default" )

        log( 1, "Adding %d packages to be installed to the `ignored_packages` setting list." % len( g_next_packages_to_ignore ) )
        log( 1, "g_next_packages_to_ignore: " + str( g_next_packages_to_ignore ) )

        # If the package is already on the users' `ignored_packages` settings, it means either that
        # the package was disabled by the user or the package is one of the development disabled
        # packages. Therefore we must not unignore it later when unignoring them.
        for package_name in g_next_packages_to_ignore:

            if package_name in g_default_ignored_packages:
                g_next_packages_to_ignore.remove( package_name )

        # This also adds them to the `in_process` list on the Package Control.sublime-settings file
        package_disabler.disable_packages( g_next_packages_to_ignore, "remove" )

        # Let the packages be unloaded by Sublime Text while ensuring anyone is putting them back in
        add_packages_to_ignored_list( g_next_packages_to_ignore )


def accumulative_unignore_user_packages(package_name="", flush_everything=False):
    """
        Flush off the remaining `g_next_packages_to_ignore` appended. There is a bug with the
        uninstalling several packages, which trigger several errors of:

        "It appears a package is trying to ignore itself, causing a loop.
        Please resolve by removing the offending ignored_packages setting."

        When trying to uninstall several package at once, then here I am unignoring them all at once.

        Package Control: Advanced Install Package
        https://github.com/wbond/package_control/issues/1191

        @param flush_everything     set all remaining packages as unignored
    """

    if flush_everything:
        unignore_some_packages( g_next_packages_to_ignore )

    else:
        log( 1, "Adding package to unignore list: %s" % str( package_name ) )

        global g_uningored_packages_to_flush
        g_uningored_packages_to_flush += 1

        if g_uningored_packages_to_flush > len( g_next_packages_to_ignore ):
            unignore_some_packages( g_next_packages_to_ignore )

            del g_next_packages_to_ignore[:]
            g_uningored_packages_to_flush = 0


def unignore_some_packages(packages_list):
    """
        Flush just a few items each time.
    """
    is_there_unignored_packages = False

    for package_name in packages_list:

        if package_name in g_default_ignored_packages:
            is_there_unignored_packages = True

            log( 1, "Unignoring the package: %s" % package_name )
            g_default_ignored_packages.remove( package_name )

    if is_there_unignored_packages:
        g_userSettings.set( "ignored_packages", g_default_ignored_packages )
        sublime.save_settings( g_channelSettings['USER_SETTINGS_FILE'] )


def add_package_to_installation_list(package_name):
    """
        When the installation is going on the PackagesManager will be installed. If the user restart
        Sublime Text after doing it, on the next time Sublime Text starts, the Package Control and
        the PackagesManager will kill each other and probably end up uninstalling all the packages
        installed.

        So, here we try to keep things nice by syncing both `Package Control` and `PackagesManager`
        settings files.
    """

    if g_package_control_settings and not IS_DEVELOPMENT_INSTALLATION:
        installed_packages = get_dictionary_key( g_package_control_settings, 'installed_packages', [] )
        add_item_if_not_exists( installed_packages, package_name )

        packagesmanager = os.path.join( g_channelSettings['USER_FOLDER_PATH'], g_packagesmanager_name )
        write_data_file( packagesmanager, sort_dictionary( g_package_control_settings ) )

    add_item_if_not_exists( g_packages_to_uninstall, package_name )

    # Progressively saves the installation data, in case the user closes Sublime Text
    save_default_settings()


def save_default_settings():
    """
        When uninstalling this channel we can only remove our packages, keeping the user's original
        ignored packages intact.
    """
    # https://stackoverflow.com/questions/9264763/unboundlocalerror-in-python
    # UnboundLocalError in Python
    global g_channelDetails

    if 'Default' in g_packages_to_uninstall:
        g_channelDetails['default_package_files'] = g_channelSettings['DEFAULT_PACKAGE_FILES']

    # `packages_to_uninstall` and `packages_to_unignore` are to uninstall and unignore they when uninstalling the channel
    g_channelDetails['packages_to_uninstall']   = g_packages_to_uninstall
    g_channelDetails['packages_to_unignore']    = g_packages_to_unignore
    g_channelDetails['files_to_uninstall']      = g_files_to_uninstall
    g_channelDetails['folders_to_uninstall']    = g_folders_to_uninstall
    g_channelDetails['next_packages_to_ignore'] = g_next_packages_to_ignore
    g_channelDetails['packages_not_installed']  = g_packages_not_installed
    g_channelDetails['installation_type']       = g_installation_type

    g_channelDetails = sort_dictionary( g_channelDetails )
    # log( 1, "save_default_settings, g_channelDetails: " + json.dumps( g_channelDetails, indent=4 ) )

    write_data_file( g_channelSettings['CHANNEL_INSTALLATION_DETAILS'], g_channelDetails )


def uninstall_package_control():
    """
        Uninstals package control only if PackagesManager was installed, otherwise the user will end
        up with no package manager.
    """
    log( 2, "uninstall_package_control, g_packages_to_uninstall: " + str( g_packages_to_uninstall ) )

    # Only uninstall it, when `PackagesManager` was also installed
    if "PackagesManager" in g_packages_to_uninstall:
        # Sublime Text is waiting the current thread to finish before loading the just installed
        # PackagesManager, therefore run a new thread delayed which finishes the job
        sublime.set_timeout_async( complete_package_control_uninstallation, 2000 )

    else:
        log( 1, "Warning: PackagesManager is was not installed on the system!" )

        # Clean right away the PackagesManager successful flag, was it was not installed
        global g_is_running
        g_is_running = False


def complete_package_control_uninstallation(maximum_attempts=3):
    log.insert_empty_line()
    log.insert_empty_line()
    log( 1, "Finishing Package Control Uninstallation... maximum_attempts: " + str( maximum_attempts ) )

    # Import the recent installed PackagesManager
    try:
        from PackagesManager.packagesmanager.show_error import silence_error_message_box
        from PackagesManager.packagesmanager.package_manager import PackageManager
        from PackagesManager.packagesmanager.package_disabler import PackageDisabler

    except ImportError:

        if maximum_attempts > 0:
            maximum_attempts -= 1

            sublime.set_timeout_async( lambda: complete_package_control_uninstallation( maximum_attempts ), 2000 )
            return

        else:
            log( 1, "Error! Could not complete the Package Control uninstalling, missing import for `PackagesManager`." )

    silence_error_message_box(300.0)

    package_manager  = PackageManager()
    package_disabler = PackageDisabler()

    packages_to_remove = [ ("Package Control", False), ("0_package_control_loader", None) ]
    packages_names     = [ package_name[0] for package_name in packages_to_remove ]

    for package_name, is_dependency in packages_to_remove:
        log.insert_empty_line()
        log.insert_empty_line()

        log( 1, "Uninstalling: %s..." % str( package_name ) )
        ignore_next_packages( package_disabler, package_name, packages_names )

        package_manager.remove_package( package_name, is_dependency )
        accumulative_unignore_user_packages( package_name )

    accumulative_unignore_user_packages( flush_everything=True )
    delete_package_control_settings()


def add_packages_to_ignored_list(packages_list):
    """
        Something, somewhere is setting the ignored_packages list to `["Vintage"]`. Then ensure we
        override this.
    """
    log( 1, "add_packages_to_ignored_list, Adding packages to unignore list: %s" % str( packages_list ) )
    unique_list_append( g_default_ignored_packages, packages_list )

    # Progressively saves the installation data, in case the user closes Sublime Text
    save_default_settings()

    for interval in range( 0, 27 ):
        g_userSettings.set( "ignored_packages", g_default_ignored_packages )
        sublime.save_settings( g_channelSettings['USER_SETTINGS_FILE'] )

        time.sleep(0.1)


def delete_package_control_settings():
    """
        Clean it a few times because Package Control is kinda running and still flushing stuff down
        to its settings file.
    """
    log( 1, "Calling delete_package_control_settings..." )

    clean_settings       = {}
    package_control_file = os.path.join( g_channelSettings['USER_FOLDER_PATH'], g_package_control_name )

    clean_settings['bootstrapped']    = False
    clean_settings['remove_orphaned'] = False

    if "remove_orphaned_backup" in g_package_control_settings:
        clean_settings['remove_orphaned_backup'] = get_dictionary_key( g_package_control_settings, 'remove_orphaned_backup', True )

    else:
        clean_settings['remove_orphaned_backup'] = get_dictionary_key( g_package_control_settings, 'remove_orphaned', True )

    write_data_file( package_control_file, clean_settings )

    # Set the flag as completed, to signalize the this part of the installation was successful
    global g_is_running
    g_is_running = False


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

    package_control_file       = os.path.join( g_channelSettings['USER_FOLDER_PATH'], g_package_control_name )
    g_package_control_settings = load_data_file( package_control_file )

    log( 2, "sync_package_control_and_manager, package_control: " + str( g_package_control_settings ) )
    ensure_installed_packages_name( g_package_control_settings )

    packagesmanager = os.path.join( g_channelSettings['USER_FOLDER_PATH'], g_packagesmanager_name )
    write_data_file( packagesmanager, g_package_control_settings )


def satisfy_dependencies():
    manager = PackageManager()
    thread  = SatisfyDependenciesThread(manager)

    thread.start()
    thread.join()


def unignore_installed_packages():
    """
        When the installation was interrupted, there will be ignored packages which are pending to
        uningored. Then these packages must to be loaded when the installer starts again.
    """
    packages_to_unignore = []

    for package_name in g_next_packages_to_ignore:

        if package_name in g_packages_to_uninstall:
            packages_to_unignore.append( package_name )

    log( _grade(), "unignore_installed_packages: " + str( packages_to_unignore ) )
    unignore_some_packages( packages_to_unignore )


def is_dependency(package_name, repositories_dictionary):
    """
        Return by default True to stop the installation as the package not was not found on the
        `channel.json` repository file
    """
    if package_name in repositories_dictionary:
        package_dicitonary = repositories_dictionary[package_name]
        return "load_order" in package_dicitonary

    log( 1, "Warning: The package name `%s` could not be found on the repositories_dictionary!" % package_name )
    return True


def ensure_installed_packages_name(package_control_settings):
    """
        Ensure the installed packages names are on the settings files.
    """

    if "installed_packages" in package_control_settings:
        installed_packages = get_dictionary_key( package_control_settings, 'installed_packages', [] )

        remove_item_if_exists( installed_packages, "Package Control" )

        add_item_if_not_exists( installed_packages, "PackagesManager" )
        add_item_if_not_exists( installed_packages, g_channelSettings['CHANNEL_PACKAGE_NAME'] )

    else:
        channel_name = g_channelSettings['CHANNEL_PACKAGE_NAME']
        package_control_settings['installed_packages'] = [ "PackagesManager", channel_name ]

    # The `remove_orphaned_backup` is used to save the default user value for the overridden key
    # `remove_orphaned` by the `PackagesManager` when configuring
    if "remove_orphaned_backup" in package_control_settings:
        package_control_settings['remove_orphaned'] = package_control_settings['remove_orphaned_backup']
        del package_control_settings['remove_orphaned_backup']


def ask_user_for_which_packages_to_install(packages_names, packages_to_install=[]):
    can_continue  = [False, False]
    active_window = sublime.active_window()

    install_message    = "Select this to not install it."
    uninstall_message  = "Select this to install it."

    selected_packages_to_not_install = []
    packages_informations            = \
    [
        [ "Cancel the Installation Process", "Select this to cancel the %s process." % INSTALLATION_TYPE_NAME ],
        [ "Continue the Installation Process...", "Select this when you are finished selections packages." ]
    ]

    for package_name in packages_names:

        if package_name in g_channelSettings['FORBIDDEN_PACKAGES']:
            packages_informations.append( [ package_name, "You must install it or cancel the %s." % INSTALLATION_TYPE_NAME ] )

        else:
            packages_informations.append( [ package_name, install_message ] )

    def on_done(item_index):

        if item_index < 1:
            can_continue[0] = True
            can_continue[1] = True
            return

        if item_index == 1:
            log.insert_empty_line()
            log( 1, "Continuing the %s after the packages pick up..." % INSTALLATION_TYPE_NAME )

            can_continue[0] = True
            return

        package_information = packages_informations[item_index]
        package_name        = package_information[0]

        if package_name not in g_channelSettings['FORBIDDEN_PACKAGES']:

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
                    "If you do not want to install this package, cancel the %s process." % INSTALLATION_TYPE_NAME )

        show_quick_panel( item_index )

    def show_quick_panel(selected_index=0):
        active_window.show_quick_panel( packages_informations, on_done, sublime.KEEP_OPEN_ON_FOCUS_LOST, selected_index )

    show_quick_panel()

    # show_quick_panel is a non-blocking function, but we can only continue after on_done being called
    while not can_continue[0]:
        time.sleep(1)

    # Show up the console, so the user can follow the process.
    sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )

    if can_continue[1]:
        log.insert_empty_line()
        raise InstallationCancelled( "The user closed the installer's packages pick up list." )

    for package_name in selected_packages_to_not_install:
        g_packages_not_installed.append( package_name )

        target_index = packages_names.index( package_name )
        del packages_names[target_index]

        if len( packages_to_install ):
            del packages_to_install[target_index]

    # Progressively saves the installation data, in case the user closes Sublime Text
    save_default_settings()


def check_installed_packages_alert(maximum_attempts=10):
    """
        Show a message to the user observing the Sublime Text console, so he know the process is not
        finished yet.
    """
    log( _grade(), "Looking for new tasks... %s seconds remaining." % str( maximum_attempts ) )
    maximum_attempts -= 1

    if maximum_attempts > 0:

        if g_is_running:
            sublime.set_timeout_async( lambda: check_installed_packages_alert( maximum_attempts ), 1000 )

        else:
            log( _grade(), "Finished looking for new tasks... The installation is complete." )


def check_installed_packages(maximum_attempts=10):
    """
        Wait PackagesManager to load the found dependencies, before announcing it to the user.

        Display warning when the installation process is finished or ask the user to restart
        Sublime Text to finish the installation.

        Compare the current installed packages list with required packages to install, and if they
        differ, attempt to install they again for some times. If not successful, stop trying and
        warn the user.
    """
    log( _grade(), "Finishing installation... maximum_attempts: " + str( maximum_attempts ) )
    maximum_attempts -= 1

    if not g_is_running:

        if not IS_UPGRADE_INSTALLATION:
            sublime.message_dialog( end_user_message( """\
                    The %s %s was successfully completed.

                    You need to restart Sublime Text to load the installed packages and finish
                    installing their missing dependencies.

                    Check you Sublime Text Console for more information.
                    """ % ( g_channelSettings['CHANNEL_PACKAGE_NAME'], INSTALLATION_TYPE_NAME ) ) )

        print_failed_repositories( g_failed_repositories )
        return

    if maximum_attempts > 0:
        sublime.set_timeout_async( lambda: check_installed_packages( maximum_attempts ), 2000 )

    else:
        sublime.error_message( end_user_message( """\
                The %s %s could NOT be successfully completed.

                Check you Sublime Text Console for more information.

                If you want help fixing the problem, please, save your Sublime Text Console output
                so later others can see what happened try to fix it.
                """ % ( g_channelSettings['CHANNEL_PACKAGE_NAME'], INSTALLATION_TYPE_NAME ) ) )

        print_failed_repositories( g_failed_repositories )


def end_user_message(message):
    # This is here because it is almost the last thing to be done
    global g_is_running
    g_is_running = False

    return wrap_text( message )


def is_allowed_to_run():
    global g_is_running

    if g_is_running:
        print( "You are already running a command. Wait until it finishes or restart Sublime Text" )
        return False

    g_is_running = True
    return True


def unpack_settings(channel_settings):
    global g_channelSettings
    global g_failed_repositories

    g_channelSettings     = channel_settings
    g_failed_repositories = []

    global g_uningored_packages_to_flush
    g_uningored_packages_to_flush = 0

    global IS_UPGRADE_INSTALLATION
    global INSTALLATION_TYPE_NAME
    global IS_DEVELOPMENT_INSTALLATION

    IS_UPGRADE_INSTALLATION     = True if g_channelSettings['INSTALLATION_TYPE'] == "upgrade"     else False
    IS_DEVELOPMENT_INSTALLATION = True if g_channelSettings['INSTALLATION_TYPE'] == "development" else False
    INSTALLATION_TYPE_NAME      = "Upgrade" if IS_UPGRADE_INSTALLATION else "Installation"

    log( 1, "IS_UPGRADE_INSTALLATION:     " + str( IS_UPGRADE_INSTALLATION ) )
    log( 1, "IS_DEVELOPMENT_INSTALLATION: " + str( IS_DEVELOPMENT_INSTALLATION ) )


def load_installation_settings_file():
    global g_package_control_name
    global g_packagesmanager_name

    g_package_control_name = "Package Control.sublime-settings"
    g_packagesmanager_name = "PackagesManager.sublime-settings"

    global g_userSettings
    global g_channelDetails
    global g_default_ignored_packages

    g_userSettings   = sublime.load_settings( g_channelSettings['USER_SETTINGS_FILE'] )
    g_channelDetails = load_data_file( g_channelSettings['CHANNEL_INSTALLATION_DETAILS'] )

    # Contains the original user's ignored packages.
    g_default_ignored_packages = g_userSettings.get( 'ignored_packages', [] )

    global g_packages_to_uninstall
    global g_files_to_uninstall
    global g_folders_to_uninstall
    global g_packages_to_unignore
    global g_next_packages_to_ignore
    global g_packages_not_installed
    global g_installation_type

    g_packages_to_uninstall   = get_dictionary_key( g_channelDetails, 'packages_to_uninstall', [] )
    g_packages_to_unignore    = get_dictionary_key( g_channelDetails, 'packages_to_unignore', [] )
    g_files_to_uninstall      = get_dictionary_key( g_channelDetails, 'files_to_uninstall', [] )
    g_folders_to_uninstall    = get_dictionary_key( g_channelDetails, 'folders_to_uninstall', [] )
    g_next_packages_to_ignore = get_dictionary_key( g_channelDetails, 'next_packages_to_ignore', [] )
    g_packages_not_installed  = get_dictionary_key( g_channelDetails, 'packages_not_installed', [] )
    g_installation_type       = get_dictionary_key( g_channelDetails, 'installation_type', g_channelSettings['INSTALLATION_TYPE'] )

    unignore_installed_packages()

    log( _grade(), "load_installation_settings_file, g_default_ignored_packages:        " + str( g_default_ignored_packages ) )
    log( _grade(), "load_installation_settings_file, PACKAGES_TO_IGNORE_ON_DEVELOPMENT: "
            + str( g_channelSettings['PACKAGES_TO_IGNORE_ON_DEVELOPMENT'] ) )

