import os
import uuid
import magic
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, UploadFile, File, HTTPException
from retrieval import search_documents
from generation import generate_response
from ingestion import index_document, delete_document_from_vectordb
from backend.app.tracing import get_langfuse

app = FastAPI(title="EIGEN FIELD RAG Agriculture API")

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

ALLOWED_MIME_TYPES = ["application/pdf"]
MAX_FILE_SIZE = 50 * 1024 * 1024
UPLOAD_DIR = "/opt/eigen_field/data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/")
async def root():
	return {"message": "RAG Agriculture API"}


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
	"""Upload and index a PDF"""

	unique_id = uuid.uuid4().hex
	safe_filename = f"{unique_id}_{file.filename}"
	file_path = os.path.join(UPLOAD_DIR, safe_filename)

	try:
		total_size = 0
		with open(file_path, "wb") as buffer:
			while chunk := await file.read(1024 * 1024):
				total_size += len(chunk)
				if total_size > MAX_FILE_SIZE:
					raise HTTPException(
						status_code=413, detail="File too large (Max 50MB)"
					)
				buffer.write(chunk)

		mime = magic.Magic(mime=True)
		file_mime = mime.from_file(file_path)
		if file_mime not in ALLOWED_MIME_TYPES:
			os.remove(file_path)
			raise HTTPException(
				status_code=400, detail=f"Invalid file type: {file_mime}"
			)

		indexing_res = index_document(file_path, file.filename, unique_id)

		return {
			"status": "success",
			"filename": file.filename,
			"internal_id": unique_id,
			"indexing_summary": indexing_res,
		}

	except HTTPException as he:
		if os.path.exists(file_path):
			os.remove(file_path)
		raise he
	except Exception as e:
		if os.path.exists(file_path):
			os.remove(file_path)
		raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/documents")
async def list_documents():
	"""List all uploaded documents"""
	try:
		files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith(".pdf")]
		return {"status": "success", "count": len(files), "documents": files}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
async def search(query: str, top_k: int = 5):
	"""Search for relevant chunks"""
	try:
		results = search_documents(query, top_k)
		return {
			"status": "success",
			"query": query,
			"count": len(results),
			"results": results,
		}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
	"""Delete a document and its vectors"""
	try:
		target_file = None
		for filename in os.listdir(UPLOAD_DIR):
			if filename.startswith(doc_id):
				target_file = filename
				break

		if not target_file:
			raise HTTPException(status_code=404, detail="Document not found.")

		os.remove(os.path.join(UPLOAD_DIR, target_file))
		delete_document_from_vectordb(doc_id)

		return {"status": "success", "message": f"ID {doc_id} deleted"}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat(query: str, top_k: int = 3):
	"""Streaming RAG response with Langfuse tracing"""
	try:
		langfuse = get_langfuse()
		trace = None

		if langfuse:
			trace = langfuse.trace(
				name="rag-chat-pipeline",
				input={"query": query, "top_k": top_k},
				tags=["chat", "rag"],
			)
		chunks = search_documents(query, top_k, trace=trace)

		def traced_stream():
			"""Wrap generator to finalize trace after streaming completes"""
			try:
				yield from generate_response(query, chunks, trace=trace)
			finally:
				if trace:
					trace.update(
						output={
							"num_chunks_retrieved": len(chunks),
							"status": "completed",
						}
					)
				if langfuse:
					langfuse.flush()

		return StreamingResponse(
			traced_stream(),
			media_type="text/plain",
			headers={
				"Cache-Control": "no-cache",
				"Connection": "keep-alive",
				"X-Accel-Buffering": "no",
				"Content-Type": "text/plain; charset=utf-8",
			},
		)
	except Exception as e:
		print(f"Chat error: {e}")
		raise HTTPException(status_code=500, detail=str(e))
