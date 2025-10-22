# IGOOR Plugin Hooks Documentation

## Overview

IGOOR uses the **pluggy** library for plugin management, implementing a hook-based architecture that allows plugins to interact with the core application and each other. Hooks are defined in `plugin_manager.py` and implemented by plugins using the `@hookimpl` decorator.

## Hook Architecture

### Hook Definition
- **Location**: `plugin_manager.py` - `MyAppSpec` class
- **Method**: Uses `@pluggy.HookspecMarker(app_name)` for hook specifications
- **Implementation**: Plugins use `@hookimpl` decorator to implement hooks
- **Execution**: Managed through `PluginManager.trigger_hook(hook_name, **kwargs)`

### Hook Calling Pattern
```python
# Trigger a hook from anywhere in the codebase
await self.pm.trigger_hook('hook_name', param1=value1, param2=value2)

# Plugin implementation
@hookimpl
def hook_name(self, param1, param2):
    # Your implementation here
    pass
```

## Available Hooks by Category

### 1. Plugin Lifecycle Hooks

#### `activate()`
- **Purpose**: Called when plugin is activated
- **Parameters**: None
- **Usage**: Initialize plugin resources, start services
- **Example**:
```python
@hookimpl
def activate(self):
    self.start_background_service()
    self.is_active = True
```

#### `deactivate()`
- **Purpose**: Called when plugin is deactivated
- **Parameters**: None
- **Usage**: Clean up resources, stop services
- **Example**:
```python
@hookimpl
def deactivate(self):
    self.stop_background_service()
    self.is_active = False
```

#### `startup()`
- **Purpose**: Called during application startup for all active plugins
- **Parameters**: None
- **Usage**: Load settings, initialize connections, prepare UI components
- **Example**:
```python
@hookimpl
def startup(self):
    self.settings = self.get_my_settings()
    self.initialize_connection()
```

#### `run_tests()`
- **Purpose**: Hook for running plugin-specific tests
- **Parameters**: None
- **Usage**: Execute plugin validation, self-tests

### 2. Settings Management Hooks

#### `custom_save_settings(plugin_name: str, settings)`
- **Purpose**: Allow plugins to handle custom setting saving logic
- **Parameters**:
  - `plugin_name` (str): Name of the plugin whose settings are being saved
  - `settings`: Settings data to be saved
- **Usage**: Custom validation, transformation, or storage of settings

#### `settings_updated(plugin_name: str, new_settings: dict)`
- **Purpose**: Called when any plugin's settings are updated
- **Parameters**:
  - `plugin_name` (str): Name of the plugin that was updated
  - `new_settings` (dict): The new settings values
- **Usage**: React to configuration changes, update internal state

#### `global_settings_updated()`
- **Purpose**: Called when the entire settings system is updated
- **Parameters**: None
- **Usage**: Refresh cached settings, update global configurations

### 3. Frontend Components Hook

#### `get_frontend_components()`
- **Purpose**: Provide Vue.js components to the frontend
- **Parameters**: None
- **Returns**: List of component dictionaries
- **Example**:
```python
@hookimpl
def get_frontend_components(self):
    return [
        {
            "vue": "myplugin_component.vue"
        }
    ]
```

### 4. GUI and Application State Hooks

#### `async gui_ready()`
- **Purpose**: Called when the GUI is fully loaded and ready
- **Parameters**: None
- **Usage**: Initialize UI-dependent features, start UI-related services

#### `async change_view(lastview, currentview)`
- **Purpose**: Called when the user switches between views
- **Parameters**:
  - `lastview`: Previous view name
  - `currentview`: New view name
- **Usage**: Update plugin state based on view changes

#### `async onboarding_toggled(is_onboarding)`
- **Purpose**: Called when onboarding mode is enabled/disabled
- **Parameters**:
  - `is_onboarding` (bool): Current onboarding state
- **Usage**: Enable/disable beginner-friendly features

#### `async user_idle_on_pc()`
- **Purpose**: Called when the user is detected as idle
- **Parameters**: None
- **Usage**: Start idle-time activities, perform background tasks

#### `async force_onboarding()`
- **Purpose**: Called to force the application into onboarding mode
- **Parameters**: None
- **Usage**: Reset user state, start tutorial flow

#### `async igoor_is_maximized()`
- **Purpose**: Called when IGOOR window is maximized
- **Parameters**: None
- **Usage**: Adjust UI for maximized state

#### `async igoor_is_minimized()`
- **Purpose**: Called when IGOOR window is minimized
- **Parameters**: None
- **Usage**: Pause resource-intensive operations

### 5. Text-to-Speech (TTS) Hooks

