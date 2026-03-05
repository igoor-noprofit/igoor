from version import __appname__, __version__
import os
import json
import zipfile
import tempfile
import shutil
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Union
from utils import get_appdata_dir, setup_logger, resource_path
from db_manager import DatabaseManager


class DataManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        appdata_dir = get_appdata_dir(create=False)
        self.logger = setup_logger('data_manager', appdata_dir)
        self.appdata_dir = appdata_dir
        
        self.logger.info("DataManager initialized")
    
    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """
        Deep merge two dictionaries recursively.
        Base dict takes precedence over update dict.
        """
        result = base.copy()
        
        for key, value in update.items():
            if key in result:
                if isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = self._deep_merge(result[key], value)
                else:
                    result[key] = value
            else:
                result[key] = value
        
        return result
    
    def _find_obsolete_keys(self, imported: Dict, current: Dict, path: str = "") -> List[str]:
        """
        Find keys that exist in imported dict but not in current dict.
        """
        obsolete = []
        
        for key, value in imported.items():
            current_path = f"{path}.{key}" if path else key
            
            if key not in current:
                obsolete.append(current_path)
            elif isinstance(value, dict) and isinstance(current.get(key), dict):
                obsolete.extend(self._find_obsolete_keys(value, current[key], current_path))
        
        return obsolete
    
    def export_user_data(self, output_path: Optional[str] = None, include_rag: bool = True) -> Dict:
        """
        Export user data to a ZIP file.
        
        Args:
            output_path: Path where to save the ZIP file. If None, generates filename in appdata.
            include_rag: Whether to include the RAG plugin data (medias and indexes).
        
        Returns:
            Dict with export status and file path.
        """
        try:
            self.logger.info("Starting user data export")
            
            # Generate output path if not provided
            if output_path is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = os.path.join(
                    self.appdata_dir,
                    f"igoor_export_{timestamp}.zip"
                )
            
            # Create temp directory for building the export
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create metadata.json
                metadata = {
                    "igoor_version": __version__,
                    "export_timestamp": datetime.now().isoformat(),
                    "export_type": "user_data",
                    "include_rag": include_rag
                }
                
                metadata_path = temp_path / "metadata.json"
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=4)
                
                self.logger.info(f"Created metadata.json: {metadata}")
                
                # Export settings.json
                settings_file = os.path.join(self.appdata_dir, "settings.json")
                if os.path.exists(settings_file):
                    shutil.copy2(settings_file, temp_path / "settings.json")
                    self.logger.info("Exported settings.json")
                else:
                    self.logger.warning("settings.json not found")
                
                # Export database folder
                db_folder = os.path.join(self.appdata_dir, "database")
                if os.path.exists(db_folder):
                    shutil.copytree(db_folder, temp_path / "database")
                    self.logger.info("Exported database folder")
                else:
                    self.logger.warning("database folder not found")
                
                # Export RAG plugin data if requested
                if include_rag:
                    rag_folder = os.path.join(self.appdata_dir, "plugins", "rag")
                    if os.path.exists(rag_folder):
                        shutil.copytree(rag_folder, temp_path / "plugins" / "rag")
                        self.logger.info("Exported plugins/rag folder")
                    else:
                        self.logger.warning("plugins/rag folder not found")
                
                # Create ZIP file
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in temp_path.rglob('*'):
                        if file_path.is_file():
                            arcname = file_path.relative_to(temp_path)
                            zipf.write(file_path, arcname)
                
                file_size = os.path.getsize(output_path)
                self.logger.info(f"Export completed successfully: {output_path} ({file_size} bytes)")
                
                return {
                    "success": True,
                    "message": "Export completed successfully",
                    "file_path": output_path,
                    "file_size": file_size,
                    "version_info": metadata
                }
                
        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            return {
                "success": False,
                "message": f"Export failed: {str(e)}"
            }
    
    def import_user_data(self, zip_path: str, overwrite_settings: bool = False) -> Dict:
        """
        Import user data from a ZIP file.
        
        Args:
            zip_path: Path to the ZIP file to import.
            overwrite_settings: If True, completely replace settings. If False, deep merge.
        
        Returns:
            Dict with import status, warnings, and details.
        """
        try:
            self.logger.info(f"Starting user data import from: {zip_path}")
            
            # Validate ZIP file exists
            if not os.path.exists(zip_path):
                return {
                    "success": False,
                    "message": "ZIP file not found"
                }
            
            # Extract to temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Extract ZIP
                with zipfile.ZipFile(zip_path, 'r') as zipf:
                    zipf.extractall(temp_path)
                
                self.logger.info("ZIP extracted successfully")
                
                # Validate required files
                metadata_path = temp_path / "metadata.json"
                settings_path = temp_path / "settings.json"
                
                if not metadata_path.exists() or not settings_path.exists():
                    return {
                        "success": False,
                        "message": "Invalid ZIP: missing metadata.json or settings.json"
                    }
                
                # Read metadata
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                self.logger.info(f"Import metadata: {metadata}")
                
                # Create backup
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = os.path.join(self.appdata_dir, f"backup_{timestamp}")
                
                backup_items = []
                
                # Backup settings.json
                current_settings = os.path.join(self.appdata_dir, "settings.json")
                if os.path.exists(current_settings):
                    backup_settings_path = os.path.join(backup_path, "settings.json")
                    os.makedirs(os.path.dirname(backup_settings_path), exist_ok=True)
                    shutil.copy2(current_settings, backup_settings_path)
                    backup_items.append("settings.json")
                    self.logger.info("Backed up settings.json")
                
                # Backup database folder
                current_db_folder = os.path.join(self.appdata_dir, "database")
                if os.path.exists(current_db_folder):
                    backup_db_path = os.path.join(backup_path, "database")
                    shutil.copytree(current_db_folder, backup_db_path)
                    backup_items.append("database")
                    self.logger.info("Backed up database folder")
                
                # Backup RAG folder
                current_rag_folder = os.path.join(self.appdata_dir, "plugins", "rag")
                imported_rag_path = temp_path / "plugins" / "rag"
                
                if imported_rag_path.exists() and os.path.exists(current_rag_folder):
                    backup_rag_path = os.path.join(backup_path, "plugins", "rag")
                    shutil.copytree(current_rag_folder, backup_rag_path)
                    backup_items.append("plugins/rag")
                    self.logger.info("Backed up plugins/rag folder")
                
                warnings = []
                
                # Handle settings.json
                if overwrite_settings:
                    shutil.copy2(settings_path, current_settings)
                    self.logger.info("Settings replaced completely")
                else:
                    with open(current_settings, 'r', encoding='utf-8') as f:
                        current_settings_data = json.load(f)
                    
                    with open(settings_path, 'r', encoding='utf-8') as f:
                        imported_settings_data = json.load(f)
                    
                    merged_settings = self._deep_merge(current_settings_data, imported_settings_data)
                    
                    with open(current_settings, 'w', encoding='utf-8') as f:
                        json.dump(merged_settings, f, indent=4)
                    
                    self.logger.info("Settings deep merged")
                    
                    # Check for obsolete settings
                    obsolete_keys = self._find_obsolete_keys(imported_settings_data, current_settings_data)
                    if obsolete_keys:
                        warnings.extend([f"Obsolete setting: {key}" for key in obsolete_keys])
                        self.logger.warning(f"Found obsolete settings: {obsolete_keys}")
                
                # Restore database folder
                import_db_path = temp_path / "database"
                if import_db_path.exists():
                    # Close all database connections before replacing database
                    try:
                        db_manager = DatabaseManager()
                        db_manager.close_all_connections()
                        self.logger.info("Database connections closed")
                    except Exception as e:
                        self.logger.warning(f"Could not close database connections: {e}")
                    
                    # Small delay to ensure all file handles are released
                    import time
                    time.sleep(0.5)
                    
                    # Now it's safe to replace the database folder
                    try:
                        if os.path.exists(current_db_folder):
                            shutil.rmtree(current_db_folder)
                        shutil.copytree(import_db_path, current_db_folder)
                        self.logger.info("Database folder restored")
                    except OSError as e:
                        # Handle file in use errors specifically
                        self.logger.error(f"Failed to restore database: {e}")
                        raise Exception(f"Database file is in use. Please restart IGOOR and try again.") from e
                
                # Restore RAG folder
                if imported_rag_path.exists():
                    if os.path.exists(current_rag_folder):
                        shutil.rmtree(current_rag_folder)
                    shutil.copytree(imported_rag_path, current_rag_folder)
                    self.logger.info("plugins/rag folder restored")
                
                self.logger.info("Import completed successfully")
                
                # Import hook - let plugins know data was imported
                try:
                    from plugin_manager import PluginManager
                    pm = PluginManager()
                    asyncio.run(pm.trigger_hook("data_imported", backup_path=backup_path))
                    self.logger.info("Triggered data_imported hook")
                except Exception as e:
                    self.logger.warning(f"Could not trigger data_imported hook: {e}")
                
                return {
                    "success": True,
                    "message": "Import completed successfully",
                    "backup_path": backup_path,
                    "backup_items": backup_items,
                    "warnings": warnings,
                    "version_info": metadata
                }
                
        except Exception as e:
            self.logger.error(f"Import failed: {e}")
            return {
                "success": False,
                "message": f"Import failed: {str(e)}"
            }
