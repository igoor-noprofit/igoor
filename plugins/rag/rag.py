from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
import os
from langchain_community.document_loaders import TextLoader
import pymupdf4llm
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import CharacterTextSplitter, MarkdownTextSplitter
from langchain.schema import Document  # Ensure all documents are of this type
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain.prompts import ChatPromptTemplate
import time
import asyncio

PROMPT_TEMPLATE = """
{system_prompt}

Réponds en utilisant aussi le contexte suivant:

{context}

---

Réponds en utilisant aussi le contexte ci-dessus à la question: {question}
"""
class Rag(Baseplugin):
    @hookimpl
    def startup(self):
        super().__init__('rag')
        print ("RAG IS STARTING UP")
        self.settings = self.get_my_settings()
        self.medias_folder_name="medias"
        self.index_folder_name="faiss_index" 
        print ("RAG settings", self.settings)
        self.create_folders()
        print ("FOLDERS CREATED")
        # self.create_index()
        # self.load_index()
        
    @hookimpl
    def send_prompt(self, prompt: str) -> None:
        print(f"Received prompt : {prompt}")
        asyncio.run(self.query_rag(prompt, "Q: Qu'est-ce que t'en pense de Rodolphe?"))

    def load_index(self):
        print ("LOADING INDEX, PLEASE WAIT...")
        db_start_time = time.time()
        embedding_function = self.get_embedding_function()
        try:
            self.db = FAISS.load_local(self.index_folder, embedding_function, allow_dangerous_deserialization=True)
            db_end_time = time.time()
            print(f"DB FAISS index loaded successfully in : {db_end_time - db_start_time:.2f} seconds")
        except Exception as e:
            print(f"Error loading FAISS index: {e}")
        
    def create_folders(self):
        self.medias_folder = self.create_subfolder(self.medias_folder_name)
        self.index_folder = self.create_subfolder(self.index_folder_name)

    # Function to load PDF content and return Document object
    def load_pdf_content(self,file_path):
        md_text = pymupdf4llm.to_markdown(file_path)
        return md_text

    def get_embedding_function(self):
        embedding_model = "BAAI/bge-small-en"
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

        # Embedding and FAISS index creation
        embedding_function = self.get_embedding_function()
        self.db = FAISS.from_documents(docs, embedding_function)
        self.db.save_local(self.index_folder)
        print("FAISS index saved.")
        db_end_time = time.time()
        print(f"DB FAISS index created successfully in : {db_end_time - db_start_time:.2f} seconds")
        return True
        
    async def query_rag(self, system_prompt_text: str, query_text: str):
        try:
            print("QUERYING INDEX: ", query_text)
            try:
                if not hasattr(self, 'db') or self.db is None:
                    self.load_index()
            except Exception as e:
                print(f"An error occurred while loading the index: {e}")
                return None
            start_time = time.time()  # Start the timer    
            # Search the DB.
            search_start_time = time.time()
            results = self.db.similarity_search(query_text)
            search_end_time = time.time()
            print(f"DB search time: {search_end_time - search_start_time:.2f} seconds")
            context_text = "\n\n---\n\n".join([doc.page_content for doc in results])
            prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
            prompt_format_start_time = time.time()
            prompt = prompt_template.format(system_prompt=system_prompt_text, context=context_text, question=query_text)
            prompt_format_end_time = time.time()
            print("************** PROMPT *******************")
            print(prompt)
            print("************* END PROMPT ****************")
            print(f"Prompt formatting time: {prompt_format_end_time - prompt_format_start_time:.2f} seconds")
        except Exception as e:
            print(f"An error occurred during query_rag execution: {e}")
        return prompt

        '''
        # Generate response
        chat_start_time = time.time()
        chat = ChatGroq(temperature=0, groq_api_key=groq_api_key, model_name=groq_model)
        response = chat.invoke(prompt)
        chat_end_time = time.time()
        print(f"Response generation time: {chat_end_time - chat_start_time:.2f} seconds")
        print("************** ANSWER *******************")
        print(response)
        print("************ END ANSWER *****************")
        
        end_time = time.time()  # End the timer
        execution_time = end_time - start_time
        print(f"Total execution time: {execution_time:.2f} seconds")
        '''
        # CALL THE HOOK
        return prompt