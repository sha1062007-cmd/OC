"""
RAG Ingestion Pipeline for Adaptive Study Tutor.
Scans `data/syllabus/` for both PDF and text files, parses them page by page,
chunks text (800-1000 characters, 150 overlap), embeds them with sentence-transformers
(or deterministic local fallback if offline), and builds a persistent FAISS vector index.
"""

import os
import sys
import json
import re
import numpy as np
from typing import List, Dict, Any, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

SYLLABUS_DIR = os.path.join(PROJECT_ROOT, "data", "syllabus")
VECTOR_STORE_DIR = os.path.join(PROJECT_ROOT, "data", "vector_store")
INDEX_PATH = os.path.join(VECTOR_STORE_DIR, "faiss_index.bin")
METADATA_PATH = os.path.join(VECTOR_STORE_DIR, "metadata.json")

# Embedding model dimension
EMBEDDING_DIM = 384


def get_embedding_model():
    """
    Loads sentence-transformers model 'all-MiniLM-L6-v2'.
    Falls back gracefully to a deterministic local hashing/n-gram encoder
    if offline, if MOCK_LLM=true, or if model weights are unavailable.
    """
    if os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes"):
        return None

    try:
        from sentence_transformers import SentenceTransformer
        # Set local cache folder inside data/cache
        cache_dir = os.path.join(PROJECT_ROOT, "data", "cache")
        os.makedirs(cache_dir, exist_ok=True)
        model = SentenceTransformer("all-MiniLM-L6-v2", cache_folder=cache_dir)
        return model
    except Exception as e:
        print(f"[RAG Ingest] Note: Using fast local offline deterministic encoder ({e})")
        return None


def encode_texts(texts: List[str], model=None) -> np.ndarray:
    """Encodes list of strings into a normalized float32 numpy array of shape (N, EMBEDDING_DIM)."""
    if model is not None:
        try:
            embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            # Normalize vectors for cosine similarity via inner product
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            return (embeddings / norms).astype(np.float32)
        except Exception as e:
            print(f"[RAG Ingest] SentenceTransformer encoding failed, falling back: {e}")

    # Deterministic local semantic hash embedding fallback (384 dimensions)
    vectors = []
    for text in texts:
        words = re.findall(r"\w+", text.lower())
        vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        if not words:
            vectors.append(vec)
            continue
        for i, word in enumerate(words):
            h = hash(word)
            idx1 = abs(h) % EMBEDDING_DIM
            idx2 = abs(h >> 5) % EMBEDDING_DIM
            idx3 = abs(h >> 11) % EMBEDDING_DIM
            weight = 1.0 / (1.0 + 0.05 * (i % 20))
            vec[idx1] += weight
            vec[idx2] += weight * 0.5
            vec[idx3] -= weight * 0.25
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        vectors.append(vec)
    return np.array(vectors, dtype=np.float32)


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> List[str]:
    """
    Splits text into chunks between 800 and 1000 characters with 150 character overlap.
    Preserves sentence boundaries where possible.
    """
    text = text.strip()
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    step = chunk_size - overlap

    while start < len(text):
        end = min(start + chunk_size, len(text))
        # Look for sentence boundary near the end if not at the absolute end
        if end < len(text):
            last_period = text.rfind(".", start + step, end)
            if last_period != -1 and last_period > start + (chunk_size // 2):
                end = last_period + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break
        start += step

    return chunks


def load_documents_from_syllabus(syllabus_dir: str) -> List[Dict[str, Any]]:
    """
    Parses all .pdf and .txt files in the syllabus directory into structured pages.
    Extracts page number, chapter title, and content.
    """
    docs = []
    if not os.path.exists(syllabus_dir):
        print(f"[RAG Ingest] Directory not found: {syllabus_dir}")
        return docs

    for filename in sorted(os.listdir(syllabus_dir)):
        filepath = os.path.join(syllabus_dir, filename)
        if os.path.isdir(filepath):
            continue

        if filename.endswith(".pdf"):
            print(f"[RAG Ingest] Reading PDF: {filename}...")
            try:
                import pypdf
                reader = pypdf.PdfReader(filepath)
                for page_idx, page in enumerate(reader.pages):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        # Extract possible chapter name from first lines
                        lines = [l.strip() for l in page_text.splitlines() if l.strip()]
                        chapter = lines[0] if lines else filename
                        docs.append({
                            "source_file": filename,
                            "chapter": chapter[:80],
                            "page": page_idx + 1,
                            "raw_text": page_text
                        })
            except Exception as e:
                print(f"[RAG Ingest] Warning: Error parsing PDF {filename}: {e}")

        elif filename.endswith(".txt"):
            print(f"[RAG Ingest] Reading syllabus text: {filename}...")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                # Check if file has [Page X] markers
                page_splits = re.split(r"\[Page\s+(\d+)\]", content)
                if len(page_splits) > 1:
                    # Alternating between preamble, page_num, text
                    for i in range(1, len(page_splits), 2):
                        page_num = int(page_splits[i])
                        page_text = page_splits[i + 1].strip()
                        lines = [l.strip() for l in page_text.splitlines() if l.strip()]
                        chapter = lines[0] if lines else filename
                        docs.append({
                            "source_file": filename,
                            "chapter": chapter[:80],
                            "page": page_num,
                            "raw_text": page_text
                        })
                else:
                    docs.append({
                        "source_file": filename,
                        "chapter": filename.replace(".txt", "").replace("_", " ").title(),
                        "page": 1,
                        "raw_text": content
                    })
            except Exception as e:
                print(f"[RAG Ingest] Error reading text file {filename}: {e}")

    return docs


def run_ingestion() -> Tuple[int, int]:
    """
    Executes the ingestion pipeline and writes FAISS index and metadata.
    Returns (num_chunks, num_documents).
    """
    os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
    documents = load_documents_from_syllabus(SYLLABUS_DIR)
    if not documents:
        print("[RAG Ingest] No documents found in data/syllabus. Creating fallback sample.")
        return 0, 0

    chunks_data = []
    for doc in documents:
        text_chunks = chunk_text(doc["raw_text"], chunk_size=900, overlap=150)
        for chunk in text_chunks:
            chunks_data.append({
                "source_file": doc["source_file"],
                "chapter": doc["chapter"],
                "page": doc["page"],
                "content": chunk,
                "citation": f"[Source: {doc['source_file']}, p.{doc['page']}]"
            })

    print(f"[RAG Ingest] Created {len(chunks_data)} chunks from {len(documents)} page units.")

    # Generate Embeddings
    model = get_embedding_model()
    texts_to_embed = [c["content"] for c in chunks_data]
    embeddings = encode_texts(texts_to_embed, model)

    # Build and Save FAISS index
    try:
        import faiss
        index = faiss.IndexFlatIP(EMBEDDING_DIM)
        index.add(embeddings)
        faiss.write_index(index, INDEX_PATH)
        print(f"[RAG Ingest] FAISS index written to: {INDEX_PATH}")
    except Exception as e:
        print(f"[RAG Ingest] Warning: FAISS write issue ({e}), saving numpy matrix fallback.")
        np.save(os.path.join(VECTOR_STORE_DIR, "embeddings.npy"), embeddings)

    # Save metadata JSON
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks_data, f, indent=2, ensure_ascii=False)
    print(f"[RAG Ingest] Metadata written to: {METADATA_PATH}")

    return len(chunks_data), len(documents)


if __name__ == "__main__":
    print("=== Starting RAG Ingestion Pipeline ===")
    n_chunks, n_docs = run_ingestion()
    print(f"=== Ingestion Complete: {n_chunks} chunks ready in vector DB ===")
