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
        
        # Print all FAISS chunks for each memory type
        # await self.print_all_chunks([INGESTED,LONG_TERM,SHORT_TERM])
        results = await self.query_rag(query_text="Qu'est-ce t'as mangé hier soir",store_types=[2],return_chunk_ids=True)
        print (f"RESULTS: ------ {results}")
        #results = await self.query_rag(query_text="Qu'est-ce que tu veux faire cet aprem",store_types=[0,2],return_chunk_ids=True)

    
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
                import traceback
                self.logger.error(f"Error processing/adding chunks from {file_name} to FAISS/DB: {e}")
                self.logger.error(traceback.format_exc())
                # Consider if you need cleanup or rollback here

    async def add_chunk_to_db(self, content, chunk_type, reason, document_id=None, conversation_id=None, theme=None, tags=None, docstore_id=None):
        """Add a chunk to the sqlite database"""
        try:
            # Ensure content is not too large (SQLite has limits)
            if content and len(content) > 10000:  # Arbitrary limit to prevent very large chunks
                content = content[:10000] + "... (truncated)"
            
            # Check if theme and tags are provided
            if theme is not None and tags is not None:
                # Include theme and tags in the query
                await self.db_execute(
                    """
                    INSERT INTO chunks 
                    (type, content, reason, theme, tags, created_at, document_id, conversation_id, docstore_id) 
                    VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?, ?)
                    """,
                    (chunk_type, content, reason, theme, tags, document_id, conversation_id, docstore_id)
                )
            else:
                # Use the original query without theme and tags
                await self.db_execute(
                    """
                    INSERT INTO chunks 
                    (type, content, reason, created_at, document_id, conversation_id, docstore_id) 
                    VALUES (?, ?, ?, datetime('now'), ?, ?, ?)
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
    async def store_memory(self, fact: str, type: str, reason:str, conversation_id: int, theme:str, tags:list):
        """
        Store a memory in either long-term or short-term memory
        """
        # Debug all incoming parameters
        self.logger.info(f"Direct parameters: fact={fact}, type={type}, theme={theme}, tags={tags},conversation_id={conversation_id}")
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
            content = json.dumps(embedding_text)
            tags_json = json.dumps(tags)
            
            # Use the updated add_chunk_to_db method
            success = await self.add_chunk_to_db(
                content=content,
                chunk_type=memory_type,
                reason=reason,
                document_id=None,
                conversation_id=conversation_id,
                theme=theme,
                tags=tags_json,
                docstore_id=docstore_id
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
        try:
            self.logger.debug(f"QUERYING INDEX with text: {query_text} in store_types: {store_types}")
            await self.loading_event.wait()  # Wait for indexes to load
            
            # Get the number of chunks to retrieve per store from settings
            chunk_num = self.settings.get("chunk_num", 4)  # Default to 4 if not specified
            self.logger.debug(f"Using chunk_num={chunk_num} from settings")
            
            # Default to all store types if none specified
            if store_types is None:
                store_types = [INGESTED, LONG_TERM, SHORT_TERM]
            
            # Ensure store_types is a list
            if not isinstance(store_types, list):
                store_types = [store_types]
            
            all_results = []
            chunk_ids_by_store = {
                INGESTED: [],
                LONG_TERM: [],
                SHORT_TERM: []
            }
            
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
                self.logger.debug(f"Returning chunk IDs: {chunk_ids_by_store}")
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

        Returns:
            str: A string containing filtered memories, formatted as
                'YYYY-MM-DD HH:MM:SS\tContent\n...', ordered by creation time.
                Returns an empty string if no matching memories are found or
                if docstore_ids_to_retrieve is empty.
        """
        all_docstore_ids = []
        if isinstance(docstore_ids_by_type, dict):
            for ids_list in docstore_ids_by_type.values():
                if isinstance(ids_list, list):
                    all_docstore_ids.extend(ids_list)
        elif isinstance(docstore_ids_by_type, list): # Optional: fallback for old list format
            self.logger.warning("Received docstore_ids as a list instead of dict, processing as flat list.")
            all_docstore_ids = docstore_ids_by_type
        else:
            self.logger.warning(f"Unexpected format for docstore_ids: {type(docstore_ids_by_type)}. Expected dict.")
            all_docstore_ids = []

        if not all_docstore_ids:
            self.logger.info("No docstore_ids found after processing input, returning empty string.")
            return ""

        timeframe_info = preflow_dict.get("timeframe")
        apply_time_filter = bool(timeframe_info and timeframe_info.get("type")) # Check if timeframe exists and has a type

        # Use placeholders for safe querying
        placeholders = ', '.join('?' for _ in all_docstore_ids)
        base_sql = f"""
            SELECT created_at, content
            FROM chunks
            WHERE docstore_id IN ({placeholders})
        """
        params = list(all_docstore_ids) # Parameters for the IN clause

        start_dt_utc = None
        end_dt_utc = None

        # Add time filtering conditions *if* timeframe is provided and type == 2
        if apply_time_filter:
            base_sql += " AND type = 2 " # Apply filter only to type 2 chunks as per prompt
            self.logger.info("Timeframe provided, calculating bounds and adding type=2 filter.")
            now_local = datetime.now(LOCAL_TIMEZONE)
            start_dt_utc, end_dt_utc = get_datetime_bounds(timeframe_info, now_local)

            if start_dt_utc and end_dt_utc:
                base_sql += " AND created_at BETWEEN ? AND ? "
                params.extend([start_dt_utc, end_dt_utc])
            elif start_dt_utc:
                base_sql += " AND created_at >= ? "
                params.append(start_dt_utc)
            elif end_dt_utc:
                base_sql += " AND created_at <= ? "
                params.append(end_dt_utc)
            # If bounds calculation failed but timeframe was requested, don't add time clauses

        # Add ordering
        base_sql += " ORDER BY created_at ASC;"

        self.logger.info(f"Executing SQL: {base_sql}")
        self.logger.info(f"With parameters: {params}")

        results = []

        try:
            self.db.execute(base_sql, params)
            rows = cursor.fetchall()

            for row in rows:
                created_at_ts, content = row
                # Ensure created_at_ts is a datetime object
                if isinstance(created_at_ts, str):
                    try:
                        # Attempt to parse assuming ISO format, potentially with timezone
                        # Adjust format string if needed based on how data is stored
                        created_at_dt = datetime.fromisoformat(created_at_ts.replace(' Z', '+00:00')) # Handle potential Z for UTC
                    except ValueError:
                        try:
                            # Fallback for common SQLite format without timezone
                            created_at_dt = datetime.strptime(created_at_ts, '%Y-%m-%d %H:%M:%S.%f')
                        except ValueError:
                            try:
                                    created_at_dt = datetime.strptime(created_at_ts, '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                    self.logger.warning(f"Could not parse timestamp string: {created_at_ts}")
                                    created_at_dt = None # Or handle as error
                elif isinstance(created_at_ts, datetime):
                    created_at_dt = created_at_ts
                else:
                    created_at_dt = None
                    self.logger.warning(f"Unexpected type for created_at: {type(created_at_ts)}")


                if created_at_dt:
                    # Optional: Convert DB timestamp (assumed UTC) to local time for display
                    if created_at_dt.tzinfo is None:
                        created_at_dt = pytz.utc.localize(created_at_dt) # Assume UTC if naive
                    created_at_local = created_at_dt.astimezone(LOCAL_TIMEZONE)
                    formatted_ts = created_at_local.strftime('%Y-%m-%d %H:%M:%S')
                    results.append(f"{formatted_ts}\t{content}")

        except sqlite3.Error as e:
            self.logger.error(f"Database error: {e}")
            self.logger.error(f"Failed SQL: {base_sql}")
            self.logger.error(f"Failed PARAMS: {params}")

        return "\n".join(results)
        
    
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
            results = await self.search_in_FAISS(query_text=query_text,store_type=SHORT_TERM,k=max_candidates,score_threshold=0.7)
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
            results = await loop.run_in_executor(
                None,
                lambda: self.vector_stores[store_type].similarity_search_with_score(
                    query_text,
                    k=fetch_k # Fetch more candidates
                )
            )

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
                        # Optional: Verify the docstore_id actually exists in the docstore, though it should
                        if docstore_id in current_docstore:
                            self.logger.debug(f"Adding chunk: score={score:.4f}, docstore_id={docstore_id}")
                            processed_results.append((doc, score, docstore_id))
                            count += 1
                        else:
                            # This case should ideally not happen if ingestion is correct
                            self.logger.warning(f"Found docstore_id '{docstore_id}' in metadata but not in '{store_type}' docstore for doc starting with: {doc.page_content[:50]}...")
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
            self.logger.error(traceback.format_exc())
            # Return whatever was processed so far, or an empty list
            return processed_results if processed_results else []
    
    
    
    '''
        
        ************************ MONITOR / TESTS ***************************** 
    
    '''
    @hookimpl
    async def check_chunk(self, store_type, chunk_id):
        """
        Public hook to check a specific chunk in a vector store against its database entry.
        
        Args:
            store_type: The type of vector store (0=INGESTED, 1=LONG_TERM, or 2=SHORT_TERM)
            chunk_id: The chunk ID to check
            
        Returns:
            A dictionary with comparison results
        """
        return await self.check_specific_chunk(store_type, chunk_id)
        
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
                        
                        # Get corresponding DB entry if available
                        db_info = ""
                        try:
                            db_result = await self.db_execute(
                                "SELECT id, reason, created_at FROM chunks WHERE chunk_id = ? AND type = ?", 
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
                        self.logger.info(f"Chunk {idx} | {db_info}")
                        self.logger.info(f"Metadata: {metadata_str}")
                        self.logger.info(f"Content: {content_preview}")
                        self.logger.info("-" * 80)
                    except Exception as e:
                        self.logger.error(f"Error printing chunk {idx} in {store_name} store: {e}")
                
            except Exception as e:
                self.logger.error(f"Error printing chunks for {store_name} store: {e}")
                
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
            
            # Track which indices need to be removed
            indices_to_remove = []
            
            # Find indices for the docstore IDs we want to delete
            for docstore_id in chunk_ids:
                if docstore_id in docstore_id_to_index:
                    indices_to_remove.append(docstore_id_to_index[docstore_id])
                    # Remove from docstore
                    if docstore_id in docstore:
                        del docstore[docstore_id]
                else:
                    self.logger.warning(f"Docstore ID {docstore_id} not found in vector store {store_type}")
            
            if not indices_to_remove:
                self.logger.info(f"No valid indices found to remove from vector store {store_type}")
                return True
            
            # Sort indices in descending order to avoid index shifting issues when deleting
            indices_to_remove.sort(reverse=True)
            
            # Remove the vectors from the FAISS index
            for idx in indices_to_remove:
                # Remove the index mapping
                if idx in index_to_docstore_id:
                    del index_to_docstore_id[idx]
            
            # Rebuild the index with remaining documents
            remaining_docs = list(docstore.values())
            if remaining_docs:
                # If we have documents left, create a new index with them
                new_vectorstore = FAISS.from_documents(remaining_docs, self.embedding_function)
                self.vector_stores[store_type] = new_vectorstore
            else:
                # If no documents left, create an empty index
                self.vector_stores[store_type] = FAISS.from_documents(
                    [Document(page_content="Initial empty document", metadata={"source": "init"})],
                    self.embedding_function
                )
            
            # Save the updated index
            await self.save_index(store_type)
            self.logger.info(f"Successfully removed {len(indices_to_remove)} chunks from vector store {store_type}")
            return True
            
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
    
    @hookimpl
    async def clear_memory(self, memory_type=None,chunk_ids=None):
        """
        Clear a specific type of memory or all memories.
        If chunk_ids is provided, only delete those specific chunks.
        """
        if chunk_ids is not None and memory_type is not None:
            # Delete specific chunks
            return await self.delete_chunks(memory_type,chunk_ids)
        try:
            if memory_type is None:
                # Clear all memory types except INGESTED
                memory_types = [LONG_TERM, SHORT_TERM]
            else:
                memory_types = [memory_type]
                
            for store_type in memory_types:
                # Create empty vector store
                self.vector_stores[store_type] = FAISS.from_documents(
                    [Document(page_content="Initial empty document", metadata={"source": "init"})],
                    self.embedding_function
                )
                
                # Save empty index
                await self.save_index(store_type)
                
                # Clear from database
                if store_type == LONG_TERM:
                    await self.db_execute("DELETE FROM chunks WHERE type = ?", (LONG_TERM,))
                elif store_type == SHORT_TERM:
                    await self.db_execute("DELETE FROM chunks WHERE type = ?", (SHORT_TERM,))
                
            return True
        except Exception as e:
            self.logger.error(f"Error clearing memory: {e}")
            return False
        
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
    