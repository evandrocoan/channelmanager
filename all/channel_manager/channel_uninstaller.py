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
# Channel Manager Uninstaller, uninstall a installed channel
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

import os
import re
import json
import time
import shutil
import threading


g_is_already_running           = False
g_is_package_control_installed = False

from . import settings

from .channel_utilities import get_installed_packages
from .channel_utilities import unique_list_join
from .channel_utilities import unique_list_append
from .channel_utilities import load_data_file
from .channel_utilities import write_data_file
from .channel_utilities import string_convert_list
from .channel_utilities import get_main_directory
from .channel_utilities import get_dictionary_key
from .channel_utilities import remove_if_exists
from .channel_utilities import delete_read_only_file
from .channel_utilities import _delete_read_only_file
from .channel_utilities import wrap_text
from .channel_utilities import safe_remove
from .channel_utilities import remove_only_if_exists
from .channel_utilities import InstallationCancelled
from .channel_utilities import NoPackagesAvailable
from .channel_utilities import load_repository_file
from .channel_utilities import is_channel_upgraded


# When there is an ImportError, means that Package Control is installed instead of PackagesManager,
# or vice-versa. Which means we cannot do nothing as this is only compatible with PackagesManager.
try:
    from PackagesManager.packagesmanager.show_error import silence_error_message_box

    from PackagesManager.packagesmanager.package_manager import PackageManager
    from PackagesManager.packagesmanager.thread_progress import ThreadProgress
    from PackagesManager.packagesmanager.package_disabler import PackageDisabler

except ImportError:
    g_is_package_control_installed = True

    from package_control.package_manager import PackageManager
    from package_control.thread_progress import ThreadProgress
    from package_control.package_disabler import PackageDisabler

    def silence_error_message_box(value):
        pass

    def disable_package_control_uninstaller():
        pass


# How many packages to ignore and unignore in batch to fix the ignored packages bug error
PACKAGES_COUNT_TO_IGNORE_AHEAD = 8

from python_debug_tools import Debugger
from estimated_time_left import sequence_timer
from estimated_time_left import progress_info
from estimated_time_left import CurrentUpdateProgress

# Debugger settings: 0 - disabled, 127 - enabled
log = Debugger( 127, os.path.basename( __file__ ) )

def _grade():
    return 1 & ( not IS_DOWNGRADE_INSTALLATION )

# log( 2, "..." )
# log( 2, "..." )
# log( 2, "Debugging" )
# log( 2, "CURRENT_PACKAGE_ROOT_DIRECTORY: " + settings.CURRENT_PACKAGE_ROOT_DIRECTORY )


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

        installer_thread = StartUninstallChannelThread( channel_settings, is_forced )
        installer_thread.start()


class StartUninstallChannelThread(threading.Thread):

    def __init__(self, channel_settings, is_forced):
        threading.Thread.__init__(self)

        self.is_forced        = is_forced
        self.channel_settings = channel_settings

    def run(self):
        """
            Python thread exit code
            https://stackoverflow.com/questions/986616/python-thread-exit-code
        """

        if is_allowed_to_run():
            unpack_settings( self.channel_settings, self.is_forced )

            uninstaller_thread = UninstallChannelFilesThread()
            uninstaller_thread.start()

            global set_progress
            set_progress = CurrentUpdateProgress( '%s of Sublime Text %s packages...'
                    % ( INSTALLATION_TYPE_NAME, g_channel_settings['CHANNEL_PACKAGE_NAME'] ) )

            ThreadProgress( uninstaller_thread, set_progress, 'The %s of %s was successfully completed.'
                    % ( INSTALLATION_TYPE_NAME, g_channel_settings['CHANNEL_PACKAGE_NAME'] ) )

            uninstaller_thread.join()

            # Wait PackagesManager to load the found dependencies, before announcing it to the user
            sublime.set_timeout_async( check_uninstalled_packages_alert, 1000 )
            sublime.set_timeout_async( check_uninstalled_packages, 10000 )


class UninstallChannelFilesThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        log( _grade(), "Entering on %s run(1)" % self.__class__.__name__ )
        load_package_manager_settings()

        global g_is_installation_complete
        g_is_installation_complete = 0

        try:
            packages_to_uninstall = get_packages_to_uninstall( IS_DOWNGRADE_INSTALLATION )

            log( _grade(), "Packages to %s: " % INSTALLATION_TYPE_NAME + str( packages_to_uninstall ) )
            package_manager = uninstall_packages( packages_to_uninstall )

            if not IS_DOWNGRADE_INSTALLATION:
                remove_channel()

                uninstall_files()
                uninstall_folders()

            attempt_to_uninstall_packagesmanager( packages_to_uninstall )

            if not IS_DOWNGRADE_INSTALLATION:
                uninstall_list_of_packages( package_manager, [(g_channel_settings['CHANNEL_PACKAGE_NAME'], False)] )

        except ( InstallationCancelled, NoPackagesAvailable ) as error:
            log( 1, str( error ) )
            g_is_installation_complete |= 3


def uninstall_packages(packages_to_uninstall):
    package_manager  = PackageManager()
    package_disabler = PackageDisabler()

    ask_user_for_which_packages_to_install( packages_to_uninstall )
    all_packages, dependencies = get_installed_repositories( package_manager )

    current_index  = 0
    packages_count = len( packages_to_uninstall )

    for package_name, pi in sequence_timer( packages_to_uninstall, info_frequency=0 ):
        current_index += 1
        progress       = progress_info( pi, set_progress )
        is_dependency  = is_package_dependency( package_name, dependencies, all_packages )

        log.insert_empty_line()
        log.insert_empty_line()

        log( 1, "%s %s of %d of %d: %s (%s)" % ( progress, INSTALLATION_TYPE_NAME,
                current_index, packages_count, str( package_name ), str( is_dependency ) ) )

        if is_dependency:
            log( 1, "Skipping the dependency as they are automatically uninstalled..." )
            continue

        if package_name == "Default":
            uninstall_default_package()
            continue

        if package_name in PACKAGES_TO_UNINSTAL_LATER:
            log( 1, "Skipping the %s of `%s`..." % ( INSTALLATION_TYPE_NAME, package_name ) )
            log( 1, "This package will be handled later." )
            continue

        silence_error_message_box(61.0)
        ignore_next_packages( package_disabler, package_name, packages_to_uninstall )

        package_manager.remove_package( package_name, is_dependency )
        remove_packages_from_list( package_name )

    return package_manager


def get_packages_to_uninstall(is_downgrade):
    filtered_packages     = []
    packages_to_uninstall = get_dictionary_key( g_channelSettings, 'packages_to_uninstall', [] )

    if is_downgrade:
        repositories_loaded    = load_repository_file( g_channel_settings['CHANNEL_REPOSITORY_FILE'], {} )
        packages_not_installed = get_dictionary_key( g_channelSettings, 'packages_not_installed', [] )

        install_exclusively    = g_channel_settings['PACKAGES_TO_INSTALL_EXCLUSIVELY'],
        is_exclusively_install = not not len( install_exclusively )

        if is_exclusively_install:
            repositories_loaded = set( repositories_loaded ).intersection( install_exclusively )

        packages_to_uninstall  = set( packages_to_uninstall + packages_not_installed ) - repositories_loaded

    for package_name in PACKAGES_TO_UNINSTALL_FIRST:

        # Only merges the packages which are actually being uninstalled
        if package_name in packages_to_uninstall:
            filtered_packages.append( package_name )

    # Add the remaining packages after the packages to install first
    for package_name in packages_to_uninstall:

        if package_name not in filtered_packages:
            filtered_packages.append( package_name )

    if not g_is_forced_uninstallation and len( filtered_packages ) < 1:
        raise NoPackagesAvailable( "There are 0 packages available to uninstall!" )

    if is_downgrade:
        log( 1, "New packages packages to uninstall found... " + str( filtered_packages ) )

    return filtered_packages


