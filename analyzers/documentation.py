"""
Documentation generator for codebase.
"""

from typing import Dict, List
from llm_client import LocalLLMClient


class DocumentationGenerator:
    """Generates documentation for code files and components."""
    
    def __init__(self, llm_client: LocalLLMClient):
        self.llm_client = llm_client
    
    def generate_file_documentation(self, file_path: str, code: str,
                                   definitions: List[Dict],
                                   references: List[Dict] = None) -> Dict:
        """
        Generate documentation for a file.
        
        Returns:
            {
                'summary': str,
                'classes': {...},
                'functions': {...},
                'usage': str
            }
        """
        # Extract comments/docstrings if available
        comments = self._extract_comments(code, file_path)
        
        # Format definitions
        defs_text = self._format_definitions(definitions)
        
        # Truncate code if needed
        max_code_length = 10000
        code_snippet = code[:max_code_length] if len(code) > max_code_length else code
        
        prompt = f"""Generate comprehensive documentation for the following code file.

File: {file_path}

Existing comments/documentation:
{comments[:1000] if comments else 'None found'}

Code structure:
{defs_text}

Code:
```{self._get_language_from_path(file_path)}
{code_snippet}
```

Please provide:
1. A clear summary of what this file/component does
2. Purpose and responsibility
3. Key classes and their purposes
4. Key functions/methods and what they do
5. How this component interacts with other parts of the system
6. Usage examples or important notes

Write in clear, professional documentation style. Be accurate and base your description on the actual code.
"""
        
        try:
            response = self.llm_client.query(
                prompt,
                system_message="You are a technical documentation writer. Write clear, accurate documentation based on the code provided."
            )
            
            return {
                'file': file_path,
                'documentation': response,
                'definitions': definitions
            }
        
        except Exception as e:
            print(f"Error generating documentation for {file_path}: {e}")
            return {
                'file': file_path,
                'documentation': f"Error generating documentation: {e}",
                'definitions': definitions
            }
    
    def _extract_comments(self, code: str, file_path: str) -> str:
        """Extract comments and docstrings from code."""
        comments = []
        
        ext = file_path.split('.')[-1].lower()
        
        if ext == 'java':
            # Extract JavaDoc comments
            import re
            javadoc_pattern = r'/\*\*.*?\*/'
            matches = re.findall(javadoc_pattern, code, re.DOTALL)
            comments.extend(matches)
        
        elif ext == 'py':
            # Extract docstrings
            import re
            docstring_pattern = r'""".*?"""'
            matches = re.findall(docstring_pattern, code, re.DOTALL)
            comments.extend(matches)
        
        return '\n\n'.join(comments[:5])  # Limit to first 5 comments
    
    def _format_definitions(self, definitions: List[Dict]) -> str:
        """Format definitions for prompt."""
        if not definitions:
            return "No major definitions found."
        
        lines = []
        for defn in definitions:
            def_type = defn.get('type', 'unknown')
            name = defn.get('name', 'unknown')
            line = defn.get('line', '?')
            methods = defn.get('methods', [])
            
            line_text = f"  - {def_type}: {name} (line {line})"
            if methods:
                line_text += f" [methods: {', '.join(methods[:5])}]"
            lines.append(line_text)
        
        return '\n'.join(lines)
    
    def _get_language_from_path(self, file_path: str) -> str:
        """Get language identifier from file path."""
        ext = file_path.split('.')[-1].lower()
        lang_map = {
            'java': 'java',
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript'
        }
        return lang_map.get(ext, 'text')

