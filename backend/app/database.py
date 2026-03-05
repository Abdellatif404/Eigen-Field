import chromadb
from chromadb.utils import embedding_functions

embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
	model_name="all-MiniLM-L6-v2"
)
chroma_client = chromadb.PersistentClient(path="/opt/eigen_field/vectordb/")

def get_collection():
	return chroma_client.get_or_create_collection(
		name="agriculture_docs", 
		embedding_function=embedding_func
	)
