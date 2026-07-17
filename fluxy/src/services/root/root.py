import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from typing import TypedDict, Literal

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

modelo = ChatOpenAI(
    model="gpt-4o-mini",
    temperature="0.5",
    api_key=api_key
)


class Rota(TypedDict):
    tipo: Literal["produto", "suporte", "renda-extra"]
    

prompt_root = ChatPromptTemplate(
    [
        ("system", "Responda apenas com as categorias a seguir: produto caso o interesse seja comprar, suporte caso o cliente precise de ajuda com qualquer coisa ou renda-extra caso sua duvida e algo sobre ganhar dinheiro ou algum sobre renda."),
        ("human", "{query}")
    ]
)

roteador = prompt_root | modelo.with_structured_output(Rota)

def definir_categoria_da_pergunta(pergunta :str):
    return roteador.invoke({"query": pergunta})['tipo']
