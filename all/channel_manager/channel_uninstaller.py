






def get_packages_to_uninstall(is_downgrade):
    filtered_packages     = []
    last_packages         = []
    packages_to_uninstall = get_dictionary_key( g_channelDetails, 'packages_to_uninstall', [] )

    if is_downgrade:
        packages_to_not_remove = set()
        repositories_loaded    = load_repository_file( g_channelSettings['CHANNEL_REPOSITORY_FILE'], {} )

        install_exclusively    = g_channelSettings['PACKAGES_TO_INSTALL_EXCLUSIVELY']
        is_exclusively_install = not not len( install_exclusively )

        if is_exclusively_install:

            for package_name in repositories_loaded:

                if package_name in install_exclusively:
                    packages_to_not_remove.add( package_name )

        packages_to_uninstall = set( packages_to_uninstall + g_packages_not_installed ) - packages_to_not_remove

    for package_name in PACKAGES_TO_UNINSTALL_FIRST:

        # Only merges the packages which are actually being uninstalled
        if package_name in packages_to_uninstall:
            filtered_packages.append( package_name )

    for package_name in PACKAGES_TO_UNINSTALL_LAST:

        # Only merges the packages which are actually being uninstalled
        if package_name in packages_to_uninstall:
            last_packages.append( package_name )
            packages_to_uninstall.remove( package_name )

    # Add the remaining packages after the packages to install first
    for package_name in packages_to_uninstall:

        if package_name not in filtered_packages:
            filtered_packages.append( package_name )

    # Finally add the last packages to the full list
    unique_list_append( filtered_packages, last_packages )

    if is_downgrade:

        # Allow to uninstall only the channel package when there is no other packages installed
        if len( filtered_packages ) < 1:
            raise NoPackagesAvailable( "There are 0 packages available to uninstall!" )

        log( 1, "New packages packages to uninstall found... " + str( filtered_packages ) )

    return filtered_packages


def uninstall_packages(packages_names):
    package_manager  = PackageManager()
    package_disabler = PackageDisabler()

    ask_user_for_which_packages_to_install( packages_names )
    all_packages, dependencies = get_installed_repositories( package_manager )

    current_index  = 0
    packages_count = len( packages_names )

    for package_name, pi in sequence_timer( packages_names, info_frequency=0 ):
        current_index += 1
        progress       = progress_info( pi, set_progress )
        is_dependency  = is_package_dependency( package_name, dependencies, all_packages )

        log.insert_empty_line()
        log.insert_empty_line()

        log( 1, "%s %s of %d of %d: %s (%s)" % ( progress, INSTALLATION_TYPE_NAME,
                current_index, packages_count, str( package_name ), str( is_dependency ) ) )

        silence_error_message_box( 61.0 )
        ignore_next_packages( package_disabler, package_name, packages_names )

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

        if package_manager.remove_package( package_name, is_dependency ) is False:
            log( 1, "Error: Failed to uninstall the repository `%s`!" % package_name )
            g_failed_repositories.append( package_name )

        else:
            remove_packages_from_list( package_name )

        accumulative_unignore_user_packages( package_name )

    accumulative_unignore_user_packages( flush_everything=True )
    return package_manager, package_disabler


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

        log( 1, "Adding %d packages to the `ignored_packages` setting list." % len( next_packages_to_ignore ) )
        log( 1, "next_packages_to_ignore: " + str( next_packages_to_ignore ) )

        # Add them to the in_process list
        package_disabler.disable_packages( next_packages_to_ignore, "remove" )
        unique_list_append( g_default_ignored_packages, next_packages_to_ignore )

        # Let the package be unloaded by Sublime Text while ensuring anyone is putting them back in
        add_packages_to_ignored_list( next_packages_to_ignore )


def add_packages_to_ignored_list(packages_list):
    """
        Something, somewhere is setting the ignored_packages list to `["Vintage"]`. Then ensure we
        override this.
    """
    global g_next_packages_to_ignore
    ignored_packages = g_user_settings.get( "ignored_packages", [] )

    # Progressively saves the installation data, in case the user closes Sublime Text
    g_next_packages_to_ignore = packages_list
    save_default_settings()

    unique_list_append( ignored_packages, packages_list )

    for interval in range( 0, 27 ):
        g_user_settings.set( "ignored_packages", ignored_packages )
        sublime.save_settings( g_channelSettings['USER_SETTINGS_FILE'] )

        time.sleep(0.1)


def accumulative_unignore_user_packages(package_name="", flush_everything=False):
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
        sublime.save_settings( g_channelSettings['USER_SETTINGS_FILE'] )


