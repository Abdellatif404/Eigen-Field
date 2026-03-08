import json
import time
from langchain_ollama import OllamaLLM
from tracing import get_langfuse

llm = OllamaLLM(
	model="qwen2:1.5b",
	base_url="http://eigenfield_ollama:11434",
	temperature=0.4,
	num_predict=800,
	num_ctx=4096,
	top_p=0.95,
	repeat_penalty=1.15,
)

SOURCES_DELIMITER = "\n<!--SOURCES_JSON-->"

def generate_response(query: str, context_chunks: list, trace=None):
	"""Generate answer using retrieved chunks"""
	langfuse = get_langfuse()

	if not context_chunks:
		yield "No information found."
		return

	context = "\n\n".join(
		[
			f"Source: {chunk['source']}\n{chunk['text']}"
			for chunk in context_chunks
		]
	)

	prompt = f"""You are an agricultural expert. Answer thoroughly using the context.

Context:
{context}

Question: {query}

Provide a detailed answer with examples and explanations (5-8 sentences):"""

	generation = None
	if trace and langfuse:
		generation = trace.generation(
			name="llm-generation",
			model="qwen2:1.5b",
			input=prompt,
			model_parameters={
				"temperature": 0.4,
				"num_predict": 800,
				"top_p": 0.95,
				"repeat_penalty": 1.15,
			},
		)

	try:
		full_response = ""
		start = time.perf_counter()
		for chunk in llm.stream(prompt):
			if chunk:
				full_response += chunk
				yield chunk
		elapsed_ms = (time.perf_counter() - start) * 1000

		sources = []
		seen = set()
		for chunk in context_chunks:
			key = f"{chunk['source']}_p{chunk.get('page_number', '?')}"
			if key not in seen:
				seen.add(key)
				sources.append({
					"source": chunk["source"],
					"page": chunk.get("page_number"),
				})

		yield SOURCES_DELIMITER
		yield json.dumps(sources)

		if generation:
			generation.end(
				output=full_response,
				metadata={
					"latency_ms": round(elapsed_ms, 1),
					"response_length": len(full_response),
					"num_sources": len(sources),
				},
			)

	except Exception as e:
		print(f"LLM Error: {e}")
		if generation:
			generation.end(
				output=f"Error: {str(e)}",
				level="ERROR",
				status_message=str(e),
			)
		yield f"\n[Error: {str(e)}]"
