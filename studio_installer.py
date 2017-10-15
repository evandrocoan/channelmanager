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
import time
import shutil

import io
import json
import shlex
import threading


# https://stackoverflow.com/questions/14087598/python-3-importerror-no-module-named-configparser
try:
    import configparser
    from configparser import NoOptionError

except:
    from six.moves import configparser
    from six.moves.configparser import NoOptionError


from .settings import *
g_is_already_running = False

from .studio_utilities import get_installed_packages
from .studio_utilities import unique_list_join
from .studio_utilities import write_data_file
from .studio_utilities import get_dictionary_key
from .studio_utilities import string_convert_list
from .studio_utilities import add_item_if_not_exists
from .studio_utilities import delete_read_only_file
from .studio_utilities import wrap_text

from collections import OrderedDict


# When there is an ImportError, means that Package Control is installed instead of PackagesManager,
# or vice-versa. Which means we cannot do nothing as this is only compatible with PackagesManager.
try:
    from package_control import cmd
    from package_control.download_manager import downloader

    from package_control.package_manager import PackageManager
    from package_control.package_disabler import PackageDisabler

    from package_control.thread_progress import ThreadProgress
    from package_control.commands.advanced_install_package_command import AdvancedInstallPackageThread

except ImportError:
    pass


# Import the debugger
from debug_tools import Debugger

# Debugger settings: 0 - disabled, 127 - enabled
log = Debugger( 127, os.path.basename( __file__ ) )

# log( 2, "..." )
# log( 2, "..." )
# log( 2, "Debugging" )
# log( 2, "CURRENT_DIRECTORY_:     " + CURRENT_DIRECTORY )


def main(channel_settings):
    """
        Before calling this installer, the `Package Control` user settings file, must have the
        Studio Channel file set before the default channel key `channels`.

        Also the current `Package Control` cache must be cleaned, ensuring it is downloading and
        using the Studio Channel repositories/channel list.
    """
    log( 2, "Entering on %s main(0)" % CURRENT_PACKAGE_NAME )

    installer_thread = StartInstallStudioThread(channel_settings)
    installer_thread.start()


def unpack_settings(channel_settings):
    global USER_SETTINGS_FILE
    global DEFAULT_PACKAGES_FILES
    global TEMPORARY_FOLDER_TO_USE

    global PACKAGES_TO_NOT_INSTALL
    global PACKAGES_TO_INSTALL_LAST

    global STUDIO_MAIN_URL
    global STUDIO_SETTINGS_URL
    global STUDIO_SETTINGS_PATH
    global STUDIO_PACKAGE_NAME

    global STUDIO_MAIN_DIRECTORY
    global IS_DEVELOPMENT_INSTALL
    global STUDIO_INSTALLATION_SETTINGS
    global USER_FOLDER_PATH

    IS_DEVELOPMENT_INSTALL       = True if channel_settings['INSTALLATION_TYPE'] == "development" else False
    STUDIO_INSTALLATION_SETTINGS = channel_settings['STUDIO_INSTALLATION_SETTINGS']

    STUDIO_MAIN_URL      = channel_settings['STUDIO_MAIN_URL']
    STUDIO_SETTINGS_URL  = channel_settings['STUDIO_SETTINGS_URL']
    STUDIO_SETTINGS_PATH = channel_settings['STUDIO_SETTINGS_PATH']
    STUDIO_PACKAGE_NAME  = channel_settings['STUDIO_PACKAGE_NAME']

    USER_SETTINGS_FILE      = channel_settings['USER_SETTINGS_FILE']
    DEFAULT_PACKAGES_FILES  = channel_settings['DEFAULT_PACKAGES_FILES']
    TEMPORARY_FOLDER_TO_USE = channel_settings['TEMPORARY_FOLDER_TO_USE']

    STUDIO_MAIN_DIRECTORY    = channel_settings['STUDIO_MAIN_DIRECTORY']
    PACKAGES_TO_NOT_INSTALL  = channel_settings['PACKAGES_TO_NOT_INSTALL']
    PACKAGES_TO_INSTALL_LAST = channel_settings['PACKAGES_TO_INSTALL_LAST']
    USER_FOLDER_PATH         = channel_settings['USER_FOLDER_PATH']


