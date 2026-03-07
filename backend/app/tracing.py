import os
from langfuse import Langfuse

_langfuse_client = None

def get_langfuse() -> Langfuse | None:
	global _langfuse_client

	if _langfuse_client is not None:
		return _langfuse_client

	host = os.environ.get("LANGFUSE_HOST")
	public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
	secret_key = os.environ.get("LANGFUSE_SECRET_KEY")

	if not all([host, public_key, secret_key]):
		print("Langfuse env vars not set — tracing disabled")
		return None

	try:
		_langfuse_client = Langfuse(
			host=host,
			public_key=public_key,
			secret_key=secret_key,
		)
		print(f"Langfuse tracing enabled ({host})")
		return _langfuse_client
	except Exception as e:
		print(f"Langfuse init failed: {e}")
		return None
