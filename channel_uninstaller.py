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

from .settings import *

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


# When there is an ImportError, means that Package Control is installed instead of PackagesManager,
# or vice-versa. Which means we cannot do nothing as this is only compatible with PackagesManager.
try:
    from PackagesManager.packagesmanager.settings import disable_package_control_uninstaller
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


# Import the debugger
from PythonDebugTools.debug_tools import Debugger

# Debugger settings: 0 - disabled, 127 - enabled
log = Debugger( 127, os.path.basename( __file__ ) )

# log( 2, "..." )
# log( 2, "..." )
# log( 2, "Debugging" )
# log( 2, "CURRENT_DIRECTORY_: " + CURRENT_DIRECTORY )


def main(channel_settings):
    """
        Before calling this installer, the `Package Control` user settings file, must have the
        Channel file set before the default channel key `channels`.

        Also the current `Package Control` cache must be cleaned, ensuring it is downloading and
        using the Channel repositories/channel list.
    """
    log( 2, "Entering on %s main(0)" % CURRENT_PACKAGE_NAME )

    installer_thread = StartUninstallChannelThread( channel_settings )
    installer_thread.start()


def unpack_settings(channel_settings):
    global CHANNEL_INSTALLATION_SETTINGS
    global PACKAGES_TO_UNINSTALL_FIRST

    global USER_SETTINGS_FILE
    global CHANNEL_FILE_URL
    global FORBIDDEN_PACKAGES

    global USER_FOLDER_PATH
    global CHANNEL_ROOT_DIRECTORY
    global CHANNEL_PACKAGE_NAME

    CHANNEL_PACKAGE_NAME          = channel_settings['CHANNEL_PACKAGE_NAME']
    CHANNEL_INSTALLATION_SETTINGS = channel_settings['CHANNEL_INSTALLATION_SETTINGS']

    setup_packages_to_uninstall_last( channel_settings )

    CHANNEL_FILE_URL   = channel_settings['CHANNEL_FILE_URL']
    FORBIDDEN_PACKAGES = channel_settings['FORBIDDEN_PACKAGES']
    USER_SETTINGS_FILE = channel_settings['USER_SETTINGS_FILE']

    CHANNEL_ROOT_DIRECTORY = channel_settings['CHANNEL_ROOT_DIRECTORY']
    USER_FOLDER_PATH       = channel_settings['USER_FOLDER_PATH']


def setup_packages_to_uninstall_last(channel_settings):
    global PACKAGES_TO_UNINSTALL_FIRST
    global PACKAGES_TO_IGNORE_UNINSTALLATION
    global USER_FOLDER_PATH

    PACKAGES_TO_IGNORE_UNINSTALLATION  = [ "PackagesManager" ]
    PACKAGES_TO_UNINSTALL_FIRST        = list( reversed( channel_settings['PACKAGES_TO_INSTALL_LAST'] ) )

    # We need to remove it by last, after installing Package Control back
    for package in PACKAGES_TO_IGNORE_UNINSTALLATION:

        if package in PACKAGES_TO_UNINSTALL_FIRST:
            PACKAGES_TO_UNINSTALL_FIRST.remove( package )


class StartUninstallChannelThread(threading.Thread):

    def __init__(self, channel_settings):
        threading.Thread.__init__(self)
        self.channel_settings = channel_settings

    def run(self):
        """
            Python thread exit code
            https://stackoverflow.com/questions/986616/python-thread-exit-code
        """

        if is_allowed_to_run():
            unpack_settings(self.channel_settings)

            uninstaller_thread = UninstallChannelFilesThread()
            uninstaller_thread.start()

            ThreadProgress( uninstaller_thread, 'Uninstalling Sublime Text %s Packages...' % CHANNEL_PACKAGE_NAME,
                    'The %s was successfully installed.' % CHANNEL_PACKAGE_NAME )

            uninstaller_thread.join()

            # Wait PackagesManager to load the found dependencies, before announcing it to the user
            sublime.set_timeout_async( check_uninstalled_packages, 10000 )

        global g_is_already_running
        g_is_already_running = False


def is_allowed_to_run():
    global g_is_already_running

    if g_is_already_running:
        print( "You are already running a command. Wait until it finishes or restart Sublime Text" )
        return False

    g_is_already_running = True
    return True


class UninstallChannelFilesThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        log( 2, "Entering on %s run(1)" % self.__class__.__name__ )
        global g_is_installation_complete
        global g_channelSettings
        global g_packages_to_unignore
        global _uningored_packages_to_flush

        g_is_installation_complete = 0
        g_channelSettings           = load_data_file( CHANNEL_INSTALLATION_SETTINGS )

        _uningored_packages_to_flush = []

        log( 1, "Loaded g_channelSettings: " + str( g_channelSettings ) )
        g_packages_to_unignore = get_dictionary_key( g_channelSettings, "packages_to_unignore", [] )

        load_package_manager_settings()
        disable_amxmodx_errors()

        uninstall_packages()
        remove_channel()

        uninstall_files()
        uninstall_folders()

        finish_uninstallation()


def disable_amxmodx_errors():
    """
        Disable the error message when uninstalling it
    """
    disable_package_control_uninstaller()

    try:
        import amxmodx
        amxmodx.AMXXEditor.g_is_package_loading = True

    except( ImportError, AttributeError ):
        pass


def finish_uninstallation():
    package_manager    = PackageManager()
    installed_packages = package_manager.list_packages()

    if "Package Control" not in installed_packages:
        install_package_control( package_manager )

    uninstall_packagesmanger( package_manager, installed_packages )

    # Restore the remove_orphaned setting
    if g_remove_orphaned_backup:
        # By default, it is already True on `Package Control.sublime-settings`, so just remove it
        del g_package_control_settings['remove_orphaned']

    else:
        g_package_control_settings['remove_orphaned'] = g_remove_orphaned_backup

    write_data_file( PACKAGE_CONTROL, g_package_control_settings )
    g_is_installation_complete = 1


def load_package_manager_settings():
    packagesmanager_name = "PackagesManager.sublime-settings"
    package_control_name = "Package Control.sublime-settings"

    global PACKAGE_CONTROL
    global PACKAGESMANAGER

    global g_package_control_settings
    global g_installed_packages

    global g_user_settings
    global g_default_ignored_packages
    global g_remove_orphaned_backup

    PACKAGESMANAGER = os.path.join( USER_FOLDER_PATH, packagesmanager_name )
    PACKAGE_CONTROL = os.path.join( USER_FOLDER_PATH, package_control_name )

    g_user_settings            = sublime.load_settings( USER_SETTINGS_FILE )
    g_default_ignored_packages = g_user_settings.get( "ignored_packages", [] )

    # Allow to not override the Package Control file when PackagesManager does exists
    if os.path.exists( PACKAGESMANAGER ):
        g_package_control_settings = load_data_file( PACKAGESMANAGER )

    else:
        g_package_control_settings = load_data_file( PACKAGE_CONTROL )

    g_installed_packages     = get_dictionary_key( g_package_control_settings, 'installed_packages', [] )
    g_remove_orphaned_backup = get_dictionary_key( g_package_control_settings, 'remove_orphaned', True )

    # Temporally stops Package Control from removing orphaned packages, otherwise it will scroll up
    # the uninstallation when Package Control is installed back
    g_package_control_settings['remove_orphaned'] = False


def uninstall_packages():
    package_manager  = PackageManager()
    package_disabler = PackageDisabler()

    packages_to_uninstall = get_packages_to_uninstall()
    log( 2, "Packages to uninstall: " + str( packages_to_uninstall ) )

    current_index      = 0
    git_packages_count = len( packages_to_uninstall )

    if g_is_package_control_installed:
        _dependencies = package_manager.list_dependencies()
        dependencies  = set( _dependencies )
        all_packages  = set( package_manager.list_packages() + _dependencies + ['Default']
                + package_manager.list_default_packages() + get_installed_packages( "PackagesManager.sublime-settings" ) )

    else:
        all_packages = set( package_manager.list_packages( list_everything=True ) + get_installed_packages( "PackagesManager.sublime-settings" ) )
        dependencies = set( package_manager.list_dependencies() )

    ask_user_for_which_packages_to_install( packages_to_uninstall )
    uninstall_default_package( packages_to_uninstall )

    for package_name in packages_to_uninstall:
        silence_error_message_box(61.0)

        is_dependency  = is_package_dependency( package_name, dependencies, all_packages )
        current_index += 1

        log( 1, "\n\nUninstalling %d of %d: %s (%s)" % ( current_index, git_packages_count, str( package_name ), str( is_dependency ) ) )
        ignore_next_packages( package_disabler, package_name, packages_to_uninstall )

        package_manager.remove_package( package_name, is_dependency )
        remove_package_from_list( package_name )

    # Remove the remaining packages to be uninstalled
    remove_package_from_list( "PackagesManager" )
    remove_package_from_list( CHANNEL_PACKAGE_NAME )