class StartInstallStudioThread(threading.Thread):

    def __init__(self, channel_settings):
        threading.Thread.__init__(self)
        self.channel_settings = channel_settings

    def run(self):
        """
            Python thread exit code
            https://stackoverflow.com/questions/986616/python-thread-exit-code
        """

        if is_allowed_to_run():
            global g_is_installation_complete
            g_is_installation_complete = False

            unpack_settings(self.channel_settings)

            installer_thread  = InstallStudioFilesThread()
            installation_type = self.channel_settings['INSTALLATION_TYPE']

            installer_thread.start()
            ThreadProgress( installer_thread, 'Installing Sublime Text Studio %s Packages' % installation_type,
                    'Sublime Text Studio %s was successfully installed.' % installation_type )

            installer_thread.join()
            set_default_settings_after(1)

            # Wait PackagesManager to load the found dependencies, before announcing it to the user
            sublime.set_timeout_async( check_installed_packages, 6000 )

        global g_is_already_running
        g_is_already_running = False


def is_allowed_to_run():
    global g_is_already_running

    if g_is_already_running:
        print( "You are already running a command. Wait until it finishes or restart Sublime Text" )
        return False

    g_is_already_running = True
    return True


class InstallStudioFilesThread(threading.Thread):

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

    global g_studioSettings
    global g_packagesmanager_settings

    g_studioSettings           = load_data_file( STUDIO_INSTALLATION_SETTINGS )
    g_packagesmanager_settings = sublime.load_settings( g_packagesmanager_name )

    global g_packages_to_uninstall
    global g_files_to_uninstall
    global g_folders_to_uninstall
    global g_packages_to_unignore

    g_packages_to_uninstall = load_list_if_exists( g_studioSettings, 'packages_to_uninstall', [] )
    g_packages_to_unignore  = load_list_if_exists( g_studioSettings, 'packages_to_unignore', [] )
    g_files_to_uninstall    = load_list_if_exists( g_studioSettings, 'files_to_uninstall', [] )
    g_folders_to_uninstall  = load_list_if_exists( g_studioSettings, 'folders_to_uninstall', [] )


def load_list_if_exists(dictionary_to_search, item_to_load, default_value):

    if item_to_load in dictionary_to_search:
        return dictionary_to_search[item_to_load]

    return default_value


def install_modules(command_line_interface, git_executable_path):
    log( 2, "install_modules_, PACKAGES_TO_NOT_INSTALL: " + str( PACKAGES_TO_NOT_INSTALL ) )

    if IS_DEVELOPMENT_INSTALL:
        clone_sublime_text_studio( command_line_interface, git_executable_path )
        download_not_packages_submodules( command_line_interface, git_executable_path )

        load_ignored_packages()
        packages_to_install = get_development_packages()

        log( 2, "install_modules, packages_to_install: " + str( packages_to_install ) )
        install_development_packages( packages_to_install, git_executable_path, command_line_interface )

    else:
        load_ignored_packages()

        git_modules_file    = download_text_file( get_git_modules_url() )
        packages_to_install = get_stable_packages( git_modules_file )

        log( 2, "install_modules, packages_to_install: " + str( packages_to_install ) )
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
    set_default_settings_before( packages_to_install )

    # Package Control: Advanced Install Package
    # https://github.com/wbond/package_control/issues/1191
    # thread = AdvancedInstallPackageThread( packages_to_install )
    # thread.start()
    # thread.join()

    package_manager = PackageManager()
    log( 2, "install_stable_packages, PACKAGES_TO_NOT_INSTALL: " + str( PACKAGES_TO_NOT_INSTALL ) )

    current_index      = 0
    git_packages_count = len( packages_to_install )

    for package_name, is_dependency in packages_to_install:
        current_index += 1

        # # For quick testing
        # if current_index > 3:
        #     break
        log( 1, "\n\nInstalling %d of %d: %s (%s)" % ( current_index, git_packages_count, str( package_name ), str( is_dependency ) ) )

        package_manager.install_package( package_name, is_dependency )
        add_package_to_installation_list( package_name )


def get_stable_packages(git_modules_file):
    """
        python ConfigParser: read configuration from string
        https://stackoverflow.com/questions/27744058/python-configparser-read-configuration-from-string
    """
    index    = 0
    packages = []

    gitModulesFile     = configparser.RawConfigParser()
    installed_packages = get_installed_packages( "Package Control.sublime-settings" )

    log( 2, "get_stable_packages, installed_packages: " + str( installed_packages ) )
    gitModulesFile.readfp( io.StringIO( git_modules_file ) )

    packages_tonot_install = unique_list_join( PACKAGES_TO_NOT_INSTALL, installed_packages, g_packages_to_ignore )
    log( 2, "get_stable_packages, packages_tonot_install: " + str( packages_tonot_install ) )

    for section in gitModulesFile.sections():
        # # For quick testing
        # index += 1
        # if index > 7:
        #     break

        path = gitModulesFile.get( section, "path" )
        log( 2, "get_stable_packages, path: " + path )

        if 'Packages' == path[0:8]:
            package_name            = os.path.basename( path )
            submodule_absolute_path = os.path.join( STUDIO_MAIN_DIRECTORY, path )

            if not os.path.isdir( submodule_absolute_path ) \
                    and package_name not in packages_tonot_install:

                packages.append( ( package_name, is_dependency( gitModulesFile, section ) ) )

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


