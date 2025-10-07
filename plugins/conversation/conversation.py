from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from prompt_manager import PromptManager
from context_manager import context_manager
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
        result = await self.db_execute(
            "INSERT INTO threads (start_time, is_processed) VALUES (?, ?)",
            (current_time, False)
        )
        
        # Get the ID of the newly created thread
        thread_data = await self.db_execute("SELECT last_insert_rowid() as id")
        if thread_data and len(thread_data) > 0:
            self.current_thread_id = thread_data[0]['id']
            self.logger.info(f"Created new conversation with ID: {self.current_thread_id}")

    @hookimpl
    async def set_conversation_topic(self, topic):
        self.logger.info(f"Setting conversation topic to: {topic}")
        self.topic = topic

    @hookimpl
    async def get_conversation_msgs_containing(self, query_text: str):
        """
        Gets last 10 conversation messages containing the query_text.
        Returns a list of matching messages by datetime ASC
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
                "UPDATE threads SET end_time = ?, cause = ?, topic = ?, content = ? WHERE id = ?",
                (current_time, cause, self.topic, txt, self.current_thread_id)
            )
            self.logger.info(f"Abandoned conversation {self.current_thread_id} with end time and topic {self.topic}")
        
        # Reset conversation state after triggering the hook
        last_thread=self.thread
        last_topic=self.topic
        last_current_thread_id=self.current_thread_id
        
        self.thread = []
        self.topic = ""
        self.current_thread_id = None
        context_manager.update_context("conversation", "")
        self.send_message_to_frontend({"action": "abandon_conversation"})
        self.conversation_is_open = False
        self.cancel_timeout()
        await self.send_switch_view_to_app("daily")
        
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