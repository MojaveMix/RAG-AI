"""Reindex existing uploaded documents using the configured embedding model (BGE-M3)."""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BASE_DIR))

from config import Config
from rag.chunking import build_chunks
from rag.loader import parse_bytes
from rag.vectorstore import get_store
from services.document_store import get_doc_store
from services.ollama_client import get_client

def main():
    print(f"Using Embedding Model: {Config.EMBED_MODEL}")
    print(f"Target Chroma Collection: {Config.COLLECTION_NAME}")
    
    client = get_client()
    if not client.is_running():
        print("ERROR: Ollama is not running! Please start Ollama.")
        sys.exit(1)
        
    if not client.has_model(Config.EMBED_MODEL):
        print(f"ERROR: Embedding model {Config.EMBED_MODEL} is not available in Ollama.")
        sys.exit(1)

    doc_store = get_doc_store()
    store = get_store()
    documents = doc_store.list_all()

    if not documents:
        print("No documents found in database.")
        return

    print(f"Found {len(documents)} documents to index with {Config.EMBED_MODEL}...\n")

    for doc in documents:
        doc_id = doc["id"]
        filename = doc["filename"]
        stored_name = doc["stored_name"]
        file_path = Config.UPLOAD_DIR / stored_name

        if not file_path.exists():
            print(f"Skipping {filename} ({doc_id}) - file not found on disk at {file_path}")
            continue

        print(f"Indexing: {filename} ({doc_id})...")
        try:
            data = file_path.read_bytes()
            extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            parsed = parse_bytes(data, filename)

            base_metadata = {"document_id": doc_id, "filename": filename}
            if parsed.page_texts:
                chunks = []
                for page_num, page_text in enumerate(parsed.page_texts, start=1):
                    if not page_text.strip():
                        continue
                    chunks.extend(
                        build_chunks(
                            page_text,
                            chunk_size=Config.CHUNK_SIZE,
                            chunk_overlap=Config.CHUNK_OVERLAP,
                            base_metadata={**base_metadata, "page": page_num},
                        )
                    )
            else:
                chunks = build_chunks(
                    parsed.text,
                    chunk_size=Config.CHUNK_SIZE,
                    chunk_overlap=Config.CHUNK_OVERLAP,
                    base_metadata=base_metadata,
                )

            if not chunks:
                print(f"  Warning: No chunks extracted from {filename}")
                continue

            for pos, chunk in enumerate(chunks, start=1):
                chunk.metadata["chunk_index"] = pos

            texts = [c.text for c in chunks]
            vectors = []
            batch_size = 16
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                vectors.extend(client.embed(batch, prefix=Config.EMBED_DOC_PREFIX))

            payload = [
                {
                    "id": f"{doc_id}:{chunk.metadata['chunk_index']}",
                    "text": chunk.text,
                    "metadata": {
                        **chunk.metadata,
                        "extension": extension,
                    },
                }
                for chunk in chunks
            ]

            store.delete_document(doc_id)
            store.add(document_id=doc_id, chunks=payload, embeddings=vectors)
            doc_store.finalize(doc_id, chunks=len(payload), pages=parsed.pages)
            print(f"  -> Successfully indexed {len(payload)} chunks into {Config.COLLECTION_NAME}")

        except Exception as e:
            print(f"  Failed to index {filename}: {e}")

    print("\nAll documents processed!")

if __name__ == "__main__":
    main()
