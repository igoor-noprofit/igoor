from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from prompt_manager import PromptManager
from context_manager import context_manager
from fastapi import APIRouter, Query, Response
import asyncio,json
from concurrent.futures import ThreadPoolExecutor

class Conversation(Baseplugin):  
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name, pm)
        self.settings = self.get_my_settings()
        self.conversation_is_open=False
        self.thread=[]
        self.topic=""
        self.current_thread_id = None
        self.router = None
        # Cache for last N conversations (formatted as XML string)
        self.last_conversations_cache = ""
        self.last_conversations_count = self.settings.get("last_conversations_count", 20)
        self.current_start_time = None  # Track start time of current conversation

    def _ensure_router(self):
        """Initialize FastAPI router for plugin endpoints"""
        if self.router is not None:
            return
        self.router = APIRouter(prefix="/api/plugins/conversation", tags=["conversation"])

        @self.router.get("/get_conversations")
        async def get_conversations(
            order_by: str = Query("start_time ASC", description="Order by clause (e.g., 'start_time ASC')"),
            limit: int = Query(20, description="Maximum number of conversations to retrieve")
        ):
            """Get conversation threads with ordering and limit"""
            try:
                # Parse order_by to ensure it's safe
                order_clauses = {
                    "start_time ASC": "start_time ASC",
                    "start_time DESC": "start_time DESC",
                    "end_time ASC": "end_time ASC",
                    "end_time DESC": "end_time DESC"
                }
                order_clause = order_clauses.get(order_by, "start_time ASC")

                sql = f"SELECT * FROM threads ORDER BY {order_clause} LIMIT ?"
                results = await self.db_execute(sql, (limit,))
                
                # Convert to list of dicts
                conversations = []
                for row in results:
                    conversations.append(dict(row))

                return conversations
            except Exception as e:
                self.logger.error(f"Error getting conversations: {e}")
                raise e

        @self.router.get("/conversations_for_llm")
        async def conversations_for_llm(
            format: str = Query("json", description="Response format: json, text, or markdown"),
            limit: int = Query(None, description="Maximum number of conversations to return (optional)")
        ):
            """
            Get all conversations with non-empty content, ordered by start_time ASC.
            Suitable for inclusion in LLM prompts.
            """
            try:
                # Validate format parameter
                valid_formats = ["json", "text", "markdown"]
                if format not in valid_formats:
                    raise ValueError(f"Invalid format '{format}'. Must be one of: {', '.join(valid_formats)}")

                # Build SQL query with optional limit
                sql = "SELECT id, start_time, topic, content FROM threads WHERE content IS NOT NULL AND content != '' ORDER BY start_time ASC"
                params = ()

                if limit is not None and limit > 0:
                    sql += " LIMIT ?"
                    params = (limit,)

                results = await self.db_execute(sql, params)

                if format == "json":
                    # Return JSON format
                    conversations = []
                    for row in results:
                        conversations.append({
                            "id": row['id'],
                            "start_time": row['start_time'],
                            "topic": row['topic'] or "",
                            "content": row['content']
                        })
                    return {"count": len(conversations), "conversations": conversations}

                elif format == "text":
                    # Return plain text format
                    lines = []
                    for row in results:
                        topic_display = row['topic'] or "No topic"
                        lines.append(f"Conversation {row['id']} - Started: {row['start_time']} - Topic: {topic_display}")
                        lines.append("---")
                        lines.append(row['content'])
                        lines.append("")
                    return Response(content="\n".join(lines), media_type="text/plain; charset=utf-8")

                elif format == "markdown":
                    # Return markdown format
                    lines = []
                    for row in results:
                        topic_display = row['topic'] or "No topic"
                        lines.append(f"## Conversation {row['id']} (Started: {row['start_time']})")
                        lines.append(f"**Topic:** {topic_display}")
                        lines.append("")
                        lines.append(row['content'])
                        lines.append("")
                    return Response(content="\n".join(lines), media_type="text/markdown; charset=utf-8")

            except Exception as e:
                self.logger.error(f"Error getting conversations for LLM: {e}")
                raise e

        @self.router.get("/start_transcribing")
        async def start_transcribing():
            """REST endpoint to trigger transcribing status"""
            self.logger.info("Transcribing started (via REST)")
            await self.send_status("transcribing_started")
            return {"status": "success"}
        
        @self.router.get("/end_transcribing")
        async def end_transcribing():
            """REST endpoint to trigger transcribing status"""
            self.logger.info("Transcribing ended (via REST)")
            await self.send_status("transcribing_ended")
            return {"status": "success"}
        
    def init_timeout(self):
        print("INIT TIMEOUT")
        self.timeout = int(self.settings.get("timeout", 120000)) / 1000  # Convert milliseconds to seconds
        self.warning_time = self.timeout - int(self.settings.get("warning_time", 5000)) / 1000  # Warning time in seconds
        self.timeout_task = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.reset_timeout()

    def cancel_timeout(self):
        if self.timeout_task:
            print("Cancelling existing timeout task")
            self.timeout_task.cancel()

    def reset_timeout(self):
        print("RESET TIMEOUT")
        self.cancel_timeout()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # No running event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        self.timeout_task = loop.create_task(self.start_timeout())
        self.send_message_to_frontend({"action": "resetCountdown"})

    async def start_timeout(self):
        print("Starting non-blocking timeout")
        try:
            self.send_message_to_frontend({"action": "startCountdown"})
            print(f"Waiting for {self.warning_time} seconds before warning")
            await asyncio.sleep(self.warning_time)
            print("Warning time elapsed, sending showProgressBar action")
            # Include the duration in milliseconds for the frontend
            self.send_message_to_frontend({
                "action": "showProgressBar", 
                "duration": int((self.timeout - self.warning_time) * 1000)  # Convert seconds to milliseconds
            })
            print(f"Waiting for {self.timeout - self.warning_time} seconds until timeout")
            await asyncio.sleep(self.timeout - self.warning_time)
            print("Timeout complete, triggering abandon_conversation")
            asyncio.create_task(self.pm.trigger_hook("abandon_conversation",cause="timeout"))
        except asyncio.CancelledError:
            print("Timeout task was cancelled")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    @hookimpl
    async def new_conversation(self):
        self.thread = []
        self.conversation_is_open = True
        context_manager.update_context("conversation", "")
        self.init_timeout()
        self.send_message_to_frontend({"action": "startCountdown"})
        
        # Create a new conversation in the database
        current_time = self._get_current_timestamp()
        self.current_start_time = current_time  # Track for cache
        result = await self.db_execute(
            "INSERT INTO threads (start_time, is_processed) VALUES (?, ?)",
            (current_time, False)
        )
        
        # Get the ID from the INSERT result (returned atomically from same connection)
        if result and len(result) > 0 and 'lastrowid' in result[0]:
            self.current_thread_id = result[0]['lastrowid']
            self.logger.info(f"Created new conversation with ID: {self.current_thread_id}")

    @hookimpl
    async def set_conversation_topic(self, topic):
        self.logger.info(f"Setting conversation topic to: {topic}")
        self.topic = topic

    @hookimpl
    async def update_conversation_topic(self, topic: str, conversation_id: int):
        """
        Update conversation topic in database directly.
        Used by memory plugin to set topic after conversation analysis.
        """
        self.logger.info(f"Updating conversation {conversation_id} topic to: {topic}")
        await self.db_execute(
            "UPDATE threads SET topic = ? WHERE id = ?",
            (topic, conversation_id)
        )

    @hookimpl
    async def get_conversation_msgs_containing(self, query_text: str):
        """
        Gets last 10 conversation messages containing the query_text.
        Returns a list of matching messages by datetime ASC
        Used by autocomplete
        """
        if not query_text:
            return []

        sql = """
            SELECT * FROM msgs
            WHERE msg LIKE ? AND author = 'master'
            ORDER BY datetime DESC
            LIMIT 10 
        """
        params = (f"%{query_text}%",)
        results = await self.db_execute(sql, params)
        print(f"Found {len(results)} messages containing '{query_text}' in conversation")
        if not results:
            return ""
        # Reverse to get ASC order after limiting DESC
        lines = [f"{row['datetime']}\t{row['msg']}" for row in reversed(results)]
        return "\n".join(lines)

    @hookimpl
    async def abandon_conversation(self, cause):
        if (not self.conversation_is_open):
            self.logger.info("Abandon conversation called, but conversation is not open")
            return
        self.send_message_to_frontend({"action": "abandon_conversation"})

        # IMPORTANT: Send view change immediately to ensure UI updates before any processing
        await self.send_switch_view_to_app("daily")

        txt = await self.get_conversation(format="txt")

        # Log the thread_id before creating the dictionary
        if (cause is None):
            cause = "timeout"

        last_conversation = {
            "thread": self.thread,
            "txt": txt,
            "cause": cause,
            "topic": self.topic,
            "thread_id": self.current_thread_id
        }

        if self.current_thread_id is not None:
            current_time = self._get_current_timestamp()
            await self.db_execute(
                "UPDATE threads SET end_time = ?, cause = ?, content = ? WHERE id = ?",
                (current_time, cause, txt, self.current_thread_id)
            )
            self.logger.info(f"Abandoned conversation {self.current_thread_id} with end time")

            # Update last conversations cache
            if txt and self.current_start_time:
                new_conv = self._format_single_conversation_xml(self.current_start_time, txt)
                self._prepend_to_cache(new_conv)

        # Reset conversation state after triggering the hook
        last_thread=self.thread
        last_topic=self.topic
        last_current_thread_id=self.current_thread_id

        self.thread = []
        self.topic = ""
        self.current_thread_id = None
        self.current_start_time = None
        context_manager.update_context("conversation", "")
        self.conversation_is_open = False
        self.cancel_timeout()

        # Create a separate task with explicit kwargs
        asyncio.create_task(
            self.pm.trigger_hook(
                "after_conversation_end",
                last_conversation={
                    "thread": last_thread,
                    "txt": txt,
                    "cause": cause,
                    "topic": last_topic,
                    "thread_id": last_current_thread_id
                }
            )
        )
        
    @hookimpl
    def startup(self):
        self._ensure_router()
        # Register router with the main FastAPI app if available
        if hasattr(self, 'pm') and hasattr(self.pm, 'fastapi_app'):
            self.pm.fastapi_app.include_router(self.router)

    @hookimpl
    async def gui_ready(self):
        """Load last conversations cache from database when GUI is ready"""
        await self._load_last_conversations_cache()

    async def _load_last_conversations_cache(self):
        """Load last N conversations from database into cache at startup"""
        try:
            sql = """
                SELECT start_time, content FROM threads 
                WHERE content IS NOT NULL AND content != '' 
                ORDER BY start_time DESC LIMIT ?
            """
            results = await self.db_execute(sql, (self.last_conversations_count,))
            if results:
                # Reverse to get chronological order (oldest first)
                conversations = list(reversed(results))
                self.last_conversations_cache = self._format_conversations_xml(conversations)
                self.logger.info(f"Loaded {len(conversations)} conversations into cache")
        except Exception as e:
            self.logger.error(f"Error loading last conversations cache: {e}")
        self.mark_ready()

    def _format_conversations_xml(self, conversations: list) -> str:
        """Format list of conversations as XML string for LLM prompts"""
        if not conversations:
            return ""
        
        lines = ["<last_conversations>"]
        for conv in conversations:
            # Truncate ISO timestamp to remove milliseconds (e.g., 2025-05-07T12:17:48.692972 -> 2025-05-07T12:17:48)
            start_time = conv.get('start_time', '')
            if '.' in start_time:
                start_time = start_time.split('.')[0]
            
            lines.append(start_time)
            lines.append(conv.get('content', ''))
            lines.append("---")
        
        lines.append("</last_conversations>")
        return "\n".join(lines)

    def _format_single_conversation_xml(self, start_time: str, content: str) -> str:
        """Format a single conversation for prepending to cache"""
        # Truncate ISO timestamp to remove milliseconds
        if '.' in start_time:
            start_time = start_time.split('.')[0]
        return f"{start_time}\n{content}\n---"

    def _prepend_to_cache(self, new_conv: str):
        """Prepend a new conversation to the cache and trim to max count"""
        if not self.last_conversations_cache:
            self.last_conversations_cache = f"<last_conversations>\n{new_conv}\n</last_conversations>"
            return
        
        # Extract existing conversations (remove tags)
        cache_content = self.last_conversations_cache
        cache_content = cache_content.replace("<last_conversations>\n", "").replace("\n</last_conversations>", "")
        
        # Prepend new conversation
        updated = f"<last_conversations>\n{new_conv}\n{cache_content}"
        
        # Count conversations and trim if needed (each conversation ends with ---)
        conv_parts = updated.split("---")
        # Remove last empty part if exists
        if conv_parts and not conv_parts[-1].strip():
            conv_parts = conv_parts[:-1]
        
        # Keep only last N conversations (from the end since new ones are at start)
        if len(conv_parts) > self.last_conversations_count:
            # Keep the first N conversation blocks (newest ones are first after prepending)
            conv_parts = conv_parts[:self.last_conversations_count]
            # Each part needs --- appended except we need proper structure
            # Rebuild properly: each conversation is date\ncontent followed by ---
            updated = "<last_conversations>\n" + "---\n".join(conv_parts) + "\n---\n</last_conversations>"
        else:
            updated = updated.rstrip() + "\n</last_conversations>"
        
        self.last_conversations_cache = updated

    @hookimpl
    def get_last_conversations(self) -> str:
        """Return cached last conversations as XML string"""
        return self.last_conversations_cache

    @hookimpl
    async def transcribing_started(self):
        self.logger.info("Transcribing started")
        await self.send_status("transcribing_started")
        
    @hookimpl
    async def transcribing_ended(self):
        self.logger.info("Transcribing ended")
        await self.send_status("transcribing_ended")
        
    @hookimpl
    async def add_msg_to_conversation(self, msg: str, author: str, msg_input: str) -> None:
        '''
        author can be:
            def     interlocutor
            master  user
        '''
        if not(self.conversation_is_open):
            await self.new_conversation()
        print(f"Adding {msg} to conversation with input {msg_input} and author {author}")
        newmsg = {"msg": msg, "author": author, "msg_input": msg_input}
        self.thread.append(newmsg)
        self.send_message_to_frontend(json.dumps(newmsg))
        bms = {"backend": "addmsg"}
        await self.send_message_to_app(json.dumps(bms))
        conv = await self.get_conversation(format="raw")
        context_manager.update_context("conversation", conv)
        self.reset_timeout()  # Reset the timeout when a new message is added
        
        # Store the message in the database
        if self.current_thread_id is not None:
            current_time = self._get_current_timestamp()
            await self.db_execute(
                "INSERT INTO msgs (thread_id, author, datetime, msg, msg_input) VALUES (?, ?, ?, ?, ?)",
                (self.current_thread_id, author, current_time, msg, msg_input)
            )
            self.logger.info(f"Added message to conversation {self.current_thread_id} with thread_id {self.current_thread_id}")
    
    def _get_current_timestamp(self):
        """Helper method to get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    @hookimpl
    async def remove_last_msg(self) -> None:
        if self.thread and self.conversation_is_open:
            self.thread.pop()
            conv = await self.get_conversation(format="raw")
            context_manager.update_context("conversation", conv)
            self.send_message_to_frontend({"action": "removeLastMessage"})
    
    @hookimpl
    async def delete_conversation(self):
        self.thread=[]
    
    
    # Other plugins can reset the timeout
    @hookimpl    
    def reset_conversation_timeout(self):
        if not self.conversation_is_open:
            print("Conversation is not open, skipping timeout reset")
            return {"timeout_active": False, "conversation_open": False}
            
        if self.timeout_task and not self.timeout_task.cancelled():
            print("Timeout is currently running, resetting it")
        else:
            print("No active timeout or timeout was cancelled, initializing a new one")
            
        self.reset_timeout()

        
    @hookimpl
    async def get_conversation(self, format="json", limit=None):
        if limit is not None and isinstance(limit, int) and limit > 0:
            # Use only the last 'limit' number of messages
            messages = self.thread[-limit:]
        else:
            # Use all messages if no limit is specified or if limit is invalid
            messages = self.thread
            
        if format == "json":
            return messages
        else:
            output = []
            for message in messages:
                if message["author"] == "def":
                    output.append(f"Q: {message['msg']}")
                else:
                    output.append(f"R: {message['msg']}")
            print(output)
            return "\n".join(output)
    
    def test_conversation(self):
        async def run_tasks():
            await self.add_msg_to_conversation("Comment s'appellent tes enfants ?", "def","test")
            await self.get_conversation()
            conversation_value = context_manager.get_value("conversation")
            print("Retrieved conversation from context:", conversation_value)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # No running event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_tasks())
        else:
            asyncio.create_task(run_tasks())
    
    def process_incoming_message(self, message):
        try:
            message_dict = json.loads(message)
            
            if message_dict.get('action') == 'get_settings':
                self.send_settings_to_frontend()
                return
            
            # Add handling for speak action
            if message_dict.get('action') == 'speak':
                asyncio.create_task(self.pm.trigger_hook("speak", message=message_dict.get('message')))
                return
                
            print(f"Default processing message for {self.plugin_name}: {message}")
                
        except json.JSONDecodeError:
            self.logger.error("Received message is not valid JSON.")