def get_installed_repositories(package_manager):
    dependencies = None
    all_packages = None

    if g_is_package_control_installed:
        _dependencies = package_manager.list_dependencies()
        dependencies  = set( _dependencies )
        all_packages  = set( _dependencies + get_installed_packages( list_default_packages=True ) )

    else:
        dependencies = set( package_manager.list_dependencies() )
        all_packages = set( package_manager.list_packages( list_everything=True ) )

    return all_packages, dependencies


def uninstall_default_package():
    log( 1, "%s of `Default Package` files..." % INSTALLATION_TYPE_NAME )

    files_installed       = get_dictionary_key( g_channelSettings, 'default_package_files', [] )
    default_packages_path = os.path.join( g_channel_settings['CHANNEL_ROOT_DIRECTORY'], "Packages", "Default" )

    for file in files_installed:
        file_path = os.path.join( default_packages_path, file )
        remove_only_if_exists( file_path )

    default_git_folder = os.path.join( default_packages_path, ".git" )
    remove_git_folder( default_git_folder, default_packages_path )


def remove_git_folder(default_git_folder, parent_folder=None):
    log( 1, "%s of default_git_folder: %s" % ( INSTALLATION_TYPE_NAME, str( default_git_folder ) ) )
    shutil.rmtree( default_git_folder, ignore_errors=True, onerror=_delete_read_only_file )

    if parent_folder:
        folders_not_empty = []
        recursively_delete_empty_folders( parent_folder, folders_not_empty )

        if len( folders_not_empty ) > 0:
            log( 1, "The installed default_git_folder `%s` could not be removed because is it not empty." % default_git_folder )
            log( 1, "Its files contents are: " + str( os.listdir( default_git_folder ) ) )


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
        last_ignored_packges    = packages_list.index( package_name )
        next_packages_to_ignore = packages_list[ last_ignored_packges : last_ignored_packges + PACKAGES_COUNT_TO_IGNORE_AHEAD + 1 ]

        # We never can ignore the Default package, otherwise several errors/anomalies show up
        intersection_set = PACKAGES_TO_NOT_ADD_TO_IGNORE_LIST.intersection( next_packages_to_ignore )

        if len( intersection_set ) > 0:
            next_packages_to_ignore = list( set( next_packages_to_ignore ) - intersection_set )

        log( 1, "Adding %d packages to be uninstalled to the `ignored_packages` setting list." % len( next_packages_to_ignore ) )
        log( 1, "next_packages_to_ignore: " + str( next_packages_to_ignore ) )

        # Add them to the in_process list
        package_disabler.disable_packages( next_packages_to_ignore, "remove" )
        unique_list_append( g_default_ignored_packages, next_packages_to_ignore )

        # Let the package be unloaded by Sublime Text while ensuring anyone is putting them back in
        add_packages_to_ignored_list( next_packages_to_ignore )


def is_package_dependency(package_name, dependencies, packages):
    """
        Return by default True to stop the uninstallation as the package not was not found on the
        `channel.json` repository file
    """
    if package_name in dependencies:
        return True

    if package_name in packages:
        return False

    log( 1, "Warning: The package name `%s` could not be found on the repositories_dictionary!" % package_name )
    return True


def install_package_control(package_manager):
    package_name = "Package Control"
    log.insert_empty_line()
    log.insert_empty_line()

    log( 1, "Installing: %s" % str( package_name ) )
    package_manager.install_package( package_name, False )


def remove_channel():
    channels = get_dictionary_key( g_package_control_settings, "channels", [] )

    while g_channel_settings['CHANNEL_FILE_URL'] in channels:
        log( 1, "Removing %s channel from Package Control settings: %s" % ( g_channel_settings['CHANNEL_PACKAGE_NAME'], str( channels ) ) )
        channels.remove( g_channel_settings['CHANNEL_FILE_URL'] )

    g_package_control_settings['channels'] = channels
    save_package_control_settings()