def load_ignored_packages():
    global g_user_settings
    global g_studio_settings

    g_user_settings = sublime.load_settings( USER_SETTINGS_FILE )

    if IS_DEVELOPMENT_INSTALL:
        g_studio_settings = load_data_file( STUDIO_SETTINGS_PATH )

    else:
        channel_settings_file = download_text_file( STUDIO_SETTINGS_URL )
        g_studio_settings     = json.loads( channel_settings_file )

    global g_default_ignored_packages
    global g_packages_to_ignore

    # `g_default_ignored_packages` contains the original user's ignored packages.
    g_default_ignored_packages = g_user_settings.get( 'ignored_packages', [] )
    g_packages_to_ignore       = get_dictionary_key( g_studio_settings, 'packages_to_ignore', [] )

    log( 2, "load_ignored_packages, g_packages_to_ignore:    " + str( g_packages_to_ignore ) )
    log( 2, "load_ignored_packages, g_default_ignored_packages: " + str( g_default_ignored_packages ) )


def is_dependency(gitModulesFile, section):

    if gitModulesFile.has_option( section, "dependency" ):
        dependency_list = string_convert_list( gitModulesFile.get( section, "dependency" ) )

        if len( dependency_list ) > 0:

            try:
                int( dependency_list[0] )
                return True

            except ValueError:
                return False

    return False


def get_git_modules_url():
    return STUDIO_MAIN_URL.replace("//github.com/", "//raw.githubusercontent.com/") + "/master/.gitmodules"


def download_text_file( git_modules_url ):
    settings = {}
    downloaded_contents = None

    with downloader( git_modules_url, settings ) as manager:
        downloaded_contents = manager.fetch( git_modules_url, 'Error downloading git_modules_url: ' + git_modules_url )

    return downloaded_contents.decode('utf-8')


def load_data_file(file_path):
    channel_dictionary = {}

    if os.path.exists( file_path ):

        with open( file_path, 'r', encoding='utf-8' ) as studio_channel_data:
            channel_dictionary = json.load( studio_channel_data )

    else:
        log( 1, "Error on load_data_file(1), the file '%s' does not exists!" % file_path )

    return channel_dictionary


def clone_sublime_text_studio(command_line_interface, git_executable_path):
    """
        Clone the main repository `https://github.com/evandrocoan/SublimeTextStudio`
        and install it on the Sublime Text Data folder.
    """
    main_git_folder         = os.path.join( STUDIO_MAIN_DIRECTORY, ".git" )
    studio_temporary_folder = os.path.join( STUDIO_MAIN_DIRECTORY, TEMPORARY_FOLDER_TO_USE )

    if not os.path.exists( main_git_folder ):
        log( 1, "The folder '%s' already exists. You already has some custom studio git installation." % main_git_folder)
        download_main_repository( command_line_interface, git_executable_path, studio_temporary_folder )

        copy_overrides( studio_temporary_folder, STUDIO_MAIN_DIRECTORY )
        shutil.rmtree( studio_temporary_folder, onerror=delete_read_only_file )

        # Progressively saves the installation data, in case the user closes Sublime Text
        set_default_settings_after()


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


def convert_absolute_path_to_relative(path):
    relative_path = os.path.commonprefix( [ STUDIO_MAIN_DIRECTORY, path ] )
    relative_path = os.path.normpath( path.replace( relative_path, "" ) )

    return convert_to_unix_path(relative_path)


def convert_to_unix_path(relative_path):
    relative_path = relative_path.replace( "\\", "/" )

    if relative_path.startswith( "/" ):
        relative_path = relative_path[1:]

    return relative_path


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