def uninstall_default_package():
    log( 1, "%s of `Default Package` files..." % INSTALLATION_TYPE_NAME )

    files_installed       = get_dictionary_key( g_channelDetails, 'default_package_files', [] )
    default_packages_path = os.path.join( g_channelSettings['CHANNEL_ROOT_DIRECTORY'], "Packages", "Default" )

    for file in files_installed:
        file_path = os.path.join( default_packages_path, file )
        remove_only_if_exists( file_path )

    default_git_folder = os.path.join( default_packages_path, ".git" )
    remove_git_folder( default_git_folder, default_packages_path )


def remove_channel():
    channels = get_dictionary_key( g_package_control_settings, "channels", [] )

    while g_channelSettings['CHANNEL_FILE_URL'] in channels:
        log( 1, "Removing %s channel from Package Control settings: %s" % ( g_channelSettings['CHANNEL_PACKAGE_NAME'], str( channels ) ) )
        channels.remove( g_channelSettings['CHANNEL_FILE_URL'] )

    g_package_control_settings['channels'] = channels
    save_package_control_settings()


def save_package_control_settings():
    g_package_control_settings['installed_packages'] = g_installed_packages
    write_data_file( PACKAGE_CONTROL, g_package_control_settings )


def remove_packages_from_list(package_name):
    remove_if_exists( g_installed_packages, package_name )
    remove_if_exists( g_packages_to_uninstall, package_name )

    # Progressively saves the installation data, in case the user closes Sublime Text
    save_default_settings()
    save_package_control_settings()


def uninstall_files():
    git_folders = []

    log.insert_empty_line()
    log.insert_empty_line()
    log( 1, "%s of added files: %s" % ( INSTALLATION_TYPE_NAME, str( g_files_to_uninstall ) ) )

    for file in g_files_to_uninstall:
        log( 1, "Uninstalling file: %s" % str( file ) )
        file_absolute_path = os.path.join( g_channelSettings['CHANNEL_ROOT_DIRECTORY'], file )

        safe_remove( file_absolute_path )
        add_git_folder_by_file( file, git_folders )

    del g_files_to_uninstall[:]
    log( 1, "Removing git_folders..." )

    for git_folder in git_folders:
        remove_git_folder( git_folder )

    # Progressively saves the installation data, in case the user closes Sublime Text
    save_default_settings()


def remove_git_folder(default_git_folder, parent_folder=None):
    log( 1, "%s of default_git_folder: %s" % ( INSTALLATION_TYPE_NAME, str( default_git_folder ) ) )
    shutil.rmtree( default_git_folder, ignore_errors=True, onerror=_delete_read_only_file )

    if parent_folder:
        folders_not_empty = []
        recursively_delete_empty_folders( parent_folder, folders_not_empty )

        if len( folders_not_empty ) > 0:
            log( 1, "The installed default_git_folder `%s` could not be removed because is it not empty." % default_git_folder )
            log( 1, "Its files contents are: " + str( os.listdir( default_git_folder ) ) )


def add_git_folder_by_file(file_relative_path, git_folders):
    match = re.search( "\.git", file_relative_path )

    if match:
        git_folder_relative = file_relative_path[:match.end(0)]

        if git_folder_relative not in git_folders:
            git_folders.append( git_folder_relative )


def uninstall_folders():
    log.insert_empty_line()
    log.insert_empty_line()
    log( 1, "%s of added folders: %s" % ( INSTALLATION_TYPE_NAME, str( g_files_to_uninstall ) ) )

    for folder in reversed( g_files_to_uninstall ):
        folders_not_empty = []
        log( 1, "Uninstalling folder: %s" % str( folder ) )

        folder_absolute_path = os.path.join( g_channelSettings['CHANNEL_ROOT_DIRECTORY'], folder )
        recursively_delete_empty_folders( folder_absolute_path, folders_not_empty )

    for folder in g_files_to_uninstall:
        folders_not_empty = []
        log( 1, "Uninstalling folder: %s" % str( folder ) )

        folder_absolute_path = os.path.join( g_channelSettings['CHANNEL_ROOT_DIRECTORY'], folder )
        recursively_delete_empty_folders( folder_absolute_path, folders_not_empty )

    for folder in g_files_to_uninstall:
        folders_not_empty = []
        log( 1, "Uninstalling folder: %s" % str( folder ) )

        folder_absolute_path = os.path.join( g_channelSettings['CHANNEL_ROOT_DIRECTORY'], folder )
        recursively_delete_empty_folders( folder_absolute_path, folders_not_empty )

        if len( folders_not_empty ) > 0:
            log( 1, "The installed folder `%s` could not be removed because is it not empty." % folder_absolute_path )
            log( 1, "Its files contents are: " + str( os.listdir( folder_absolute_path ) ) )

    del g_files_to_uninstall[:]

    # Progressively saves the installation data, in case the user closes Sublime Text
    save_default_settings()


