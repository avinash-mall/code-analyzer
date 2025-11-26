"""
Elasticsearch integration for storing and retrieving code analysis results.
Enables incremental analysis by caching results keyed by file hash.
"""

import hashlib
from typing import Dict, List, Optional

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.exceptions import NotFoundError
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False
    Elasticsearch = None
    NotFoundError = Exception


class ElasticIndex:
    """Elasticsearch client for code analysis storage."""
    
    def __init__(self, host: str = 'http://localhost:9200', 
                 index_prefix: str = 'code_analyzer',
                 project_id: str = 'default'):
        """
        Initialize Elasticsearch index.
        
        Args:
            host: Elasticsearch host URL
            index_prefix: Prefix for index names
            project_id: Project identifier for multi-project support
        
        Raises:
            ImportError: If elasticsearch module is not installed
        """
        if not ELASTICSEARCH_AVAILABLE:
            raise ImportError(
                "Elasticsearch module is not installed. "
                "Install it with: pip install elasticsearch>=8.0.0"
            )
        self.client = Elasticsearch(hosts=[host])
        self.project_id = project_id
        self.code_index = f'{index_prefix}-code'
        self.workflow_index = f'{index_prefix}-workflows'
        self._ensure_indices()
    
    def _ensure_indices(self):
        """Create indices if they don't exist."""
        # Code analysis index mapping
        code_mapping = {
            "mappings": {
                "properties": {
                    "project_id": {"type": "keyword"},
                    "path": {"type": "keyword"},
                    "language": {"type": "keyword"},
                    "hash": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "code": {"type": "text"},
                    "symbols": {"type": "keyword"},
                    "doc": {"type": "text"},
                    "issues": {"type": "nested"},
                    "static_findings": {"type": "nested"},
                    "embedding": {"type": "dense_vector", "dims": 384}  # Default for all-MiniLM-L6-v2
                }
            }
        }
        
        # Workflow index mapping
        workflow_mapping = {
            "mappings": {
                "properties": {
                    "project_id": {"type": "keyword"},
                    "workflow_id": {"type": "keyword"},
                    "name": {"type": "text"},
                    "entry_point": {"type": "keyword"},
                    "files": {"type": "keyword"},
                    "description": {"type": "text"},
                    "steps": {"type": "nested"},
                    "mermaid_diagram": {"type": "text"},
                    "process_issues": {"type": "nested"}
                }
            }
        }
        
        # Create indices if they don't exist
        if not self.client.indices.exists(index=self.code_index):
            self.client.indices.create(index=self.code_index, body=code_mapping)
        
        if not self.client.indices.exists(index=self.workflow_index):
            self.client.indices.create(index=self.workflow_index, body=workflow_mapping)
    
    def compute_file_hash(self, code: str) -> str:
        """Compute SHA-256 hash of file contents."""
        return hashlib.sha256(code.encode('utf-8')).hexdigest()
    
    def upsert_code_analysis(self, path: str, hash: str, language: str,
                            code: str, symbols: List[str] = None,
                            doc: str = None, issues: List[Dict] = None,
                            static_findings: List[Dict] = None,
                            embedding: List[float] = None,
                            chunk_index: int = 0) -> None:
        """
        Upsert code analysis for a file/chunk.
        
        Args:
            path: Relative file path
            hash: SHA-256 hash of file contents
            language: Programming language
            code: Code content
            symbols: List of symbol names defined in this file/chunk
            doc: Generated documentation
            issues: List of code review issues
            static_findings: Static analysis findings
            embedding: Optional dense vector embedding
            chunk_index: Chunk index (0 for whole file)
        """
        doc_id = f"{self.project_id}:{path}:{chunk_index}"
        body = {
            'project_id': self.project_id,
            'path': path,
            'language': language,
            'hash': hash,
            'chunk_index': chunk_index,
            'code': code,
            'symbols': symbols or [],
            'doc': doc or '',
            'issues': issues or [],
            'static_findings': static_findings or [],
        }
        
        if embedding:
            body['embedding'] = embedding
        
        self.client.index(index=self.code_index, id=doc_id, document=body)
    
    def get_code_analysis(self, path: str, chunk_index: int = 0) -> Optional[Dict]:
        """
        Get code analysis for a file/chunk.
        
        Args:
            path: Relative file path
            chunk_index: Chunk index (0 for whole file)
        
        Returns:
            Analysis document or None if not found
        """
        doc_id = f"{self.project_id}:{path}:{chunk_index}"
        try:
            res = self.client.get(index=self.code_index, id=doc_id)
            return res['_source']
        except NotFoundError:
            return None
    
    def get_all_code_analysis(self, project_id: str = None) -> List[Dict]:
        """
        Get all code analysis documents for a project.
        
        Args:
            project_id: Project ID (uses instance default if None)
        
        Returns:
            List of analysis documents
        """
        pid = project_id or self.project_id
        query = {
            "query": {
                "term": {"project_id": pid}
            },
            "size": 10000  # Adjust if you have more files
        }
        
        results = []
        response = self.client.search(index=self.code_index, body=query)
        for hit in response['hits']['hits']:
            results.append(hit['_source'])
        
        return results
    
    def upsert_workflow(self, workflow_id: str, name: str, entry_point: str,
                       files: List[str], description: str,
                       steps: List[Dict] = None, mermaid_diagram: str = None,
                       process_issues: List[Dict] = None) -> None:
        """
        Upsert workflow analysis.
        
        Args:
            workflow_id: Unique workflow identifier
            name: Workflow name
            entry_point: Entry point file/symbol
            files: List of file paths in the workflow
            description: Workflow description
            steps: List of workflow steps
            mermaid_diagram: Mermaid diagram code
            process_issues: List of process issues
        """
        doc_id = f"{self.project_id}:{workflow_id}"
        body = {
            'project_id': self.project_id,
            'workflow_id': workflow_id,
            'name': name,
            'entry_point': entry_point,
            'files': files,
            'description': description,
            'steps': steps or [],
            'mermaid_diagram': mermaid_diagram or '',
            'process_issues': process_issues or []
        }
        
        self.client.index(index=self.workflow_index, id=doc_id, document=body)
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        """
        Get workflow analysis.
        
        Args:
            workflow_id: Workflow identifier
        
        Returns:
            Workflow document or None if not found
        """
        doc_id = f"{self.project_id}:{workflow_id}"
        try:
            res = self.client.get(index=self.workflow_index, id=doc_id)
            return res['_source']
        except NotFoundError:
            return None
    
    def get_all_workflows(self, project_id: str = None) -> List[Dict]:
        """
        Get all workflows for a project.
        
        Args:
            project_id: Project ID (uses instance default if None)
        
        Returns:
            List of workflow documents
        """
        pid = project_id or self.project_id
        query = {
            "query": {
                "term": {"project_id": pid}
            },
            "size": 1000
        }
        
        results = []
        response = self.client.search(index=self.workflow_index, body=query)
        for hit in response['hits']['hits']:
            results.append(hit['_source'])
        
        return results
    
    def delete_project(self, project_id: str = None) -> None:
        """
        Delete all documents for a project (useful for cleanup).
        
        Args:
            project_id: Project ID (uses instance default if None)
        """
        pid = project_id or self.project_id
        
        # Delete code analysis
        query = {"query": {"term": {"project_id": pid}}}
        self.client.delete_by_query(index=self.code_index, body=query)
        
        # Delete workflows
        self.client.delete_by_query(index=self.workflow_index, body=query)

