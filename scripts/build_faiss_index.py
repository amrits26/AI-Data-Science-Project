"""
Build and persist FAISS index for Imperial Cars knowledge base.
Run this script after updating the knowledge base to save the index to disk.
"""
import os
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

INDEX_DIR = Path(os.getenv("KNOWLEDGE_BASE_DIR", "knowledge_base")) / "index"
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Example: load your documents here
# from your_data_loader import load_documents
# docs = load_documents()
docs = []  # TODO: Replace with real document loading

if not docs:
    print("No documents to index. Please implement document loading.")
    exit(1)

embeddings = HuggingFaceEmbeddings(model_name=MODEL_NAME)
vs = FAISS.from_documents(docs, embeddings)
INDEX_DIR.mkdir(parents=True, exist_ok=True)
vs.save_local(str(INDEX_DIR))
print(f"FAISS index saved to {INDEX_DIR}")
