"""
Dependency graph construction and analysis.
"""

import networkx as nx
from typing import Dict, List, Set
from collections import defaultdict


class DependencyGraphBuilder:
    """Builds and analyzes dependency graphs from repository map."""
    
    def __init__(self, repo_map: Dict, symbol_to_file: Dict, central_files_top_n: int,
                 trace_max_depth: int, entry_point_keywords: List[str],
                 min_dependents: int, max_dependencies: int):
        """
        Initialize dependency graph builder.
        
        Args:
            repo_map: Repository map with code information
            symbol_to_file: Mapping of symbols to files
            central_files_top_n: Number of top central files to return
            trace_max_depth: Maximum depth for call sequence tracing
            entry_point_keywords: Keywords to identify entry point files
            min_dependents: Minimum dependents to be considered entry point
            max_dependencies: Maximum dependencies to be considered entry point
        """
        self.repo_map = repo_map
        self.symbol_to_file = symbol_to_file
        self.central_files_top_n = central_files_top_n
        self.trace_max_depth = trace_max_depth
        self.entry_point_keywords = entry_point_keywords
        self.min_dependents = min_dependents
        self.max_dependencies = max_dependencies
        self.graph = nx.DiGraph()
    
    def build_graph(self) -> nx.DiGraph:
        """Build dependency graph from repository map."""
        # Add all files as nodes
        for file_path in self.repo_map.keys():
            self.graph.add_node(file_path)
        
        # Add edges based on references
        for file_path, info in self.repo_map.items():
            references = info.get('references', [])
            
            for ref in references:
                ref_name = ref.get('name')
                if ref_name:
                    # Find files that define this symbol
                    target_files = self.symbol_to_file.get(ref_name, [])
                    
                    for target_file in target_files:
                        if target_file != file_path:  # Don't self-reference
                            self.graph.add_edge(file_path, target_file)
        
        return self.graph
    
    def get_central_files(self, top_n: int = None) -> List[str]:
        """
        Get most central/important files using PageRank-like algorithm.
        Files referenced by many others are considered central.
        
        Args:
            top_n: Number of top files to return (uses instance default if None)
        """
        if len(self.graph) == 0:
            return []
        
        n = top_n if top_n is not None else self.central_files_top_n
        
        # Use in-degree as a simple centrality measure
        # (files that are referenced by many others are important)
        in_degree = dict(self.graph.in_degree())
        
        # Sort by in-degree
        sorted_files = sorted(
            in_degree.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [file_path for file_path, _ in sorted_files[:n]]
    
    def get_dependencies(self, file_path: str) -> List[str]:
        """Get files that a given file depends on."""
        return list(self.graph.successors(file_path))
    
    def get_dependents(self, file_path: str) -> List[str]:
        """Get files that depend on a given file."""
        return list(self.graph.predecessors(file_path))
    
    def find_entry_points(self) -> List[str]:
        """
        Find potential entry points (files with few dependencies but many dependents).
        Often these are controllers, main classes, or API handlers.
        """
        entry_points = []
        
        for file_path in self.graph.nodes():
            deps = len(list(self.graph.successors(file_path)))
            dependents = len(list(self.graph.predecessors(file_path)))
            
            # Entry points typically have many dependents but few dependencies
            # Also check naming conventions
            file_lower = file_path.lower()
            is_named_entry = any(keyword in file_lower for keyword in self.entry_point_keywords)
            
            if (dependents > self.min_dependents and deps < self.max_dependencies) or is_named_entry:
                entry_points.append(file_path)
        
        return entry_points
    
    def trace_call_sequence(self, start_file: str, max_depth: int = None) -> List[str]:
        """
        Trace a call sequence starting from a file.
        Returns a list of files in the call chain.
        
        Args:
            start_file: File to start tracing from
            max_depth: Maximum depth to trace (uses instance default if None)
        """
        depth_limit = max_depth if max_depth is not None else self.trace_max_depth
        visited = set()
        sequence = []
        
        def dfs(node, depth):
            if depth > depth_limit or node in visited:
                return
            visited.add(node)
            sequence.append(node)
            
            # Follow dependencies
            for successor in self.graph.successors(node):
                dfs(successor, depth + 1)
        
        dfs(start_file, 0)
        return sequence