def save_package_control_settings():
    g_package_control_settings['installed_packages'] = g_installed_packages
    write_data_file( PACKAGE_CONTROL, g_package_control_settings )


def remove_packages_from_list(package_name):
    remove_if_exists( g_installed_packages, package_name )
    save_package_control_settings()

    unignore_user_packages( package_name )


def unignore_user_packages(package_name="", flush_everything=False):
    """
        There is a bug with the uninstalling several packages, which trigger several errors of:
        "It appears a package is trying to ignore itself, causing a loop.
        Please resolve by removing the offending ignored_packages setting."
        * Package Control: Advanced Install Package https://github.com/wbond/package_control/issues/1191

        When trying to uninstall several package at once, then here I am unignoring them all at once.
        @param flush_everything     set all remaining packages as unignored
    """

    if flush_everything:
        unignore_some_packages( g_packages_to_unignore + _uningored_packages_to_flush )

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
    is_there_unignored_packages = False

    for package_name in packages_list:

        if package_name in g_default_ignored_packages:
            is_there_unignored_packages = True

            log( 1, "Unignoring the package: %s" % package_name )
            g_default_ignored_packages.remove( package_name )

    if is_there_unignored_packages:
        g_user_settings.set( "ignored_packages", g_default_ignored_packages )
        sublime.save_settings( g_channel_settings['USER_SETTINGS_FILE'] )


def uninstall_packagesmanger(package_manager, installed_packages):
    """
        Uninstals PackagesManager only if Control was installed, otherwise the user will end up with
        no package manager.
    """

    # Only uninstall them when they were installed
    if "PackagesManager" in installed_packages:
        log.insert_empty_line()
        log.insert_empty_line()

        log( 1, "Finishing PackagesManager %s..." % INSTALLATION_TYPE_NAME )
        uninstall_list_of_packages( [ ("PackagesManager", False), ("0_packagesmanager_loader", None) ] )

        remove_0_packagesmanager_loader()
        clean_packagesmanager_settings()


def uninstall_list_of_packages(package_manager, packages_to_uninstall):
    """
        By last uninstall itself `g_channel_settings['CHANNEL_PACKAGE_NAME']` and let the package be
        unloaded by Sublime Text
    """
    log( 1, "uninstall_list_of_packages, %s... " % INSTALLATION_TYPE_NAME + str( packages_to_uninstall ) )
    packages_to_remove = []

    packages_to_remove.extend( packages_to_uninstall )
    add_packages_to_ignored_list( [ package_name for package_name, _ in packages_to_remove ] )

    for package_name, is_dependency in packages_to_remove:
        log.insert_empty_line()
        log.insert_empty_line()
        log( 1, "%s of: %s..." % ( INSTALLATION_TYPE_NAME, str( package_name ) ) )

        silence_error_message_box(62.0)
        package_manager.remove_package( package_name, is_dependency )


def remove_0_packagesmanager_loader():
    """
        Most times the 0_packagesmanager_loader is not being deleted/removed, then try again.
    """
    _packagesmanager_loader_path     = os.path.join( g_channel_settings['CHANNEL_ROOT_DIRECTORY'], "Installed Packages", "0_packagesmanager_loader.sublime-package" )
    _packagesmanager_loader_path_new = os.path.join( g_channel_settings['CHANNEL_ROOT_DIRECTORY'], "Installed Packages", "0_packagesmanager_loader.sublime-package-new" )

    remove_only_if_exists( _packagesmanager_loader_path )
    remove_only_if_exists( _packagesmanager_loader_path_new )


def add_packages_to_ignored_list(packages_list):
    """
        Something, somewhere is setting the ignored_packages list to `["Vintage"]`. Then ensure we
        override this.
    """
    ignored_packages = g_user_settings.get( "ignored_packages", [] )
    unique_list_append( ignored_packages, packages_list )

    for interval in range( 0, 27 ):
        g_user_settings.set( "ignored_packages", ignored_packages )
        sublime.save_settings( g_channel_settings['USER_SETTINGS_FILE'] )

        time.sleep(0.1)