#### `speak(message: str)`
- **Purpose**: Primary TTS hook for speaking text
- **Parameters**:
  - `message` (str): Text to be spoken
- **Usage**: Main TTS implementation
- **Example**:
```python
@hookimpl
def speak(self, message):
    if self.is_loaded:
        self.tts_engine.speak(message)
```

#### `speak_fallback(message: str)`
- **Purpose**: Fallback TTS when primary TTS fails
- **Parameters**:
  - `message` (str): Text to be spoken
- **Usage**: Backup TTS implementation, often uses system TTS

#### `speak_as_igoor(message: str)`
- **Purpose**: TTS for system responses (as IGOOR persona)
- **Parameters**:
  - `message` (str): System message to be spoken
- **Usage**: System announcements, status updates

### 6. Automatic Speech Recognition (ASR) Hooks

#### `wakeword_detected()`
- **Purpose**: Called when a wake word is detected
- **Parameters**: None
- **Usage**: Start listening for commands, activate voice mode

#### `process_wake_word(text)`
- **Purpose**: Process detected wake word text
- **Parameters**:
  - `text`: Detected wake word text
- **Usage**: Validate wake word, trigger actions

#### `pause_asr()`
- **Purpose**: Pause speech recognition
- **Parameters**: None
- **Usage**: Temporarily disable microphone input

#### `restart_asr()`
- **Purpose**: Resume/restart speech recognition
- **Parameters**: None
- **Usage**: Re-enable microphone input

#### `async asr_msg(msg: str)`
- **Purpose**: Called when user speech is recognized
- **Parameters**:
  - `msg` (str): Recognized speech text
- **Usage**: Process user commands, input conversation text

### 7. Conversation Management Hooks

#### `set_conversation_topic(topic: str)`
- **Purpose**: Set the current conversation topic
- **Parameters**:
  - `topic` (str): New conversation topic
- **Usage**: Update conversation context, trigger topic-specific behavior

#### `new_conversation()`
- **Purpose**: Start a new conversation thread
- **Parameters**: None
- **Usage**: Reset conversation state, initialize new thread

#### `add_msg_to_conversation(msg, author, msg_input)`
- **Purpose**: Add a message to the current conversation
- **Parameters**:
  - `msg`: Message content
  - `author`: Message author (user/assistant)
  - `msg_input`: Original input text
- **Usage**: Store conversation history, update UI

#### `abandon_conversation(cause)`
- **Purpose**: Abandon the current conversation
- **Parameters**:
  - `cause`: Reason for abandonment
- **Usage**: Cleanup conversation state, trigger analysis

#### `after_conversation_end(last_conversation)`
- **Purpose**: Called after a conversation ends
- **Parameters**:
  - `last_conversation`: Final conversation data
- **Usage**: Analyze conversation, extract insights, update knowledge base

#### `reset_conversation_timeout()`
- **Purpose**: Reset the conversation timeout timer
- **Parameters**: None
- **Usage**: Prevent conversation timeout, extend session

#### `async get_conversation_msgs_containing(query_text: str)`
- **Purpose**: Search previous conversation messages
- **Parameters**:
  - `query_text` (str): Text to search for
- **Returns**: List of matching messages
- **Usage**: Provide context for autocomplete, memory retrieval

#### `async transcribing_started()`
- **Purpose**: Called when audio transcription starts
- **Parameters**: None
- **Usage**: Show transcription UI, prepare storage

#### `async transcribing_ended()`
- **Purpose**: Called when audio transcription ends
- **Parameters**: None
- **Usage**: Hide transcription UI, process results

### 8. AI Flow and RAG (Retrieval-Augmented Generation) Hooks

#### `rag_loaded()`
- **Purpose**: Called when RAG system is loaded and ready
- **Parameters**: None
- **Usage**: Start RAG-dependent services, confirm readiness

#### `send_prompt(prompt: str)`
- **Purpose**: Send a prompt to the AI system
- **Parameters**:
  - `prompt` (str): Prompt text to send
- **Usage**: Custom prompt processing, logging, modification

#### `async query_rag(query_text: str, store_types: list, return_chunk_ids: bool)`
- **Purpose**: Query the RAG knowledge base
- **Parameters**:
  - `query_text` (str): Search query
  - `store_types` (list): Types of knowledge stores to search
  - `return_chunk_ids` (bool): Whether to return chunk identifiers
- **Returns**: Search results from knowledge base
- **Usage**: Retrieve relevant information for AI responses

