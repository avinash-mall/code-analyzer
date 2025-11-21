"""
AST-based code parser using Tree-sitter.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from tree_sitter import Language, Parser
import tree_sitter_languages


class CodeParser:
    """Parses source code files into AST and extracts definitions."""
    
    # Language mappings
    LANGUAGE_MAP = {
        '.java': 'java',
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'javascript',
        '.tsx': 'typescript',
    }
    
    def __init__(self):
        self.parsers = {}
        self._init_parsers()
    
    def _init_parsers(self):
        """Initialize Tree-sitter parsers for supported languages."""
        try:
            # Use tree-sitter-languages which provides pre-built grammars
            for lang_name in ['java', 'python', 'javascript', 'typescript']:
                try:
                    language = tree_sitter_languages.get_language(lang_name)
                    parser = Parser()
                    parser.set_language(language)
                    self.parsers[lang_name] = parser
                except Exception as e:
                    print(f"Warning: Could not load parser for {lang_name}: {e}")
        except Exception as e:
            print(f"Warning: tree-sitter-languages not available: {e}")
            print("Install with: pip install tree-sitter-languages")
    
    def get_language(self, file_path: str) -> Optional[str]:
        """Determine language from file extension."""
        ext = Path(file_path).suffix.lower()
        return self.LANGUAGE_MAP.get(ext)
    
    def parse_file(self, file_path: str, code: str) -> Dict:
        """
        Parse a file and extract definitions and references.
        
        Returns:
            {
                'definitions': [...],  # Classes, functions, etc.
                'references': [...],   # External symbols used
                'ast': tree_sitter.Tree
            }
        """
        lang = self.get_language(file_path)
        if not lang or lang not in self.parsers:
            # Fallback: basic text-based extraction
            return self._fallback_parse(file_path, code)
        
        parser = self.parsers[lang]
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
    
    def _parse_java(self, tree, code: str) -> Tuple[List, List]:
        """Extract definitions and references from Java code."""
        definitions = []
        references = []
        
        def traverse(node):
            if node.type == 'class_declaration':
                name = self._get_node_text(node.child_by_field_name('name'), code)
                if name:
                    methods = []
                    for child in node.children:
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