def download_main_repository(command_line_interface, git_executable_path, studio_temporary_folder):
    log( 1, "download_main_repository, \n\nInstalling: %s" % ( str( STUDIO_MAIN_URL ) ) )

    if os.path.isdir( studio_temporary_folder ):
        shutil.rmtree( studio_temporary_folder )

    command = shlex.split( '"%s" clone "%s" "%s"' % ( git_executable_path, STUDIO_MAIN_URL, TEMPORARY_FOLDER_TO_USE ) )
    output  = str( command_line_interface.execute( command, cwd=STUDIO_MAIN_DIRECTORY ) )

    log( 1, "download_main_repository, output: " + str( output ) )
    studio_temporary_packages_folder = os.path.join( studio_temporary_folder, "Packages" )

    shutil.rmtree( studio_temporary_packages_folder )


def download_not_packages_submodules(command_line_interface, git_executable_path):
    log( 1, "download_not_packages_submodules" )

    gitFilePath    = os.path.join( STUDIO_MAIN_DIRECTORY, '.gitmodules' )
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
            submodule_absolute_path = os.path.join( STUDIO_MAIN_DIRECTORY, path )

            # How to check to see if a folder contains files using python 3
            # https://stackoverflow.com/questions/25675352/how-to-check-to-see-if-a-folder-contains-files-using-python-3
            try:
                os.rmdir( submodule_absolute_path )
                is_empty = True

            except OSError:
                is_empty = False

            if is_empty:
                log( 1, "download_not_packages_submodules, \n\nInstalling: %s" % ( str( url ) ) )

                command = shlex.split( '"%s" clone "%s" "%s"' % ( git_executable_path, url, path ) )
                output  = str( command_line_interface.execute( command, cwd=STUDIO_MAIN_DIRECTORY ) )

                add_folders_and_files_for_removal( submodule_absolute_path, path )
                log( 1, "download_not_packages_submodules, output: " + str( output ) )

                # Progressively saves the installation data, in case the user closes Sublime Text
                set_default_settings_after()


def install_development_packages(packages_to_install, git_executable_path, command_line_interface):
    set_default_settings_before( packages_to_install )
    log( 2, "install_submodules_packages, PACKAGES_TO_NOT_INSTALL: " + str( PACKAGES_TO_NOT_INSTALL ) )

    current_index      = 0
    git_packages_count = len( packages_to_install )

    for package_name, url, path in packages_to_install:
        current_index += 1

        # # For quick testing
        # if current_index > 3:
        #     break

        log( 1, "\n\nInstalling %d of %d: %s" % ( current_index, git_packages_count, str( package_name ) ) )

        command = shlex.split( '"%s" clone --recursive "%s" "%s"' % ( git_executable_path, url, path) )
        output  = str( command_line_interface.execute( command, cwd=STUDIO_MAIN_DIRECTORY ) )

        command = shlex.split( '"%s" checkout master' % ( git_executable_path ) )
        output += "\n" + str( command_line_interface.execute( command, cwd=os.path.join( STUDIO_MAIN_DIRECTORY, path ) ) )

        log( 1, "install_development_packages, output: " + str( output ) )
        add_package_to_installation_list( package_name )


def get_development_packages():
    gitFilePath    = os.path.join( STUDIO_MAIN_DIRECTORY, '.gitmodules' )
    gitModulesFile = configparser.RawConfigParser()

    index = 0
    installed_packages = get_installed_packages( "Package Control.sublime-settings" )

    packages_tonot_install = unique_list_join( PACKAGES_TO_NOT_INSTALL, installed_packages )
    log( 2, "get_development_packages, packages_tonot_install: " + str( packages_tonot_install ) )

    packages = []
    gitModulesFile.read( gitFilePath )

    for section in gitModulesFile.sections():
        url  = gitModulesFile.get( section, "url" )
        path = gitModulesFile.get( section, "path" )

        # # For quick testing
        # index += 1
        # if index > 3:
        #     break

        if 'Packages' == path[0:8]:
            package_name            = os.path.basename( path )
            submodule_absolute_path = os.path.join( STUDIO_MAIN_DIRECTORY, path )

            if not os.path.isdir( submodule_absolute_path ) \
                    and package_name not in packages_tonot_install :

                packages.append( ( package_name, url, path ) )
                log( 2, "get_development_packages, path: " + path )

    # return \
    # [
    #     ('Active View Jump Back', 'https://github.com/evandrocoan/SublimeActiveViewJumpBack', 'Packages/Active View Jump Back'),
    #     ('amxmodx', 'https://github.com/evandrocoan/SublimeAMXX_Editor', 'Packages/amxmodx'),
    #     ('Amxx Pawn', 'https://github.com/evandrocoan/SublimeAmxxPawn', 'Packages/Amxx Pawn'),
    #     ('Clear Cursors Carets', 'https://github.com/evandrocoan/ClearCursorsCarets', 'Packages/Clear Cursors Carets'),
    #     ('Notepad++ Color Scheme', 'https://github.com/evandrocoan/SublimeNotepadPlusPlusTheme', 'Packages/Notepad++ Color Scheme'),
    #     ('PackagesManager', 'https://github.com/evandrocoan/package_control', 'Packages/PackagesManager'),
    #     ('Toggle Words', 'https://github.com/evandrocoan/ToggleWords', 'Packages/Toggle Words'),
    #     ('Default', 'https://github.com/evandrocoan/SublimeDefault', 'Packages/Default'),
    # ]

    return packages


