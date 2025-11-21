"""
Vector embeddings and semantic search for code (RAG).
"""

import os
from typing import Dict, List, Optional
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("Warning: sentence-transformers not available. Install for semantic search.")

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("Warning: chromadb not available. Install for vector storage.")


class ContentIndex:
    """Vector index for semantic code search."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize content index with embedding model.
        
        Args:
            model_name: SentenceTransformer model name
        """
        self.model = None
        self.client = None
        self.collection = None
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.model = SentenceTransformer(model_name)
            except Exception as e:
                print(f"Warning: Could not load embedding model: {e}")
        
        if CHROMADB_AVAILABLE:
            try:
                self.client = chromadb.Client()
                self.collection = self.client.get_or_create_collection(
                    name="code_index",
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                print(f"Warning: Could not initialize ChromaDB: {e}")
    
    def index_codebase(self, repo_map: Dict, chunk_size: int = 500) -> None:
        """
        Index codebase by embedding code chunks.
        
        Args:
            repo_map: Repository map with code content
            chunk_size: Approximate characters per chunk
        """
        if not self.model or not self.collection:
            print("Content indexing skipped (dependencies not available)")
            return
        
        print("Indexing codebase for semantic search...")
        
        documents = []
        metadatas = []
        ids = []
        
        for file_path, info in repo_map.items():
            code = info.get('code', '')
            if not code:
                continue
            
            # Split code into chunks
            chunks = self._chunk_code(code, chunk_size)
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{file_path}:{i}"
                documents.append(chunk)
                metadatas.append({
                    'file': file_path,
                    'chunk_index': i,
                    'language': info.get('language', 'unknown')
                })
                ids.append(chunk_id)
        
        if documents:
            # Generate embeddings
            embeddings = self.model.encode(documents, show_progress_bar=True)
            
            # Store in ChromaDB
            self.collection.add(
                embeddings=embeddings.tolist(),
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
        
        print(f"Indexed {len(documents)} code chunks")
    
    def _chunk_code(self, code: str, chunk_size: int) -> List[str]:
        """Split code into chunks, trying to break at logical boundaries."""
        chunks = []
        
        # Try to split by functions/methods
        lines = code.split('\n')
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line)
            
            # If adding this line would exceed chunk size, save current chunk
            if current_size + line_size > chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search codebase semantically.
        
        Args:
            query: Search query
            top_k: Number of results to return
        
        Returns:
            List of relevant code chunks with metadata
        """
        if not self.model or not self.collection:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.model.encode([query])[0]
            
            # Search
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=top_k
            )
            
            # Format results
            formatted_results = []
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    'file': results['metadatas'][0][i]['file'],
                    'chunk_index': results['metadatas'][0][i]['chunk_index'],
                    'content': results['documents'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
            
            return formatted_results
        
        except Exception as e:
            print(f"Error in semantic search: {e}")
            return []

