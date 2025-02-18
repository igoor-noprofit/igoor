import os
import sys
import logging
from pathlib import Path
import sys
from datetime import datetime

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def setup_logger(name, appdata_folder, separate_plugin_log=False):
    """
    Sets up a logger that writes to both console and file
    
    Args:
        name (str): Logger name (usually __name__ from the calling module)
        appdata_folder (str): Path to IGOOR_FOLDER
        separate_plugin_log (bool): If True, also writes to a plugin-specific log file
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Create logs directory if it doesn't exist
    logs_dir = Path(appdata_folder) / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    main_file_handler = logging.FileHandler(
        logs_dir / f'igoor_{datetime.now().strftime("%Y%m%d")}.log',
        encoding='utf-8'
    )
    
    # Set levels
    console_handler.setLevel(logging.INFO)
    main_file_handler.setLevel(logging.DEBUG)
    
    # Create formatters and add it to handlers
    log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(log_format)
    main_file_handler.setFormatter(log_format)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(main_file_handler)

    # If this is a plugin and separate logging is requested, add plugin-specific file handler
    if separate_plugin_log and 'plugins.' in name:
        plugin_name = name.split('plugins.')[-1]
        plugin_logs_dir = Path(appdata_folder) / 'logs' / 'plugins'
        plugin_logs_dir.mkdir(exist_ok=True)
        
        plugin_file_handler = logging.FileHandler(
            plugin_logs_dir / f'{plugin_name}_{datetime.now().strftime("%Y%m%d")}.log',
            encoding='utf-8'
        )
        plugin_file_handler.setLevel(logging.DEBUG)
        plugin_file_handler.setFormatter(log_format)
        logger.addHandler(plugin_file_handler)
    
    return logger