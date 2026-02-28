from version import __appname__, __version__, __codename__
import sqlite3
import asyncio
import os
import json
import threading
from pathlib import Path
from typing import Dict, Optional, List, Any, Union
from utils import setup_logger, get_appdata_dir

class DatabaseManager:
    _instance = None
    _lock = threading.RLock()  # Reentrant lock for thread safety
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        with self._lock:
            if self.initialized:
                return
                
            # Setup logger
            self.logger = setup_logger('db_manager', get_appdata_dir(create=True))
            
            # Create database file in the app's data directory
            app_data_path = get_appdata_dir(create=True)
            self.db_path = Path(app_data_path) / "database" / "igoor.db"
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.logger.info(f"Initializing database at {self.db_path}")
            
            # Store the database path but don't create a connection yet
            # We'll create connections per-thread as needed
            self.connections = {}
            self._create_metadata_table()
            self.initialized = True
    
    def _get_connection(self):
        """Get a thread-specific connection"""
        thread_id = threading.get_ident()
        with self._lock:
            if thread_id not in self.connections:
                self.logger.info(f"Creating new database connection for thread {thread_id}")
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                self.connections[thread_id] = conn
            return self.connections[thread_id]
    
    def _create_metadata_table(self):
        """Create table to track plugin database versions"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plugin_metadata (
                plugin_name TEXT PRIMARY KEY,
                tables TEXT,
                version TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    
    def register_plugin(self, plugin_name: str, tables_config: Dict[str, Dict]):
        """
        Register plugin tables and create them if they don't exist
        
        :param plugin_name: Name of the plugin
        :param tables_config: Dict of table configurations from plugin.json
        """
        try:
            self.logger.info(f"Registering database tables for plugin: {plugin_name}")
            self.logger.info(f"Tables to create: {list(tables_config.keys())}")
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Store the current versions of tables
            current_versions = {}
            try:
                cursor.execute("SELECT tables FROM plugin_metadata WHERE plugin_name = ?", (plugin_name,))
                result = cursor.fetchone()
                if result and result[0]:
                    current_versions = json.loads(result[0])
            except (sqlite3.Error, json.JSONDecodeError) as e:
                self.logger.warning(f"Could not retrieve current table versions: {e}")
            
            # Create or update plugin tables
            for table_name, config in tables_config.items():
                try:
                    prefixed_table = f"{plugin_name}_{table_name}"
                    schema = config.get('schema', '')
                    version = config.get('version', '1.0')
                    
                    # Check if table needs to be updated
                    current_version = current_versions.get(table_name, {}).get('version', '0')
                    
                    if current_version != version:
                        # Replace the original table name with the prefixed one in the schema
                        prefixed_schema = schema.replace(f"CREATE TABLE IF NOT EXISTS {table_name}", 
                                                    f"CREATE TABLE IF NOT EXISTS {prefixed_table}")
                        
                        # Fix foreign key references if they exist
                        if "FOREIGN KEY" in prefixed_schema and "REFERENCES" in prefixed_schema:
                            # Look for references to other tables in this plugin
                            for ref_table in tables_config.keys():
                                prefixed_schema = prefixed_schema.replace(
                                    f"REFERENCES {ref_table}", 
                                    f"REFERENCES {plugin_name}_{ref_table}"
                                )
                        
                        self.logger.info(f"Creating/updating table {prefixed_table} (v{version})")
                        self.logger.info(f"Executing SQL: {prefixed_schema}")
                        cursor.execute(prefixed_schema)
                        
                        # Update version in our tracking
                        current_versions[table_name] = {'version': version}
                except sqlite3.Error as e:
                    self.logger.error(f"Error creating table {table_name}: {e}")
                    # Continue with other tables instead of failing completely
            
            # Update plugin metadata
            cursor.execute("""
                INSERT OR REPLACE INTO plugin_metadata (plugin_name, tables, version)
                VALUES (?, ?, ?)
            """, (plugin_name, json.dumps(current_versions), "1.0"))
            
            conn.commit()
            self.logger.info(f"Successfully registered database for plugin: {plugin_name}")
            
        except sqlite3.Error as e:
            self.logger.error(f"Error registering plugin {plugin_name}: {e}")
            conn = self._get_connection()
            conn.rollback()
    
    def _prefix_table_names(self, plugin_name: str, query: str) -> str:
        """
        Add plugin prefix to table names in query
        This is a simplified implementation - in production you'd want to use a proper SQL parser
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get all tables registered for this plugin
        cursor.execute("SELECT tables FROM plugin_metadata WHERE plugin_name = ?", (plugin_name,))
        result = cursor.fetchone()
        
        if not result or not result[0]:
            return query
            
        tables = json.loads(result[0])
        
        # Replace table names with prefixed versions
        modified_query = query
        for table_name in tables.keys():
            # This is a simple replacement and might have edge cases
            modified_query = modified_query.replace(f" {table_name} ", f" {plugin_name}_{table_name} ")
            modified_query = modified_query.replace(f" {table_name},", f" {plugin_name}_{table_name},")
            modified_query = modified_query.replace(f" {table_name})", f" {plugin_name}_{table_name})")
            modified_query = modified_query.replace(f"FROM {table_name}", f"FROM {plugin_name}_{table_name}")
            modified_query = modified_query.replace(f"INTO {table_name}", f"INTO {plugin_name}_{table_name}")
            
        return modified_query
    
    async def execute(self, plugin_name: str, query: str, params: tuple = ()) -> Optional[List[Any]]:
        """
        Execute a query for a plugin
        """
        try:
            # Add plugin prefix to table names in query
            query = self._prefix_table_names(plugin_name, query)
            
            # Execute in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._execute_sync,
                query,
                params
            )
        except sqlite3.Error as e:
            self.logger.error(f"Error executing query for {plugin_name}: {e}")
            return None

    def execute_sync(self, plugin_name: str, query: str, params: tuple = ()) -> Optional[List[Any]]:
        """
        Execute a query synchronously for a plugin
        """
        try:
            query = self._prefix_table_names(plugin_name, query)
            return self._execute_sync(query, params)
        except sqlite3.Error as e:
            self.logger.error(f"Error executing sync query for {plugin_name}: {e}")
            return None

    def _execute_sync(self, query: str, params: Union[tuple, dict]) -> Optional[List[Any]]:
        """Execute SQL query synchronously"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        query_upper = query.strip().upper()
        if query_upper.startswith(('SELECT', 'PRAGMA')):
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        conn.commit()
        # Return lastrowid for INSERT operations to support atomic ID retrieval
        if query_upper.startswith('INSERT'):
            return [{"lastrowid": cursor.lastrowid}]
        return None

    def __del__(self):
        """Clean up database connections"""
        with self._lock:
            for thread_id, conn in self.connections.items():
                try:
                    conn.close()
                except:
                    pass