def clean_packagesmanager_settings(maximum_attempts=3):
    """
        Clean it a few times because PackagesManager is kinda running and still flushing stuff down
        to its settings file.
    """
    log( 1, "Finishing PackagesManager %s... maximum_attempts: " % INSTALLATION_TYPE_NAME + str( maximum_attempts ) )

    if maximum_attempts == 3:
        write_data_file( PACKAGESMANAGER, {} )

    maximum_attempts -= 1

    # If we do not write nothing to package_control file, Sublime Text will create another
    remove_only_if_exists( PACKAGESMANAGER )

    if maximum_attempts > 0:
        sublime.set_timeout_async( lambda: clean_packagesmanager_settings( maximum_attempts ), 2000 )
        return

    global g_is_installation_complete
    g_is_installation_complete |= 2


def uninstall_folders():
    folders_to_remove = get_dictionary_key( g_channelSettings, "folders_to_uninstall", [] )

    log.insert_empty_line()
    log.insert_empty_line()
    log( 1, "%s of added folders: %s" % ( INSTALLATION_TYPE_NAME, str( folders_to_remove ) ) )

    for folder in reversed( folders_to_remove ):
        folders_not_empty = []
        log( 1, "Uninstalling folder: %s" % str( folder ) )

        folder_absolute_path = os.path.join( g_channel_settings['CHANNEL_ROOT_DIRECTORY'], folder )
        recursively_delete_empty_folders( folder_absolute_path, folders_not_empty )

    for folder in folders_to_remove:
        folders_not_empty = []
        log( 1, "Uninstalling folder: %s" % str( folder ) )

        folder_absolute_path = os.path.join( g_channel_settings['CHANNEL_ROOT_DIRECTORY'], folder )
        recursively_delete_empty_folders( folder_absolute_path, folders_not_empty )

    for folder in folders_to_remove:
        folders_not_empty = []
        log( 1, "Uninstalling folder: %s" % str( folder ) )

        folder_absolute_path = os.path.join( g_channel_settings['CHANNEL_ROOT_DIRECTORY'], folder )
        recursively_delete_empty_folders( folder_absolute_path, folders_not_empty )

        if len( folders_not_empty ) > 0:
            log( 1, "The installed folder `%s` could not be removed because is it not empty." % folder_absolute_path )
            log( 1, "Its files contents are: " + str( os.listdir( folder_absolute_path ) ) )


def recursively_delete_empty_folders(root_folder, folders_not_empty):
    """
        Recursively descend the directory tree rooted at top, calling the callback function for each
        regular file.

        Python script: Recursively remove empty folders/directories
        https://www.jacobtomlinson.co.uk/2014/02/16/python-script-recursively-remove-empty-folders-directories/
    """

    try:
        children_folders = os.listdir( root_folder )

        for child_folder in children_folders:
            child_path = os.path.join( root_folder, child_folder )

            if os.path.isdir( child_path ):
                recursively_delete_empty_folders( child_path, folders_not_empty )

                try:
                    os.removedirs( root_folder )
                    is_empty = True

                except OSError:
                    is_empty = False

                    try:
                        _removeEmptyFolders( root_folder )

                    except:
                        pass

                if not is_empty:
                    folders_not_empty.append( child_path )

        os.rmdir( root_folder )

    except:
        pass


def _removeEmptyFolders(path):

    if not os.path.isdir( path ):
        return

    files = os.listdir( path )

    if len( files ):

        for file in files:
            fullpath = os.path.join( path, file )

            if os.path.isdir( fullpath ):
                _removeEmptyFolders( fullpath )

    os.rmdir( path )


