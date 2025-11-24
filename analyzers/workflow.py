"""
Workflow definition and analysis.
"""

from typing import Dict, List
import concurrent.futures
from llm_client import LocalLLMClient


class WorkflowAnalyzer:
    """Identifies and defines workflows/processes in the codebase."""
    
    def __init__(self, llm_client: LocalLLMClient, workflow_keywords: List[str],
                 business_analyst_message: str, architect_overview_message: str,
                 workflow_context_max_files: int, architecture_context_max_files: int,
                 repo_summary_context_limit: int, workflow_file_summary_length: int,
                 architecture_file_summary_length: int, no_file_summary_message: str,
                 no_workflows_message: str):
        """
        Initialize workflow analyzer.
        
        Args:
            llm_client: LLM client instance
            workflow_keywords: Keywords for identifying workflows
            business_analyst_message: System message for business analyst
            architect_overview_message: System message for architect overview
            workflow_context_max_files: Maximum files per workflow context
            architecture_context_max_files: Maximum files for architecture overview
            repo_summary_context_limit: Maximum characters for repository summary context
            workflow_file_summary_length: Truncate file summary to this length in workflow context
            architecture_file_summary_length: Truncate file summary to this length in architecture context
            no_file_summary_message: Default message when file summary is not available
            no_workflows_message: Message when no workflows are identified
        """
        self.llm_client = llm_client
        self.workflow_keywords = workflow_keywords
        self.business_analyst_message = business_analyst_message
        self.architect_overview_message = architect_overview_message
        self.workflow_context_max_files = workflow_context_max_files
        self.architecture_context_max_files = architecture_context_max_files
        self.repo_summary_context_limit = repo_summary_context_limit
        self.workflow_file_summary_length = workflow_file_summary_length
        self.architecture_file_summary_length = architecture_file_summary_length
        self.no_file_summary_message = no_file_summary_message
        self.no_workflows_message = no_workflows_message

    def analyze_workflows(self, repo_map: Dict, documentation: Dict, repo_summary: str) -> Dict:
        """
        High-level function to identify and describe major workflows.
        
        Args:
            repo_map: The repository map from the indexer.
            documentation: Documentation generated for each file.
            repo_summary: A summary of the repository structure.

        Returns:
            A dictionary where keys are workflow names and values are their descriptions.
        """
        # 1. Identify potential workflows/features
        potential_workflows = self._identify_potential_workflows(repo_map, documentation)
        
        if not potential_workflows:
            return {"Overall Summary": self.no_workflows_message}

        # 2. For each workflow, generate a description
        workflow_descriptions = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_workflow = {
                executor.submit(self._describe_workflow, name, files, repo_map, documentation, repo_summary): name
                for name, files in potential_workflows.items()
            }
            for future in concurrent.futures.as_completed(future_to_workflow):
                name = future_to_workflow[future]
                description = future.result()
                if description:
                    workflow_descriptions[name] = description
        
        return workflow_descriptions

    def _identify_potential_workflows(self, repo_map: Dict, documentation: Dict) -> Dict[str, List[str]]:
        """Identify clusters of files that represent a business workflow."""
        
        # Heuristic: group files by keywords in their paths or documentation
        clusters = {}
        
        for file_path, doc_info in documentation.items():
            content_to_check = file_path.lower() + " " + doc_info.get('file_summary', '').lower()
            
            for keyword in self.workflow_keywords:
                if keyword in content_to_check:
                    if keyword not in clusters:
                        clusters[keyword] = set()
                    clusters[keyword].add(file_path)
                    break # Assign file to first matching keyword cluster
        
        # Convert sets to lists
        return {k: list(v) for k, v in clusters.items()}
    
    def _describe_workflow(self, name: str, files: List[str], repo_map: Dict,
                          documentation: Dict, repo_summary: str) -> str:
        """Use LLM to generate a description for an identified workflow."""
        
        print(f"  - Describing workflow: {name.capitalize()}...")
        
        context = f"The following files are considered part of the '{name}' workflow:\n"
        for file_path in files[:self.workflow_context_max_files]: # Limit context size
            context += f"- `{file_path}`: {documentation.get(file_path, {}).get('file_summary', '')[:self.workflow_file_summary_length]}...\n"
        
        prompt = f"""Based on the following files and their summaries, describe the end-to-end business workflow for '{name.capitalize()}'.

{context}

Please provide:
1.  A high-level description of the workflow's purpose.
2.  The typical sequence of events or steps.
3.  The key business rules or logic involved.
4.  Any potential issues, bottlenecks, or areas for improvement in the process.

Focus on the business process, not the technical implementation.
"""
        
        if repo_summary:
            prompt = f"""Brief codebase context:
{repo_summary[:self.repo_summary_context_limit]}

{prompt}"""
            
        try:
            response = self.llm_client.query(
                prompt,
                system_message=self.business_analyst_message
            )
            return response
        except Exception as e:
            print(f"    - Error describing workflow '{name}': {e}")
            return f"An error occurred while analyzing the '{name}' workflow."

    def generate_architecture_overview(self, documentation: Dict, repo_summary: str) -> str:
        """Generate a top-level architecture overview of the system."""

        context = "The system consists of the following modules/components:\n\n"
        for file_path, doc_info in list(documentation.items())[:self.architecture_context_max_files]: # Limit context
             context += f"- **{file_path}**: {doc_info.get('file_summary', self.no_file_summary_message)[:self.architecture_file_summary_length]}...\n"

        prompt = f"""Based on the following list of components and their summaries, generate a high-level architecture overview for the entire system.

{context}

Please describe:
1.  The main subsystems or layers (e.g., UI, services, data).
2.  The primary responsibilities of each subsystem.
3.  How the major components seem to interact.
4.  The overall architectural pattern, if one is apparent (e.g., Monolith, Microservices, Layered).

Synthesize this information into a coherent, executive-level summary.
"""
        if repo_summary:
            prompt = f"""Repository file structure summary:
{repo_summary}

{prompt}
"""
        try:
            response = self.llm_client.query(
                prompt,
                system_message=self.architect_overview_message
            )
            return response
        except Exception as e:
            print(f"  - Error generating architecture overview: {e}")
            return f"Error generating architecture overview: {e}"

