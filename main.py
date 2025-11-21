#!/usr/bin/env python3
"""
Main orchestration script for codebase analysis.
"""

import argparse
import yaml
import os
import sys
from pathlib import Path
from typing import Dict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from code_parser import CodeParser, RepositoryIndexer, DependencyGraphBuilder
from code_parser.static_analyzer import StaticAnalyzer
from code_parser.content_index import ContentIndex
from llm_client import LocalLLMClient
from analyzers import (
    CodeReviewAnalyzer,
    DocumentationGenerator,
    BusinessLogicExtractor,
    WorkflowAnalyzer,
    ProcessIssueDetector
)
from analyzers.cross_file_analyzer import CrossFileAnalyzer
from ui import ReportGenerator, WebServer


def load_config(config_path: str = "config.yaml") -> Dict:
    """Load configuration from YAML file."""
    if not os.path.exists(config_path):
        # Try example config
        example_path = config_path + ".example"
        if os.path.exists(example_path):
            print(f"Config file not found. Using example config: {example_path}")
            config_path = example_path
        else:
            print("Warning: No config file found. Using defaults.")
            return get_default_config()
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def get_default_config() -> Dict:
    """Get default configuration."""
    return {
        'llm': {
            'api_base': 'http://localhost:11434/v1',
            'api_key': 'ollama',
            'model': 'codellama:34b',
            'temperature': 0.1,
            'max_tokens': 4000,
            'timeout': 300
        },
        'analysis': {
            'languages': ['java', 'python', 'javascript', 'typescript'],
            'extensions': ['.java', '.py', '.js', '.ts', '.jsx', '.tsx'],
            'exclude': ['**/node_modules/**', '**/__pycache__/**', '**/.git/**'],
            'max_file_size': 1000000,
            'modules': ['code_review', 'documentation', 'business_logic', 'workflows', 'process_issues']
        },
        'output': {
            'report_dir': 'reports',
            'html_file': 'analysis_report.html',
            'pdf_file': 'analysis_report.pdf'
        },
        'ui': {
            'host': '127.0.0.1',
            'port': 5000,
            'debug': False
        }
    }


