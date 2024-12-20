import os
import subprocess

# Base command for PyInstaller
base_command = [
    'pyinstaller',
    '--noconfirm',
    '--onedir',
    '--windowed',
    '--add-data', 'js/*.js;js',
    '--add-data', 'locales/**/*;locales',
]

# Path to your project's plugin directory
plugins_path = os.path.join('plugins')

# Iterate over plugins and add frontend files
for plugin in os.listdir(plugins_path):
    plugin_frontend_path = os.path.join(plugins_path, plugin, 'frontend')
    if os.path.exists(plugin_frontend_path):
        vue_files = [
            f for f in os.listdir(plugin_frontend_path) if f.endswith('.vue')
        ]
        for vue_file in vue_files:
            add_data_entry = f"{os.path.join(plugin_frontend_path, vue_file)};{os.path.join('plugins', plugin, 'frontend')}"
            base_command.extend(['--add-data', add_data_entry])

# Add the main file to compile
base_command.append('main.py')

# Execute the command
subprocess.run(base_command)