def set_default_settings_before(packages_to_install):
    """
        Set some package to be enabled at last due their settings being dependent on other packages
        which need to be installed first.

        This also disables all development disabled packages, when installing the development
        version. It sets the current user's `ignored_packages` settings including all packages
        already disabled and the new packages to be installed and must be disabled before attempting
        to install them.
    """
    set_last_packages_to_install( packages_to_install )

    # The development version does not need to ignore all installed packages before starting the
    # installation process as it is not affected by the Sublime Text bug.
    if IS_DEVELOPMENT_INSTALL:
        set_development_ignored_packages( packages_to_install )


def set_development_ignored_packages(packages_to_install):

    for package_name in g_packages_to_ignore:

        # Only ignore the packages which are being installed
        if package_name in packages_to_install and package_name not in g_default_ignored_packages:
            g_default_ignored_packages.append( package_name )
            add_item_if_not_exists( g_packages_to_unignore, package_name )

    g_user_settings.set( 'ignored_packages', g_default_ignored_packages )
    log( 1, "set_default_settings_before, g_user_settings: " + str( g_user_settings.get("ignored_packages") ) )

    # Save our changes to the user ignored packages list
    sublime.save_settings( USER_SETTINGS_FILE )


def set_last_packages_to_install(packages_to_install):
    """
        Ignore everything except some packages, until it is finished
    """
    last_packages = {}

    for package_name in packages_to_install:

        if package_name[0] in PACKAGES_TO_INSTALL_LAST:
            last_packages[package_name[0]] = package_name
            packages_to_install.remove( package_name )

    for package_name in PACKAGES_TO_INSTALL_LAST:

        if package_name in last_packages:
            packages_to_install.append( last_packages[package_name] )


def sync_package_control_and_manager():
    """
        When the installation is going on the PackagesManager will be installed. If the user restart
        Sublime Text after doing it, on the next time Sublime Text starts, the Package Control and
        the PackagesManager will kill each other and probably end up uninstalling all the packages
        installed.

        This happens due their configurations files list different sets of packages. So to fix this
        we need to keep both files synced while the installation process is going on.
    """
    # Ensure they exists on the User folder
    sublime.load_settings( g_package_control_name )
    sublime.save_settings( g_package_control_name )

    package_control = os.path.join( USER_FOLDER_PATH, g_package_control_name )

    package_control_settings = load_data_file( package_control )
    ensure_installed_packages_name( package_control_settings )

    packagesmanager = os.path.join( USER_FOLDER_PATH, g_packagesmanager_name )
    write_data_file( packagesmanager, package_control_settings )


def ensure_installed_packages_name(package_control_settings):
    """
        Ensure the installed packages names are on the settings files.
    """

    if "installed_packages" in package_control_settings:
        installed_packages = package_control_settings['installed_packages']
        add_item_if_not_exists( installed_packages, "Package Control" )

    else:
        package_control_settings['installed_packages'] = [ "Package Control" ]


def set_default_settings_after(print_settings=0):
    """
        Populate the global variable `g_default_ignored_packages` with the packages this installation
        process added to the user's settings files and also save it to the file system. So later
        when uninstalling this studio we can only remove our packages, keeping the user's original
        ignored packages intact.
    """
    global g_studioSettings

    if 'Default' in g_packages_to_uninstall:
        g_studioSettings['default_packages_files'] = DEFAULT_PACKAGES_FILES

    # `packages_to_uninstall` and `packages_to_unignore` are to uninstall and unignore they when
    # uninstalling the studio channel
    g_studioSettings['packages_to_uninstall'] = g_packages_to_uninstall
    g_studioSettings['packages_to_unignore']  = g_packages_to_unignore
    g_studioSettings['files_to_uninstall']    = g_files_to_uninstall
    g_studioSettings['folders_to_uninstall']  = g_folders_to_uninstall

    g_studioSettings = sort_dictionary( g_studioSettings )

    log( 1 & print_settings, "set_default_settings_after, g_studioSettings: " + json.dumps( g_studioSettings, indent=4 ) )
    write_data_file( STUDIO_INSTALLATION_SETTINGS, g_studioSettings )


