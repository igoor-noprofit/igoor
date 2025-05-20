from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager
import os, json
from langchain_community.document_loaders import TextLoader
import pymupdf4llm
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import CharacterTextSplitter, MarkdownTextSplitter
from langchain.schema import Document  # Ensure all documents are of this type
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain.prompts import ChatPromptTemplate
import time,sys, asyncio, threading
import numpy as np
from typing import Union, List, Dict, Optional
from datetime import datetime, timedelta, date

# Vector store types
INGESTED = 0
LONG_TERM = 1
SHORT_TERM = 2
class Rag(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        
    @hookimpl
    def startup(self):
        print("RAG IS STARTING UP")
        self.is_loaded = False
        self.settings = self.get_my_settings()
        self.medias_folder_name = "medias"
        
        # Define folder names for the three vector stores
        self.index_folder_names = {
            INGESTED: "ingested",
            LONG_TERM: "long",
            SHORT_TERM: "short"
        }
        
        # Initialize vector stores
        self.vector_stores = {
            INGESTED: None,
            LONG_TERM: None,
            SHORT_TERM: None
        }
        
        self.index_loaded = {
            INGESTED: False,
            LONG_TERM: False,
            SHORT_TERM: False
        }
        
        self.embedding_loaded = False
        self.loading_event = asyncio.Event()
        
        self.score_threshold = self.settings.get("score_threshold", 0.5)
        
        
        # Start a thread to load both embedding model and indexes
        thread = threading.Thread(target=lambda: asyncio.run(self.initialize_resources()))
        thread.start()
        
    '''
        **************** SETUP ******************** 
    '''
    async def load_all_indexes(self):
        """Load all FAISS indexes"""
        for store_type, folder_name in self.index_folder_names.items():
            folder_path = os.path.join(self.plugin_folder, folder_name)
            
            # Check if the index exists
            if os.path.exists(folder_path) and not self.is_folder_empty(folder_name):
                await self.load_index(store_type)
            else:
                # Create empty index for this type
                self.logger.info(f"Creating empty index for store type {store_type}")
                self.vector_stores[store_type] = FAISS.from_documents(
                    [Document(page_content="Initial empty document", metadata={"source": "init"})],
                    self.embedding_function
                )
                await self.save_index(store_type)
                self.index_loaded[store_type] = True
    
    async def initialize_resources(self):
        # 1. Check if DB tables have been created
        self.logger.info("Checking database tables...")
        try:
            if not self.debug_db_status():
                self.logger.error("Database tables not properly initialized")
                self.loading_event.set()  # Signal even on error to prevent hanging
                return
        except Exception as e:
            self.logger.error(f"Error checking database status: {e}")
            self.loading_event.set()
            return
        
        # 2. Create necessary folders
        self.logger.info("Creating necessary folders...")
        self.create_folders()
        
        # Load embedding model in thread pool
        self.logger.info("Loading embedding model...")
        try:
            loop = asyncio.get_event_loop()
            self.embedding_function = await loop.run_in_executor(None, self.get_embedding_function)
            self.embedding_loaded = True
            self.logger.info("Embedding model loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading embedding model: {e}")
            self.loading_event.set()
            return
        
        # 3. Check for new files to ingest
        if self.subfolder_exists(self.medias_folder_name):
            self.logger.info("Media folder exists, checking for new files...")
            await self.check_for_new_files()
        else:
            self.logger.warning(f"Media folder '{self.medias_folder_name}' does not exist")
        
        # 4. Load all three FAISS indexes
        self.logger.info("Loading FAISS indexes...")
        await self.load_all_indexes()
        
        # Signal that loading is complete
        self.is_loaded = True
        self.loading_event.set()
        self.logger.info("RAG plugin initialization complete")
        await self.pm.trigger_hook(hook_name="rag_loaded")
        
        # Fix any docstore ID inconsistencies before running tests
        for store_type in [INGESTED, LONG_TERM, SHORT_TERM]:
            if self.index_loaded.get(store_type):
                await self.fix_docstore_id_inconsistencies(store_type)
        
        # await self.clear_memory(memory_type=LONG_TERM) 
        # await self.import_long_term_memories_from_json(os.path.join(self.plugin_folder,"chunks_new.json"))
        
        # await self.run_tests()
        # await self.clean_short_term_memory(7)
        # await self.print_all_chunks()
        # await self.check_all_chunks()
        # await self.test_query_rag()
        
        
    
    def create_folders(self):
        """Create all necessary folders for the plugin"""
        self.medias_folder = self.create_subfolder(self.medias_folder_name)
        
        # Create folders for each vector store
        for store_type, folder_name in self.index_folder_names.items():
            folder_path = self.create_subfolder(folder_name)
            self.logger.info(f"Created/verified folder for store type {store_type}: {folder_path}")
    
    async def load_index(self, store_type):
        """Load a specific FAISS index"""
        folder_name = self.index_folder_names[store_type]
        folder_path = os.path.join(self.plugin_folder, folder_name)
        
        self.logger.info(f"LOADING INDEX for type {store_type} from {folder_path}, PLEASE WAIT...")
        db_start_time = time.time()
        
        try:
            # Run the CPU-intensive FAISS loading in a thread pool
            loop = asyncio.get_event_loop()
            self.vector_stores[store_type] = await loop.run_in_executor(
                None, 
                lambda: FAISS.load_local(folder_path, self.embedding_function, allow_dangerous_deserialization=True)
            )
            db_end_time = time.time()
            self.logger.info(f"FAISS index type {store_type} loaded successfully in: {db_end_time - db_start_time:.2f} seconds")
            self.index_loaded[store_type] = True
        except Exception as e:
            self.logger.error(f"Error loading FAISS index type {store_type}: {e}")
            
    def get_datetime_bounds(self, timeframe_info, now_local):
        """
        Calculate datetime bounds based on timeframe information.
        
        Args:
            timeframe_info (dict): Dictionary containing timeframe information with fields like:
                - type: 'absolute' or 'relative'
                - start_date, end_date: Optional date strings in YYYY-MM-DD format
                - start_time, end_time: Optional time strings in HH:MM format
                - relative_days: Optional integer for days relative to current date
                - period: Optional period of day ('morning', 'afternoon', 'evening', 'full_day')
            now_local (datetime): Current local datetime to use as reference
            
        Returns:
            tuple: (start_datetime, end_datetime) in UTC format, either can be None if not applicable
        """
        try:
            # Initialize return values
            start_dt = None
            end_dt = None
            
            # Get timeframe type
            timeframe_type = timeframe_info.get("type")
            
            # Handle absolute dates (specific calendar dates)
            if timeframe_type == "absolute":
                # Process start date if provided
                if timeframe_info.get("start_date"):
                    start_date_str = timeframe_info["start_date"]
                    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                    
                    # Add start time if provided
                    if timeframe_info.get("start_time"):
                        start_time_str = timeframe_info["start_time"]
                        start_time = datetime.strptime(start_time_str, "%H:%M").time()
                        start_dt = datetime.combine(start_dt.date(), start_time)
                    else:
                        # Default to start of day
                        start_dt = datetime.combine(start_dt.date(), datetime.min.time())
                
                # Process end date if provided
                if timeframe_info.get("end_date"):
                    end_date_str = timeframe_info["end_date"]
                    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
                    
                    # Add end time if provided
                    if timeframe_info.get("end_time"):
                        end_time_str = timeframe_info["end_time"]
                        end_time = datetime.strptime(end_time_str, "%H:%M").time()
                        end_dt = datetime.combine(end_dt.date(), end_time)
                    else:
                        # Default to end of day
                        end_dt = datetime.combine(end_dt.date(), datetime.max.time())
            
            # Handle relative dates (like "yesterday", "last week")
            elif timeframe_type == "relative":
                # Get relative days if provided
                relative_days = timeframe_info.get("relative_days")
                
                if relative_days is not None:
                    # Calculate the reference date
                    reference_date = (now_local + timedelta(days=relative_days)).date()
                    self.logger.info(f"Calculated reference date: {reference_date}")
                    # Get period of day
                    period = timeframe_info.get("period")
                    if period == "full_period":
                        start_dt = datetime.combine(reference_date, datetime.strptime("00:00", "%H:%M").time())
                        end_dt = now_local
                    elif period == "morning":
                        # Morning: 6:00 AM - 12:00 PM
                        start_dt = datetime.combine(reference_date, datetime.strptime("06:00", "%H:%M").time())
                        end_dt = datetime.combine(reference_date, datetime.strptime("12:00", "%H:%M").time())
                    elif period == "afternoon":
                        # Afternoon: 12:00 PM - 6:00 PM
                        start_dt = datetime.combine(reference_date, datetime.strptime("12:00", "%H:%M").time())
                        end_dt = datetime.combine(reference_date, datetime.strptime("18:00", "%H:%M").time())
                    elif period == "evening":
                        # Evening: 6:00 PM - 11:59 PM
                        start_dt = datetime.combine(reference_date, datetime.strptime("18:00", "%H:%M").time())
                        end_dt = datetime.combine(reference_date, datetime.strptime("23:59", "%H:%M").time())
                    else:  # full_day or None
                        # Full day: 00:00 AM - 11:59 PM
                        start_dt = datetime.combine(reference_date, datetime.min.time())
                        end_dt = datetime.combine(reference_date, datetime.max.time())
                else:
                    # Handle special relative references without explicit days
                    reference = timeframe_info.get("reference", "").lower()
                    
                    if "yesterday" in reference:
                        reference_date = (now_local - timedelta(days=1)).date()
                        start_dt = datetime.combine(reference_date, datetime.min.time())
                        end_dt = datetime.combine(reference_date, datetime.max.time())
                    elif "last week" in reference:
                        # Last week: 7 days ago to yesterday
                        end_date = (now_local - timedelta(days=1)).date()
                        start_date = (now_local - timedelta(days=7)).date()
                        start_dt = datetime.combine(start_date, datetime.min.time())
                        end_dt = datetime.combine(end_date, datetime.max.time())
                    elif "last month" in reference:
                        # Approximate last month as 30 days ago to yesterday
                        end_date = (now_local - timedelta(days=1)).date()
                        start_date = (now_local - timedelta(days=30)).date()
                        start_dt = datetime.combine(start_date, datetime.min.time())
                        end_dt = datetime.combine(end_date, datetime.max.time())
                    elif "today" in reference:
                        reference_date = now_local.date()
                        start_dt = datetime.combine(reference_date, datetime.min.time())
                        end_dt = datetime.combine(reference_date, datetime.max.time())
            
            # Format datetime objects as strings for SQLite
            if start_dt:
                start_dt_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                start_dt_str = None
                
            if end_dt:
                end_dt_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                end_dt_str = None
                
            self.logger.warning(f"Calculated start_dt_str: {start_dt_str}")
            self.logger.warning(f"Calculated end_dt_str: {end_dt_str}")
            return start_dt_str, end_dt_str
            
        except Exception as e:
            self.logger.error(f"Error calculating datetime bounds: {e}")
            return None, None

    '''
        **************** INGESTION ******************** 
    '''
    async def check_for_new_files(self):
        """Check if there are new files in the medias folder that need to be ingested"""
        self.logger.info("Checking for new files to ingest...")
        folder_path = os.path.join(self.plugin_folder, self.medias_folder_name)
        
        # Get all files in the medias folder
        files_in_folder = set()
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            if os.path.isfile(file_path) and file_name.endswith((".txt", ".md", ".pdf")):
                files_in_folder.add(file_name)
        
        # Get files already in the database
        files_in_db = set()
        try:
            results = await self.db_execute("SELECT filename FROM documents")
            if results:
                files_in_db = {row['filename'] for row in results}
        except Exception as e:
            self.logger.error(f"Error retrieving files from database: {e}")
        
        # Find new files
        new_files = files_in_folder - files_in_db
        if new_files:
            self.logger.info(f"Found {len(new_files)} new files to ingest: {new_files}")
            await self.ingest_new_files(new_files)
        else:
            self.logger.info("No new files to ingest")

    async def ingest_new_files(self, new_files):
        """Ingest new files into the index and add them to the database"""
        folder_path = os.path.join(self.plugin_folder, self.medias_folder_name)
        for file_name in new_files:
            file_path = os.path.join(folder_path, file_name)
            original_file_docs = [] # Renamed to avoid confusion with split 'docs'

            title = os.path.splitext(file_name)[0]

            # --- Database Document Insertion ---
            document_id = None # Initialize
            try:
                await self.db_execute(
                    "INSERT INTO documents (title, filename, created_at) VALUES (?, ?, datetime('now'))",
                    (title, file_name)
                )
                result = await self.db_execute(
                    "SELECT id FROM documents WHERE filename = ? ORDER BY id DESC LIMIT 1", # Ensure latest if duplicates somehow exist
                    (file_name,)
                )
                document_id = result[0]['id'] if result else None
                if document_id is None:
                    self.logger.error(f"Failed to get document ID for {file_name} after insertion, skipping")
                    continue
                self.logger.info(f"Added document to database: {file_name} with ID {document_id}")
            except Exception as e:
                self.logger.error(f"Error adding document record {file_name} to database: {e}")
                continue # Skip this file if DB entry fails

            # --- Document Loading ---
            try:
                if file_name.endswith(".txt"):
                    loader = TextLoader(file_path, encoding='utf-8') # Specify encoding
                    original_file_docs = loader.load()
                elif file_name.endswith(".md"):
                    with open(file_path, "r", encoding="utf-8") as f:
                        md_content = f.read()
                    # Ensure metadata source is added if not already by loader
                    original_file_docs = [Document(page_content=md_content, metadata={"source": file_path})]
                elif file_name.endswith(".pdf"):
                    # Assuming load_pdf_content returns a string
                    pdf_content = self.load_pdf_content(file_path)
                    if pdf_content: # Check if content extraction was successful
                        original_file_docs = [Document(page_content=pdf_content, metadata={"source": file_path})]
                    else:
                        self.logger.warning(f"No content extracted from PDF: {file_name}")
                        continue # Skip if PDF content is empty
                else:
                    self.logger.warning(f"Unsupported file type: {file_name}, skipping")
                    continue

                if not original_file_docs:
                    self.logger.warning(f"No documents loaded from {file_name}, skipping")
                    continue

            except Exception as e:
                self.logger.error(f"Error loading content from {file_name}: {e}")
                continue # Skip this file if loading fails

            # --- Add DB document_id to Metadata (before splitting) ---
            for doc in original_file_docs:
                # Ensure metadata dict exists
                if not hasattr(doc, 'metadata') or doc.metadata is None:
                    doc.metadata = {}
                doc.metadata["document_id"] = document_id
                # Ensure source is present if loader didn't add it
                if "source" not in doc.metadata:
                    doc.metadata["source"] = file_path

            # --- Splitting ---
            text_splitter = CharacterTextSplitter(
                chunk_size=self.settings.get("chunk_size", 1000),
                chunk_overlap=self.settings.get("chunk_overlap", 200)
            )
            # Use split_documents which preserves metadata better
            docs = text_splitter.split_documents(original_file_docs)

            # Ensure document_id is preserved in all chunks (redundant if splitter behaves, but safe)
            for chunk in docs:
                if "document_id" not in chunk.metadata:
                    chunk.metadata["document_id"] = document_id
                    self.logger.warning(f"Had to re-add document_id to chunk metadata for {file_name}")
                # Add filename to chunk metadata for easier debugging
                chunk.metadata["filename"] = file_name


            if not docs:
                self.logger.warning(f"File {file_name} resulted in zero chunks after splitting, skipping.")
                continue

            # --- Add Chunks to Vector Store and Database ---
            current_docstore_ids = []
            try:
                vector_store = self.vector_stores.get(INGESTED) # Use .get for safer access

                # --- Case 1: Add to EXISTING Index ---
                if self.index_loaded.get(INGESTED) and vector_store:
                    self.logger.info(f"Adding {len(docs)} chunks from {file_name} to existing INGESTED index")
                    # Use add_documents which returns the list of added docstore_ids
                    added_ids = vector_store.add_documents(docs)
                    current_docstore_ids.extend(added_ids)

                    # --- METADATA UPDATE needed after add_documents too ---
                    # add_documents might not modify the docstore objects in place consistently across versions
                    if len(added_ids) == len(docs):
                        for i, docstore_id in enumerate(added_ids):
                            try:
                                # Access the document directly in the docstore
                                stored_doc = vector_store.docstore._dict.get(docstore_id)
                                if stored_doc:
                                    # Ensure metadata exists and add docstore_id
                                    if not hasattr(stored_doc, 'metadata') or stored_doc.metadata is None:
                                        stored_doc.metadata = {}
                                    stored_doc.metadata["docstore_id"] = docstore_id
                                else:
                                    self.logger.warning(f"Docstore ID {docstore_id} not found immediately after add_documents for {file_name}")
                            except Exception as meta_err:
                                self.logger.error(f"Error updating metadata for docstore_id {docstore_id}: {meta_err}")
                    else:
                        self.logger.error(f"Mismatch between number of docs ({len(docs)}) and added IDs ({len(added_ids)}) for {file_name}")
                        # Handle potential partial failure? For now, log error and proceed cautiously.


                # --- Case 2: Create NEW Index ---
                else:
                    self.logger.info(f"Creating new INGESTED index with {len(docs)} chunks from {file_name}")
                    # Create index using from_documents
                    self.vector_stores[INGESTED] = FAISS.from_documents(docs, self.embedding_function)
                    self.index_loaded[INGESTED] = True
                    vector_store = self.vector_stores[INGESTED] # Update reference

                    # Get all docstore_ids (should match the order of 'docs')
                    all_ids = list(vector_store.docstore._dict.keys())
                    current_docstore_ids.extend(all_ids)

                    # --- *** ADDED METADATA UPDATE STEP *** ---
                    if len(all_ids) == len(docs):
                        for i, docstore_id in enumerate(all_ids):
                            try:
                                # Access the document directly in the docstore
                                stored_doc = vector_store.docstore._dict.get(docstore_id)
                                if stored_doc:
                                        # Ensure metadata exists and add docstore_id
                                        if not hasattr(stored_doc, 'metadata') or stored_doc.metadata is None:
                                            stored_doc.metadata = {}
                                        stored_doc.metadata["docstore_id"] = docstore_id
                                else:
                                        self.logger.warning(f"Docstore ID {docstore_id} not found immediately after from_documents for {file_name}")
                            except Exception as meta_err:
                                self.logger.error(f"Error updating metadata for docstore_id {docstore_id}: {meta_err}")
                    else:
                        self.logger.error(f"Mismatch between number of docs ({len(docs)}) and docstore IDs ({len(all_ids)}) after from_documents for {file_name}")
                        # Handle error? If lengths don't match, subsequent DB insertion might be wrong.


                # --- Add Chunks to Database (Common Logic) ---
                if len(current_docstore_ids) == len(docs):
                    self.logger.info(f"Adding {len(docs)} chunk records to database for {file_name}")
                    for i, chunk in enumerate(docs):
                        docstore_id = current_docstore_ids[i]
                        db_doc_id = chunk.metadata.get("document_id") # Get ID from chunk metadata

                        if db_doc_id is None:
                            self.logger.error(f"Chunk {i} from {file_name} is missing database document_id in metadata. Cannot add to chunk table.")
                            continue # Skip adding this chunk to DB if document_id is missing

                        success = await self.add_chunk_to_db(
                            content=chunk.page_content,
                            chunk_type=INGESTED,
                            reason="ingested",
                            document_id=db_doc_id, # Use ID from chunk metadata
                            conversation_id=None,
                            docstore_id=docstore_id # Use the retrieved/generated ID
                        )
                        if not success:
                            self.logger.warning(f"Failed to add chunk {i} (docstore_id: {docstore_id}) from {file_name} to database")
                else:
                    self.logger.error(f"Skipping database chunk insertion for {file_name} due to ID count mismatch.")


                # --- Save Index (After processing each file) ---
                self.logger.info(f"Saving INGESTED index after processing {file_name}")
                await self.save_index(INGESTED)

            except Exception as e:
                self.logger.error(f"Error processing/adding chunks from {file_name} to FAISS/DB: {e}")
                # Consider if you need cleanup or rollback here

    async def add_chunk_to_db(self, content, chunk_type, reason, document_id=None, conversation_id=None, theme=None, tags=None, docstore_id=None, created_at=None):
        """Add a chunk to the sqlite database"""
        try:
            # Ensure content is not too large (SQLite has limits)
            if content and len(content) > 10000:  # Arbitrary limit to prevent very large chunks
                content = content[:10000] + "... (truncated)"
            
            # Determine the datetime value to use
            datetime_value = f"'{created_at}'" if created_at else "datetime('now')"
            
            # Check if theme and tags are provided
            if theme is not None and tags is not None:
                # Include theme and tags in the query
                await self.db_execute(
                    f"""
                    INSERT INTO chunks 
                    (type, content, reason, theme, tags, created_at, document_id, conversation_id, docstore_id) 
                    VALUES (?, ?, ?, ?, ?, {datetime_value}, ?, ?, ?)
                    """,
                    (chunk_type, content, reason, theme, tags, document_id, conversation_id, docstore_id)
                )
            else:
                # Use the original query without theme and tags
                await self.db_execute(
                    f"""
                    INSERT INTO chunks 
                    (type, content, reason, created_at, document_id, conversation_id, docstore_id) 
                    VALUES (?, ?, ?, {datetime_value}, ?, ?, ?)
                    """,
                    (chunk_type, content, reason, document_id, conversation_id, docstore_id)
                )
            return True
        except Exception as e:
            self.logger.error(f"Error adding chunk to database: {e}")
            return False
    
    @hookimpl
    async def save_index(self, store_type=None):
        """Save a specific or all FAISS indexes"""
        if store_type is not None:
            # Save specific index
            try:
                if not self.index_loaded[store_type]:
                    self.logger.warning(f"Index type {store_type} is not loaded, cannot save.")
                    return False
                    
                folder_name = self.index_folder_names[store_type]
                folder_path = os.path.join(self.plugin_folder, folder_name)
                
                # Ensure the folder exists
                os.makedirs(folder_path, exist_ok=True)
                
                self.vector_stores[store_type].save_local(folder_path)
                self.logger.info(f"Index type {store_type} saved successfully to {folder_path}.")
                return True
            except Exception as e:
                self.logger.error(f"Error saving FAISS index type {store_type}: {e}")
                return False
        else:
            # Save all indexes
            success = True
            for store_type in self.vector_stores.keys():
                if self.vector_stores[store_type] is not None:  # Only try to save if the store exists
                    if not await self.save_index(store_type):
                        success = False
            return success
    
    
    @hookimpl
    async def store_memory(self, fact: str, type: str, reason:str, conversation_id: int, theme:str, tags:list, created_at=None):
        """
        Store a memory in either long-term or short-term memory
        """
        # Debug all incoming parameters
        self.logger.info(f"Direct parameters: fact={fact}, type={type}, theme={theme}, tags={tags},conversation_id={conversation_id}, created_at={created_at}")
        if (type=="short"):
            memory_type=SHORT_TERM
        else:
            memory_type=LONG_TERM
        if not self.index_loaded[memory_type]:
            self.logger.error(f"Index type {memory_type} not loaded, cannot store memory")
            return False
        
        # Create embedding text that focuses on the most semantically relevant information
        embedding_text = fact
        if theme:
            embedding_text = f"{theme}: {embedding_text}"
        if tags:
            embedding_text = f"{embedding_text} [{', '.join(tags)}]"
        
        self.logger.info(f"Creating embedding for memory: {embedding_text}")
        # Create document for vector store with full metadata
        new_doc = Document(
            page_content=embedding_text,
            metadata={
                "source": "memory",
                "type": "long_term" if memory_type==LONG_TERM else "short_term",
                "theme": theme,
                "tags": tags,
                "conversation_id": conversation_id
            }
        )
        self.logger.info(f"Metadata: {new_doc.metadata}")
        try:
            # Add to vector store
            self.vector_stores[memory_type].add_documents([new_doc])

            # Get the docstore_id that was assigned to this document
            docstore_ids = list(self.vector_stores[memory_type].docstore._dict.keys())
            docstore_id = docstore_ids[-1]  # Get the last added docstore_id

            # Update the document's metadata with the docstore_id
            # This ensures that when we retrieve it later, it will have the docstore_id
            for doc_id, doc in self.vector_stores[memory_type].docstore._dict.items():
                if doc_id == docstore_id:
                    doc.metadata["docstore_id"] = docstore_id
                    break

            # Store the full structured data as JSON in the content field
            content = embedding_text
            tags_json = json.dumps(tags)
            # content = embedding_text
            # tags_json = tags
            if created_at is None:
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Use the updated add_chunk_to_db method
            success = await self.add_chunk_to_db(
                content=content,
                chunk_type=memory_type,
                reason=reason,
                document_id=None,
                conversation_id=conversation_id,
                theme=theme,
                tags=tags_json,
                docstore_id=docstore_id,
                created_at=created_at
            )
            
            if success:
                await self.save_index(memory_type)
                self.logger.info(f"Successfully stored memory (type={memory_type}, conversation_id={conversation_id}): {fact}")
                return True
            else:
                self.logger.error(f"Failed to add memory to database (conversation_id={conversation_id})")
                return False
        except Exception as e:
            self.logger.error(f"Error adding memory to index: {e}")
            return False
    
    # Function to load PDF content and return Document object
    def load_pdf_content(self,file_path):
        md_text = pymupdf4llm.to_markdown(file_path)
        return md_text

    def get_embedding_function(self):
        self.logger.debug("LOADING EMBEDDING FUNCTION")
        embedding_model = self.settings.get("embedding_model")
        model_kwargs = {"device": "cpu", 'trust_remote_code': True}
        encode_kwargs = {"normalize_embeddings": True}
        
        hf = HuggingFaceBgeEmbeddings(
            model_name=embedding_model, model_kwargs=model_kwargs, encode_kwargs=encode_kwargs
        )
        return hf

    def create_index(self):
        self.logger.info("CREATING DB, PLEASE WAIT...")
        db_start_time = time.time()
        folder_path = os.path.join(self.plugin_folder,"medias")
        self.logger.info(f"Folder path: {folder_path}")
        # Load all .txt and .pdf files
        documents = []
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            
            if file_name.endswith(".txt"):
                loader = TextLoader(file_path)
                documents.extend(loader.load())
            elif file_name.endswith(".md"):
                with open(file_path, "r", encoding="utf-8") as f:
                    md_content = f.read()
                # Wrap the markdown content in a Document object with appropriate metadata
                documents.append(Document(page_content=md_content, metadata={"source": file_path}))
            elif file_name.endswith(".pdf"):
                md_content = self.load_pdf_content(file_path)
                documents.append(Document(page_content=md_content, metadata={"source": file_path}))
                
            # Extract title from filename (remove extension)
            title = os.path.splitext(file_name)[0]
            
            # Add file to database if it's not already there
            try:
                # Use synchronous execution since we're in a synchronous method
                existing = self.db_execute_sync(
                    "SELECT filename FROM documents WHERE filename = ?", 
                    (file_name,)
                )
                
                if not existing:
                    self.db_execute_sync(
                        "INSERT INTO documents (title, filename, created_at) VALUES (?, ?, datetime('now'))",
                        (title, file_name)
                    )
                    self.logger.info(f"Added document to database: {file_name}")
            except Exception as e:
                self.logger.error(f"Error adding document to database: {e}")

        # Check if there are no documents
        if not documents:
            self.logger.warning("No documents found in the folder. FAISS index cannot be created.")
            return False

        # Split documents
        text_splitter = CharacterTextSplitter(chunk_size=self.settings.get("chunk_size"), chunk_overlap=self.settings.get("chunk_overlap"))
        docs = text_splitter.split_documents(documents)

        for doc in docs:
            if "pdf" in doc.metadata["source"]:
                print(doc.page_content)
                print("-------")

        self.logger.info("CREATING INDEX")
        # Rename self.db to self.vector_store
        self.vector_store = FAISS.from_documents(docs, self.embedding_function)
        self.vector_store.save_local(self.index_folder)
        self.logger.info("FAISS index saved.")
        db_end_time = time.time()
        self.logger.info(f"DB FAISS index created successfully in : {db_end_time - db_start_time:.2f} seconds")
        
        # Set these flags directly instead of calling the async method
        self.index_loaded = True
        self.is_loaded = True
        self.loading_event.set()  # Signal that loading is complete
        return True
    
    
    '''
        
        ************************ SEARCH ***************************** 
    
    '''
    
    @hookimpl
    async def query_rag(self, query_text: str, store_types: list, return_chunk_ids:bool) -> Union[str, dict, bool]:
        # Check if the RAG system is loaded. If not, return an empty/informative result.
        chunk_ids_by_store = {
            INGESTED: [],
            LONG_TERM: [],
            SHORT_TERM: []
        }
        all_results = []
        if not self.is_loaded:
            if return_chunk_ids:
                # Mimic the behavior of the final return block for chunk IDs when no results are found.
                # The original code logs a warning if no chunk IDs are found.
                self.logger.warning("Indexes not loaded: No chunk IDs will be returned as RAG is not ready.")
                return {} # This is what `{k: v for k, v in chunk_ids_by_store.items() if v}` would yield for empty/no results.
            else:
                # Mimic the behavior of the final return block for text when no results are found.
                return "No relevant information found."

        # Original method logic continues below
        try:
            self.logger.debug(f"QUERYING INDEX with text: {query_text} in store_types: {store_types}")
            # Ensure that if is_loaded is true, we still wait for the loading process to fully complete.
            await self.loading_event.wait()             
            
            # Get the number of chunks to retrieve per store from settings
            chunk_num = self.settings.get("chunk_num", 4)  # Default to 4 if not specified
            self.logger.debug(f"Using chunk_num={chunk_num} from settings")
            
            # Default to all store types if none specified
            if store_types is None:
                store_types = [INGESTED, LONG_TERM, SHORT_TERM]
            
            # Ensure store_types is a list
            if not isinstance(store_types, list):
                store_types = [store_types]
            
            for store_type in store_types:
                if not self.index_loaded[store_type]:
                    self.logger.warning(f"Index type {store_type} not loaded yet, skipping")
                    continue
                    
                start_time = time.time()
            
                if store_type == SHORT_TERM:
                    results = await self.search_short_term_memory(query_text=query_text)
                else:
                    # For INGESTED and LONG_TERM, use the regular chunk_num approach
                    results = await self.search_in_FAISS(query_text=query_text,store_type=store_type,k=chunk_num,score_threshold=1)
                    search_end_time = time.time()
                    self.logger.debug(f"Store type {store_type} search time: {search_end_time - start_time:.2f} seconds")
                
                # Process results which now include (doc, score, index)
                for doc, score, index in results:
                    # Add store type to metadata for tracking
                    doc.metadata["store_type"] = store_type
                    doc.metadata["score"] = score
                    doc.metadata["index"] = index
                    
                    # Add to results
                    all_results.append(doc)
                    
                    # Add to chunk IDs dictionary
                    chunk_ids_by_store[store_type].append(index)
            
            # If return_chunk_ids is True, return the dictionary of chunk IDs
            if return_chunk_ids:
                # Filter out empty lists
                # self.logger.debug(f"Returning chunk IDs: {chunk_ids_by_store}")
                if not any(chunk_ids_by_store.values()):
                    self.logger.warning("No chunk IDs found for any store type.")
                return {k: v for k, v in chunk_ids_by_store.items() if v}
            
            # Otherwise, return the context text as before
            if all_results:
                context_text = "\n\n---\n\n".join([doc.page_content for doc in all_results])
                return context_text
            else:
                return "No relevant information found."
                
        except Exception as e:
            self.logger.error(f"An error occurred during query_rag execution: {e}")
            return False
    
    @hookimpl    
    async def filter_by_timeframe(self,preflow_dict: dict, docstore_ids_by_type: dict):
        """
        Filters memories from SQLite based on LLM timeframe and docstore IDs.

        Args:
            preflow_dict (dict): The JSON dictionary returned by the LLM.
            db_path (str): Path to the SQLite database file.
            docstore_ids_to_retrieve (list): A list of docstore_id strings to filter by.
            
        """
        if preflow_dict is None:
            preflow_dict = {}
        results_by_type = {INGESTED: [], LONG_TERM: [], SHORT_TERM: []} # Initialize for all types

        # Validate input format
        if not isinstance(docstore_ids_by_type, dict):
            # Handle the case where it might be a list containing a dict (as seen before)
            if isinstance(docstore_ids_by_type, list) and len(docstore_ids_by_type) == 1 and isinstance(docstore_ids_by_type[0], dict):
                self.logger.warning("Received docstore_ids as a list containing a dict, using the inner dict.")
                docstore_ids_by_type = docstore_ids_by_type[0]
            else:
                self.logger.warning(f"Unexpected format for docstore_ids: {type(docstore_ids_by_type)}. Expected dict. Processing failed.")
                return results_by_type # Return empty initialized dict

        timeframe_info = preflow_dict.get("timeframe")
        apply_time_filter = bool(timeframe_info and timeframe_info.get("type")) # Check if timeframe exists and has a type

        start_dt_utc = None
        end_dt_utc = None

        # Calculate time bounds *once* if filter is needed
        if apply_time_filter:
            self.logger.info("Timeframe provided, calculating bounds.")
            now_local = datetime.now()
            start_dt_utc, end_dt_utc = self.get_datetime_bounds(timeframe_info, now_local)
            if start_dt_utc is None and end_dt_utc is None:
                self.logger.warning("Timeframe bounds calculation failed, time filter will not be applied.")
                apply_time_filter = False # Disable filter if bounds are invalid

        # Iterate through each store type provided in the input
        for store_type_key, docstore_ids in docstore_ids_by_type.items():
            # Ensure store_type is an integer key
            try:
                store_type = int(store_type_key)
                if store_type not in results_by_type:
                    self.logger.warning(f"Received unexpected store_type key: {store_type_key}. Skipping.")
                    continue # Skip if key is not 0, 1, or 2
            except (ValueError, TypeError):
                self.logger.warning(f"Could not convert store_type key '{store_type_key}' to integer. Skipping.")
                continue

            # Ensure docstore_ids is a list
            if not isinstance(docstore_ids, list):
                self.logger.warning(f"Expected list for docstore_ids of type {store_type}, got {type(docstore_ids)}. Skipping.")
                results_by_type[store_type] = []
                continue

            # Ensure all elements are strings
            current_docstore_ids = [str(id_val) for id_val in docstore_ids]

            if not current_docstore_ids:
                self.logger.info(f"No valid docstore_ids provided for store_type {store_type}. Skipping query.")
                results_by_type[store_type] = []
                continue

            # Use placeholders for safe querying
            placeholders = ', '.join('?' for _ in current_docstore_ids)
            base_sql = f"""
                SELECT created_at, content
                FROM chunks
                WHERE docstore_id IN ({placeholders})
            """
            params = list(current_docstore_ids) # Parameters for the IN clause

            # Add type filtering based on the current store_type being processed
            base_sql += " AND type = ? "
            params.append(store_type)

            # Add time filtering conditions *only* if timeframe is provided AND store_type is SHORT_TERM (2)
            if apply_time_filter and store_type == SHORT_TERM:
                self.logger.info(f"Applying time filter for SHORT_TERM store (type {store_type}).")
                if start_dt_utc and end_dt_utc:
                    base_sql += " AND created_at BETWEEN ? AND ? "
                    params.extend([start_dt_utc, end_dt_utc])
                elif start_dt_utc:
                    base_sql += " AND created_at >= ? "
                    params.append(start_dt_utc)
                elif end_dt_utc:
                    base_sql += " AND created_at <= ? "
                    params.append(end_dt_utc)
            elif apply_time_filter:
                self.logger.info(f"Time filter requested but not applied for store_type {store_type} (only applied to SHORT_TERM).")

            # Add ordering
            base_sql += " ORDER BY created_at ASC;"

            # self.logger.info(f"Executing SQL for store_type {store_type}: {base_sql}")
            # self.logger.info(f"With parameters for store_type {store_type}: {params}")

            rows = [] # Initialize rows for this type

            try:
                # Use the correct db_execute method which handles connection and cursor
                rows = await self.db_execute(base_sql, params)

                # Check if rows were returned successfully
                if rows is None:
                    self.logger.error(f"Database query execution failed or returned None for store_type {store_type}.")
                    results_by_type[store_type] = [] # Store empty list on DB error for this type
                    continue # Move to the next store type
                elif not rows:
                    self.logger.info(f"Database query returned no rows matching the criteria for store_type {store_type}.")
                    results_by_type[store_type] = []
                    continue
                else:
                    self.logger.info(f"Database query returned {len(rows)} rows for store_type {store_type} before processing.")

                # Process the fetched rows for the current store_type
                current_results = []
                for i, row in enumerate(rows):
                    # self.logger.debug(f"Processing row {i+1}/{len(rows)} for type {store_type}: {row}")
                    created_at_ts = row.get('created_at')
                    content = row.get('content')

                    # --- Timestamp parsing logic (same as before) ---
                    created_at_dt = None
                    if isinstance(created_at_ts, str):
                        try:
                            created_at_dt = datetime.fromisoformat(created_at_ts.replace(' Z', '+00:00'))
                        except ValueError:
                            try:
                                created_at_dt = datetime.strptime(created_at_ts, '%Y-%m-%d %H:%M:%S.%f')
                            except ValueError:
                                try:
                                    created_at_dt = datetime.strptime(created_at_ts, '%Y-%m-%d %H:%M:%S')
                                except ValueError:
                                    self.logger.warning(f"Could not parse timestamp string for type {store_type}: {created_at_ts}")
                                    # created_at_dt remains None
                    elif isinstance(created_at_ts, datetime):
                        created_at_dt = created_at_ts
                    else:
                        self.logger.warning(f"Unexpected type for created_at in row {i+1} for type {store_type}: {type(created_at_ts)}")
                        # created_at_dt remains None
                    # --- End Timestamp parsing logic ---

                    if created_at_dt:
                        # --- Timezone localization logic (same as before) ---
                        try:
                            import pytz
                            if created_at_dt.tzinfo is None:
                                created_at_dt = pytz.utc.localize(created_at_dt) # Assume UTC if naive
                            created_at_local = created_at_dt.astimezone()
                        except ImportError:
                            self.logger.warning("pytz not installed, cannot localize timezone. Using naive datetime.")
                            created_at_local = created_at_dt
                        # --- End Timezone localization logic ---

                        # For INGESTED, do not include created_at in the result string
                        if store_type == INGESTED:
                            if content and content.strip():
                                current_results.append(f"{content}")
                            else:
                                self.logger.warning(f"Skipping row {i+1} for type {store_type} due to empty or whitespace content.")
                        else:
                            if content and content.strip():
                                formatted_ts = created_at_local.strftime('%Y-%m-%d %H:%M:%S')
                                current_results.append(f"{formatted_ts}\t{content}")
                            else:
                                self.logger.warning(f"Skipping row {i+1} for type {store_type} due to empty or whitespace content.")

                    else:
                        self.logger.warning(f"Skipping row {i+1} for type {store_type} due to invalid or unparseable timestamp.")

                results_by_type[store_type] = current_results # Assign results for this type

            except Exception as e:
                self.logger.error(f"Database error during query for store_type {store_type}: {e}")
                self.logger.error(f"Failed SQL for store_type {store_type}: {base_sql}")
                self.logger.error(f"Failed PARAMS for store_type {store_type}: {params}")

        self.logger.info(f"Filter by timeframe finished. Returning results grouped by type: { {k: len(v) for k, v in results_by_type.items()} }")
        return results_by_type
        
    
    async def search_short_term_memory(self, query_text: str):
        self.logger.debug("SEARCHING SHORT TERM MEMORY")
        try:
            # Get more candidates for filtering by score
            max_candidates = min(50, len(self.vector_stores[SHORT_TERM].index_to_docstore_id))
            
            # Skip if only the initial empty document exists
            if max_candidates <= 1:
                self.logger.info(f"SHORT_TERM store has only the initial document, skipping")
                return []
                
            # Get more candidates to filter by score
            results = await self.search_in_FAISS(query_text=query_text,store_type=SHORT_TERM,k=max_candidates,score_threshold=self.score_threshold)
            print(f"------ {max_candidates} RESULTS: {results} --------")
            print(f"------ UP TO {max_candidates} RESULTS: {results} --------")
                
        except Exception as e:
            self.logger.error(f"Error querying SHORT_TERM store: {e}")
            results = []
        return results
    
    async def search_in_FAISS(self, query_text: str, store_type: str, k: int, score_threshold: float) -> list:
        """
        Search in specific FAISS vector store and return results with scores and docstore_ids.
        """
        if store_type not in self.vector_stores or not self.vector_stores[store_type]:
            self.logger.warning(f"Vector store '{store_type}' not found or is empty.")
            return []

        results = []
        processed_results = []
        try:
            # Ensure the index is not empty before searching
            if not self.vector_stores[store_type].index_to_docstore_id:
                self.logger.warning(f"Vector store '{store_type}' has an empty index_to_docstore_id map.")
                return []

            # Determine a reasonable number of candidates to fetch initially
            # Fetch more candidates than k initially to allow for score filtering
            num_docs_in_index = len(self.vector_stores[store_type].index_to_docstore_id)
            fetch_k = min(max(k * 5, 20), num_docs_in_index) # Fetch more to filter by score, capped by index size

            if fetch_k == 0:
                self.logger.warning(f"Vector store '{store_type}' index is effectively empty for search.")
                return []

            loop = asyncio.get_event_loop()
            # Run the synchronous FAISS search in a thread pool executor
            try:
                results = await loop.run_in_executor(
                    None,
                    lambda: self.vector_stores[store_type].similarity_search_with_score(
                        query_text,
                        k=fetch_k # Fetch more candidates
                    )
                )
            except Exception as e:
                self.logger.error(f"Error during FAISS search in '{store_type}' store: {e}")
                return []

            # --- Correction: Use store_type consistently ---
            current_docstore = self.vector_stores[store_type].docstore._dict
            # No need for docstore_to_index map if we get docstore_id from metadata

            count = 0
            for doc, score in results:
                # Filter by score threshold
                if score <= score_threshold:
                    if doc.page_content.startswith("Initial empty document"):
                        self.logger.debug(f"Ignoring known initial placeholder document (score={score:.4f})")
                        continue 
                    # Get the docstore_id directly from the metadata
                    docstore_id = doc.metadata.get("docstore_id")

                    if docstore_id is not None:
                        # Verify the docstore_id actually exists in the docstore
                        # This is critical to prevent 'ID not found' errors
                        if docstore_id not in current_docstore:
                            # This case should ideally not happen if ingestion is correct
                            self.logger.warning(f"Found docstore_id '{docstore_id}' in metadata but not in '{store_type}' docstore for doc starting with: {doc.page_content[:50]}...")
                            # Skip this document since its ID doesn't exist in the docstore
                            continue
                        # If we get here, the docstore_id exists in the current_docstore
                        # self.logger.debug(f"Adding chunk: score={score:.4f}, docstore_id={docstore_id}")
                        processed_results.append((doc, score, docstore_id))
                        count += 1
                    else:
                        # Fallback: Try to find based on content if ID wasn't in metadata (less reliable, maybe log warning)
                        # This indicates a potential issue during ingestion where metadata wasn't updated/saved correctly
                        self.logger.warning(f"Missing 'docstore_id' in metadata for retrieved doc (score={score:.4f}) starting with: {doc.page_content[:50]}... Attempting content match (inefficient).")
                        found_by_content = False
                        # --- Correction: Use store_type consistently ---
                        for current_id, stored_doc in current_docstore.items():
                            # Be cautious with direct content comparison - might be slow or slightly differ
                            if stored_doc.page_content == doc.page_content:
                                self.logger.debug(f"Found docstore_id {current_id} by content match (score={score:.4f})")
                                processed_results.append((doc, score, current_id)) # Use the found ID
                                count += 1
                                found_by_content = True
                                break # Found the match
                        if not found_by_content:
                            self.logger.error(f"Could not find docstore_id via metadata or content match for doc (score={score:.4f}) starting with: {doc.page_content[:50]}...")

                    # Stop once we have enough results satisfying the original k
                    if count >= k:
                        break
                else:
                    self.logger.debug(f"Skipping chunk score={score:.4f} (above threshold {score_threshold})")
                    # Since results are ordered by similarity, we can potentially break early
                    # if we fetched significantly more than k initially.
                    # break # Uncomment this if you are sure score increases monotonically

            self.logger.debug(f"Found {len(processed_results)} chunks in '{store_type}' with score <= {score_threshold} (target k={k})")
            return processed_results # Return the filtered and processed list

        except KeyError:
            self.logger.error(f"Vector store type '{store_type}' does not exist.")
            return []
        except Exception as e:
            self.logger.error(f"Error during FAISS search or processing in '{store_type}' store: {e}")
            # self.logger.error(traceback.format_exc())
            # Return whatever was processed so far, or an empty list
            return processed_results if processed_results else []
    
    '''
        
        ************************ CLEANING ***************************** 
        
    '''
    @hookimpl
    async def clean_short_term_memory(self, clean_after_days: int):
        """
        Clean short-term memories older than the specified number of days.
        
        Args:
            clean_after_days (int): Number of days after which memories should be cleaned
        """
        self.logger.info(f"Cleaning short-term memories older than {clean_after_days} days")
        
        # Wait for RAG to be fully loaded
        if not self.is_loaded:
            self.logger.info("Waiting for RAG to be fully loaded before cleaning memories...")
            await self.loading_event.wait()
        
        try:
            # 1. Get IDs of memories to be cleaned from the database
            cutoff_date = datetime.now() - timedelta(days=clean_after_days)
            cutoff_date_str = cutoff_date.isoformat()
            
            # Query the database for short-term memories older than the cutoff date
            # Make sure to get the docstore_ids which are needed for FAISS deletion
            memories_to_clean = await self.db_execute(
                "SELECT id, docstore_id FROM chunks WHERE type = ? AND created_at < ?",
                (SHORT_TERM, cutoff_date_str)
            )
            
            if not memories_to_clean:
                self.logger.info(f"No short-term memories found older than {clean_after_days} days")
                return True
                
            self.logger.info(f"Found {len(memories_to_clean)} short-term memories to clean")
            
            # 2. Extract and validate docstore_ids for FAISS deletion
            valid_docstore_ids = []
            invalid_db_ids = []
            
            # Get current docstore IDs from vector store
            if not self.index_loaded.get(SHORT_TERM) or self.vector_stores.get(SHORT_TERM) is None:
                self.logger.error("Short-term memory vector store not loaded")
                return False
                
            current_docstore = self.vector_stores[SHORT_TERM].docstore._dict
            
            # Validate each docstore_id
            for memory in memories_to_clean:
                db_id = memory['id']
                docstore_id = memory['docstore_id']
                
                if not docstore_id:
                    # No docstore_id, just delete from database
                    invalid_db_ids.append(db_id)
                    continue
                    
                # Check if this docstore_id exists in the vector store
                if docstore_id in current_docstore:
                    valid_docstore_ids.append(docstore_id)
                else:
                    # Docstore ID doesn't exist in vector store, just delete from database
                    self.logger.warning(f"Found docstore_id '{docstore_id}' in database but not in vector store")
                    invalid_db_ids.append(db_id)
            
            # 3. Delete valid IDs from both FAISS and database
            success = True
            if valid_docstore_ids:
                self.logger.info(f"Deleting {len(valid_docstore_ids)} valid docstore IDs from vector store and database")
                success = await self.delete_chunks(SHORT_TERM, valid_docstore_ids)
                if not success:
                    self.logger.error("Failed to delete chunks from vector store")
            else:
                self.logger.info("No valid docstore IDs found to delete from vector store")
            
            # 4. Delete invalid IDs from database only
            if invalid_db_ids:
                self.logger.info(f"Cleaning {len(invalid_db_ids)} database records with invalid docstore IDs")
                placeholders = ', '.join('?' for _ in invalid_db_ids)
                await self.db_execute(
                    f"DELETE FROM chunks WHERE id IN ({placeholders})",
                    invalid_db_ids
                )
                
            total_cleaned = len(valid_docstore_ids) + len(invalid_db_ids)
            
            if success:
                self.logger.info(f"Successfully cleaned {total_cleaned} short-term memories")
                
                # 5. Reload the SHORT_TERM index to ensure consistency between FAISS and DB
                # This is critical to prevent 'ID not found' errors when querying after cleaning
                self.logger.info("Reloading SHORT_TERM index after cleaning to ensure consistency")
                await self.load_index(SHORT_TERM)
                self.logger.info("SHORT_TERM index reloaded successfully")
            else:
                self.logger.error("Failed to clean short-term memories")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error cleaning short-term memories: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    async def delete_chunks_from_FAISS_index(self, store_type, chunk_ids):
        """
        Delete specific chunks from a vector store based on docstore IDs.

        Args:
            store_type: The type of vector store (0=INGESTED, 1=LONG_TERM, or 2=SHORT_TERM)
            chunk_ids: List of docstore IDs to delete (e.g., '01f92471-3d5e-4a84-854a-d4dc4af6284b')
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.index_loaded[store_type] or self.vector_stores[store_type] is None:
            self.logger.info(f"Vector store for type {store_type} not loaded, skipping deletion")
            return False
        
        try:
            vector_store = self.vector_stores[store_type]
            docstore = vector_store.docstore._dict
            index_to_docstore_id = vector_store.index_to_docstore_id
            docstore_id_to_index = {docstore_id: index for index, docstore_id in index_to_docstore_id.items()}
            
            # Use the built-in delete method which handles index and docstore removal
            deleted_count = vector_store.delete(chunk_ids)
            
            if deleted_count:
                self.logger.info(f"Successfully requested deletion of {len(chunk_ids)} chunks from vector store {store_type}. Actual deleted: {deleted_count}")
                # Save the updated index after deletion
                await self.save_index(store_type)
                # No need to reload here, the calling function (clean_short_term_memory) handles reloading if necessary.
                return True
            else:
                # Check if any of the IDs were actually found
                found_ids = [doc_id for doc_id in chunk_ids if doc_id in docstore]
                if not found_ids:
                    self.logger.warning(f"None of the provided docstore IDs {chunk_ids} were found in vector store {store_type}. No deletion performed.")
                    return True # Return True as no error occurred, just nothing to delete
                else:
                    self.logger.error(f"Failed to delete chunks with IDs {found_ids} from vector store {store_type}, though they were found.")
                    return False
            
        except Exception as e:
            self.logger.error(f"Error deleting chunks from FAISS index type {store_type}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False        

                
    async def delete_chunks(self, store_type, chunk_ids):
        """
        Delete specific chunks from both the vector store and database.
        
        Args:
            store_type: The type of vector store (0=INGESTED, 1=LONG_TERM, or 2=SHORT_TERM)
            chunk_ids: List of docstore IDs to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Step 1: Delete from FAISS index
            faiss_success = await self.delete_chunks_from_FAISS_index(store_type, chunk_ids)
            if not faiss_success:
                self.logger.error(f"Failed to delete chunks from FAISS index type {store_type}")
                return False
                
            # Step 2: Delete from database
            # Create placeholders for SQL IN clause
            placeholders = ', '.join(['?' for _ in chunk_ids])
            query = f"DELETE FROM chunks WHERE type = ? AND docstore_id IN ({placeholders})"
            
            # Combine parameters (store_type and all chunk_ids)
            params = [store_type] + chunk_ids
            
            # Execute the delete query
            await self.db_execute(query, params)
            
            self.logger.info(f"Successfully deleted {len(chunk_ids)} chunks from database for store type {store_type}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting chunks: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
                
    async def retrieve_expired_memories(self,clean_after_days: int):
        """Retrieve expired SHORT_TERM memories from the db
        Memories expire clean_after_days days after they were created
        Returns:
            List[dict]: List of expired memory records
        """
        try:
            # Validate and sanitize input
            if clean_after_days < 0:
                self.logger.warning(f"Invalid clean_after_days value: {clean_after_days}, using default 7")
                clean_after_days = 14
                
            # Use parameterized query to prevent SQL injection
            query = """
                SELECT id, docstore_id, type, created_at 
                FROM chunks
                WHERE type = 2 AND created_at < datetime('now', ?)
            """
            params = (f"-{clean_after_days} days",)
            
            self.logger.info(f"Retrieving expired memories older than {clean_after_days} days")
            expired_memories = await self.db_execute(query, params)
            self.logger.info(f"Found {len(expired_memories)} expired memories")
            return expired_memories
            
        except Exception as e:
            self.logger.error(f"Error retrieving expired memories: {str(e)}")
            return []
        
    
    @hookimpl
    async def clear_memory(self, memory_type=None, chunk_ids: Optional[List[str]]=None):
        """
        Clear a specific type of memory.
        
        Args:
            memory_type: The type of memory to clear (0=INGESTED, 1=LONG_TERM, or 2=SHORT_TERM).
                        If None, will refuse to clear all memories.
            chunk_ids: Optional list of docstore IDs (UUIDs as strings, e.g., '01f92471-3d5e-4a84-854a-d4dc4af6284b')
                        to delete specific chunks. If provided, memory_type must also be specified.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if chunk_ids is not None and memory_type is not None:
            # Delete specific chunks
            success = await self.delete_chunks(memory_type, chunk_ids)
            if success:
                # Reload the index to ensure consistency between FAISS and DB
                self.logger.info(f"Reloading index type {memory_type} after deleting specific chunks")
                await self.load_index(memory_type)
                self.logger.info(f"Index type {memory_type} reloaded successfully")
            return success
        else:
            try:
                if memory_type is None:
                    # Clear all memory types except INGESTED
                    # memory_types = [LONG_TERM, SHORT_TERM]
                    self.logger.info(f"Refusing to clear all memories")
                    return False
                else:
                    memory_types = [memory_type]
                    
                for store_type in memory_types:
                    # Create empty vector store
                    self.vector_stores[store_type] = FAISS.from_documents(
                        [Document(page_content="Initial empty document", metadata={"source": "init"})],
                        self.embedding_function
                    )
                    self.index_loaded[store_type] = True
                    
                    # Save empty index
                    await self.save_index(store_type)
                    
                    # Clear from database
                    if store_type == LONG_TERM:
                        await self.db_execute("DELETE FROM chunks WHERE type = ?", (LONG_TERM,))
                    elif store_type == SHORT_TERM:
                        await self.db_execute("DELETE FROM chunks WHERE type = ?", (SHORT_TERM,))
                    
                    # Reload the index to ensure consistency
                    self.logger.info(f"Reloading index type {store_type} after clearing")
                    await self.load_index(store_type)
                    self.logger.info(f"Index type {store_type} cleared and reloaded successfully")
                    
                return True
            except Exception as e:
                self.logger.error(f"Error clearing memory: {e}")
                return False

    '''
        
        ************************ MONITOR / TESTS ***************************** 
    
    '''    
    @hookimpl
    async def run_tests(self):
        await self.clear_memory(SHORT_TERM)
        await self.clear_memory(LONG_TERM)
        await self.test_fill_short_term_memory()

    async def test_query_rag(self):
        print("TESTING RAG:::")
        queries = [
            "Qu'est-ce que t'as fait hier ?"
            # "est-ce que tu as faim igor"
            # "Qu'est-ce que t'as fait de beau hier soir ?"
            # "C'était quand la dernière fois que t'as vu un film"
            # "Qu'est-ce que t'as mangé hier ?"
        ]
        await asyncio.sleep(2)
        for query in queries:
            await self.pm.trigger_hook(hook_name="add_msg_to_conversation", msg=query, author="def",msg_input="test")
            await self.pm.trigger_hook(hook_name="asr_msg", msg="Q: " + query)
            # asyncio.create_task(self.pm.trigger_hook(hook_name="abandon_conversation"))
            # asyncio.create_task(asyncio.sleep(5))  # Wait 5 seconds before each query
    
    async def test_fill_short_term_memory(self):
        """
        Test function to fill the short-term memory with examples from short_term_examples.json
        """
        self.logger.info("Loading short-term memory examples from JSON file")
        json_path = os.path.join(os.path.dirname(__file__), "short_term_examples.json")
        
        try:
            # Wait for  model and indexes to be loaded
            if not self.embedding_loaded or not self.index_loaded[SHORT_TERM]:
                self.logger.info("Waiting for embedding model and indexes to load...")
                await self.loading_event.wait()
            
            # Load the JSON file
            with open(json_path, "r", encoding="utf-8") as f:
                examples = json.load(f)
            
            self.logger.info(f"Loaded {len(examples)} example entries from short_term_examples.json")
            
            # Generate a range of dates from 14 days ago to today
            end_date = datetime.now()
            start_date = end_date - timedelta(days=14)
            total_facts = sum(len(example.get("facts", [])) for example in examples)
            
            # Keep track of the current fact index
            fact_index = 0
            
            # Process each example
            for example in examples:
                theme = example.get("theme", "")
                tags = example.get("tags", [])
                facts = example.get("facts", [])
                
                for fact_entry in facts:
                    fact = fact_entry.get("fact", "")
                    fact_type = fact_entry.get("type", "short")  # Default to short-term memory
                    
                    if fact:
                        # Calculate a progressive timestamp for this fact
                        # The progression is from start_date to end_date based on the fact's position
                        progress_ratio = fact_index / max(1, total_facts - 1)  # Avoid division by zero
                        time_delta = (end_date - start_date) * progress_ratio
                        fact_timestamp = start_date + time_delta
                        
                        # Add some randomness (up to ±12 hours) to make it more natural
                        random_hours = np.random.uniform(-12, 12)
                        fact_timestamp += timedelta(hours=random_hours)
                        
                        # Format the timestamp for SQLite (ISO format)
                        timestamp_str = fact_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                        
                        self.logger.info(f"Adding fact to memory with timestamp {timestamp_str}: {fact}")
                        
                        # Store the memory with conversation_id=-1 to indicate test data
                        success = await self.store_memory(
                            fact=fact,
                            type=fact_type,
                            reason="test_data",
                            conversation_id=-1,
                            theme=theme,
                            tags=tags,
                            created_at=timestamp_str
                        )
                        
                        if success:
                            self.logger.info(f"Successfully added fact: {fact}")
                        else:
                            self.logger.warning(f"Failed to add fact: {fact}")
                        
                        # Increment the fact index
                        fact_index += 1
            
            self.logger.info("Finished loading short-term memory examples")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading short-term memory examples: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
        
    async def check_all_chunks(self):
        """
        Check all chunks in all store types using the check_chunk function.
        Returns:
            dict: {store_type: {chunk_id: result, ...}, ...}
        """
        self.logger.info("Checking all chunks in all stores")
        results = {}
        for store_type in [INGESTED, LONG_TERM, SHORT_TERM]:
            if not self.index_loaded.get(store_type) or self.vector_stores.get(store_type) is None:
                continue
            vector_store = self.vector_stores[store_type]
            chunk_results = {}
            # Get all docstore_ids for this store_type
            docstore_ids = list(vector_store.docstore._dict.keys())
            for chunk_id in docstore_ids:
                try:
                    res = await self.check_chunk(store_type, chunk_id)
                    chunk_results[chunk_id] = res
                except Exception as e:
                    chunk_results[chunk_id] = {'error': str(e)}
            results[store_type] = chunk_results
            
            # Check for inconsistencies and fix them
            await self.fix_docstore_id_inconsistencies(store_type)
        return results
        
    async def fix_docstore_id_inconsistencies(self, store_type):
        """
        Fix inconsistencies between database and vector store docstore IDs.
        This helps prevent warnings about docstore IDs that exist in metadata but not in the docstore.
        """
        if not self.index_loaded.get(store_type) or self.vector_stores.get(store_type) is None:
            return
            
        self.logger.info(f"Checking for docstore ID inconsistencies in store type {store_type}")
        vector_store = self.vector_stores[store_type]
        current_docstore = vector_store.docstore._dict
        
        # Get all docstore_ids from the database for this store type
        try:
            db_results = await self.db_execute(
                "SELECT id, docstore_id FROM chunks WHERE type = ?",
                (store_type,)
            )
            
            if not db_results:
                self.logger.info(f"No chunks found in database for store type {store_type}")
                return
                
            # Check each docstore_id in the database
            inconsistent_ids = []
            for row in db_results:
                db_id = row['id']
                docstore_id = row['docstore_id']
                
                # Skip if docstore_id is None or empty
                if not docstore_id:
                    continue
                    
                # Check if this docstore_id exists in the vector store
                if docstore_id not in current_docstore:
                    inconsistent_ids.append((db_id, docstore_id))
            
            if inconsistent_ids:
                self.logger.warning(f"Found {len(inconsistent_ids)} inconsistent docstore IDs in store type {store_type}")
                # Option 1: Remove the docstore_id from the database records
                for db_id, docstore_id in inconsistent_ids:
                    try:
                        await self.db_execute(
                            "UPDATE chunks SET docstore_id = NULL WHERE id = ?",
                            (db_id,)
                        )
                        self.logger.info(f"Cleared inconsistent docstore_id '{docstore_id}' from database record {db_id}")
                    except Exception as e:
                        self.logger.error(f"Error updating inconsistent docstore_id in database: {e}")
            else:
                self.logger.info(f"No inconsistent docstore IDs found in store type {store_type}")
                
        except Exception as e:
            self.logger.error(f"Error checking docstore ID inconsistencies: {e}")
            return

    async def print_all_chunks(self, store_types=None):
        """
        Print all chunks and their metadata for specified memory types
        
        Args:
            store_types: List of store types to print chunks for. If None, prints all types.
        """
        if store_types is None:
            store_types = [INGESTED, LONG_TERM, SHORT_TERM]
            
        for store_type in store_types:
            store_name = {INGESTED: "INGESTED", LONG_TERM: "LONG_TERM", SHORT_TERM: "SHORT_TERM"}.get(store_type, f"Unknown({store_type})")
            
            if not self.index_loaded[store_type] or self.vector_stores[store_type] is None:
                self.logger.info(f"Vector store {store_name} not loaded, skipping chunk printing")
                continue
                
            try:
                vector_store = self.vector_stores[store_type]
                total_docs = len(vector_store.index_to_docstore_id)
                
                self.logger.info(f"=== {store_name} Vector Store: {total_docs} total documents ===")
                
                if total_docs <= 1:  # Skip if only the initial empty document exists
                    self.logger.info(f"{store_name} store has only the initial document, skipping")
                    continue
                
                # Print each document in the store
                for idx in range(total_docs):
                    try:
                        docstore_id = vector_store.index_to_docstore_id[idx]
                        doc = vector_store.docstore.search(docstore_id)
                        
                        # Add this check:
                        if not hasattr(doc, "metadata"):
                            self.logger.error(f"Chunk {idx} in {store_name} store is not a Document (type={type(doc)}): {doc}")
                            continue

                        # Get corresponding DB entry if available
                        db_info = ""
                        try:
                            db_result = await self.db_execute(
                                "SELECT id, reason, created_at FROM chunks WHERE docstore_id = ? AND type = ?", 
                                (idx, store_type)
                            )
                            if db_result:
                                db_info = f"DB ID: {db_result[0]['id']}, Reason: {db_result[0]['reason']}, Created: {db_result[0]['created_at']}"
                        except Exception as e:
                            db_info = f"Error retrieving DB info: {e}"
                        
                        # Format metadata as string
                        metadata_str = ", ".join([f"{k}: {v}" for k, v in doc.metadata.items()])
                        
                        # Print chunk info with content preview
                        content_preview = doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
                        self.logger.info(f"Chunk {idx} | DocStoreID: {docstore_id} | {db_info}")
                        self.logger.info(f"Metadata: {metadata_str}")
                        self.logger.info(f"Content: {content_preview}")
                        self.logger.info("-" * 80)
                    except Exception as e:
                        self.logger.error(f"Error printing chunk {idx} in {store_name} store: {e}")
                
            except Exception as e:
                self.logger.error(f"Error printing chunks for {store_name} store: {e}")

    async def check_chunk(self, store_type, chunk_id):
        """
        Check consistency of a chunk between FAISS and the SQLite3 database.
        Returns a dict with status and details.
        """
        result = {"faiss_exists": False, "db_exists": False, "content_match": None, "details": {}}
        # 1. Check FAISS
        vector_store = self.vector_stores.get(store_type)
        faiss_doc = None
        if vector_store and chunk_id in vector_store.docstore._dict:
            faiss_doc = vector_store.docstore._dict[chunk_id]
            result["faiss_exists"] = True
            result["details"]["faiss_content"] = faiss_doc.page_content[:100]  # preview
        # 2. Check DB
        db_rows = await self.db_execute(
            "SELECT content FROM chunks WHERE docstore_id = ? AND type = ?",
            (chunk_id, store_type)
        )
        if db_rows and len(db_rows) > 0:
            result["db_exists"] = True
            db_content = db_rows[0]["content"]
            result["details"]["db_content"] = db_content[:100]  # preview
            # 3. Compare content (if both exist)
            if faiss_doc:
                result["content_match"] = (faiss_doc.page_content.strip() == db_content.strip())
        else:
            result["details"]["db_content"] = None
        return result

    '''
        Reset Huggingface embedding models dir
    '''
    def clear_all_models(self):
        import shutil
        import os

        # Define the path to the Hugging Face cache directory
        from pathlib import Path
        user_dir = Path.home()
        cache_dir = os.path.join(user_dir,".cache","huggingface")
        
        # Check if the directory exists
        if os.path.exists(cache_dir):
            # Remove the directory and all its contents
            shutil.rmtree(cache_dir)
            self.logger.debug(f"Cleared Hugging Face cache at: {cache_dir}")
        else:
            self.logger.debug(f"No cache found at: {cache_dir}")

    async def import_long_term_memories_from_json(self, json_path):
        """
        Imports memories from a JSON file and stores them as long-term memories using store_memory.
        Each entry in the JSON should have a "text" field.
        """
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data:
                fact = entry.get("text")
                if not fact:
                    self.logger.warning("Skipping entry without 'text' field.")
                    continue
                await self.store_memory(
                    fact=fact,
                    type="long",
                    reason="imported",
                    conversation_id=-1,
                    theme="",
                    tags=[],
                    created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            self.logger.info(f"Imported {len(data)} long-term memories from {json_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error importing long-term memories: {e}")
            return False