import os
import json
import openai
import logging
from rich import print
from pyats import aetest
from dotenv import load_dotenv
from langchain.vectorstores import Chroma
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import JSONLoader
#from langchain.llms import TextGen
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import HuggingFaceInstructEmbeddings
from langchain.embeddings.openai import OpenAIEmbeddings

load_dotenv()

openai.api_key = os.getenv("OPENAI_KEY")
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_KEY")
## Get Logger 
log = logging.getLogger(__name__)

## AE TEST SETUP
class common_setup(aetest.CommonSetup):
    """Common Setup Section"""
    #Connect to testbed
    @aetest.subsection
    def connect_to_devices(self,testbed):
        print("[bright_yellow]Connect to device[/bright_yellow]")
        testbed.connect(log_stdout=False)

    @aetest.subsection
    def loop_mark(self,testbed):
        aetest.loop.mark(ShowLogging, device_name=testbed.devices)

class ShowLogging(aetest.Testcase):
    """Try to identify problems and helf heal"""
    @aetest.test
    def setup(self,testbed,device_name):
        self.device = testbed.devices[device_name]

    @aetest.test
    def summary_and_highlights(self):
        print("[bright_yellow]Setup LLM[/bright_yellow]")
#        self.llm = TextGen(model_url="http://10.0.40.61:5000")
        self.llm = ChatOpenAI(temperature=0.5, model="gpt-4")

        print("[bright_yellow]Get the show logging data[/bright_yellow]")
        self.parsed_interfaces = self.device.parse("show interfaces")
        self.interface_data_to_write = {"info": self.parsed_interfaces}

        with open(f'Show_Interfaces.json', 'w') as f:
            f.write(json.dumps(self.interface_data_to_write, indent=4, sort_keys=True))

        print("[bright_yellow]JSONLoader load the output[/bright_yellow]")
        loader = JSONLoader(
            file_path='Show_Interfaces.json',
            jq_schema='.info | to_entries[] | {interface: .key, data: .value}',
            text_content=False
        )

        print("[bright_yellow]Load and split into pages[/bright_yellow]")
        pages = loader.load_and_split()

        print("[bright_yellow]Setup Recursive Character Text Splitter[/bright_yellow]")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            length_function=len,
        )

        print("[bright_yellow]Split pages into documents with text splitter[/bright_yellow]")
        docs = text_splitter.split_documents(pages)

        print("[bright_yellow]Do Embeddings[/bright_yellow]")
        self.embeddings = OpenAIEmbeddings()
        #self.embeddings = HuggingFaceInstructEmbeddings(model_name="/app/instructor-xl",
        #                                           model_kwargs={"device": "cuda"})

        print("[bright_yellow]Store both the embeddings and the docs in ChromaDB vector store[/bright_yellow]")
        self.vectordb = Chroma.from_documents(docs, embedding=self.embeddings)
        self.vectordb.persist()

        print("[bright_yellow]Setup memory, Conversational Buffer Memory, so our chat history is available to future prompts[/bright_yellow]")
        memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

        print("[bright_yellow]Setup a Conversational Retreival Chain from our private LLM, using the vector store, with K Values of 25, and the memory[/bright_yellow]")
        self.qa = ConversationalRetrievalChain.from_llm(self.llm, self.vectordb.as_retriever(search_kwargs={"k": 25}), memory=memory)

        print("[bright_yellow]Ask our question[/bright_yellow]")
        question = "Please analyze the show interfaces JSON output and provide me a summary and highlight anything important."
        print(f"[bright_green]{question}[/bright_green]")
        
        print("[bright_yellow]Run our Conversational Retreival Chain[/bright_yellow]")
        result = self.qa.run(question)

        print(f"[bright_magenta]{result}[/bright_magenta]")

    @aetest.test
    def are_they_healthy(self):
        question = "Are all of my interfaces healthy?"
        print(f"[bright_green]{question}[/bright_green]")

        print("[bright_yellow]Run our Conversational Retreival Chain[/bright_yellow]")
        result = self.qa.run(question)

        print(f"[bright_magenta]{result}[/bright_magenta]")

    @aetest.test
    def anomolies(self):
        question = "Please analyze the syslog output identify any anomolies from the show interfaces JSON output."
        print(f"[bright_green]{question}[/bright_green]")

        print("[bright_yellow]Run our Conversational Retreival Chain[/bright_yellow]")
        result = self.qa.run(question)

        print(f"[bright_magenta]{result}[/bright_magenta]") 


class common_cleanup(aetest.CommonCleanup):
    """Common Cleanup Section"""
    @aetest.subsection
    def disconnect_from_devices(self,testbed):
        testbed.disconnect()