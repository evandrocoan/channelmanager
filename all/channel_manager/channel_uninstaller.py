








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


