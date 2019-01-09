[
    {
        "caption": "Preferences",
        "mnemonic": "n",
        "id": "preferences",
        "children":
        [
            {
                "caption": "Package Settings",
                "mnemonic": "P",
                "id": "package-settings",
                "children":
                [
                    {
                        "caption": "MyBrandNewChannel",
                        "id": "MyBrandNewChannel",
                        "children":
                        [
                            { "caption": "Generate Channel File",
                                    "command": "my_brand_new_channel_generate_channel_file",
                                    "args": {"command": "all" } },

                            { "caption": "Select Packages to Update Git Tag",
                                    "command": "my_brand_new_channel_generate_channel_file",
                                    "args": {"command": "git_tag" } },

                            { "caption": "Update All Packages Git Tag",
                                    "command": "my_brand_new_channel_generate_channel_file",
                                    "args": {"command": "git_tag_all" } },

                            { "caption": "Cancel Current Operation",
                                    "command": "my_brand_new_channel_generate_channel_file",
                                    "args": {"command": "cancel_operation" } },

                            { "caption": "Run Installation Wizard",
                                    "command": "my_brand_new_channel_run_installation" },

                            { "caption": "Run Uninstallation Wizard",
                                    "command": "my_brand_new_channel_run_uninstallation" },

                            { "caption": "Extract Default Package",
                                    "command": "my_brand_new_channel_extract_default_packages" },

                            { "caption": "Merge Upstreams Locally",
                                    "command": "my_brand_new_channel_run", "args": {"run": "-m"} },

                            { "caption": "Fetch All Submodules remote origin",
                                    "command": "my_brand_new_channel_run", "args": {"run": "-fo"} },

                            { "caption": "Pull & Rebase All Submodules (git)",
                                    "command": "my_brand_new_channel_run", "args": {"run": "-p"} },

                            { "caption": "Pull & Rebase All Submodules (python)",
                                    "command": "my_brand_new_channel_run", "args": {"run": "-o"} },

                            { "caption": "Push Local Git Tags",
                                    "command": "my_brand_new_channel_run", "args": {"run": "-t"} },

                            { "caption": "Add All Upstreams Remotes",
                                    "command": "my_brand_new_channel_run", "args": {"run": "-u"} },

                            { "caption": "Delete All remote Except origin",
                                    "command": "my_brand_new_channel_run", "args": {"run": "-d"} },
                        ]
                    }
                ]
            }
        ]
    }
]
