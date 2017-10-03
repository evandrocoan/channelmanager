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

import io
import json
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


g_is_already_running = False
PACKAGES_TO_INSTALL_LAST = ["Default"]

CURRENT_DIRECTORY    = os.path.dirname( os.path.realpath( __file__ ) )
CURRENT_PACKAGE_NAME = os.path.basename( CURRENT_DIRECTORY ).rsplit('.', 1)[0]

# Do not try to install this own package and the Package Control, as they are currently running
PACKAGES_TO_NOT_INSTALL = [ "Package Control", CURRENT_PACKAGE_NAME ]

# print( "CURRENT_DIRECTORY: " + CURRENT_DIRECTORY )
assert_path( os.path.join( os.path.dirname( CURRENT_DIRECTORY ), 'PythonDebugTools/all' ) )
assert_path( os.path.join( os.path.dirname( CURRENT_DIRECTORY ), "Package Control" ) )


from .channel_manager import write_data_file
from .channel_manager import string_convert_list
from .submodules_manager import get_main_directory

from package_control import cmd
from package_control.download_manager import downloader

from package_control.package_manager import PackageManager
from package_control.thread_progress import ThreadProgress
from package_control.commands.advanced_install_package_command import AdvancedInstallPackageThread


# Import the debugger
from debug_tools import Debugger

# Debugger settings: 0 - disabled, 127 - enabled
log = Debugger( 127, os.path.basename( __file__ ) )

log( 2, "..." )
log( 2, "..." )
log( 2, "Debugging" )
log( 2, "CURRENT_DIRECTORY:     " + CURRENT_DIRECTORY )


def main(command="stable"):
    """
        Before calling this installer, the `Package Control` user settings file, must have the
        Studio Channel file set before the default channel key `channels`.

        Also the current `Package Control` cache must be cleaned, ensuring it is downloading and
        using the Studio Channel repositories/channel list.
    """
    log( 2, "Entering on main(0)" )

    installer_thread = StartInstallStudioThread(command)
    installer_thread.start()


class StartInstallStudioThread(threading.Thread):

    def __init__(self, command):
        threading.Thread.__init__(self)
        self.command = command

    def run(self):
        """
            Python thread exit code
            https://stackoverflow.com/questions/986616/python-thread-exit-code
        """

        if is_allowed_to_run():
            global USER_SETTINGS_FILE
            global STUDIO_MAIN_DIRECTORY
            global CHANNEL_MAIN_FILE_PATH
            global CHANNEL_MAIN_FILE_URL
            global STUDIO_MAIN_URL

            USER_SETTINGS_FILE     = "Preferences.sublime-settings"
            STUDIO_MAIN_DIRECTORY  = os.path.dirname( sublime.packages_path() )
            CHANNEL_MAIN_FILE_PATH = os.path.join( STUDIO_MAIN_DIRECTORY, "StudioChannel", "settings.json" )
            CHANNEL_MAIN_FILE_URL  = "https://raw.githubusercontent.com/evandrocoan/SublimeStudioChannel/master/settings.json"
            STUDIO_MAIN_URL        = "https://github.com/evandrocoan/SublimeTextStudio"

            log( 2, "STUDIO_MAIN_URL:       " + STUDIO_MAIN_URL )
            log( 2, "STUDIO_MAIN_DIRECTORY: " + STUDIO_MAIN_DIRECTORY )

            is_development_install = True if self.command == "development" else False
            installer_thread       = InstallStudioFilesThread( is_development_install )

            installer_thread.start()
            ThreadProgress( installer_thread, 'Installing Sublime Text Studio %s Packages' % self.command,
                    'Sublime Text Studio %s was successfully installed.' % self.command )

            installer_thread.join()

            set_default_settings_after( is_development_install )
            check_installed_packages()

        global g_is_already_running
        g_is_already_running = False


class InstallStudioFilesThread(threading.Thread):

    def __init__(self, is_development_install):
        threading.Thread.__init__(self)
        self.is_development_install = is_development_install

    def run(self):
        log( 2, "Entering on run(1)" )
        global g_packages_to_uninstall

        g_packages_to_uninstall = []
        command_line_interface  = cmd.Cli( None, True )

        git_executable_path = command_line_interface.find_binary( "git.exe" if os.name == 'nt' else "git" )
        log( 2, "run, git__executable_path: " + str( git_executable_path ) )

        install_modules( command_line_interface, git_executable_path, self.is_development_install )


def is_allowed_to_run():
    global g_is_already_running

    if g_is_already_running:
        print( "You are already running a command. Wait until it finishes or restart Sublime Text" )
        return False

    g_is_already_running = True
    return True


def clone_sublime_text_studio(command_line_interface, git_executable_path):
    """
        Clone the main repository `https://github.com/evandrocoan/SublimeTextStudio`
        and install it on the Sublime Text Data folder.
    """
    main_git_folder = os.path.join( STUDIO_MAIN_DIRECTORY, ".git" )

    if os.path.exists( main_git_folder ):
        raise ValueError("The folder '%s' already exists. You already has some custom studio git installation." % main_git_folder)


