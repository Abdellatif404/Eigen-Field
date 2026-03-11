import re
import fitz
import unicodedata
from langchain_text_splitters import RecursiveCharacterTextSplitter
from database import get_collection, embedding_func

collection = get_collection()
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
	all_chunks = []
	all_metadata = []
	chunk_counter = 0

	for page_num, page_text in pages:
		chunks = chunk_text(page_text)
		for chunk in chunks:
			all_chunks.append(chunk)
			all_metadata.append({
				"source": doc_name,
				"file_id": unique_id,
				"page_number": page_num,
				"chunk_index": chunk_counter,
			})
			chunk_counter += 1
	if not all_chunks:
		raise ValueError("No chunks created")

	all_embeddings = embedding_func(all_chunks)
	all_ids = [f"{unique_id}_ch_{j}" for j in range(len(all_chunks))]
	collection.add(
		ids=all_ids,
		documents=all_chunks,
		metadatas=all_metadata,
		embeddings=all_embeddings,
	)
	return len(all_chunks)

def delete_document_from_vectordb(doc_id: str):
	"""Remove all chunks from a document"""
	try:
		collection.delete(where={"file_id": doc_id})
		print(f"Deleted all chunks for {doc_id}")
	except Exception as e:
		print(f"Failed to delete {doc_id}: {e}")
		raise
