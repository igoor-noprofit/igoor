# IGOOR Plugins Database Structure Documentation

## Overview

IGOOR uses a SQLite database with a plugin-prefixed table system. Each plugin that requires database access gets its own set of tables with the plugin name as a prefix to avoid naming conflicts. The database is located at `%APPDATA%\igoor\database\igoor.db`.

## Database Architecture

### Table Prefixing
- All plugin tables are prefixed with `{plugin_name}_` 
- Example: `recorder_records` for the recorder plugin
- This prevents table name conflicts between plugins

### Metadata Management
- `plugin_metadata` table tracks database versions and table schemas for each plugin
- Supports schema versioning and migrations

## Plugin Database Tables

### 1. Recorder Plugin (`recorder`)
**Purpose**: Central audio recording storage and metadata

#### `recorder_records`
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique identifier for each recording |
| plugin | TEXT NOT NULL | Plugin that created the recording |
| created_at | TEXT NOT NULL | Timestamp when recording was created |
| filename | TEXT NOT NULL | Path to the audio file |

---

### 2. Speaker ID Plugin (`speakerid`)
**Purpose**: Manages speaker identification and voice reference recordings

#### `speakerid_speakers`
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique speaker identifier |
| people_id | INTEGER DEFAULT 0 | Reference to person/people database (if available) |

#### `speakerid_records`
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique record identifier |
| recorder_id | INTEGER NOT NULL | References `recorder_records.id` |
| speakers_id | INTEGER NOT NULL | References `speakerid_speakers.id` |

**Relationships**: Links recordings to specific speakers for voice recognition training

---

### 3. Shortcuts Plugin (`shortcuts`)
**Purpose**: Tracks usage of shortcut buttons for analytics and optimization

#### `shortcuts_usage`
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique usage record identifier |
| msg | TEXT NOT NULL | The message/command triggered by the shortcut |
| datetime | TIMESTAMP NOT NULL | When the shortcut was used |
| onboarding | INTEGER NOT NULL | Whether user was in onboarding mode (1/0) |
| bid | INTEGER NOT NULL | Button ID that was pressed |

---

### 4. Knowledge Base Plugin (`rag`)
**Purpose**: Retrieval-Augmented Generation system for user knowledge management

#### `rag_documents`
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique document identifier |
| title | TEXT | Document title (optional) |
| filename | TEXT NOT NULL | Path to the source file |
| created_at | TIMESTAMP | When document was added to knowledge base |

#### `rag_chunks`
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique chunk identifier |
| docstore_id | TEXT | Vector database document identifier |
| type | INTEGER | Type of content chunk (categorization) |
| content | TEXT | The actual text content |
| reason | TEXT | Why this chunk was created/extracted |
| theme | TEXT | Topic or category of the content |
| tags | TEXT | Comma-separated tags for search |
| created_at | TIMESTAMP | When chunk was created |
| document_id | INTEGER | References `rag_documents.id` |
| conversation_id | INTEGER | References `conversation_threads.id` |

**Relationships**: Links content chunks to source documents and conversation threads for context retrieval

---

### 5. Conversation Plugin (`conversation`)
**Purpose**: Manages conversation threads and message history

#### `conversation_threads`
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique thread identifier |
| start_time | TIMESTAMP | When conversation started |
| end_time | TIMESTAMP | When conversation ended |
| cause | TEXT | What triggered this conversation |
| topic | TEXT | Main topic of conversation |
| content | TEXT | Summary or key content |
| is_processed | BOOLEAN | Whether conversation has been processed by RAG system |

#### `conversation_msgs`
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique message identifier |
| thread_id | INTEGER | References `conversation_threads.id` |
| author | TEXT NOT NULL | Who sent the message (user/assistant) |
| datetime | TIMESTAMP | When message was sent |
| msg | TEXT | The message content |
| answers | TEXT | Response or answers to this message |
| msg_input | TEXT | Original input (if processed) |

**Relationships**: Groups messages into conversation threads for context management

---

### 6. Autocomplete Plugin (`autocomplete`)
**Purpose**: LLM-based autocomplete predictions and caching

#### `autocomplete_predictions`
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique prediction identifier |
| input | TEXT NOT NULL | User input that triggered prediction |
| completion | TEXT NOT NULL | The suggested completion |
| hits | INTEGER DEFAULT 1 | How many times this prediction was useful |
| created_at | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | When prediction was first created |
| updated_at | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | Last time this prediction was used |

## Cross-Plugin Relationships

### Recording ↔ Speaker Identification
- `speakerid_records.recorder_id` → `recorder_records.id`
- Links voice recordings to identified speakers

### RAG ↔ Conversation
- `rag_chunks.conversation_id` → `conversation_threads.id`
- Links knowledge chunks to conversation contexts

### RAG Document Management
- `rag_chunks.document_id` → `rag_documents.id`
- Links processed content chunks to source documents

## Database Access Methods

### For Plugin Developers

#### Initialization (Automatic)
```python
# In plugin.json
{
    "requires_db": true,
    "db_tables": {
        "my_table": {
            "schema": "CREATE TABLE IF NOT EXISTS my_table (id INTEGER PRIMARY KEY, name TEXT)",
            "version": "1.0"
        }
    }
}
```

#### Database Operations
```python
# Async queries
result = await self.db_execute("SELECT * FROM my_table WHERE name = ?", ("value",))

# Sync queries  
result = self.db_execute_sync("INSERT INTO my_table (name) VALUES (?)", ("value",))
```

#### Table Prefixing
- Database manager automatically prefixes table names with plugin name
- Write queries with simple table names: `SELECT * FROM my_table`
- Becomes: `SELECT * FROM plugin_my_table`

## Version Management

- Each table has a version number in `plugin.json`
- `plugin_metadata` table tracks current versions
- Schema changes require version bump
- **⚠️ IMPORTANT**: Database manager does NOT recreate tables on version changes - it only runs `CREATE TABLE IF NOT EXISTS`

### Schema Migration Process
Currently, there is **no automatic schema migration**. When you need to modify a table structure:

1. **Add columns**: Use `ALTER TABLE` in your plugin initialization code
2. **Remove columns**: Data remains but your code should handle missing columns
3. **Major restructuring**: Consider creating a new table with a different name

**Example for adding a column:**
```python
# In your plugin __init__
await self.db_execute("ALTER TABLE my_table ADD COLUMN new_field TEXT")
```

## Best Practices

1. **Use descriptive field names** - Clear naming helps other developers understand data flow
2. **Document relationships** - Foreign keys should reference actual plugin tables
3. **Version your schemas** - Always bump version when changing table structure
4. **Handle missing database gracefully** - Database access should be optional where possible
5. **Use appropriate data types** - TEXT for strings, INTEGER for IDs, TIMESTAMP for dates
6. **Consider data privacy** - Avoid storing sensitive personal information when possible

## Troubleshooting

### Common Issues
1. **Table not found** - Check plugin name prefix in database
2. **Foreign key constraints** - Ensure referenced tables exist and have correct prefixes
3. **Permission errors** - Database file should be in user's APPDATA directory
4. **Schema mismatches** - Version changes don't modify existing table structure, use ALTER TABLE for schema changes

### Debug Database Status
```python
self.debug_db_status()  # From BasePlugin
```

This documentation provides a complete overview of the IGOOR plugin database structure for new contributors.
