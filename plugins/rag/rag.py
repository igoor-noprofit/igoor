from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
import os
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyPDFLoader 
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import CharacterTextSplitter, MarkdownTextSplitter
from langchain.schema import Document  # Ensure all documents are of this type
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
import time


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
        self.create_index()
        self.load_index()

    def load_index(self):
        global embedding_function, db
        db_start_time = time.time()
        embedding_function = self.get_embedding_function()
        
        db = FAISS.load_local(self.index_folder_name, embedding_function, allow_dangerous_deserialization=True)
        db_end_time = time.time()
        print(f"DB preparation time: {db_end_time - db_start_time:.2f} seconds")
        
    def create_folders(self):
        self.medias_folder = self.create_subfolder(self.medias_folder_name)
        self.index_folder = self.create_subfolder(self.index_folder_name)

    # Function to load PDF content and return Document object
    def load_pdf_content(self,file_path):
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        # Ensure the first document is returned if the loader yields multiple
        return documents if documents else None

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
        global embedding_function, db
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
                document = self.load_pdf_content(file_path)
                documents.append(document)

        # Check if there are no documents
        if not documents:
            print("No documents found in the folder. FAISS index cannot be created.")
            return

        # Split documents
        text_splitter = CharacterTextSplitter(chunk_size=400, chunk_overlap=50)
        docs = text_splitter.split_documents(documents)

        for doc in docs:
            if "pdf" in doc.metadata["source"]:
                print(doc.page_content)
                print("-------")

        # Embedding and FAISS index creation
        embedding_function = self.get_embedding_function()
        
        # Load or create FAISS index
        try:
            db = FAISS.load_local(self.index_folder, embedding_function, allow_dangerous_deserialization=True)
            print("FAISS index loaded successfully.")
        except:
            db = FAISS.from_documents(docs, embedding_function)
            db.save_local("faiss_index")
            print("FAISS index created and saved.")

        db_end_time = time.time()
        print(f"DB preparation time: {db_end_time:.2f} seconds")
        
    async def query_rag(self,system_prompt_text: str, query_text: str):
        # print(system_prompt_text)
        if db is None or embedding_function is None:
            self.prepare_db()
        start_time = time.time()  # Start the timer    
        # Search the DB.
        search_start_time = time.time()
        results = db.similarity_search(query_text)
        search_end_time = time.time()
        print(f"DB search time: {search_end_time - search_start_time:.2f} seconds")
        context_text = "\n\n---\n\n".join([doc.page_content for doc in results])
        # print(context_text);
        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        prompt_format_start_time = time.time()
        prompt = prompt_template.format(system_prompt=system_prompt_text, context=context_text, question=query_text)
        prompt_format_end_time = time.time()
        print("************** PROMPT *******************")
        print(prompt)
        print("************* END PROMPT ****************")
        print(f"Prompt formatting time: {prompt_format_end_time - prompt_format_start_time:.2f} seconds")
        # print(prompt)

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