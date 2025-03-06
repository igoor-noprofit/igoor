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

class Rag(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        
    @hookimpl
    def startup(self):
        print ("RAG IS STARTING UP")
        self.settings = self.get_my_settings()
        self.medias_folder_name = "medias"
        self.index_folder_name = "faiss_index"
        self.index_loaded = False
        self.embedding_loaded = False
        self.loading_event = asyncio.Event()
        # Rename self.db to self.vector_store to avoid conflict with SQLite db
        self.vector_store = None
        
        # Start a thread to load both embedding model and index
        thread = threading.Thread(target=lambda: asyncio.run(self.initialize_resources()))
        thread.start()
        
    async def initialize_resources(self):
        # Load embedding model in thread pool
        loop = asyncio.get_event_loop()
        self.embedding_function = await loop.run_in_executor(None, self.get_embedding_function)
        
        if self.subfolder_exists(self.medias_folder_name):
            self.create_folders()
            if not self.subfolder_exists(self.index_folder_name) or self.is_folder_empty(self.index_folder_name):
                self.logger.info("INDEX FOLDER DOES NOT EXIST OR IS EMPTY, CREATING FROM FOLDER")
                self.create_index()
            else:
                self.logger.info("BOTH FOLDERS EXIST AND INDEX IS NOT EMPTY")
                self.logger.info("RAG settings", self.settings)
                await self.load_index()
    
    async def load_index(self):  # Make load_index async
        self.logger.info("LOADING INDEX, PLEASE WAIT...")
        db_start_time = time.time()
        try:
            # Run the CPU-intensive FAISS loading in a thread pool
            loop = asyncio.get_event_loop()
            # Rename self.db to self.vector_store
            self.vector_store = await loop.run_in_executor(None, 
                lambda: FAISS.load_local(self.index_folder, self.embedding_function, allow_dangerous_deserialization=True)
            )
            db_end_time = time.time()
            self.logger.info(f"DB FAISS index loaded successfully in : {db_end_time - db_start_time:.2f} seconds")
            self.index_loaded = True
            self.is_loaded = True
            self.loading_event.set()  # Signal that loading is complete
        except Exception as e:
            self.logger.error(f"Error loading FAISS index: {e}")
            self.loading_event.set()  # Signal even on error to prevent hanging
        
    @hookimpl
    async def store_memory(self, memory: str) -> bool:
        await self.loading_event.wait()  # Wait for index to load
        if not self.index_loaded:
            return False
            
        new_doc = Document(
            page_content=memory,
            metadata={"source": "memory"}
        )
        try:
            # Use vector_store instead of db
            self.vector_store.add_documents([new_doc])
            return True
        except Exception as e:
            self.logger.error(f"Error adding fact to index: {e}")
            return False
        
    @hookimpl
    async def save_index(self) -> bool:
        if not self.index_loaded:
            self.logger.warning("Index is not loaded, cannot save.")
            return False
        try:
            # Use vector_store instead of db
            self.vector_store.save_local(self.index_folder)
            self.logger.info("Index saved successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Error saving FAISS index: {e}")
            return False
        
    def create_folders(self):
        self.medias_folder = self.create_subfolder(self.medias_folder_name)
        self.index_folder = self.create_subfolder(self.index_folder_name)

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
        self.load_index()
        return True
    
    @hookimpl
    async def query_rag(self, query_text: str):
        try:
            self.logger.debug(f"QUERYING INDEX with text: {query_text}")
            await self.loading_event.wait()  # Wait for index to load
            if not self.index_loaded:
                return False

            start_time = time.time()
            search_start_time = time.time()
            loop = asyncio.get_event_loop()
            # Use vector_store instead of db
            results = await loop.run_in_executor(None, self.vector_store.similarity_search, query_text)
            search_end_time = time.time()
            self.logger.debug(f"DB search time: {search_end_time - search_start_time:.2f} seconds")
            context_text = "\n\n---\n\n".join([doc.page_content for doc in results])
            return context_text
        except Exception as e:
            self.logger.error(f"An error occurred during query_rag execution: {e}")
            return False