def attempt_to_uninstall_packagesmanager(package_manager, package_disabler, packages_to_uninstall):

    if "PackagesManager" in packages_to_uninstall:
        installed_packages = package_manager.list_packages()

        if "Package Control" not in installed_packages:
            install_package_control( package_manager, package_disabler)

        uninstall_packagesmanger( package_manager, package_disabler, installed_packages )
        restore_remove_orphaned_setting()

    else:
        # Clean right away the PackagesManager successful flag, was it was not installed
        global g_is_running
        g_is_running &= ~CLEAN_PACKAGESMANAGER_FLAG


def install_package_control(package_manager, package_disabler):
    package_name = "Package Control"
    log.insert_empty_line()
    log.insert_empty_line()

    log( 1, "Installing: %s" % str( package_name ) )
    ignore_next_packages( package_disabler, package_name, [package_name] )

    package_manager.install_package( package_name, False )
    accumulative_unignore_user_packages( flush_everything=True )


def uninstall_packagesmanger(package_manager, package_disabler, installed_packages):
    """
        Uninstals PackagesManager only if Control was installed, otherwise the user will end up with
        no package manager.
    """

    # Only uninstall them when they were installed
    if "PackagesManager" in installed_packages:
        log.insert_empty_line()
        log.insert_empty_line()

        log( 1, "Finishing PackagesManager %s..." % INSTALLATION_TYPE_NAME )
        uninstall_list_of_packages( package_manager, package_disabler, [("PackagesManager", False), ("0_packagesmanager_loader", None)] )

        remove_0_packagesmanager_loader()
        clean_packagesmanager_settings()


def uninstall_list_of_packages(package_manager, package_disabler, packages_infos):
    """
        By last uninstall itself `g_channelSettings['CHANNEL_PACKAGE_NAME']` and let the package be
        unloaded by Sublime Text
    """
    log( 1, "uninstall_list_of_packages, %s... " % INSTALLATION_TYPE_NAME + str( packages_infos ) )
    packages_names = [ package_name for package_name, _ in packages_infos ]

    for package_name, is_dependency in packages_infos:
        log.insert_empty_line()
        log.insert_empty_line()

        log( 1, "%s of: %s..." % ( INSTALLATION_TYPE_NAME, str( package_name ) ) )

        silence_error_message_box( 62.0 )
        ignore_next_packages( package_disabler, package_name, packages_names )

        if package_manager.remove_package( package_name, is_dependency ) is False:
            log( 1, "Error: Failed to uninstall the repository `%s`!" % package_name )
            g_failed_repositories.append( package_name )

        else:
            remove_packages_from_list( package_name )

        accumulative_unignore_user_packages( package_name )

    accumulative_unignore_user_packages( flush_everything=True )


def remove_0_packagesmanager_loader():
    """
        Most times the 0_packagesmanager_loader is not being deleted/removed, then try again.
    """
    _packagesmanager_loader_path     = os.path.join( g_channelSettings['CHANNEL_ROOT_DIRECTORY'], "Installed Packages", "0_packagesmanager_loader.sublime-package" )
    _packagesmanager_loader_path_new = os.path.join( g_channelSettings['CHANNEL_ROOT_DIRECTORY'], "Installed Packages", "0_packagesmanager_loader.sublime-package-new" )

    remove_only_if_exists( _packagesmanager_loader_path )
    remove_only_if_exists( _packagesmanager_loader_path_new )


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

    # Set the flag as completed, to signalize the this part of the installation was successful
    global g_is_running
    g_is_running &= ~CLEAN_PACKAGESMANAGER_FLAG


def restore_remove_orphaned_setting():

    if g_remove_orphaned_backup:
        # By default, it is already True on `Package Control.sublime-settings`, so just remove it
        del g_package_control_settings['remove_orphaned']

    else:
        g_package_control_settings['remove_orphaned'] = g_remove_orphaned_backup

    save_package_control_settings()

    # Set the flag as completed, to signalize the this part of the installation was successful
    global g_is_running
    g_is_running &= ~RESTORE_REMOVE_ORPHANED_FLAG


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

    g_channelDetails = sort_dictionary( g_channelDetails )
    # log( 1, "save_default_settings, g_channelDetails: " + json.dumps( g_channelDetails, indent=4 ) )

    write_data_file( g_channelSettings['CHANNEL_INSTALLATION_DETAILS'], g_channelDetails )


