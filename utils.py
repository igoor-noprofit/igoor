import logging
import sys
from pathlib import Path
from datetime import datetime
import os
import json
from logging.handlers import TimedRotatingFileHandler

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)


class JsonFormatter(logging.Formatter):
    """Formats log records as JSON strings."""
    def format(self, record):
        log_entry = {
            'timestamp': self.formatTime(record, self.datefmt),
            # 'level': record.levelname,  # Removed
            # 'name': record.name,        # Removed
        }
        # If the message is already a dict, merge it
        if isinstance(record.msg, dict):
            log_entry.update(record.msg)
        else:
            log_entry['message'] = record.getMessage()
            
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry, ensure_ascii=False)

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
    
    # Check if handlers already exist for this logger to prevent duplicates
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # Create logs directory if it doesn't exist
        logs_dir = Path(appdata_folder) / 'logs'
        logs_dir.mkdir(parents=True, exist_ok=True)
        
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
        # Enhanced format with filename, line number, and function name
        detailed_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s'
        )
        console_handler.setFormatter(detailed_format)
        main_file_handler.setFormatter(detailed_format)
        
        # Add handlers to logger
        logger.addHandler(console_handler)
        logger.addHandler(main_file_handler)

        # If this is a plugin and separate logging is requested, add plugin-specific file handler
        if separate_plugin_log and 'plugins.' in name:
            plugin_name = name.split('plugins.')[-1]
            plugin_logs_dir = Path(appdata_folder) / 'logs' / 'plugins'
            plugin_logs_dir.mkdir(parents=True, exist_ok=True)
            
            plugin_file_handler = logging.FileHandler(
                plugin_logs_dir / f'{plugin_name}_{datetime.now().strftime("%Y%m%d")}.log',
                encoding='utf-8'
            )
            plugin_file_handler.setLevel(logging.DEBUG)
            plugin_file_handler.setFormatter(detailed_format)
            logger.addHandler(plugin_file_handler)
        
        # Prevent propagation to root logger if necessary (optional, depends on desired behavior)
        # logger.propagate = False

    return logger

def setup_jsonl_logger(name, appdata_folder):
    """
    Sets up a logger that writes JSONL records to a daily rotating file.

    Args:
        name (str): Logger name (e.g., 'llm_invocations')
        appdata_folder (str): Path to IGOOR_FOLDER
    """
    logger = logging.getLogger(name)
    
    # Prevent duplicate handlers
    if not logger.handlers:
        logger.setLevel(logging.INFO) # Log INFO level and above
        
        # Create logs directory if it doesn't exist
        logs_dir = Path(appdata_folder) / 'logs'
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create daily rotating file handler for JSONL
        # Use date in filename for simplicity, matching the original plan
        log_filename = logs_dir / f'{name}_{datetime.now().strftime("%Y%m%d")}.jsonl'
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Use the custom JSON formatter
        formatter = JsonFormatter()
        file_handler.setFormatter(formatter)
        
        # Add handler to the logger
        logger.addHandler(file_handler)
        
        # Prevent propagation to avoid duplicate logs in the main logger
        logger.propagate = False

    return logger

def get_base_language_code(lang_code_with_region, default_lang="en"):
    """
    Extracts the base language code from a regional code (e.g., "fr" from "fr_FR").
    Returns the original code if no region is specified, or a default if input is empty.
    """
    if not lang_code_with_region:
        return default_lang
    if "_" in lang_code_with_region:
        return lang_code_with_region.split("_")[0]
    return lang_code_with_region

def normalize_filter_by_timeframe_result(filtered_results):
    """
    Ensures the result from filter_by_timeframe is always a dict.
    Accepts a dict or a list containing a dict (from hook aggregation).
    Returns an empty dict if the input is not recognized.
    """
    if isinstance(filtered_results, list) and filtered_results:
        if isinstance(filtered_results[0], dict):
            return filtered_results[0]
        else:
            return {}
    elif isinstance(filtered_results, dict):
        return filtered_results
    else:
        return {}