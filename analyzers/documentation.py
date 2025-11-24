"""
Documentation generator for codebase.
"""

from typing import Dict, List
import concurrent.futures
from llm_client import LocalLLMClient


class DocumentationGenerator:
    """Generates documentation for code files and components."""
    
    def __init__(self, llm_client: LocalLLMClient, symbol_to_file: Dict,
                 technical_writer_message: str, architect_message: str,
                 chunk_doc_truncate: int, repo_summary_context_limit: int,
                 min_symbol_length: int, default_chunk_type: str,
                 default_chunk_name: str, no_documentation_message: str,
                 no_file_summary_message: str):
        """
        Initialize documentation generator.
        
        Args:
            llm_client: LLM client instance
            symbol_to_file: Mapping of symbol names to files
            technical_writer_message: System message for technical writer
            architect_message: System message for software architect
            chunk_doc_truncate: Truncate chunk docs to this length in file summary
            repo_summary_context_limit: Maximum characters for repository summary context
            min_symbol_length: Minimum symbol name length for cross-referencing
            default_chunk_type: Default chunk type when type is not available
            default_chunk_name: Default chunk name when name is not available
            no_documentation_message: Message when no documentation can be generated
            no_file_summary_message: Default message when file summary is not available
        """
        self.llm_client = llm_client
        self.symbol_to_file = symbol_to_file
        self.technical_writer_message = technical_writer_message
        self.architect_message = architect_message
        self.chunk_doc_truncate = chunk_doc_truncate
        self.repo_summary_context_limit = repo_summary_context_limit
        self.min_symbol_length = min_symbol_length
        self.default_chunk_type = default_chunk_type
        self.default_chunk_name = default_chunk_name
        self.no_documentation_message = no_documentation_message
        self.no_file_summary_message = no_file_summary_message

    def generate_docs_for_file(self, file_path: str, chunks: List[Dict],
                               language: str, repo_summary: str) -> Dict:
        """
        Generate documentation for a file by documenting chunks and then summarizing.
        
        Returns:
            {
                'file_summary': str,
                'chunk_docs': List[Dict] 
            }
        """
        chunk_docs = []
        
        # Use a thread pool to document chunks in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_chunk = {
                executor.submit(self._generate_doc_for_chunk, file_path, chunk, language): chunk
                for chunk in chunks
            }
            for future in concurrent.futures.as_completed(future_to_chunk):
                chunk_docs.append(future.result())

        # Sort chunk_docs by start line to maintain order
        chunk_docs.sort(key=lambda x: x['start_line'])

        # Generate file summary using chunk documentation
        file_summary = self._generate_summary_for_file(file_path, chunk_docs, repo_summary)
        
        return {
            'file_summary': file_summary,
            'chunk_docs': chunk_docs
        }
    
    def _generate_doc_for_chunk(self, file_path: str, chunk: Dict, language: str) -> Dict:
        """Generate documentation for a single code chunk."""
        
        prompt = self._build_chunk_prompt(file_path, chunk, language)
        
        try:
            response = self.llm_client.query(
                prompt,
                system_message=self.technical_writer_message
            )
            
            # Add cross-references to the documentation
            response_with_links = self._add_cross_references(response, file_path)
            
            return {
                'name': chunk['name'],
                'type': chunk['type'],
                'start_line': chunk['start_line'],
                'end_line': chunk['end_line'],
                'documentation': response_with_links
            }
        except Exception as e:
            print(f"  - Error documenting chunk {chunk['name']}: {e}")
            return {
                'name': chunk['name'],
                'type': chunk['type'],
                'start_line': chunk['start_line'],
                'end_line': chunk['end_line'],
                'documentation': f"Error generating documentation: {e}"
            }

    def _build_chunk_prompt(self, file_path: str, chunk: Dict, language: str) -> str:
        """Builds a prompt to document a single chunk."""
        
        chunk_type = chunk.get('type', self.default_chunk_type)
        chunk_name = chunk.get('name', self.default_chunk_name)
        code_snippet = chunk.get('text', '')

        prompt = f"""Generate a documentation comment for the following {chunk_type} named '{chunk_name}'.

File: {file_path}
Language: {language}

Code:
```{language}
{code_snippet}
```

Please explain its purpose, parameters (if any), and return values (if any).
Format the output appropriately for the language (e.g., JavaDoc for Java, reStructuredText for Python).
Be concise and accurate.
"""
        return prompt

    def _generate_summary_for_file(self, file_path: str, chunk_docs: List[Dict], repo_summary: str) -> str:
        """Generate a high-level summary for a file using chunk documentation."""
        
        if not chunk_docs:
            return self.no_documentation_message
        
        context = "Here is the documentation for each component in the file:\n\n"
        for doc in chunk_docs:
            context += f"## {doc['type']}: {doc['name']}\n"
            context += f"{doc['documentation'][:self.chunk_doc_truncate]}\n\n" # Truncate to keep context manageable

        prompt = f"""Given the documentation for all components in the file '{file_path}', write a high-level summary.

{context}

Please provide:
1.  A one-paragraph summary of the file's overall purpose and responsibility.
2.  A brief description of how the components interact.

Do not repeat the detailed documentation, but synthesize it into a coherent overview.
"""

        if repo_summary:
            prompt = f"""Brief codebase context:
{repo_summary[:self.repo_summary_context_limit]}

{prompt}
"""

        try:
            response = self.llm_client.query(
                prompt,
                system_message=self.architect_message
            )
            return response
        except Exception as e:
            print(f"  - Error generating summary for {file_path}: {e}")
            return f"Error generating summary: {e}"

    def _add_cross_references(self, documentation: str, current_file: str) -> str:
        """Add hyperlinks to class/function names mentioned in documentation."""
        import re
        
        if not self.symbol_to_file:
            return documentation
            
        result = documentation
        
        # Sort symbols by length to match longer names first
        sorted_symbols = sorted(self.symbol_to_file.keys(), key=len, reverse=True)
        
        for symbol_name in sorted_symbols:
            if len(symbol_name) < self.min_symbol_length:  # Skip very short names
                continue
            
            # Match whole words only, not as part of another word
            pattern = r'\b(' + re.escape(symbol_name) + r')\b'
            
            files = self.symbol_to_file[symbol_name]
            
            # Find a file that is not the current one, if possible
            target_file = None
            if files:
                for f in files:
                    if f != current_file:
                        target_file = f
                        break
                if not target_file:
                    target_file = files[0] # Link to self if only defined here

                # Create anchor link
                anchor = target_file.replace('/', '-').replace('\\', '-').replace('.', '_')
                link = f'<a href="#file-{anchor}" class="doc-link">\\1</a>'
                
                # Replace if not already inside a link
                # This is a simple check to avoid nested links
                if f'href="#file-' not in result:
                    result = re.sub(pattern, link, result)
        
        return result

