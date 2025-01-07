'''
PROPOSED CENTRAL MANAGER SINGLETON FOR SQLITE DB
TODO: change path
'''
import sqlite3
import asyncio
from pathlib import Path
from typing import Dict, Optional, List, Any

class DatabaseManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        if self.initialized:
            return
            
        # Create database file in the app's data directory
        self.db_path = Path("data/plugin_database.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize connection
        self.conn = sqlite3.connect(str(self.db_path))
        self.cursor = self.conn.cursor()
        
        # Create metadata table for tracking plugin tables
        self._create_metadata_table()
        self.initialized = True
    
    def _create_metadata_table(self):
        """Create table to track plugin database versions"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS plugin_metadata (
                plugin_name TEXT PRIMARY KEY,
                version TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
    
    def register_plugin(self, plugin_name: str, version: str, tables: Dict[str, str]):
        """
        Register plugin tables and create them if they don't exist
        
        :param plugin_name: Name of the plugin
        :param version: Plugin version
        :param tables: Dict of table_name: create_table_sql
        """
        try:
            # Create plugin tables with prefixed names
            for table_name, create_table_sql in tables.items():
                prefixed_table = f"{plugin_name}_{table_name}"
                # Replace the original table name with the prefixed one
                prefixed_sql = create_table_sql.replace(table_name, prefixed_table)
                self.cursor.execute(prefixed_sql)
            
            # Update plugin metadata
            self.cursor.execute("""
                INSERT OR REPLACE INTO plugin_metadata (plugin_name, version)
                VALUES (?, ?)
            """, (plugin_name, version))
            
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error registering plugin {plugin_name}: {e}")
            self.conn.rollback()
    
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
            print(f"Error executing query for {plugin_name}: {e}")
            return None

    def _execute_sync(self, query: str, params: tuple) -> Optional[List[Any]]:
        """Execute SQL query synchronously"""
        self.cursor.execute(query, params)
        if query.strip().upper().startswith(('SELECT', 'PRAGMA')):
            return self.cursor.fetchall()
        self.conn.commit()
        return None

    def __del__(self):
        """Clean up database connection"""
        if hasattr(self, 'conn'):
            self.conn.close()