def ask_user_for_which_packages_to_install(packages_names):
    can_continue  = [False, False]
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

        if package_name in g_channelSettings['FORBIDDEN_PACKAGES']:
            packages_informations.append( [ package_name, "You must uninstall it or cancel the %s." % INSTALLATION_TYPE_NAME ] )

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

    if can_continue[1]:
        log.insert_empty_line()
        raise InstallationCancelled( "The user closed the installer's packages pick up list." )

    for package_name in selected_packages_to_not_install:
        g_packages_not_installed.append( package_name )

        target_index = packages_names.index( package_name )
        del packages_names[target_index]

    # Progressively saves the installation data, in case the user closes Sublime Text
    save_default_settings()


def check_uninstalled_packages_alert(maximum_attempts=10):
    """
        Show a message to the user observing the Sublime Text console, so he know the process is not
        finished yet.
    """
    log( _grade(), "Looking for new tasks... %s seconds remaining." % str( maximum_attempts ) )
    maximum_attempts -= 1

    if maximum_attempts > 0:

        if g_is_running:
            sublime.set_timeout_async( lambda: check_uninstalled_packages_alert( maximum_attempts ), 1000 )

        else:
            log( _grade(), "Finished looking for new tasks... The installation is complete." )


def check_uninstalled_packages(maximum_attempts=10):
    """
        Display warning when the uninstallation process is finished or ask the user to restart
        Sublime Text to finish the uninstallation.

        Compare the current uninstalled packages list with required packages to uninstall, and if
        they differ, attempt to uninstall they again for some times. If not successful, stop trying
        and warn the user.
    """
    log( _grade(), "Finishing %s... maximum_attempts: " % INSTALLATION_TYPE_NAME + str( maximum_attempts ) )

    global g_is_running
    maximum_attempts -= 1

    if not g_is_running:
        accumulative_unignore_user_packages( flush_everything=True )

        if not IS_UPDATE_INSTALLATION:
            complete_channel_uninstallation()

        return

    if maximum_attempts > 0:
        sublime.set_timeout_async( lambda: check_uninstalled_packages( maximum_attempts ), 2000 )

    else:
        sublime.error_message( end_user_message( """\
                The %s %s could NOT be successfully completed.

                Check you Sublime Text Console for more information.

                If you want help fixing the problem, please, save your Sublime Text Console output
                so later others can see what happened try to fix it.
                """ % ( g_channelSettings['CHANNEL_PACKAGE_NAME'], INSTALLATION_TYPE_NAME ) ) )

        accumulative_unignore_user_packages( flush_everything=True )
        sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )


def complete_channel_uninstallation(maximum_attempts=3):
    """
        Ensure the file is deleted
    """
    sublime.message_dialog( end_user_message( """\
            The %s %s was successfully completed.

            You need to restart Sublime Text to unload the uninstalled packages and finish
            uninstalling the unused dependencies.

            Check you Sublime Text Console for more information.
            """ % ( g_channelSettings['CHANNEL_PACKAGE_NAME'], INSTALLATION_TYPE_NAME ) ) )

    sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )


def end_user_message(message):
    # This is here because it is almost the last thing to be done
    global g_is_running
    g_is_running = 0

    log( 1, message )
    return wrap_text( message )


def is_allowed_to_run():
    global g_is_running

    if g_is_running:
        print( "You are already running a command. Wait until it finishes or restart Sublime Text" )
        return False

    g_is_running = ALL_RUNNING_CONTROL_FLAGS
    return True


def unpack_settings(channel_settings):
    global g_channelSettings
    global g_failed_repositories

    g_channelSettings     = channel_settings
    g_failed_repositories = []

    global INSTALLATION_TYPE_NAME
    global IS_UPDATE_INSTALLATION

    IS_UPDATE_INSTALLATION = True if g_channelSettings['INSTALLATION_TYPE'] == "downgrade" else False
    INSTALLATION_TYPE_NAME    = "Downgrade" if IS_UPDATE_INSTALLATION else "Uninstallation"

    log( 1, "IS_UPDATE_INSTALLATION: " + str( IS_UPDATE_INSTALLATION ) )
    setup_packages_to_uninstall_last( g_channelSettings )