def uninstall_default_package(packages_names):

    if 'Default' in packages_names:
        log( 1, "\n\nUninstalling `Default Package` files..." )
        default_packages_path = os.path.join( CHANNEL_ROOT_DIRECTORY, "Packages", "Default" )

        packages_names.remove('Default')
        files_installed = get_dictionary_key( g_channelSettings, 'default_packages_files', [] )

        for file in files_installed:

            file_path = os.path.join( default_packages_path, file )
            remove_only_if_exists( file_path )

        default_git_folder = os.path.join( default_packages_path, ".git" )
        remove_git_folder( default_git_folder, default_packages_path )


def remove_git_folder(default_git_folder, parent_folder=None):
    log( 1, "Uninstalling default_git_folder: %s" % str( default_git_folder ) )
    shutil.rmtree( default_git_folder, ignore_errors=True, onerror=_delete_read_only_file )

    if parent_folder:
        folders_not_empty = []
        recursively_delete_empty_folders( parent_folder, folders_not_empty )

        if len( folders_not_empty ) > 0:
            log( 1, "The installed default_git_folder `%s` could not be removed because is it not empty." % default_git_folder )
            log( 1, "Its files contents are: " + str( os.listdir( default_git_folder ) ) )


def get_packages_to_uninstall():
    filtered_packages     = []
    packages_to_uninstall = get_dictionary_key( g_channelSettings, 'packages_to_uninstall', [] )

    # Only merges the packages which are actually being uninstalled
    for package_name in PACKAGES_TO_UNINSTALL_FIRST:

        if package_name in packages_to_uninstall:
            filtered_packages.append( package_name )

    # Add the actual packages after the packages to install first
    for package_name in packages_to_uninstall:

        if package_name not in filtered_packages:
            filtered_packages.append( package_name )

    # Ignore everything except some packages, until it is finished
    for package_name in PACKAGES_TO_IGNORE_UNINSTALLATION:

        if package_name in filtered_packages:
            filtered_packages.remove( package_name )

    return filtered_packages


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

        log( 1, "Adding %d packages to be uninstalled to the `ignored_packages` setting list." % len( next_packages_to_ignore ) )
        log( 1, "next_packages_to_ignore: " + str( next_packages_to_ignore ) )

        # We never can ignore the Default package, otherwise several errors/anomalies show up
        if "Default" in next_packages_to_ignore:
            next_packages_to_ignore.remove( "Default" )

        # Add them to the in_process list
        package_disabler.disable_packages( next_packages_to_ignore, "remove" )
        unique_list_append( g_default_ignored_packages, next_packages_to_ignore )

        # Let the package be unloaded by Sublime Text while ensuring anyone is putting them back in
        add_packages_to_ignored_list( next_packages_to_ignore )


def is_package_dependency(package, dependencies, packages):
    """
        None when the package is not found.
    """
    if package in dependencies:
        return True

    if package in packages:
        return False

    return None


def install_package_control(package_manager):
    package_name = "Package Control"

    log( 1, "\n\nInstalling: %s" % str( package_name ) )
    package_manager.install_package( package_name, False )


def remove_channel():
    channels = get_dictionary_key( g_package_control_settings, "channels", [] )

    while CHANNEL_FILE_URL in channels:
        log( 1, "Removing %s channel from Package Control settings: %s" % ( CURRENT_PACKAGE_NAME, str( channels ) ) )
        channels.remove( CHANNEL_FILE_URL )

    g_package_control_settings['channels'] = channels
    save_package_control_settings()


def save_package_control_settings():
    g_package_control_settings['installed_packages'] = g_installed_packages
    write_data_file( PACKAGE_CONTROL, g_package_control_settings )


def remove_package_from_list(package_name):
    remove_if_exists( g_installed_packages, package_name )
    save_package_control_settings()

    unignore_user_packages( package_name )


def unignore_user_packages(package_name="", flush_everything=False):
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

    for package_name in packages_list:

        if package_name in g_default_ignored_packages:
            log( 1, "Unignoring the package: %s" % package_name )
            g_default_ignored_packages.remove( package_name )

    g_user_settings.set( "ignored_packages", g_default_ignored_packages )
    sublime.save_settings( USER_SETTINGS_FILE )


