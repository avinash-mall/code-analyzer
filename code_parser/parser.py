"""
AST-based code parser using Tree-sitter.
"""

import os
import re
import ast as python_ast
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from tree_sitter import Language, Parser, Node
try:
    from tree_sitter_languages import get_language
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


class CodeParser:
    """Parses source code files into AST and extracts definitions."""
    
    def __init__(self, max_chunk_lines: int, chunk_by: str, supported_languages: List[str],
                 language_map: Dict[str, str], chunk_node_types: Dict[str, List[str]],
                 sub_chunk_types: Dict[str, List[str]], default_chunk_type: str,
                 default_node_name: str, default_chunk_name_format: str):
        """
        Initialize code parser.
        
        Args:
            max_chunk_lines: Maximum lines per code chunk
            chunk_by: Chunking strategy ("function_or_class" or "size")
            supported_languages: List of languages to initialize Tree-sitter parsers for
            language_map: Mapping of file extensions to language names
            chunk_node_types: Top-level node types for chunking per language
            sub_chunk_types: Sub-chunk node types (e.g., methods within classes) per language
            default_chunk_type: Default chunk type when chunking by size
            default_node_name: Default name when node name cannot be extracted
            default_chunk_name_format: Format string for size-based chunk names (use {start_line} and {end_line})
        """
        self.max_chunk_lines = max_chunk_lines
        self.chunk_by = chunk_by
        self.supported_languages = supported_languages
        self.language_map = language_map
        self.chunk_node_types = chunk_node_types
        self.sub_chunk_types = sub_chunk_types
        self.default_chunk_type = default_chunk_type
        self.default_node_name = default_node_name
        self.default_chunk_name_format = default_chunk_name_format
        self.parsers = {}
        self._init_parsers()
    
    def _init_parsers(self):
        """Initialize Tree-sitter parsers for supported languages."""
        if not TREE_SITTER_AVAILABLE:
            print("Warning: tree-sitter-languages not available. Using Python AST for Python files.")
            print("Install with: pip install tree-sitter-languages")
            return
        
        # Use tree-sitter-languages which provides pre-built grammars
        for lang_name in self.supported_languages:
            try:
                # Workaround for Windows bug in tree-sitter-languages
                # Try to get parser directly, or use Python AST for Python
                if lang_name == 'python':
                    # For Python, we'll use Python's built-in ast module as a workaround
                    # This is more reliable on Windows
                    self.parsers['python'] = 'python_ast'  # Special marker
                    print(f"Using Python's built-in AST module for Python parsing (Windows compatibility).")
                    continue
                
                language = get_language(lang_name)
                if language is None:
                    print(f"Warning: Language '{lang_name}' not available in tree-sitter-languages. Falling back to size-based chunking.")
                    continue
                parser = Parser()
                parser.set_language(language)
                self.parsers[lang_name] = parser
            except (TypeError, Exception) as e:
                # Catch the Windows-specific TypeError bug in tree-sitter-languages
                error_type = type(e).__name__
                error_msg = str(e)
                if lang_name == 'python' and error_type == 'TypeError':
                    # Use Python AST as fallback for Python
                    self.parsers['python'] = 'python_ast'
                    print(f"Using Python's built-in AST module for Python parsing (tree-sitter workaround).")
                else:
                    print(f"Warning: Could not load parser for {lang_name}: {error_type}: {error_msg}")
                    print(f"  Note: Code will still be parsed using fallback size-based chunking.")

    def chunk_code(self, file_path: str, code: str) -> List[Dict]:
        """
        Split code into logical chunks based on AST or fixed size.
        
        Args:
            file_path: Path to the file
            code: Source code as a string
            
        Returns:
            List of chunks, where each chunk is a dict with 'text', 'type', 'name', 
            'start_line', 'end_line'.
        """
        lang = self.get_language(file_path)
        if not lang or self.chunk_by != "function_or_class":
            return self._chunk_by_size(code, self.max_chunk_lines)

        # Use Python's AST for Python files (workaround for Windows tree-sitter-languages bug)
        if lang == 'python' and lang in self.parsers and self.parsers[lang] == 'python_ast':
            return self._chunk_python_with_ast(code)
        
        # Use Tree-sitter for other languages
        if lang not in self.parsers:
            return self._chunk_by_size(code, self.max_chunk_lines)

        parser = self.parsers[lang]
        if not isinstance(parser, Parser):
            return self._chunk_by_size(code, self.max_chunk_lines)
            
        tree = parser.parse(bytes(code, 'utf8'))
        
        chunks = []
        
        # Get top-level node types for chunking per language from config
        top_level_nodes = [
            node for node in tree.root_node.children 
            if node.type in self.chunk_node_types.get(lang, [])
        ]
        
        if not top_level_nodes:
            return self._chunk_by_size(code, self.max_chunk_lines)
            
        for node in top_level_nodes:
            name = self._get_node_name(node, code)
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            
            chunk_text = self._get_node_text_from_lines(code, start_line, end_line)
            
            # Handle potentially large top-level nodes by sub-chunking
            if (end_line - start_line) > self.max_chunk_lines:
                # Sub-chunk (e.g., methods inside a class)
                sub_chunks = self._get_sub_chunks(node, code, lang, start_line)
                if sub_chunks:
                    chunks.extend(sub_chunks)
                else: # Fallback if no sub-chunks found in large node
                    chunks.append({
                        "text": chunk_text, "type": node.type, "name": name,
                        "start_line": start_line, "end_line": end_line
                    })
            else:
                chunks.append({
                    "text": chunk_text, "type": node.type, "name": name,
                    "start_line": start_line, "end_line": end_line
                })
        
        return chunks

    def _get_sub_chunks(self, parent_node: Node, code: str, lang: str, parent_start_line: int) -> List[Dict]:
        """Extract chunks from children of a large node (e.g., methods in a class)."""
        sub_chunks = []
        
        nodes_to_check = list(parent_node.children)
        q = [item for item in nodes_to_check if hasattr(item, 'type')]
        
        visited_nodes = set()
        
        while q:
            node = q.pop(0)
            if node in visited_nodes:
                continue
            visited_nodes.add(node)
            
            if node.type in self.sub_chunk_types.get(lang, []):
                name = self._get_node_name(node, code)
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                
                sub_chunks.append({
                    "text": self._get_node_text_from_lines(code, start_line, end_line),
                    "type": node.type, "name": name,
                    "start_line": start_line, "end_line": end_line
                })
            else:
                for child in node.children:
                    if child not in visited_nodes:
                        q.append(child)
                        
        return sub_chunks

    def _get_node_name(self, node: Node, code: str) -> str:
        """Get the name identifier from a definition node."""
        name_node = node.child_by_field_name('name')
        if name_node:
            return self._get_node_text(name_node, code)
        # Fallback for JS/TS lexical declarations like `const myFunc = () => {}`
        if node.type == 'lexical_declaration':
            for child in node.children:
                if child.type == 'variable_declarator':
                    name_node = child.child_by_field_name('name')
                    if name_node:
                        return self._get_node_text(name_node, code)
        return self.default_node_name
        
    def _chunk_python_with_ast(self, code: str) -> List[Dict]:
        """Chunk Python code using Python's built-in AST module (Windows-compatible)."""
        try:
            tree = python_ast.parse(code)
            lines = code.split('\n')
            chunks = []
            
            # Only process top-level definitions (direct children of module)
            for node in tree.body:
                if isinstance(node, (python_ast.FunctionDef, python_ast.AsyncFunctionDef)):
                    # Get function definition
                    start_line = node.lineno
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') and node.end_lineno else start_line + 1
                    
                    # Get function name
                    name = node.name
                    func_type = 'async_function' if isinstance(node, python_ast.AsyncFunctionDef) else 'function'
                    
                    # Extract function code
                    chunk_text = '\n'.join(lines[start_line - 1:end_line]) if end_line > start_line else lines[start_line - 1]
                    
                    chunks.append({
                        "text": chunk_text,
                        "type": func_type,
                        "name": name,
                        "start_line": start_line,
                        "end_line": end_line
                    })
                    
                elif isinstance(node, python_ast.ClassDef):
                    # Get class definition
                    start_line = node.lineno
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') and node.end_lineno else start_line + 1
                    
                    # Get class name
                    name = node.name
                    
                    chunk_text = '\n'.join(lines[start_line - 1:end_line]) if end_line > start_line else lines[start_line - 1]
                    
                    # If class is too large, sub-chunk by methods
                    if end_line and (end_line - start_line) > self.max_chunk_lines:
                        sub_chunks = []
                        for child in node.body:
                            if isinstance(child, (python_ast.FunctionDef, python_ast.AsyncFunctionDef)):
                                method_start = child.lineno
                                method_end = child.end_lineno if hasattr(child, 'end_lineno') and child.end_lineno else method_start + 1
                                method_text = '\n'.join(lines[method_start - 1:method_end]) if method_end > method_start else lines[method_start - 1]
                                sub_chunks.append({
                                    "text": method_text,
                                    "type": 'async_function' if isinstance(child, python_ast.AsyncFunctionDef) else 'method',
                                    "name": child.name,
                                    "start_line": method_start,
                                    "end_line": method_end
                                })
                        if sub_chunks:
                            chunks.extend(sub_chunks)
                            continue
                    
                    chunks.append({
                        "text": chunk_text,
                        "type": "class",
                        "name": name,
                        "start_line": start_line,
                        "end_line": end_line
                    })
            
            # Sort chunks by start_line
            chunks.sort(key=lambda x: x['start_line'])
            
            return chunks if chunks else self._chunk_by_size(code, self.max_chunk_lines)
            
        except SyntaxError:
            # If Python code has syntax errors, fall back to size-based chunking
            return self._chunk_by_size(code, self.max_chunk_lines)
        except Exception:
            # Any other error, fall back to size-based chunking
            return self._chunk_by_size(code, self.max_chunk_lines)
    
    def _chunk_by_size(self, code: str, max_lines: int) -> List[Dict]:
        """Fallback to chunking by fixed number of lines."""
        lines = code.split('\n')
        chunks = []
        
        for i in range(0, len(lines), max_lines):
            chunk_lines = lines[i:i + max_lines]
            start_line = i + 1
            end_line = i + len(chunk_lines)
            
            chunk_name = self.default_chunk_name_format.format(
                start_line=start_line,
                end_line=end_line
            )
            chunks.append({
                "text": '\n'.join(chunk_lines),
                "type": self.default_chunk_type,
                "name": chunk_name,
                "start_line": start_line,
                "end_line": end_line,
            })
            
        return chunks
    
    def get_language(self, file_path: str) -> Optional[str]:
        """Determine language from file extension."""
        ext = Path(file_path).suffix.lower()
        return self.language_map.get(ext)
    
    def parse_file(self, file_path: str, code: str) -> Dict:
        """
        Parse a file and extract definitions and references.
        
        Returns:
            {
                'definitions': [...],  # Classes, functions, etc.
                'references': [...],   # External symbols used
                'ast': tree_sitter.Tree or python_ast.AST
            }
        """
        lang = self.get_language(file_path)
        if not lang:
            # Fallback: basic text-based extraction
            return self._fallback_parse(file_path, code)
        
        # Use Python AST for Python files (workaround for Windows tree-sitter-languages bug)
        if lang == 'python' and lang in self.parsers and self.parsers[lang] == 'python_ast':
            return self._parse_python_with_ast(file_path, code)
        
        # Use Tree-sitter for other languages
        if lang not in self.parsers:
            return self._fallback_parse(file_path, code)
        
        parser = self.parsers[lang]
        if not isinstance(parser, Parser):
            return self._fallback_parse(file_path, code)
            
        tree = parser.parse(bytes(code, 'utf8'))
        
        definitions = []
        references = []
        
        if lang == 'java':
            definitions, references = self._parse_java(tree, code)
        elif lang == 'python':
            definitions, references = self._parse_python(tree, code)
        elif lang in ['javascript', 'typescript']:
            definitions, references = self._parse_javascript(tree, code)
        
        return {
            'definitions': definitions,
            'references': references,
            'ast': tree,
            'language': lang
        }
    
    def _parse_python_with_ast(self, file_path: str, code: str) -> Dict:
        """Parse Python file using Python's built-in AST module."""
        try:
            tree = python_ast.parse(code)
            definitions = []
            references = []
            
            # Only process top-level definitions (direct children of module)
            for node in tree.body:
                if isinstance(node, python_ast.ClassDef):
                    # Get methods within class
                    methods = [child.name for child in node.body 
                              if isinstance(child, (python_ast.FunctionDef, python_ast.AsyncFunctionDef))]
                    definitions.append({
                        'type': 'class',
                        'name': node.name,
                        'line': node.lineno,
                        'methods': methods
                    })
                    
                elif isinstance(node, (python_ast.FunctionDef, python_ast.AsyncFunctionDef)):
                    definitions.append({
                        'type': 'function',
                        'name': node.name,
                        'line': node.lineno
                    })
            
            # Collect references from all nodes
            for node in python_ast.walk(tree):
                if isinstance(node, python_ast.Call):
                    # Function calls
                    if isinstance(node.func, python_ast.Name):
                        references.append({
                            'type': 'function_call',
                            'name': node.func.id,
                            'line': node.lineno
                        })
            
            return {
                'definitions': definitions,
                'references': references,
                'ast': tree,
                'language': 'python'
            }
        except SyntaxError:
            # If Python code has syntax errors, fall back to regex parsing
            return self._fallback_parse(file_path, code)
        except Exception:
            # Any other error, fall back to regex parsing
            return self._fallback_parse(file_path, code)
    
    def _parse_java(self, tree, code: str) -> Tuple[List, List]:
        """Extract definitions and references from Java code."""
        definitions = []
        references = []
        
        def traverse(node):
            if node.type == 'class_declaration':
                name = self._get_node_text(node.child_by_field_name('name'), code)
                if name:
                    methods = []
                    
                    # Find method names within class body
                    class_body = None
                    for child in node.children:
                        if child.type == 'class_body':
                            class_body = child
                            break
                    
                    if class_body:
                        for child in class_body.children:
                            if child.type == 'method_declaration':
                                method_name = self._get_node_text(
                                    child.child_by_field_name('name'), code
                                )
                                if method_name:
                                    methods.append(method_name)

                    definitions.append({
                        'type': 'class',
                        'name': name,
                        'methods': methods,
                        'line': node.start_point[0] + 1
                    })
            
            elif node.type == 'method_declaration':
                name = self._get_node_text(node.child_by_field_name('name'), code)
                if name and name not in [d.get('name') for d in definitions if d.get('type') == 'method']:
                    definitions.append({
                        'type': 'method',
                        'name': name,
                        'line': node.start_point[0] + 1
                    })
            
            elif node.type == 'method_invocation':
                name = self._get_node_text(node.child_by_field_name('name'), code)
                if name:
                    references.append({
                        'type': 'method_call',
                        'name': name,
                        'line': node.start_point[0] + 1
                    })
            
            elif node.type == 'type_identifier':
                # Could be a class reference
                text = self._get_node_text(node, code)
                if text and text[0].isupper():  # Likely a class name
                    references.append({
                        'type': 'class_reference',
                        'name': text,
                        'line': node.start_point[0] + 1
                    })
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return definitions, references
    
    def _parse_python(self, tree, code: str) -> Tuple[List, List]:
        """Extract definitions and references from Python code."""
        definitions = []
        references = []
        
        def traverse(node):
            if node.type == 'class_definition':
                name = self._get_node_text(node.child_by_field_name('name'), code)
                if name:
                    definitions.append({
                        'type': 'class',
                        'name': name,
                        'line': node.start_point[0] + 1
                    })
            
            elif node.type == 'function_definition':
                name = self._get_node_text(node.child_by_field_name('name'), code)
                if name:
                    definitions.append({
                        'type': 'function',
                        'name': name,
                        'line': node.start_point[0] + 1
                    })
            
            elif node.type == 'call':
                # Function call
                func_node = node.child_by_field_name('function')
                if func_node:
                    name = self._get_node_text(func_node, code)
                    if name:
                        references.append({
                            'type': 'function_call',
                            'name': name.split('.')[-1],  # Get last part of dotted name
                            'line': node.start_point[0] + 1
                        })
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return definitions, references
    
    def _parse_javascript(self, tree, code: str) -> Tuple[List, List]:
        """Extract definitions and references from JavaScript/TypeScript code."""
        definitions = []
        references = []
        
        def traverse(node):
            if node.type == 'class_declaration':
                name = self._get_node_text(node.child_by_field_name('name'), code)
                if name:
                    definitions.append({
                        'type': 'class',
                        'name': name,
                        'line': node.start_point[0] + 1
                    })
            
            elif node.type == 'function_declaration':
                name = self._get_node_text(node.child_by_field_name('name'), code)
                if name:
                    definitions.append({
                        'type': 'function',
                        'name': name,
                        'line': node.start_point[0] + 1
                    })
            
            elif node.type == 'method_definition':
                name = self._get_node_text(node.child_by_field_name('name'), code)
                if name:
                    definitions.append({
                        'type': 'method',
                        'name': name,
                        'line': node.start_point[0] + 1
                    })
            
            elif node.type == 'call_expression':
                func_node = node.child_by_field_name('function')
                if func_node:
                    name = self._get_node_text(func_node, code)
                    if name:
                        references.append({
                            'type': 'function_call',
                            'name': name.split('.')[-1],
                            'line': node.start_point[0] + 1
                        })
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return definitions, references
    
    def _get_node_text(self, node, code: str) -> Optional[str]:
        """Extract text from a node."""
        if not node:
            return None
        start = node.start_byte
        end = node.end_byte
        return code[start:end].strip()
    
    def _get_node_text_from_lines(self, code: str, start_line: int, end_line: int) -> str:
        """Extract text from code based on 1-indexed line numbers."""
        lines = code.split('\n')
        # Adjust for 0-based list indexing
        return '\n'.join(lines[start_line - 1:end_line])

    def _fallback_parse(self, file_path: str, code: str) -> Dict:
        """Fallback parser using regex when Tree-sitter is unavailable."""
        definitions = []
        references = []
        
        ext = Path(file_path).suffix.lower()
        
        if ext == '.java':
            # Extract class definitions
            for match in re.finditer(r'class\s+(\w+)', code):
                definitions.append({
                    'type': 'class',
                    'name': match.group(1),
                    'line': code[:match.start()].count('\n') + 1
                })
            # Extract method definitions
            for match in re.finditer(r'(?:public|private|protected)?\s*\w+\s+(\w+)\s*\([^)]*\)\s*\{', code):
                definitions.append({
                    'type': 'method',
                    'name': match.group(1),
                    'line': code[:match.start()].count('\n') + 1
                })
        
        elif ext == '.py':
            # Extract class definitions
            for match in re.finditer(r'class\s+(\w+)', code):
                definitions.append({
                    'type': 'class',
                    'name': match.group(1),
                    'line': code[:match.start()].count('\n') + 1
                })
            # Extract function definitions
            for match in re.finditer(r'def\s+(\w+)\s*\(', code):
                definitions.append({
                    'type': 'function',
                    'name': match.group(1),
                    'line': code[:match.start()].count('\n') + 1
                })
        
        return {
            'definitions': definitions,
            'references': references,
            'ast': None,
            'language': self.get_language(file_path)
        }