#### `async store_memory(fact: str, type: int, conversation_id: int, theme: str, tags: list, reason: str, created_at: None)`
- **Purpose**: Store information in the knowledge base
- **Parameters**:
  - `fact` (str): Information to store
  - `type` (int): Type of memory/concern
  - `conversation_id` (int): Related conversation
  - `theme` (str): Theme/category
  - `tags` (list): Tags for categorization
  - `reason` (str): Why this was stored
  - `created_at`: Creation timestamp
- **Usage**: Learn from conversations, build knowledge base

#### `async filter_by_timeframe(preflow_dict: dict, docstore_ids_by_type: dict)`
- **Purpose**: Filter RAG results by time constraints
- **Parameters**:
  - `preflow_dict` (dict): Pre-flow data
  - `docstore_ids_by_type` (dict): Document store IDs by type
- **Usage**: Apply time-based filtering to search results

#### `async clean_short_term_memory(clean_after_days: int)`
- **Purpose**: Clean up old short-term memories
- **Parameters**:
  - `clean_after_days` (int): Age threshold for cleanup
- **Usage**: Memory management, storage optimization

### 9. Autocomplete and Input Hooks

#### `store_autocomplete_prediction(input_text: str, completion: str)`
- **Purpose**: Store successful autocomplete predictions
- **Parameters**:
  - `input_text` (str): User input that triggered prediction
  - `completion` (str): The successful completion
- **Usage**: Learn from user behavior, improve predictions

#### `show_virtual_keyboard()`
- **Purpose**: Display virtual keyboard
- **Parameters**: None
- **Usage**: Show on-screen keyboard for touch input

#### `hide_virtual_keyboard()`
- **Purpose**: Hide virtual keyboard
- **Parameters**: None
- **Usage**: Hide on-screen keyboard

## Hook Implementation Guidelines

### Basic Implementation Pattern
```python
from plugin_manager import hookimpl
from plugins.baseplugin.baseplugin import Baseplugin

class MyPlugin(Baseplugin):
    def __init__(self, plugin_name, pm):
        super().__init__(plugin_name, pm)
    
    @hookimpl
    def hook_name(self, param1, param2):
        """Optional docstring explaining hook usage"""
        try:
            # Your implementation here
            result = self.process_data(param1, param2)
            return result  # Optional return value
        except Exception as e:
            self.logger.error(f"Error in hook_name: {e}")
            return None
```

### Error Handling Best Practices
1. **Always wrap hook implementations in try/except blocks**
2. **Log errors using `self.logger`** (not print statements)
3. **Return appropriate default values** for failed operations
4. **Don't let hook exceptions crash the application**

### Async vs Sync Hooks
- **Async hooks**: Use `async def` and `await` for I/O operations
- **Sync hooks**: Use regular `def` for simple operations
- **The plugin manager handles both types automatically**

### Hook Ordering and Priority
- **Multiple plugins can implement the same hook**
- **Execution order is determined by plugin loading order**
- **All implementations are called (unless one raises an exception)**

## Debugging Hooks

### Enable Hook Debugging
```python
# Set environment variable
IGOOR_DEBUG=True

# Or in code
import os
os.environ['IGOOR_DEBUG'] = 'True'
```

### Hook Logging
The plugin manager logs:
- Hook trigger events: `"Hook triggered: {hook_name}"`
- Hook parameters: `"Executing hook {hook_name} with kwargs: {kwargs}"`
- Hook execution results

### Testing Hooks
```python
# Test hook implementation manually
await plugin.pm.trigger_hook('hook_name', param1='test', param2='value')
```

## Common Hook Usage Patterns

### 1. Plugin Initialization Sequence
```python
class MyPlugin(Baseplugin):
    @hookimpl
    def startup(self):
        # Load settings and resources
        self.settings = self.get_my_settings()
        self.initialize_service()
    
    @hookimpl
    async def gui_ready(self):
        # Start UI-dependent operations
        self.start_ui_updates()
```

### 2. Event-Driven Processing
```python
class MyPlugin(Baseplugin):
    @hookimpl
    async def asr_msg(self, msg):
        # Process user voice input
        if msg.startswith("my command"):
            await self.handle_command(msg)
    
    @hookimpl
    def speak(self, message):
        # Optionally intercept or modify TTS
        if self.should_modify_message(message):
            message = self.modify_message(message)
        # Let other TTS plugins handle it
```

### 3. Cross-Plugin Communication
```python
class MyPlugin(Baseplugin):
    @hookimpl
    def settings_updated(self, plugin_name, new_settings):
        # React to other plugins' setting changes
        if plugin_name == "conversation":
            self.adapt_to_conversation_settings(new_settings)
```

This documentation provides a comprehensive guide to all available hooks in IGOOR, helping contributors understand how to properly implement and use the plugin system.
