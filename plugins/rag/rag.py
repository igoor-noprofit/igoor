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

class Rag(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        
    @hookimpl
    def startup(self):
        # self.clear_all_models()
        print ("RAG IS STARTING UP")
        self.settings = self.get_my_settings()
        self.medias_folder_name = "medias"
        self.index_folder_name = "faiss_index"
        self.index_loaded = False
        self.embedding_loaded = False
        self.embedding_function=self.get_embedding_function()
        # Check if medias folder exists
        if self.subfolder_exists(self.medias_folder_name):
            self.create_folders()
            # Check if index folder does not exist or is empty
            if not self.subfolder_exists(self.index_folder_name) or self.is_folder_empty(self.index_folder_name):
                print("INDEX FOLDER DOES NOT EXIST OR IS EMPTY, CREATING FROM FOLDER")
                self.create_index()
            else:
                print("BOTH FOLDERS EXIST AND INDEX IS NOT EMPTY")
                print("RAG settings", self.settings)
                threading.Thread(target=self.load_index).start()
    
    '''
    def load_embedding_function(self):
        if not (self.embedding_loaded):
            self.embedding_function=self.get_embedding_function()
        else:
            print("Embedding function already loaded")
    '''
    
    def load_index(self):
        print ("LOADING INDEX, PLEASE WAIT...")
        db_start_time = time.time()
        try:
            self.db = FAISS.load_local(self.index_folder, self.embedding_function, allow_dangerous_deserialization=True)
            db_end_time = time.time()
            print(f"DB FAISS index loaded successfully in : {db_end_time - db_start_time:.2f} seconds")
            self.index_loaded = True  # Set index_loaded to True after successful loading
            # self.send_prompt("test")
        except Exception as e:
            print(f"Error loading FAISS index: {e}")
        
    @hookimpl
    def send_prompt(self, prompt: str) -> None:
        print(f"Received prompt : {prompt}")
        queries = [
            prompt,
            "Q: Tu te souviens de l'expo Drosephilia",
            "Q: Combien d'enfants tu as",
            "Q: Comment s'appelle ta femme",
            "Q: Quels sont tes réalisateurs préférés",
            "Q: Est-ce que t'aimes Tarantino",
            "Q: Comment s'appelle tes fils"
        ]
        for query in queries:
            asyncio.run(self.query_rag(query))
        
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
            print(f"Cleared Hugging Face cache at: {cache_dir}")
        else:
            print(f"No cache found at: {cache_dir}")
            
    def get_embedding_function(self):
        print("LOADING EMBEDDING FUNCTION")
        embedding_model = self.settings.get("embedding_model")
        model_kwargs = {"device": "cpu"}
        encode_kwargs = {"normalize_embeddings": True}
        
        hf = HuggingFaceBgeEmbeddings(
            model_name=embedding_model, model_kwargs=model_kwargs, encode_kwargs=encode_kwargs
        )
        return hf

    def create_index(self):
        print ("CREATING DB, PLEASE WAIT...")
        db_start_time = time.time()
        folder_path = os.path.join(self.plugin_folder,"medias")
        print (folder_path)
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
            print("No documents found in the folder. FAISS index cannot be created.")
            return False

        # Split documents
        text_splitter = CharacterTextSplitter(chunk_size=self.settings.get("chunk_size"), chunk_overlap=self.settings.get("chunk_overlap"))
        docs = text_splitter.split_documents(documents)

        for doc in docs:
            if "pdf" in doc.metadata["source"]:
                print(doc.page_content)
                print("-------")

        print ("CREATING INDEX")
        self.db = FAISS.from_documents(docs, self.embedding_function)
        self.db.save_local(self.index_folder)
        print("FAISS index saved.")
        db_end_time = time.time()
        print(f"DB FAISS index created successfully in : {db_end_time - db_start_time:.2f} seconds")
        self.load_index()
        return True
    
    @hookimpl
    async def query_rag(self, query_text: str):
        try:
            print("QUERYING INDEX: ", query_text)
            if not self.index_loaded:
                print("Index still loading")
            while not self.index_loaded:
                print(".", end="", flush=True)
                await asyncio.sleep(0.1)

            start_time = time.time()
            search_start_time = time.time()
            # Assuming similarity_search is a blocking call, you might need to run it in a thread
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, self.db.similarity_search, query_text)
            search_end_time = time.time()
            print(f"DB search time: {search_end_time - search_start_time:.2f} seconds")
            context_text = "\n\n---\n\n".join([doc.page_content for doc in results])
            return context_text
        except Exception as e:
            print(f"An error occurred during query_rag execution: {e}")
            return False
    
    