def uninstall_packagesmanger(package_manager, installed_packages):
    """
        Uninstals PackagesManager only if Control was installed, otherwise the user will end up with
        no package manager.
    """
    log(1, "\n\nFinishing PackagesManager Uninstallation..." )
    packages_to_remove = []

    # Only uninstall it when it is installed
    if "PackagesManager" in installed_packages:
        packages_to_remove.extend( [ ("PackagesManager", False), ("0_packagesmanager_loader", None) ] )

    # By last uninstall itself `CHANNEL_PACKAGE_NAME`
    packages_to_remove.extend( [ (CHANNEL_PACKAGE_NAME, False) ] )

    # Let the package be unloaded by Sublime Text1
    add_packages_to_ignored_list( [ package_name for package_name, _ in packages_to_remove ] )

    for package_name, is_dependency in packages_to_remove:
        log( 1, "\n\nUninstalling: %s..." % str( package_name ) )

        silence_error_message_box(62.0)
        package_manager.remove_package( package_name, is_dependency )

    remove_0_packagesmanager_loader()
    clean_packagesmanager_settings()


def remove_0_packagesmanager_loader():
    """
        Most times the 0_packagesmanager_loader is not being deleted/removed, then try again.
    """
    _packagesmanager_loader_path     = os.path.join( CHANNEL_ROOT_DIRECTORY, "Installed Packages", "0_packagesmanager_loader.sublime-package" )
    _packagesmanager_loader_path_new = os.path.join( CHANNEL_ROOT_DIRECTORY, "Installed Packages", "0_packagesmanager_loader.sublime-package-new" )

    remove_only_if_exists( _packagesmanager_loader_path )
    remove_only_if_exists( _packagesmanager_loader_path_new )


def remove_only_if_exists(file_path):

    if os.path.exists( file_path ):
        safe_remove( file_path )


def add_packages_to_ignored_list(packages_list):
    """
        Something, somewhere is setting the ignored_packages list to `["Vintage"]`. Then ensure we
        override this.
    """
    ignored_packages = g_user_settings.get( "ignored_packages", [] )
    unique_list_append( ignored_packages, packages_list )

    for interval in range( 0, 27 ):
        g_user_settings.set( "ignored_packages", ignored_packages )
        sublime.save_settings( USER_SETTINGS_FILE )

        time.sleep(0.1)


def clean_packagesmanager_settings(maximum_attempts=3):
    """
        Clean it a few times because PackagesManager is kinda running and still flushing stuff down
        to its settings file.
    """
    log( 1, "Finishing PackagesManager Uninstallation... maximum_attempts: " + str( maximum_attempts ) )

    if maximum_attempts == 3:
        write_data_file( PACKAGESMANAGER, {} )

    maximum_attempts -= 1

    # If we do not write nothing to package_control file, Sublime Text will create another
    remove_only_if_exists( PACKAGESMANAGER )

    if maximum_attempts > 0:
        sublime.set_timeout_async( lambda: clean_packagesmanager_settings( maximum_attempts ), 2000 )
        return

    global g_is_installation_complete
    g_is_installation_complete = 2


def uninstall_folders():
    folders_to_remove = get_dictionary_key( g_channelSettings, "folders_to_uninstall", [] )
    log( 1, "\n\nUninstalling added folders: %s" % str( folders_to_remove ) )

    for folder in reversed( folders_to_remove ):
        folders_not_empty = []
        log( 1, "Uninstalling folder: %s" % str( folder ) )

        folder_absolute_path = os.path.join( CHANNEL_ROOT_DIRECTORY, folder )
        recursively_delete_empty_folders( folder_absolute_path, folders_not_empty )

    for folder in folders_to_remove:
        folders_not_empty = []
        log( 1, "Uninstalling folder: %s" % str( folder ) )

        folder_absolute_path = os.path.join( CHANNEL_ROOT_DIRECTORY, folder )
        recursively_delete_empty_folders( folder_absolute_path, folders_not_empty )

    for folder in folders_to_remove:
        folders_not_empty = []
        log( 1, "Uninstalling folder: %s" % str( folder ) )

        folder_absolute_path = os.path.join( CHANNEL_ROOT_DIRECTORY, folder )
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
    log( 1, "\n\nUninstalling added files: %s" % str( files_to_remove ) )

    for file in files_to_remove:
        log( 1, "Uninstalling file: %s" % str( file ) )
        file_absolute_path = os.path.join( CHANNEL_ROOT_DIRECTORY, file )

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


