import time
from database import get_collection
from backend.app.tracing import get_langfuse

def search_documents(query: str, top_k: int = 3, trace=None):
	"""Search for relevant document chunks"""
	langfuse = get_langfuse()

	span = None
	if trace and langfuse:
		span = trace.span(
			name="chromadb-retrieval",
			input={"query": query, "top_k": top_k},
		)
	start = time.perf_counter()
	results = get_collection().query(
		query_texts=[query],
		n_results=top_k,
		include=["documents", "metadatas", "distances"],
	)
	elapsed_ms = (time.perf_counter() - start) * 1000

	formatted = []
	if results["documents"] and results["documents"][0]:
		docs = results["documents"][0]
		metadatas = results["metadatas"][0] if results["metadatas"] else []
		distances = results["distances"][0] if results["distances"] else []

		for i in range(len(docs)):
			metadata = metadatas[i] if i < len(metadatas) else {}
			doc_text = docs[i]
			formatted.append(
				{
					"text": doc_text,
					"source": metadata.get("source", "Unknown"),
					"file_id": metadata.get("file_id", f"chunk_{i}"),
					"page_number": metadata.get("page_number"),
					"relevance_score": (
						float(distances[i]) if i < len(distances) else 0.0
					),
				}
			)
	if span:
		span.end(
			output={
				"num_results": len(formatted),
				"latency_ms": round(elapsed_ms, 1),
				"sources": [
					{
						"source": c["source"],
						"page": c.get("page_number"),
						"score": c["relevance_score"],
					}
					for c in formatted
				],
			}
		)
	print(f"ChromaDB search: {len(formatted)} results in {elapsed_ms:.1f}ms")
	return formatted