def setup_packages_to_uninstall_last(channel_settings):
    """
        Remove the remaining packages to be uninstalled separately on another function call.
    """
    global PACKAGES_TO_UNINSTALL_FIRST
    global PACKAGES_TO_UNINSTALL_LAST

    global PACKAGES_TO_UNINSTAL_LATER
    global PACKAGES_TO_NOT_ADD_TO_IGNORE_LIST

    PACKAGES_TO_UNINSTAL_LATER  = [ "PackagesManager", g_channelSettings['CHANNEL_PACKAGE_NAME'] ]
    PACKAGES_TO_UNINSTALL_FIRST = list( reversed( channel_settings['PACKAGES_TO_INSTALL_LAST'] ) )
    PACKAGES_TO_UNINSTALL_LAST  = list( reversed( channel_settings['PACKAGES_TO_INSTALL_FIRST'] ) )

    # We need to remove it by last, after installing Package Control back
    for package in PACKAGES_TO_UNINSTAL_LATER:

        if package in PACKAGES_TO_UNINSTALL_FIRST:
            PACKAGES_TO_UNINSTALL_FIRST.remove( package )

    PACKAGES_TO_NOT_ADD_TO_IGNORE_LIST = set( PACKAGES_TO_UNINSTAL_LATER )
    PACKAGES_TO_NOT_ADD_TO_IGNORE_LIST.add( "Default" )


def load_installation_settings_file():
    global _uningored_packages_to_flush
    _uningored_packages_to_flush = []

    global PACKAGE_CONTROL
    global PACKAGESMANAGER

    packagesmanager_name = "PackagesManager.sublime-settings"
    package_control_name = "Package Control.sublime-settings"

    PACKAGESMANAGER = os.path.join( g_channelSettings['USER_FOLDER_PATH'], packagesmanager_name )
    PACKAGE_CONTROL = os.path.join( g_channelSettings['USER_FOLDER_PATH'], package_control_name )

    global g_user_settings
    global g_default_ignored_packages
    global g_remove_orphaned_backup

    g_user_settings            = sublime.load_settings( g_channelSettings['USER_SETTINGS_FILE'] )
    g_default_ignored_packages = g_user_settings.get( "ignored_packages", [] )

    global g_installed_packages
    global g_package_control_settings

    # Allow to not override the Package Control file when PackagesManager does exists
    if os.path.exists( PACKAGESMANAGER ):
        g_package_control_settings = load_data_file( PACKAGESMANAGER )

    else:
        g_package_control_settings = load_data_file( PACKAGE_CONTROL )

    g_installed_packages     = get_dictionary_key( g_package_control_settings, 'installed_packages', [] )
    g_remove_orphaned_backup = get_dictionary_key( g_package_control_settings, 'remove_orphaned', True )

    if not IS_UPDATE_INSTALLATION:

        # Temporally stops Package Control from removing orphaned packages, otherwise it will scroll up
        # the uninstallation when Package Control is installed back
        g_package_control_settings['remove_orphaned'] = False
        save_package_control_settings()

    global g_channelDetails
    global g_packages_to_uninstall
    global g_files_to_uninstall
    global g_folders_to_uninstall
    global g_packages_to_unignore
    global g_next_packages_to_ignore
    global g_packages_not_installed

    g_channelDetails = load_data_file( g_channelSettings['CHANNEL_INSTALLATION_DETAILS'] )
    log( _grade(), "Loaded g_channelDetails: " + str( g_channelDetails ) )

    g_packages_to_uninstall   = get_dictionary_key( g_channelDetails, 'packages_to_uninstall', [] )
    g_packages_to_unignore    = get_dictionary_key( g_channelDetails, 'packages_to_unignore', [] )
    g_files_to_uninstall      = get_dictionary_key( g_channelDetails, 'files_to_uninstall', [] )
    g_folders_to_uninstall    = get_dictionary_key( g_channelDetails, 'folders_to_uninstall', [] )
    g_next_packages_to_ignore = get_dictionary_key( g_channelDetails, 'next_packages_to_ignore', [] )
    g_packages_not_installed  = get_dictionary_key( g_channelDetails, 'packages_not_installed', [] )

    unignore_installed_packages()


def unignore_installed_packages():
    """
        When the installation was interrupted, there will be ignored packages which are pending to
        uningored.
    """
    packages_to_unignore = []

    for package_name in g_next_packages_to_ignore:

        if package_name in g_packages_to_uninstall:
            packages_to_unignore.append( package_name )

    log( _grade(), "unignore_installed_packages: " + str( packages_to_unignore ) )
    unignore_some_packages( packages_to_unignore )