def safe_remove(path):

    try:
        os.remove( path )

    except Exception as error:
        log( 1, "Failed to remove `%s`. Error is: %s" % ( path, error) )

        try:
            delete_read_only_file(path)

        except Exception as error:
            log( 1, "Failed to remove `%s`. Error is: %s" % ( path, error) )


def delete_channel_settings_file(maximum_attempts=3):
    """
        Ensure the file is deleted
    """
    if maximum_attempts == 3:
        log( 1, "\n\nUninstalling channel settings file: %s" % str( CHANNEL_INSTALLATION_SETTINGS ) )
        write_data_file( CHANNEL_INSTALLATION_SETTINGS, {} )

    else:
        log( 1, "Uninstalling channel settings file, maximum_attempts: %s" % str( maximum_attempts ) )

    remove_only_if_exists( CHANNEL_INSTALLATION_SETTINGS )

    if maximum_attempts > 0:
        maximum_attempts -= 1

        sublime.set_timeout_async( lambda: delete_channel_settings_file( maximum_attempts ), 1000 )
        return

    sublime.message_dialog( wrap_text( """\
            The %s uninstallation was successfully completed.

            You need to restart Sublime Text to unload the uninstalled packages and finish
            uninstalling the unused dependencies.

            Check you Sublime Text Console for more information.
            """ % CHANNEL_PACKAGE_NAME ) )

    sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )


def ask_user_for_which_packages_to_install(packages_names):
    can_continue  = [False]
    active_window = sublime.active_window()

    install_message    = "Select this to not uninstall it."
    uninstall_message  = "Select this to uninstall it."

    selected_packages_to_not_install = []
    packages_informations            = \
    [
        [ "Cancel the Uninstallation Process", "Select this to cancel the uninstallation process." ],
        [ "Continue the Uninstallation Process...", "Select this when you are finished selecting packages." ],
    ]

    for package_name in packages_names:

        if package_name in FORBIDDEN_PACKAGES:
            packages_informations.append( [ package_name, "You must uninstall it or cancel the uninstallation." ] )

        else:
            packages_informations.append( [ package_name, install_message ] )

    def on_done(item_index):

        if item_index < 1:
            global g_is_already_running
            g_is_already_running = False

            log.insert_empty_line( 1 )
            raise RuntimeError( "The user closed the uninstaller's packages pick up list." )

        if item_index == 1:
            log.insert_empty_line( 1 )
            log( 1, "Continuing the uninstallation after the packages pick up..." )

            can_continue[0] = True
            return

        package_information = packages_informations[item_index]
        package_name        = package_information[0]

        if package_name not in FORBIDDEN_PACKAGES:

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
                    "If you do not want to uninstall this package, cancel the uninstallation process." )

        show_quick_panel( item_index )

    def show_quick_panel(selected_index=0):
        active_window.show_quick_panel( packages_informations, on_done, sublime.KEEP_OPEN_ON_FOCUS_LOST, selected_index )

    show_quick_panel()

    # show_quick_panel is a non-blocking function, but we can only continue after on_done being called
    while not can_continue[0]:
        time.sleep(1)

    for package_name in selected_packages_to_not_install:
        target_index = packages_names.index( package_name )

        del packages_names[target_index]


def check_uninstalled_packages(maximum_attempts=10):
    """
        Display warning when the uninstallation process is finished or ask the user to restart
        Sublime Text to finish the uninstallation.

        Compare the current uninstalled packages list with required packages to uninstall, and if
        they differ, attempt to uninstall they again for some times. If not successful, stop trying
        and warn the user.
    """
    log( 1, "Finishing Uninstallation... maximum_attempts: " + str( maximum_attempts ) )
    maximum_attempts -= 1

    if g_is_installation_complete & 3:
        unignore_user_packages(flush_everything=True)

        delete_channel_settings_file()
        return

    if maximum_attempts > 0:
        sublime.set_timeout_async( lambda: check_uninstalled_packages( maximum_attempts ), 2000 )

    else:
        sublime.error_message( wrap_text( """\
                The %s uninstallation could not be successfully completed.

                Check you Sublime Text Console for more information.

                If you want help fixing the problem, please, save your Sublime Text Console output
                so later others can see what happened try to fix it.
                """ % CHANNEL_PACKAGE_NAME ) )

        sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )
        unignore_user_packages(flush_everything=True)