def run_analysis(codebase_path: str, config: Dict, start_ui: bool = True):
    """Run complete analysis pipeline."""
    
    print("=" * 60)
    print("AI-Powered Codebase Analysis System")
    print("=" * 60)
    print()
    
    # Step 1: Code Ingestion & Indexing
    print("Step 1: Parsing codebase and building indexes...")
    parser = CodeParser()
    indexer = RepositoryIndexer(parser)
    
    repo_map = indexer.index_codebase(
        codebase_path,
        extensions=config['analysis']['extensions'],
        exclude_patterns=config['analysis'].get('exclude', []),
        max_file_size=config['analysis'].get('max_file_size', 1000000)
    )
    
    print(f"Indexed {len(repo_map)} files")
    
    # Build dependency graph
    print("Building dependency graph...")
    graph_builder = DependencyGraphBuilder(repo_map, indexer.symbol_to_file)
    dep_graph = graph_builder.build_graph()
    print(f"Dependency graph: {len(dep_graph.nodes())} nodes, {len(dep_graph.edges())} edges")
    
    # Get repository summary
    repo_summary = indexer.get_repository_summary()
    
    # Initialize content index (optional, for RAG)
    print("Initializing content index (optional)...")
    content_index = ContentIndex()
    if content_index.model:
        content_index.index_codebase(repo_map)
    
    # Run static analysis (optional)
    print("Running static analysis (optional)...")
    static_analyzer = StaticAnalyzer(config.get('static_analysis', {}))
    static_findings = static_analyzer.run_all(codebase_path)
    print(f"Static analysis found {sum(len(v) for v in static_findings.values())} issues")
    
    # Step 2: Initialize LLM
    print("\nStep 2: Initializing LLM client...")
    llm_config = config['llm']
    llm_client = LocalLLMClient(
        api_base=llm_config['api_base'],
        api_key=llm_config.get('api_key', 'ollama'),
        model=llm_config['model'],
        temperature=llm_config.get('temperature', 0.1),
        max_tokens=llm_config.get('max_tokens', 4000),
        timeout=llm_config.get('timeout', 300)
    )
    
    # Test connection
    print("Testing LLM connection...")
    if not llm_client.test_connection():
        print("ERROR: Could not connect to LLM server.")
        print(f"Please ensure your LLM server is running at {llm_config['api_base']}")
        print("\nFor Ollama: ollama pull codellama:34b && ollama serve")
        print("For vLLM: python -m vllm.entrypoints.openai.api_server --model <model> --port 8000")
        return
    print("LLM connection successful!")
    
    # Step 3: Run Analysis Modules
    print("\nStep 3: Running analysis modules...")
    results = {
        'code_review': {'issues': []},
        'documentation': {'docs': {}},
        'business_logic': {},
        'workflows': {'workflows': []},
        'process_issues': {'issues': []}
    }
    
    modules = config['analysis'].get('modules', [])
    
    # Code Review
    if 'code_review' in modules:
        print("  - Code Review & Bug Detection...")
        review_analyzer = CodeReviewAnalyzer(llm_client, static_analyzer)
        for file_path, info in list(repo_map.items())[:50]:  # Limit for demo
            code = info.get('code', '')
            if code:
                file_static_findings = static_findings.get(file_path, [])
                issues = review_analyzer.analyze_file(
                    file_path, code, info['definitions'], repo_summary, file_static_findings
                )
                results['code_review']['issues'].extend(issues)
        print(f"    Found {len(results['code_review']['issues'])} issues")
        
        # Cross-file analysis
        print("  - Cross-file Issue Detection...")
        cross_file_analyzer = CrossFileAnalyzer(llm_client, content_index)
        cross_file_issues = cross_file_analyzer.analyze_interactions(repo_map, dep_graph)
        results['code_review']['issues'].extend(cross_file_issues)
        print(f"    Found {len(cross_file_issues)} cross-file issues")
    
    # Documentation
    if 'documentation' in modules:
        print("  - Documentation Generation...")
        doc_generator = DocumentationGenerator(llm_client, indexer.symbol_to_file)
        for file_path, info in list(repo_map.items())[:30]:  # Limit for demo
            code = info.get('code', '')
            if code:
                doc = doc_generator.generate_file_documentation(
                    file_path, code, info['definitions'], info.get('references', [])
                )
                # Add code snippet for viewer
                doc['code_snippet'] = code[:1000]  # First 1000 chars
                doc['language'] = info.get('language', 'text')
                results['documentation']['docs'][file_path] = doc
        print(f"    Generated documentation for {len(results['documentation']['docs'])} files")
    
    # Business Logic
    if 'business_logic' in modules:
        print("  - Business Logic Extraction...")
        biz_extractor = BusinessLogicExtractor(llm_client, content_index)
        
        # Cluster by feature
        clusters = biz_extractor.cluster_by_feature(repo_map)
        print(f"    Identified {len(clusters)} feature clusters")
        
        core_files = graph_builder.get_central_files(top_n=10)
        extractions = []
        for file_path in core_files:
            if file_path in repo_map:
                info = repo_map[file_path]
                code = info.get('code', '')
                if code:
                    extraction = biz_extractor.extract_from_file(
                        file_path, code, info['definitions']
                    )
                    extractions.append(extraction)
        
        # Consolidate
        overview = biz_extractor.consolidate_business_logic(extractions, repo_summary)
        results['business_logic'] = {
            'overview': overview,
            'extractions': extractions,
            'clusters': clusters
        }
        print("    Business logic extracted and consolidated")
    
    # Workflows
    if 'workflows' in modules:
        print("  - Workflow Definition...")
        workflow_analyzer = WorkflowAnalyzer(llm_client)
        entry_points = graph_builder.find_entry_points()[:5]  # Limit to 5 workflows
        
        for entry_point in entry_points:
            call_sequence = graph_builder.trace_call_sequence(entry_point, max_depth=5)
            if call_sequence:
                # Get code snippets for sequence
                code_snippets = {}
                for file_path in call_sequence[:10]:
                    if file_path in repo_map:
                        code_snippets[file_path] = repo_map[file_path].get('code', '')[:2000]
                
                workflow = workflow_analyzer.define_workflow(
                    entry_point, call_sequence, repo_map, code_snippets
                )
                results['workflows']['workflows'].append(workflow)
        print(f"    Defined {len(results['workflows']['workflows'])} workflows")
    
    # Process Issues
    if 'process_issues' in modules and 'workflows' in modules:
        print("  - Process Issue Detection...")
        issue_detector = ProcessIssueDetector(llm_client)
        for workflow in results['workflows']['workflows']:
            issues = issue_detector.analyze_workflow(workflow)
            for issue in issues:
                results['process_issues']['issues'].append(issue)
        print(f"    Found {len(results['process_issues']['issues'])} process issues")
    
    # Step 4: Generate Report
    print("\nStep 4: Generating report...")
    report_dir = config['output']['report_dir']
    report_generator = ReportGenerator(report_dir)
    
    html_path = report_generator.generate_html_report(
        results,
        output_file=config['output']['html_file']
    )
    print(f"    HTML report generated: {html_path}")
    
    # Generate PDF if possible
    try:
        pdf_path = report_generator.generate_pdf(
            html_path,
            pdf_file=config['output']['pdf_file']
        )
        if pdf_path:
            print(f"    PDF report generated: {pdf_path}")
    except Exception as e:
        print(f"    PDF generation skipped: {e}")
    
    # Step 5: Start UI
    if start_ui:
        print("\nStep 5: Starting web UI...")
        ui_config = config['ui']
        server = WebServer(
            report_dir=report_dir,
            host=ui_config['host'],
            port=ui_config['port']
        )
        print(f"\n✅ Analysis complete!")
        print(f"View report at: http://{ui_config['host']}:{ui_config['port']}/")
        print(f"Or open directly: {html_path}")
        print("\nPress Ctrl+C to stop the server.")
        try:
            server.run(debug=ui_config.get('debug', False))
        except KeyboardInterrupt:
            print("\nServer stopped.")
    else:
        print(f"\n✅ Analysis complete!")
        print(f"View report at: {html_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='AI-Powered Codebase Analysis System'
    )
    parser.add_argument(
        '--codebase',
        type=str,
        required=True,
        help='Path to codebase directory'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to config file (default: config.yaml)'
    )
    parser.add_argument(
        '--no-ui',
        action='store_true',
        help='Skip starting web UI (just generate report)'
    )
    
    args = parser.parse_args()
    
    # Validate codebase path
    if not os.path.isdir(args.codebase):
        print(f"Error: Codebase path does not exist: {args.codebase}")
        sys.exit(1)
    
    # Load config
    config = load_config(args.config)
    
    # Run analysis
    run_analysis(args.codebase, config, start_ui=not args.no_ui)


if __name__ == '__main__':
    main()

