import re
import fitz
import chromadb
import unicodedata
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

embeddings = embedding_functions.DefaultEmbeddingFunction()
chroma_client = chromadb.PersistentClient(path="/opt/eigen_field/vectordb/")

collection = chroma_client.get_or_create_collection(
	name="agriculture_docs", embedding_function=embeddings
)

splitter = RecursiveCharacterTextSplitter(
	chunk_size=1500,
	chunk_overlap=250,
	length_function=len,
	separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""]
)

def clean_text(text: str) -> str:
	"""Clean extracted text"""
	if not text:
		return ""
	text = unicodedata.normalize("NFKC", text)
	text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text) # Remove hyphen line breaks
	text = re.sub(r"[ \t]+", " ", text) # Remove extra spaces and tabs
	text = re.sub(r"\n\s*\n+", "\n\n", text) # Remove extra newlines
	return text.strip()

def process_pdf(file_path: str) -> list[tuple[int, str]]:
	"""Extract and clean text from PDF"""
	try:
		doc = fitz.open(file_path)
		pages = []
		for page_num, page in enumerate(doc):
			blocks = page.get_text("blocks")
			blocks.sort(key=lambda b: (b[1], b[0]))
			page_text = "\n".join([b[4] for b in blocks])
			cleaned = clean_text(page_text)
			if cleaned.strip():
				pages.append((page_num + 1, cleaned))
		if not pages:
			raise ValueError("No text could be extracted")
		return pages
	except Exception as e:
		print(f"Error processing PDF: {e}")
		raise

def chunk_text(text: str):
	"""Split text into chunks"""
	if not text or not text.strip():
		return []
	chunks = splitter.split_text(text)
	chunks = [chunk.strip() for chunk in chunks]
	return list(dict.fromkeys(chunks))

def index_document(file_path: str, doc_name: str, unique_id: str):
	"""Extract text from PDF, split into chunks, and index into ChromaDB"""
	pages = process_pdf(file_path)
	all_chanks = []
	all_metadata = []
	chunk_counter = 0

	for page_num, page_text in pages:
		chunks = chunk_text(page_text)
		for chunk in chunks:
			all_chanks.append(chunk)
			all_metadata.append({
				"source": doc_name,
				"file_id": unique_id,
				"page_number": page_num,
				"chunk_index": chunk_counter,
			})
			chunk_counter += 1
	if not all_chanks:
		raise ValueError("No chunks created")

	BATCH_SIZE = 100
	for i in range(0, len(all_chanks), BATCH_SIZE):
		batch = all_chanks[i : i + BATCH_SIZE]
		batch_metadata = all_metadata[i : i + BATCH_SIZE]
		batch_ids = [
			f"{unique_id}_ch_{j}"
			for j in range(i, i + len(batch))
		]
		collection.add(
			ids=batch_ids,
			documents=batch,
			metadatas=batch_metadata
		)
	return len(all_chanks)

def delete_document_from_vectordb(doc_id: str):
	"""Remove all chunks from a document"""
	try:
		collection.delete(where={"file_id": doc_id})
		print(f"Deleted all chunks for {doc_id}")
	except Exception as e:
		print(f"Failed to delete {doc_id}: {e}")
		raise