def sort_dictionary(dictionary):
    return OrderedDict( sorted( dictionary.items() ) )


def add_package_to_installation_list(package_name):
    """
        When the installation is going on the PackagesManager will be installed. If the user restart
        Sublime Text after doing it, on the next time Sublime Text starts, the Package Control and
        the PackagesManager will kill each other and probably end up uninstalling all the packages
        installed.
    """
    installed_packages = g_packagesmanager_settings.get( 'installed_packages', [] )

    add_item_if_not_exists( installed_packages, package_name )
    add_item_if_not_exists( g_packages_to_uninstall, package_name )

    g_packagesmanager_settings.set( 'installed_packages', installed_packages )
    sublime.save_settings( g_packagesmanager_name )

    # Progressively saves the installation data, in case the user closes Sublime Text
    set_default_settings_after()


def uninstall_package_control():
    """
        Uninstals package control only if PackagesManager was installed, otherwise the user will end
        up with no package manager.
    """
    installed_packages = g_packagesmanager_settings.get( 'installed_packages', [] )

    if "PackagesManager" in installed_packages:
        installed_packages.remove( "Package Control" )

        g_packagesmanager_settings.set( 'installed_packages', installed_packages )
        sublime.save_settings( g_package_control_name )

        # Sublime Text is waiting the current thread to finish before loading the just installed
        # PackagesManager, therefore run a new thread delayed which finishes the job
        sublime.set_timeout_async( complete_package_control, 2000 )

    else:
        log( 1, "\n\nWarning: PackagesManager is was not installed on the system!" )
        global g_is_installation_complete
        g_is_installation_complete = True


def complete_package_control(maximum_attempts=3):
    log(1, "Finishing Package Control Uninstallation... maximum_attempts: " + str( maximum_attempts ) )

    # Import the recent installed PackagesManager
    try:
        from PackagesManager.packagesmanager.show_error import silence_error_message_box
        from PackagesManager.packagesmanager.package_manager import PackageManager
        from PackagesManager.packagesmanager.package_disabler import PackageDisabler

    except ImportError:

        if maximum_attempts > 0:
            maximum_attempts -= 1

            sublime.set_timeout_async( lambda: complete_package_control( maximum_attempts ), 2000 )
            return

        else:
            log( 1, "Error! Could not complete the Package Control uninstalling, missing import for `PackagesManager`." )

    silence_error_message_box(300)
    packages_to_remove = [ ("Package Control", False), ("0_package_control_loader", None) ]

    package_manager  = PackageManager()
    package_disabler = PackageDisabler()

    package_disabler.disable_packages( [ package_name for package_name, _ in packages_to_remove ], "remove" )
    time.sleep(1.7)

    for package_name, is_dependency in packages_to_remove:
        log( 1, "\n\nUninstalling: %s" % str( package_name ) )

        package_manager.remove_package( package_name, is_dependency )

    sync_package_control_and_manager()
    clean_package_control_settings()


def clean_package_control_settings(maximum_attempts=3):
    """
        Clean it a few times because Package Control is kinda running and still flushing stuff down
        to its settings file.
    """
    log( 1, "Finishing Package Control Uninstallation... maximum_attempts: " + str( maximum_attempts ) )
    maximum_attempts -= 1
    package_control   = os.path.join( USER_FOLDER_PATH, g_package_control_name )

    # If we do not write nothing to package_control file, Sublime Text will create another
    write_data_file( package_control, {} )
    os.remove( package_control )

    if maximum_attempts > 0:
        sublime.set_timeout_async( lambda: clean_package_control_settings( maximum_attempts ), 2000 )

    global g_is_installation_complete
    g_is_installation_complete = True


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
                """ % STUDIO_PACKAGE_NAME ) )

        sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )
        return

    if maximum_attempts > 0:
        sublime.set_timeout_async( lambda: check_installed_packages( maximum_attempts ), 2000 )

    else:
        sublime.error_message( wrap_text( """\
                The %s installation could not be successfully completed.

                Check you Sublime Text Console for more information.

                If you want help fixing the problem, please, save your Sublime Text Console output
                so later others can see what happened try to fix it.
                """ % STUDIO_PACKAGE_NAME ) )

        sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )


