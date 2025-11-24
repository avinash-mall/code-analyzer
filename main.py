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
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from code_parser import CodeParser, RepositoryIndexer, StaticAnalyzer
from llm_client import LocalLLMClient
from analyzers import (
    CodeReviewAnalyzer,
    DocumentationGenerator,
    WorkflowAnalyzer,
)
from ui import ReportGenerator, WebServer


def load_config(config_path: str, config_example_suffix: str) -> Dict:
    """Load configuration from YAML file."""
    if not os.path.exists(config_path):
        example_path = config_path + config_example_suffix
        if os.path.exists(example_path):
            print(f"Config file not found. Using example config: {example_path}")
            config_path = example_path
        else:
            raise FileNotFoundError(f"Configuration file not found at {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def run_analysis(codebase_path: str, config: Dict, start_ui: bool):
    """Run complete analysis pipeline."""
    
    print("=" * 60)
    print("AI-Powered Codebase Analysis System")
    print("=" * 60)
    
    # === Step 1: Code Ingestion & Indexing ===
    print("\n[Step 1/4] Parsing and indexing codebase...")
    parser_config = config['parser']
    parser_defaults = parser_config['default_values']
    parser = CodeParser(
        max_chunk_lines=parser_config['max_chunk_lines'],
        chunk_by=parser_config['chunk_by'],
        supported_languages=parser_config['supported_languages'],
        language_map=parser_config['language_map'],
        chunk_node_types=parser_config['chunk_node_types'],
        sub_chunk_types=parser_config['sub_chunk_types'],
        default_chunk_type=parser_defaults['default_chunk_type'],
        default_node_name=parser_defaults['default_node_name'],
        default_chunk_name_format=parser_defaults['default_chunk_name_format']
    )
    
    analysis_config = config['analysis']
    file_limits = analysis_config['file_limits']
    summary_display = analysis_config['summary_display']
    indexer = RepositoryIndexer(
        parser,
        repo_summary_max_files=file_limits['repo_summary_max_files'],
        max_methods_shown=summary_display['max_methods_shown'],
        max_functions_shown=summary_display['max_functions_shown']
    )
    
    repo_map = indexer.index_codebase(
        codebase_path,
        extensions=analysis_config['extensions'],
        exclude_patterns=analysis_config['exclude'],
        max_file_size=analysis_config['max_file_size']
    )
    repo_summary = indexer.get_repository_summary()
    print(f"  > Indexed {len(repo_map)} files.")

    # === Step 2: Initialize LLM Client ===
    print("\n[Step 2/4] Initializing LLM client...")
    llm_config = config['llm']
    llm_client = LocalLLMClient(
        api_base=llm_config['api_base'],
        api_key=llm_config['api_key'],
        model=llm_config['model'],
        temperature=llm_config['temperature'],
        max_tokens=llm_config['max_tokens'],
        timeout=llm_config['timeout'],
        max_retries=llm_config['max_retries'],
        retry_backoff_base=llm_config['retry_backoff_base'],
        test_message=llm_config['test_message']
    )
    
    print("  > Testing LLM connection...")
    if not llm_client.test_connection():
        print("\nERROR: Could not connect to LLM server.")
        print(f"Please ensure your LLM server is running and accessible at {llm_config['api_base']}")
        return
    print("  > LLM connection successful!")

    # === Step 3: Run Analysis Modules ===
    print("\n[Step 3/4] Running analysis modules...")
    analysis_results = {
        'repo_map': repo_map,
        'code_review': [],
        'documentation': {},
        'workflows': {},
        'architecture': "",
        'static_analysis': {}
    }
    
    # Initialize analyzers with config
    context_limits = analysis_config['context_limits']
    file_limits = analysis_config['file_limits']
    system_messages = analysis_config['system_messages']
    cross_ref = analysis_config['cross_reference']
    default_values = analysis_config['default_values']
    
    review_analyzer = CodeReviewAnalyzer(
        llm_client,
        system_message=system_messages['code_reviewer'],
        repo_summary_context_limit=context_limits['repo_summary'],
        issue_description_key_length=context_limits['issue_description_key'],
        default_issue_type=default_values['default_issue_type'],
        no_issues_message=default_values['no_issues_message']
    )
    
    doc_generator = DocumentationGenerator(
        llm_client,
        symbol_to_file=indexer.symbol_to_file,
        technical_writer_message=system_messages['technical_writer'],
        architect_message=system_messages['software_architect'],
        chunk_doc_truncate=context_limits['chunk_doc_truncate'],
        repo_summary_context_limit=context_limits['repo_summary'],
        min_symbol_length=cross_ref['min_symbol_length'],
        default_chunk_type=default_values['default_chunk_type'],
        default_chunk_name=default_values['default_chunk_name'],
        no_documentation_message=default_values['no_documentation_message'],
        no_file_summary_message=default_values['no_file_summary_message']
    )
    
    workflow_analyzer = WorkflowAnalyzer(
        llm_client,
        workflow_keywords=analysis_config['workflow_keywords'],
        business_analyst_message=system_messages['business_analyst'],
        architect_overview_message=system_messages['architect_overview'],
        workflow_context_max_files=file_limits['workflow_context_max_files'],
        architecture_context_max_files=file_limits['architecture_context_max_files'],
        repo_summary_context_limit=context_limits['repo_summary'],
        workflow_file_summary_length=context_limits['workflow_file_summary'],
        architecture_file_summary_length=context_limits['architecture_file_summary'],
        no_file_summary_message=default_values['no_file_summary_message'],
        no_workflows_message=default_values['no_workflows_message']
    )

    # File-by-file analysis
    print("  > Analyzing files for documentation and code review...")
    for file_path, file_info in tqdm(repo_map.items(), desc="Analyzing files"):
        chunks = file_info.get('chunks', [])
        language = file_info.get('language', default_values['default_language'])
        
        if not chunks:
            continue

        # Documentation Generation
        doc_result = doc_generator.generate_docs_for_file(file_path, chunks, language, repo_summary)
        analysis_results['documentation'][file_path] = doc_result
        
        # Code Review
        review_issues = review_analyzer.analyze_file_chunks(file_path, chunks, language, repo_summary)
        analysis_results['code_review'].extend(review_issues)
    
    print(f"  > Generated documentation for {len(analysis_results['documentation'])} files.")
    print(f"  > Found {len(analysis_results['code_review'])} potential issues.")

    # Static Analysis (Semgrep and SonarQube)
    static_config = config.get('static_analyzer', {})
    if static_config.get('enabled', True):
        print("  > Running static analysis tools...")
        static_defaults = static_config.get('default_values', {})
        static_analyzer = StaticAnalyzer(
            semgrep_path=static_config.get('semgrep_path', 'semgrep'),
            semgrep_timeout=static_config.get('semgrep_timeout', 300),
            sonarqube_path=static_config.get('sonarqube_path', ''),
            default_rule_id=static_defaults.get('default_rule_id', 'unknown'),
            default_severity=static_defaults.get('default_severity', 'medium'),
            default_line=static_defaults.get('default_line', 0)
        )
        
        static_findings = static_analyzer.run_all(
            codebase_path,
            sonarqube_url=static_config.get('sonarqube_url'),
            sonarqube_token=static_config.get('sonarqube_token'),
            project_key=static_config.get('project_key', 'codebase-analysis')
        )
        analysis_results['static_analysis'] = static_findings
        total_static_issues = sum(len(issues) for issues in static_findings.values())
        print(f"  > Static analysis found {total_static_issues} issues across {len(static_findings)} files.")

    # High-level analysis (Workflows and Architecture)
    print("  > Analyzing high-level workflows and architecture...")
    workflows = workflow_analyzer.analyze_workflows(repo_map, analysis_results['documentation'], repo_summary)
    analysis_results['workflows'] = workflows
    
    architecture = workflow_analyzer.generate_architecture_overview(analysis_results['documentation'], repo_summary)
    analysis_results['architecture'] = architecture
    print("  > High-level analysis complete.")

    # === Step 4: Generate Report ===
    print("\n[Step 4/4] Generating report...")
    output_config = config['output']
    report_config = config['report']
    report_generator = ReportGenerator(
        output_dir=output_config['report_dir'],
        pygments_style=report_config['pygments_style'],
        pygments_linenos=report_config['pygments_linenos'],
        code_not_found_message=default_values['code_not_found_message']
    )
    
    html_path = report_generator.generate_report(
        analysis_results,
        output_filename=output_config['report_filename_base']
    )

    # === Step 5: Start UI ===
    if start_ui:
        ui_config = config['ui']
        server = WebServer(
            report_dir=output_config['report_dir'],
            host=ui_config['host'],
            port=ui_config['port'],
            default_html_filename=output_config['default_html_filename']
        )
        server.run(debug=ui_config['debug'])
    else:
        print(f"\n[OK] Analysis complete!")
        print(f"   Report generated at: {html_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='AI-Powered Codebase Analysis System'
    )
    parser.add_argument(
        'codebase',
        type=str,
        help='Path to the codebase directory to analyze'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Path to the configuration file'
    )
    parser.add_argument(
        '--no-ui',
        action='store_true',
        help='Only generate the report and do not start the web server'
    )
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.codebase):
        print(f"Error: Provided codebase path is not a directory: {args.codebase}")
        sys.exit(1)
    
    try:
        # Determine config path - use provided or default
        config_path = args.config if args.config else 'config.yaml'
        
        # First load to get app config
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                temp_config = yaml.safe_load(f)
                app_config = temp_config['app']
                config_example_suffix = app_config['config_example_suffix']
        else:
            # If config doesn't exist yet, try to load example
            example_path = config_path + '.example'
            if os.path.exists(example_path):
                with open(example_path, 'r') as f:
                    temp_config = yaml.safe_load(f)
                    app_config = temp_config['app']
                    config_example_suffix = app_config['config_example_suffix']
            else:
                raise FileNotFoundError(f"Configuration file not found at {config_path}")
        
        config = load_config(config_path, config_example_suffix)
        app_config = config['app']
        default_start_ui = app_config['default_start_ui']
        run_analysis(args.codebase, config, start_ui=not args.no_ui if args.no_ui else default_start_ui)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

