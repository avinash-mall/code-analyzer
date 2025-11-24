"""
Repository indexing: builds repository map from parsed code.
"""

import os
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict
from tqdm import tqdm

from .parser import CodeParser


class RepositoryIndexer:
    """Builds a repository map from codebase."""
    
    def __init__(self, parser: CodeParser, repo_summary_max_files: int,
                 max_methods_shown: int, max_functions_shown: int):
        """
        Initialize repository indexer.
        
        Args:
            parser: CodeParser instance
            repo_summary_max_files: Maximum number of files to include in repository summary
            max_methods_shown: Maximum number of methods to show per class in summary
            max_functions_shown: Maximum number of functions to show in summary
        """
        self.parser = parser
        self.repo_map = {}
        self.symbol_to_file = {}  # Maps symbol names to files
        self.repo_summary_max_files = repo_summary_max_files
        self.max_methods_shown = max_methods_shown
        self.max_functions_shown = max_functions_shown
    
    def index_codebase(self, root_path: str, extensions: List[str], 
                      exclude_patterns: List[str],
                      max_file_size: int) -> Dict:
        """
        Index entire codebase.
        
        Args:
            root_path: Root directory of codebase
            extensions: List of file extensions to include
            exclude_patterns: Glob patterns to exclude
            max_file_size: Maximum file size to process (bytes)
        
        Returns:
            Repository map: {file_path: {definitions, references, ...}}
        """
        self.repo_map = {}
        self.symbol_to_file = {}
        
        files = self._collect_files(root_path, extensions, exclude_patterns)
        
        print(f"Indexing {len(files)} files...")
        
        for file_path in tqdm(files, desc="Parsing files"):
            try:
                file_size = os.path.getsize(file_path)
                if file_size > max_file_size:
                    print(f"Skipping large file: {file_path} ({file_size} bytes)")
                    continue
                
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    code = f.read()
                
                if not code.strip():
                    continue # Skip empty files

                parse_result = self.parser.parse_file(file_path, code)
                chunks = self.parser.chunk_code(file_path, code)
                
                # Store relative path
                rel_path = os.path.relpath(file_path, root_path)
                
                self.repo_map[rel_path] = {
                    'definitions': parse_result['definitions'],
                    'references': parse_result['references'],
                    'language': parse_result.get('language'),
                    'file_path': file_path,
                    'chunks': chunks, # Store chunks instead of full code
                }
                
                # Build symbol-to-file mapping
                for defn in parse_result['definitions']:
                    symbol_name = defn.get('name')
                    if symbol_name:
                        if symbol_name not in self.symbol_to_file:
                            self.symbol_to_file[symbol_name] = []
                        self.symbol_to_file[symbol_name].append(rel_path)
            
            except Exception as e:
                print(f"Error parsing {file_path}: {e}")
                continue
        
        return self.repo_map
    
    def _collect_files(self, root_path: str, extensions: List[str],
                      exclude_patterns: List[str]) -> List[str]:
        """Collect all source files matching criteria."""
        files = []
        root = Path(root_path)
        
        for ext in extensions:
            for file_path in root.rglob(f'*{ext}'):
                # Check exclude patterns
                should_exclude = False
                file_str = str(file_path)
                for pattern in exclude_patterns:
                    # Simple glob matching
                    if self._matches_pattern(file_str, pattern):
                        should_exclude = True
                        break
                
                if not should_exclude:
                    files.append(str(file_path))
        
        return sorted(files)
    
    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Simple glob pattern matching."""
        import fnmatch
        # Convert ** pattern
        pattern = pattern.replace('**/', '').replace('**', '')
        return fnmatch.fnmatch(path, f'*{pattern}*')
    
    def get_repository_summary(self) -> str:
        """
        Generate a concise summary of the repository for LLM context.
        Includes most important files (by centrality or size).
        """
        summary_lines = []
        
        # Sort files by number of definitions (proxy for importance)
        sorted_files = sorted(
            self.repo_map.items(),
            key=lambda x: len(x[1]['definitions']),
            reverse=True
        )[:self.repo_summary_max_files]
        
        for file_path, info in sorted_files:
            defs = info['definitions']
            classes = [d for d in defs if d.get('type') == 'class']
            functions = [d for d in defs if d.get('type') in ['function', 'method']]
            
            summary_lines.append(f"\n## {file_path}")
            if classes:
                summary_lines.append("Classes:")
                for cls in classes:
                    methods = cls.get('methods', [])
                    methods_str = ', '.join(methods[:self.max_methods_shown])  # Limit methods shown
                    summary_lines.append(f"  - {cls['name']}" + 
                                        (f" (methods: {methods_str})" if methods_str else ""))
            if functions:
                summary_lines.append("Functions/Methods:")
                for func in functions[:self.max_functions_shown]:  # Limit functions shown
                    summary_lines.append(f"  - {func['name']}")
        
        return '\n'.join(summary_lines)
    
    def find_file_by_symbol(self, symbol_name: str) -> List[str]:
        """Find files containing a symbol definition."""
        return self.symbol_to_file.get(symbol_name, [])

