import os
from google import genai
from google.genai import types as genai_types
import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from dotenv import load_dotenv

# Load env variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Initialize the google.genai Client for embeddings
_genai_client = genai.Client(api_key=api_key)

# Verified available embedding model for this API key.
# Run: [m.name for m in client.models.list() if 'embed' in m.name]
# Result: ['models/gemini-embedding-001', 'models/gemini-embedding-2-preview', 'models/gemini-embedding-2']
EMBEDDING_MODEL = "models/gemini-embedding-001"


class GeminiEmbeddingFunction(EmbeddingFunction):
    """Embedding function for ChromaDB using Gemini embedding API."""

    def __init__(self, task_type: str = "RETRIEVAL_DOCUMENT"):
        self.task_type = task_type

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            try:
                result = _genai_client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=text,
                    config=genai_types.EmbedContentConfig(task_type=self.task_type)
                )
                embeddings.append(result.embeddings[0].values)
            except Exception as e:
                print(f"[RAG EMBEDDING ERROR] model={EMBEDDING_MODEL} task={self.task_type} err={e}")
                raise RuntimeError(f"Failed to generate embedding: {str(e)}")
        return embeddings


# Initialize local persistent ChromaDB client
is_vercel = os.getenv("VERCEL") == "1"
CHROMA_DB_PATH = "/tmp/chroma_db" if is_vercel else "./chroma_db"
os.makedirs(CHROMA_DB_PATH, exist_ok=True)
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)


def get_collection_name(session_id: str) -> str:
    """Collection names: 3-63 chars, alphanumeric/underscores/hyphens."""
    safe_id = session_id.replace("-", "_")
    return f"session_{safe_id}"[:63]


def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 150) -> list[str]:
    """Splits text into overlapping chunks with sentence-boundary awareness."""
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        # Expand to nearest sentence boundary for cleaner context
        if end < text_len:
            next_period = text.find('.', end - 50, end + 100)
            if next_period != -1 and next_period < text_len:
                end = next_period + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - chunk_overlap
        if start >= text_len - chunk_overlap:
            break

    return chunks


def add_document_to_rag(session_id: str, pages_data: list[dict]):
    """Chunks text page-by-page and ingests into ChromaDB with source metadata."""
    coll_name = get_collection_name(session_id)

    # Delete existing collection to overwrite fresh
    try:
        chroma_client.delete_collection(name=coll_name)
    except Exception:
        pass

    collection = chroma_client.create_collection(
        name=coll_name,
        embedding_function=GeminiEmbeddingFunction(task_type="RETRIEVAL_DOCUMENT")
    )

    chunks_list = []
    metadatas_list = []
    ids_list = []

    chunk_idx = 0
    for page in pages_data:
        text = page.get("text", "")
        page_num = page.get("page_num", 1)
        filename = page.get("filename", "unknown.pdf")

        chunks = chunk_text(text)
        for chunk in chunks:
            chunks_list.append(chunk)
            metadatas_list.append({
                "session_id": session_id,
                "page": page_num,
                "filename": filename
            })
            ids_list.append(f"chunk_{chunk_idx}")
            chunk_idx += 1

    if not chunks_list:
        print(f"[RAG] Warning: no text chunks extracted for session {session_id}")
        return

    collection.add(
        documents=chunks_list,
        ids=ids_list,
        metadatas=metadatas_list
    )
    print(f"[RAG] Indexed {len(chunks_list)} chunks for session {session_id}")


def query_rag(session_id: str, query: str, n_results: int = 4) -> list[dict]:
    """Queries ChromaDB for the most relevant chunks and returns with page references."""
    coll_name = get_collection_name(session_id)

    try:
        collection = chroma_client.get_collection(
            name=coll_name,
            embedding_function=GeminiEmbeddingFunction(task_type="RETRIEVAL_QUERY")
        )
    except Exception:
        return []

    try:
        count = collection.count()
        if count == 0:
            return []
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, count)
        )
    except Exception as e:
        print(f"[RAG QUERY ERROR] {e}")
        return []

    if (results and 'documents' in results and results['documents']
            and 'metadatas' in results and results['metadatas']):
        output = []
        for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
            output.append({
                "text": doc,
                "page": meta.get("page", 1),
                "filename": meta.get("filename", "unknown.pdf")
            })
        return output
    return []
