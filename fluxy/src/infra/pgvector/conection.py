import os

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector

load_dotenv()

DATABASE_URL = (
    "postgresql+psycopg://postgres:"
    "tvro6pe192uzxm3ziaxi"
    "@147.79.110.10:8200/fluxe"
    "?sslmode=disable"
)

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small"
)


def get_vector_store(collection_name: str):
    return PGVector(
        embeddings=embeddings,
        collection_name=collection_name,
        connection=DATABASE_URL,
        use_jsonb=True
    )