def install_modules(command_line_interface, git_executable_path, is_development_install):
    log( 2, "install__modules, PACKAGES_TO_NOT_INSTALL: " + str( PACKAGES_TO_NOT_INSTALL ) )
    load_ignored_packages( is_development_install )

    if is_development_install:
        clone_sublime_text_studio( command_line_interface, git_executable_path )
        git_packages = get_submodules_packages()

        log( 2, "install__modules, git_packages: " + str( git_packages ) )
        install_submodules_packages( git_packages, git_executable_path, command_line_interface )

    else:
        git_modules_file = download_text_file( get_git_modules_url() )
        git_packages     = get_sublime_packages( git_modules_file )

        log( 2, "install__modules, git_packages: " + str( git_packages ) )
        install_sublime_packages( git_packages )


def load_ignored_packages( is_development_install ):
    global g_user_settings
    global g_studio_settings

    g_user_settings = sublime.load_settings( USER_SETTINGS_FILE )

    if is_development_install:
        g_studio_settings = load_data_file( CHANNEL_MAIN_FILE_PATH )

    else:
        channel_settings_file = download_text_file( CHANNEL_MAIN_FILE_URL )
        g_studio_settings     = json.loads( channel_settings_file )

    global g_user_ignored_packages
    global g_packages_to_ignore

    g_user_ignored_packages = g_user_settings.get( 'ignored_packages', [] )
    g_packages_to_ignore    = get_dictionary_key( g_studio_settings, 'packages_to_ignore', [] )

    log( 2, "load__ignored_packages, g__packages_to_ignore:    " + str( g_packages_to_ignore ) )
    log( 2, "load__ignored_packages, g__user_ignored_packages: " + str( g_user_ignored_packages ) )


def get_dictionary_key(dictionary, key, default=None):

    if key in dictionary:
        default = dictionary[key]

    return default


def load_data_file(file_path):
    channel_dictionary = {}

    if os.path.exists( file_path ):

        with open( file_path, 'r', encoding='utf-8' ) as studio_channel_data:
            channel_dictionary = json.load( studio_channel_data)

    else:
        log( 1, "Error on load__data_file(1), the file '%s' does not exists!" % file_path )

    return channel_dictionary


def set_default_settings_before(git_packages):
    """
        Set some package to be enabled at last due their settings being dependent on other packages
        which need to be installed first. Also disable almost all packages to not lag/hang/slow down the
        installation process.
    """

    # Ignore everything except some packages, until it is finished
    if len( git_packages ) > 0 and isinstance( git_packages[0], str ):

        for package in PACKAGES_TO_INSTALL_LAST:

            if package in git_packages:
                git_packages.remove(package)
                git_packages.append(package)

        g_user_settings.set('ignored_packages', git_packages)

    else:
        packages_to_ignore = []

        for package in git_packages:
            packages_to_ignore.append( package[0] )

            if package[0] in PACKAGES_TO_INSTALL_LAST:
                git_packages.remove(package)
                git_packages.append(package)

        g_user_settings.set('ignored_packages', packages_to_ignore)

    # Save our changes to the user ignored packages list
    sublime.save_settings( USER_SETTINGS_FILE )


def set_default_settings_after(is_development_install):
    """
        Populate the global variable `g_user_ignored_packages` with the packages this installation
        process added to the user's settings files and also save it to the file system. So later
        when uninstalling this studio we can only remove our packages, keeping the user's original
        ignored packages intact.

        This also sets the current user's `ignored_packages` settings including all packages already
        disabled and the new packages to be installed and must be disabled before attempting to
        install them.
    """
    studioSettings          = {}
    studio_ignored_packages = []

    if is_development_install:
        global g_user_ignored_packages

        for package in g_packages_to_ignore:

            if package not in g_user_ignored_packages:
                g_user_ignored_packages.append(package)
                studio_ignored_packages.append(package)


    # `packages_to_uninstall` and `packages_to_unignore` are to uninstall and unignore they when
    # uninstalling the studio channel
    studioSettings['packages_to_uninstall'] = g_packages_to_uninstall
    studioSettings['packages_to_unignore']  = studio_ignored_packages

    g_user_settings.set("ignored_packages", g_user_ignored_packages)

    log( 1, "set__default_settings_after, studioSettings: " + json.dumps( studioSettings, indent=4 ) )
    log( 1, "set__default_settings_after, g_user_settings:   " + str( g_user_settings.get("ignored_packages") ) )

    write_data_file( CHANNEL_SETTINGS, studioSettings )
    sublime.save_settings( USER_SETTINGS_FILE )


