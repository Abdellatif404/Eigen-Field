from database import get_collection

def search_documents(query: str, top_k: int = 3):
	"""Search for relevant document chunks"""
	results = get_collection().query(
		query_texts=[query],
		n_results=top_k,
		include=["documents", "metadatas", "distances"],
	)

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
	return formatted
