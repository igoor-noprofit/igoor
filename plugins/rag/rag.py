from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager
import os
from langchain_community.document_loaders import TextLoader
import pymupdf4llm
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import CharacterTextSplitter, MarkdownTextSplitter
from langchain.schema import Document  # Ensure all documents are of this type
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain.prompts import ChatPromptTemplate
import time, sys, asyncio, threading
import numpy as np

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
        
    def create_folders(self):
        """Create all necessary folders for the plugin"""
        self.medias_folder = self.create_subfolder(self.medias_folder_name)
        
        # Create folders for each vector store
        for store_type, folder_name in self.index_folder_names.items():
            folder_path = self.create_subfolder(folder_name)
            self.logger.info(f"Created/verified folder for store type {store_type}: {folder_path}")
    
    async def load_all_indexes(self):
        """Load all three FAISS indexes"""
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
        
        # Process each file individually to properly track document IDs
        for file_name in new_files:
            file_path = os.path.join(folder_path, file_name)
            documents = []
            
            # Extract title from filename (remove extension)
            title = os.path.splitext(file_name)[0]
            
            # First add the document to the database to get its ID
            try:
                # Use a simpler query without RETURNING clause which might be causing issues
                await self.db_execute(
                    "INSERT INTO documents (title, filename, created_at) VALUES (?, ?, datetime('now'))",
                    (title, file_name)
                )
                
                # Then query for the ID in a separate operation
                result = await self.db_execute(
                    "SELECT id FROM documents WHERE filename = ?",
                    (file_name,)
                )
                
                document_id = result[0]['id'] if result else None
                self.logger.info(f"Added document to database: {file_name} with ID {document_id}")
                
                if document_id is None:
                    self.logger.error(f"Failed to get document ID for {file_name}, skipping")
                    continue
                    
            except Exception as e:
                self.logger.error(f"Error adding document to database: {e}")
                continue
            
            # Now load the document content
            try:
                if file_name.endswith(".txt"):
                    loader = TextLoader(file_path)
                    file_docs = loader.load()
                elif file_name.endswith(".md"):
                    with open(file_path, "r", encoding="utf-8") as f:
                        md_content = f.read()
                    file_docs = [Document(page_content=md_content, metadata={"source": file_path})]
                elif file_name.endswith(".pdf"):
                    md_content = self.load_pdf_content(file_path)
                    file_docs = [Document(page_content=md_content, metadata={"source": file_path})]
                else:
                    self.logger.warning(f"Unsupported file type: {file_name}")
                    continue
            except Exception as e:
                self.logger.error(f"Error loading content from {file_name}: {e}")
                continue
                    
            # Add document_id to all documents from this file
            for doc in file_docs:
                doc.metadata["document_id"] = document_id
                
            documents.extend(file_docs)
            
            # Split documents
            text_splitter = CharacterTextSplitter(chunk_size=self.settings.get("chunk_size", 1000), 
                                                chunk_overlap=self.settings.get("chunk_overlap", 200))
            docs = text_splitter.split_documents(documents)
            
            # Ensure document_id is preserved in all chunks
            for doc in docs:
                if "document_id" not in doc.metadata:
                    doc.metadata["document_id"] = document_id
            
            # Add to INGESTED vector store
            if self.index_loaded[INGESTED] and self.vector_stores[INGESTED]:
                self.logger.info(f"Adding {len(docs)} chunks from {file_name} to INGESTED index")
                
                try:
                    # Get the current size of the vector store to determine starting index for new chunks
                    current_size = len(self.vector_stores[INGESTED].index_to_docstore_id)
                    
                    # Add documents to vector store
                    self.vector_stores[INGESTED].add_documents(docs)
                    
                    # Add chunks to database with proper IDs - one by one to avoid transaction issues
                    for i, doc in enumerate(docs):
                        chunk_id = current_size + i  # This is the actual index in the FAISS store
                        success = await self.add_chunk_to_db(
                            content=doc.page_content,
                            chunk_type=INGESTED,
                            reason="ingested",
                            document_id=doc.metadata.get("document_id"),
                            conversation_id=None,
                            chunk_id=chunk_id  # Use the actual FAISS index
                        )
                        if not success:
                            self.logger.warning(f"Failed to add chunk {i} from {file_name} to database")
                    
                    # Save the updated index after each file to prevent data loss
                    await self.save_index(INGESTED)
                except Exception as e:
                    self.logger.error(f"Error processing chunks from {file_name}: {e}")
            else:
                self.logger.info(f"Creating new INGESTED index with {len(docs)} chunks from {file_name}")
                try:
                    self.vector_stores[INGESTED] = FAISS.from_documents(docs, self.embedding_function)
                    self.index_loaded[INGESTED] = True
                    
                    # Add chunks to database with proper IDs - one by one to avoid transaction issues
                    for i, doc in enumerate(docs):
                        success = await self.add_chunk_to_db(
                            content=doc.page_content,
                            chunk_type=INGESTED,
                            reason="ingested",
                            document_id=doc.metadata.get("document_id"),
                            conversation_id=None,
                            chunk_id=i  # For a new index, the IDs start at 0
                        )
                        if not success:
                            self.logger.warning(f"Failed to add chunk {i} from {file_name} to database")
                    
                    await self.save_index(INGESTED)
                except Exception as e:
                    self.logger.error(f"Error creating index for {file_name}: {e}")

    async def add_chunk_to_db(self, content, chunk_type, reason, document_id=None, conversation_id=None, chunk_id=None):
        """Add a chunk to the database"""
        try:
            # Generate a unique chunk_id if not provided
            if chunk_id is None:
                chunk_id = int(time.time() * 1000)
            
            # Ensure content is not too large (SQLite has limits)
            if content and len(content) > 10000:  # Arbitrary limit to prevent very large chunks
                content = content[:10000] + "... (truncated)"
            
            # We'll remove faiss_id from the schema since it's redundant with type
            await self.db_execute(
                """
                INSERT INTO chunks 
                (chunk_id, type, content, reason, created_at, document_id, conversation_id) 
                VALUES (?, ?, ?, ?, datetime('now'), ?, ?)
                """,
                (chunk_id, chunk_type, content, reason, document_id, conversation_id)
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
    async def store_memory(self, memory: str, is_long_term=True) -> bool:
        """Store a memory in either long-term or short-term memory"""
        await self.loading_event.wait()  # Wait for indexes to load
        
        store_type = LONG_TERM if is_long_term else SHORT_TERM
        if not self.index_loaded[store_type]:
            return False
            
        new_doc = Document(
            page_content=memory,
            metadata={"source": "memory", "type": "long_term" if is_long_term else "short_term"}
        )
        
        try:
            # Get the current size of the vector store to determine starting index for new chunk
            current_size = len(self.vector_stores[store_type].index_to_docstore_id)
            
            # Add to vector store
            self.vector_stores[store_type].add_documents([new_doc])
            
            # Add to database with proper chunk_id
            await self.add_chunk_to_db(
                content=memory,
                chunk_type=store_type,
                reason="memory",
                document_id=None,
                conversation_id=None,
                chunk_id=current_size  # Use the actual index in the FAISS store
            )
            
            # Save the updated index
            await self.save_index(store_type)
            return True
        except Exception as e:
            self.logger.error(f"Error adding memory to index: {e}")
            return False
        



    # Function to load PDF content and return Document object
    def load_pdf_content(self,file_path):
        md_text = pymupdf4llm.to_markdown(file_path)
        return md_text

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
    
    
    @hookimpl
    async def clear_memory(self, memory_type=None):
        """Clear a specific type of memory or all memories"""
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
    
    @hookimpl
    async def query_rag(self, query_text: str, store_types=None):
        """Query one or more RAG indexes"""
        try:
            self.logger.debug(f"QUERYING INDEX with text: {query_text}")
            await self.loading_event.wait()  # Wait for indexes to load
            
            # Default to all store types if none specified
            if store_types is None:
                store_types = [INGESTED, LONG_TERM, SHORT_TERM]
            
            # Ensure store_types is a list
            if not isinstance(store_types, list):
                store_types = [store_types]
            
            all_results = []
            for store_type in store_types:
                if not self.index_loaded[store_type]:
                    self.logger.warning(f"Index type {store_type} not loaded, skipping")
                    continue
                    
                start_time = time.time()
                loop = asyncio.get_event_loop()
                
                # Query this specific vector store
                try:
                    results = await loop.run_in_executor(
                        None, 
                        self.vector_stores[store_type].similarity_search, 
                        query_text
                    )
                    search_end_time = time.time()
                    self.logger.debug(f"Store type {store_type} search time: {search_end_time - start_time:.2f} seconds")
                    
                    # Add store type to metadata for tracking
                    for doc in results:
                        doc.metadata["store_type"] = store_type
                    
                    all_results.extend(results)
                except Exception as e:
                    self.logger.error(f"Error querying store type {store_type}: {e}")
            
            # If we have results, format them
            if all_results:
                # Sort by relevance (assuming results are already sorted within each store)
                context_text = "\n\n---\n\n".join([doc.page_content for doc in all_results])
                return context_text
            else:
                return "No relevant information found."
                
        except Exception as e:
            self.logger.error(f"An error occurred during query_rag execution: {e}")
            return False