def install_sublime_packages(git_packages):
    """
        python multithreading wait till all threads finished
        https://stackoverflow.com/questions/11968689/python-multithreading-wait-till-all-threads-finished

        There is a bug with the AdvancedInstallPackageThread thread which trigger several errors of:

        "It appears a package is trying to ignore itself, causing a loop.
        Please resolve by removing the offending ignored_packages setting."

        When trying to install several package at once, then here I am installing them one by one.
    """
    set_default_settings_before( git_packages )

    # Package Control: Advanced Install Package
    # https://github.com/wbond/package_control/issues/1191
    # thread = AdvancedInstallPackageThread( git_packages )
    # thread.start()
    # thread.join()

    package_manager = PackageManager()
    log( 2, "install__sublime_packages, PACKAGES_TO_NOT_INSTALL: " + str( PACKAGES_TO_NOT_INSTALL ) )

    for package_name, is_dependency in git_packages:
        log( 1, "\n\nInstalling: %s (%s)" % ( str( package_name ), str( is_dependency ) ) )
        package_manager.install_package( package_name, is_dependency )


def get_sublime_packages( git_modules_file ):
    """
        python ConfigParser: read configuration from string
        https://stackoverflow.com/questions/27744058/python-configparser-read-configuration-from-string
    """
    index    = 0
    packages = []

    gitModulesFile     = configparser.RawConfigParser()
    installed_packages = get_installed_packages()

    log( 2, "get__sublime_packages, installed_packages: " + str( installed_packages ) )
    gitModulesFile.readfp( io.StringIO( git_modules_file ) )

    packages_to_ignore = unique_list_join( PACKAGES_TO_NOT_INSTALL, installed_packages, g_packages_to_ignore )
    log( 2, "get__sublime_packages, packages_to_ignore: " + str( packages_to_ignore ) )

    for section in gitModulesFile.sections():
        # # For quick testing
        # index += 1
        # if index > 7:
        #     break

        path = gitModulesFile.get( section, "path" )
        log( 2, "get__sublime_packages, path: " + path )

        if 'Packages' == path[0:8]:
            package_name            = os.path.basename( path )
            submodule_absolute_path = os.path.join( STUDIO_MAIN_DIRECTORY, path )

            if not os.path.isdir( submodule_absolute_path ) \
                    and package_name not in packages_to_ignore:

                packages.append( ( package_name, is_dependency( gitModulesFile, section ) ) )
                g_packages_to_uninstall.append( package_name )

    return packages


def unique_list_join(*lists):
    unique_list = []

    for _list in lists:

        for item in _list:

            if item not in unique_list:
                unique_list.append( item )

    return unique_list


def get_installed_packages():
    package_control_settings = sublime.load_settings("Package Control.sublime-settings")
    return package_control_settings.get("installed_packages", [])


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


def install_submodules_packages(git_packages, git_executable_path, command_line_interface):
    set_default_settings_before( git_packages )
    log( 2, "install__submodules_packages, PACKAGES_TO_NOT_INSTALL: " + str( PACKAGES_TO_NOT_INSTALL ) )

    for package_name in git_packages:
        log( 1, "\n\nInstalling: %s" % ( str( package_name ) ) )

        command = shlex.split( '"%s" clone --recursive "%s" "%s"', git_executable_path, url, path )
        output  = command_line_interface.execute( command, cwd=STUDIO_MAIN_DIRECTORY )

        log( 1, "install__submodules_packages, output: " + output )


def get_submodules_packages():
    gitFilePath    = os.path.join( STUDIO_MAIN_DIRECTORY, '.gitmodules' )
    gitModulesFile = configparser.RawConfigParser()

    index = 0
    installed_packages = get_installed_packages()

    packages_to_ignore = unique_list_join( PACKAGES_TO_NOT_INSTALL, installed_packages )
    log( 2, "get__submodules_packages, packages__to_ignore: " + str( packages_to_ignore ) )

    packages = []
    gitModulesFile.read( gitFilePath )

    for section in gitModulesFile.sections():
        url  = gitModulesFile.get( section, "url" )
        path = gitModulesFile.get( section, "path" )

        # # For quick testing
        # index += 1
        # if index > 3:
        #     break

        log( 2, "get__submodules_packages, path: " + path )

        if 'Packages' == path[0:8]:
            package_name            = os.path.basename( path )
            submodule_absolute_path = os.path.join( STUDIO_MAIN_DIRECTORY, path )

            if not os.path.isdir( submodule_absolute_path ) \
                    and package_name not in packages_to_ignore :

                packages.append( package_name )
                g_packages_to_uninstall.append( package_name )

    return packages


def check_installed_packages():
    """
        Display warning when the installation process is finished or ask the user to restart
        Sublime Text to finish the installation.

        Compare the current installed packages list with required packages to install, and if they
        differ, attempt to install they again for some times. If not successful, stop trying and
        warn the user.
    """
    studioSettings         = sublime.load_settings(CHANNEL_SETTINGS)
    packageControlSettings = sublime.load_settings("Package Control.sublime-settings")

    # installed_packages =


if __name__ == "__main__":
    main()


def plugin_loaded():
    global CHANNEL_SETTINGS
    CHANNEL_SETTINGS = os.path.join( get_main_directory(), "Packages", "User", CURRENT_PACKAGE_NAME + ".sublime-settings" )

    # main()
    check_installed_packages()