def uninstall_files():
    git_folders = []
    files_to_remove = get_dictionary_key( g_channelSettings, "files_to_uninstall", [] )

    log.insert_empty_line()
    log.insert_empty_line()
    log( 1, "%s of added files: %s" % ( INSTALLATION_TYPE_NAME, str( files_to_remove ) ) )

    for file in files_to_remove:
        log( 1, "Uninstalling file: %s" % str( file ) )
        file_absolute_path = os.path.join( g_channel_settings['CHANNEL_ROOT_DIRECTORY'], file )

        safe_remove( file_absolute_path )
        add_git_folder_by_file( file, git_folders )

    log( 1, "Removing git_folders..." )

    for git_folder in git_folders:
        remove_git_folder( git_folder )


def add_git_folder_by_file(file_relative_path, git_folders):
    match = re.search( "\.git", file_relative_path )

    if match:
        git_folder_relative = file_relative_path[:match.end(0)]

        if git_folder_relative not in git_folders:
            git_folders.append( git_folder_relative )


def ask_user_for_which_packages_to_install(packages_names):
    can_continue  = [False]
    active_window = sublime.active_window()

    install_message    = "Select this to not uninstall it."
    uninstall_message  = "Select this to uninstall it."

    selected_packages_to_not_install = []
    packages_informations            = \
    [
        [ "Cancel the %s Process" % INSTALLATION_TYPE_NAME, "Select this to cancel the %s process." % INSTALLATION_TYPE_NAME ],
        [ "Continue the %s Process..." % INSTALLATION_TYPE_NAME, "Select this when you are finished selecting packages." ],
    ]

    for package_name in packages_names:

        if package_name in g_channel_settings['FORBIDDEN_PACKAGES']:
            packages_informations.append( [ package_name, "You must uninstall it or cancel the %s." % INSTALLATION_TYPE_NAME ] )

        else:
            packages_informations.append( [ package_name, install_message ] )

    def on_done(item_index):

        if item_index < 1:
            global g_is_already_running
            g_is_already_running = False

            can_continue[0] = True
            return

        if item_index == 1:
            log.insert_empty_line()
            log( 1, "Continuing the %s after the packages pick up..." % INSTALLATION_TYPE_NAME )

            can_continue[0] = True
            return

        package_information = packages_informations[item_index]
        package_name        = package_information[0]

        if package_name not in g_channel_settings['FORBIDDEN_PACKAGES']:

            if package_information[1] == install_message:
                log( 1, "Keeping the package: %s" % package_name )

                package_information[1] = uninstall_message
                selected_packages_to_not_install.append( package_name )

            else:
                log( 1, "Removing the package: %s" % package_name )

                package_information[1] = install_message
                selected_packages_to_not_install.remove( package_name )

        else:
            log( 1, "The package %s must be uninstalled. " % package_name +
                    "If you do not want to uninstall this package, cancel the %s process." % INSTALLATION_TYPE_NAME )

        show_quick_panel( item_index )

    def show_quick_panel(selected_index=0):
        active_window.show_quick_panel( packages_informations, on_done, sublime.KEEP_OPEN_ON_FOCUS_LOST, selected_index )

    show_quick_panel()

    # show_quick_panel is a non-blocking function, but we can only continue after on_done being called
    while not can_continue[0]:
        time.sleep(1)

    # Show up the console, so the user can follow the process.
    sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )

    if not g_is_already_running:
        log.insert_empty_line()
        raise InstallationCancelled( "The user closed the installer's packages pick up list." )

    for package_name in selected_packages_to_not_install:
        target_index = packages_names.index( package_name )
        del packages_names[target_index]


def complete_channel_uninstallation(maximum_attempts=3):
    """
        Ensure the file is deleted
    """

    if maximum_attempts == 3:
        log.insert_empty_line()
        log.insert_empty_line()

        log( 1, "Uninstalling channel settings file: %s" % str( g_channel_settings['CHANNEL_INSTALLATION_DETAILS'] ) )
        write_data_file( g_channel_settings['CHANNEL_INSTALLATION_DETAILS'], {} )

    else:
        log( 1, "Uninstalling channel settings file, maximum_attempts: %s" % str( maximum_attempts ) )

    remove_only_if_exists( g_channel_settings['CHANNEL_INSTALLATION_DETAILS'] )

    if maximum_attempts > 0:
        maximum_attempts -= 1

        sublime.set_timeout_async( lambda: complete_channel_uninstallation( maximum_attempts ), 1000 )
        return

    sublime.message_dialog( end_user_message( """\
            The %s %s was successfully completed.

            You need to restart Sublime Text to unload the uninstalled packages and finish
            uninstalling the unused dependencies.

            Check you Sublime Text Console for more information.
            """ % ( g_channel_settings['CHANNEL_PACKAGE_NAME'], INSTALLATION_TYPE_NAME ) ) )

    sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )


def check_uninstalled_packages_alert(maximum_attempts=10):
    """
        Show a message to the user observing the Sublime Text console, so he know the process is not
        finished yet.
    """
    log( _grade(), "Looking for new tasks... %s seconds remaining." % str( maximum_attempts ) )
    maximum_attempts -= 1

    if maximum_attempts > 0 and g_is_already_running:
        sublime.set_timeout_async( lambda: check_uninstalled_packages_alert( maximum_attempts ), 1000 )


def check_uninstalled_packages(maximum_attempts=10):
    """
        Display warning when the uninstallation process is finished or ask the user to restart
        Sublime Text to finish the uninstallation.

        Compare the current uninstalled packages list with required packages to uninstall, and if
        they differ, attempt to uninstall they again for some times. If not successful, stop trying
        and warn the user.
    """
    log( _grade(), "Finishing %s... maximum_attempts: " % INSTALLATION_TYPE_NAME + str( maximum_attempts ) )
    maximum_attempts -= 1

    if g_is_installation_complete & 3:
        unignore_user_packages( flush_everything=True )

        if not IS_DOWNGRADE_INSTALLATION:
            complete_channel_uninstallation()

        else:
            global g_is_already_running
            g_is_already_running = False

        return

    if maximum_attempts > 0:
        sublime.set_timeout_async( lambda: check_uninstalled_packages( maximum_attempts ), 2000 )

    else:
        sublime.error_message( end_user_message( """\
                The %s %s could NOT be successfully completed.

                Check you Sublime Text Console for more information.

                If you want help fixing the problem, please, save your Sublime Text Console output
                so later others can see what happened try to fix it.
                """ % ( g_channel_settings['CHANNEL_PACKAGE_NAME'], INSTALLATION_TYPE_NAME ) ) )

        unignore_user_packages( flush_everything=True )
        sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )


def end_user_message(message):
    # This is here because it is almost the last thing to be done
    global g_is_already_running
    g_is_already_running = False

    return wrap_text( message )


def is_allowed_to_run():
    global g_is_already_running

    if g_is_already_running:
        print( "You are already running a command. Wait until it finishes or restart Sublime Text" )
        return False

    g_is_already_running = True
    return True


def unpack_settings(channel_settings, is_forced):
    global g_channel_settings
    global g_is_forced_uninstallation

    g_channel_settings       = channel_settings
    g_is_forced_uninstallation = is_forced

    global INSTALLATION_TYPE_NAME
    global IS_DOWNGRADE_INSTALLATION

    IS_DOWNGRADE_INSTALLATION = True if g_channel_settings['INSTALLATION_TYPE'] == "downgrade" else False
    INSTALLATION_TYPE_NAME    = "Downgrade" if IS_DOWNGRADE_INSTALLATION else "Uninstallation"

    log( 1, "IS_DOWNGRADE_INSTALLATION: " + str( IS_DOWNGRADE_INSTALLATION ) )
    setup_packages_to_uninstall_last( g_channel_settings )


def setup_packages_to_uninstall_last(channel_settings):
    """
        Remove the remaining packages to be uninstalled separately on another function call.
    """
    global PACKAGES_TO_UNINSTALL_FIRST
    global PACKAGES_TO_UNINSTAL_LATER
    global PACKAGES_TO_NOT_ADD_TO_IGNORE_LIST

    PACKAGES_TO_UNINSTAL_LATER = [ "PackagesManager", g_channel_settings['CHANNEL_PACKAGE_NAME'] ]
    PACKAGES_TO_UNINSTALL_FIRST       = list( reversed( channel_settings['PACKAGES_TO_INSTALL_LAST'] ) )

    # We need to remove it by last, after installing Package Control back
    for package in PACKAGES_TO_UNINSTAL_LATER:

        if package in PACKAGES_TO_UNINSTALL_FIRST:
            PACKAGES_TO_UNINSTALL_FIRST.remove( package )

    PACKAGES_TO_NOT_ADD_TO_IGNORE_LIST = set( PACKAGES_TO_UNINSTAL_LATER )
    PACKAGES_TO_NOT_ADD_TO_IGNORE_LIST.add( "Default" )


def attempt_to_uninstall_packagesmanager(packages_to_uninstall):

    if "PackagesManager" in packages_to_uninstall:
        package_manager    = PackageManager()
        installed_packages = package_manager.list_packages()

        if "Package Control" not in installed_packages:
            install_package_control( package_manager )

        uninstall_packagesmanger( package_manager, installed_packages )
        restore_the_remove_orphaned_setting()

    else:
        global g_is_installation_complete
        g_is_installation_complete |= 3


def restore_the_remove_orphaned_setting():

    if g_remove_orphaned_backup:
        # By default, it is already True on `Package Control.sublime-settings`, so just remove it
        del g_package_control_settings['remove_orphaned']

    else:
        g_package_control_settings['remove_orphaned'] = g_remove_orphaned_backup

    save_package_control_settings()

    global g_is_installation_complete
    g_is_installation_complete |= 1


def load_package_manager_settings():
    global _uningored_packages_to_flush
    _uningored_packages_to_flush = []

    packagesmanager_name = "PackagesManager.sublime-settings"
    package_control_name = "Package Control.sublime-settings"

    global PACKAGE_CONTROL
    global PACKAGESMANAGER

    global g_package_control_settings
    global g_installed_packages

    global g_user_settings
    global g_default_ignored_packages
    global g_remove_orphaned_backup

    global g_packages_to_unignore
    global g_channelSettings

    g_channelSettings      = load_data_file( g_channel_settings['CHANNEL_INSTALLATION_DETAILS'] )
    g_packages_to_unignore = get_dictionary_key( g_channelSettings, "packages_to_unignore", [] )

    log( _grade(), "Loaded g_channelSettings: " + str( g_channelSettings ) )

    PACKAGESMANAGER = os.path.join( g_channel_settings['USER_FOLDER_PATH'], packagesmanager_name )
    PACKAGE_CONTROL = os.path.join( g_channel_settings['USER_FOLDER_PATH'], package_control_name )

    g_user_settings            = sublime.load_settings( g_channel_settings['USER_SETTINGS_FILE'] )
    g_default_ignored_packages = g_user_settings.get( "ignored_packages", [] )

    # Allow to not override the Package Control file when PackagesManager does exists
    if os.path.exists( PACKAGESMANAGER ):
        g_package_control_settings = load_data_file( PACKAGESMANAGER )

    else:
        g_package_control_settings = load_data_file( PACKAGE_CONTROL )

    g_installed_packages     = get_dictionary_key( g_package_control_settings, 'installed_packages', [] )
    g_remove_orphaned_backup = get_dictionary_key( g_package_control_settings, 'remove_orphaned', True )

    if not IS_DOWNGRADE_INSTALLATION:

        # Temporally stops Package Control from removing orphaned packages, otherwise it will scroll up
        # the uninstallation when Package Control is installed back
        g_package_control_settings['remove_orphaned'] = False
        save_package_control_settings()

