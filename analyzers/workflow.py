"""
Workflow definition and analysis.
"""

from typing import Dict, List
from llm_client import LocalLLMClient


class WorkflowAnalyzer:
    """Identifies and defines workflows/processes in the codebase."""
    
    def __init__(self, llm_client: LocalLLMClient):
        self.llm_client = llm_client
    
    def define_workflow(self, entry_point: str, call_sequence: List[str],
                       repo_map: Dict, code_snippets: Dict[str, str]) -> Dict:
        """
        Define a workflow from entry point and call sequence.
        
        Args:
            entry_point: Entry point file/function
            call_sequence: List of files in call sequence
            repo_map: Repository map for context
            code_snippets: Code snippets for files in sequence
        
        Returns:
            {
                'name': str,
                'entry_point': str,
                'steps': List[Dict],
                'description': str
            }
        """
        # Build workflow outline
        outline = self._build_workflow_outline(entry_point, call_sequence, repo_map)
        
        prompt = f"""Based on the following code flow, describe the workflow step by step in plain language.

Workflow Entry Point: {entry_point}

Call Sequence:
{outline}

Please provide:
1. A clear name for this workflow
2. Step-by-step description of what happens
3. Purpose and outcome
4. Key decision points or branches

Write in business/process terms, describing what the system does, not technical implementation details.
"""
        
        try:
            response = self.llm_client.query(
                prompt,
                system_message="You are a process analyst describing workflows from code. Focus on business processes, not technical details."
            )
            
            # Extract workflow name and steps
            name = self._extract_workflow_name(response, entry_point)
            steps = self._extract_steps(response)
            
            # Generate Mermaid diagram
            mermaid_diagram = self._generate_mermaid_diagram(call_sequence, repo_map)
            
            return {
                'name': name,
                'entry_point': entry_point,
                'steps': steps,
                'description': response,
                'call_sequence': call_sequence,
                'mermaid_diagram': mermaid_diagram
            }
        
        except Exception as e:
            print(f"Error defining workflow for {entry_point}: {e}")
            return {
                'name': entry_point,
                'entry_point': entry_point,
                'steps': [],
                'description': f"Error: {e}",
                'call_sequence': call_sequence
            }
    
    def _build_workflow_outline(self, entry_point: str, call_sequence: List[str],
                               repo_map: Dict) -> str:
        """Build a text outline of the workflow."""
        outline_lines = []
        
        for i, file_path in enumerate(call_sequence[:10], 1):  # Limit to 10 steps
            info = repo_map.get(file_path, {})
            defs = info.get('definitions', [])
            
            # Get main class/function name
            main_def = defs[0] if defs else None
            name = main_def.get('name', file_path) if main_def else file_path
            
            outline_lines.append(f"{i}. {file_path} ({name})")
        
        return '\n'.join(outline_lines)
    
    def _extract_workflow_name(self, description: str, entry_point: str) -> str:
        """Extract workflow name from description."""
        # Look for patterns like "The X workflow" or "X process"
        import re
        match = re.search(r'(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:workflow|process)', 
                         description, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Fallback: use entry point name
        return entry_point.split('/')[-1].replace('.java', '').replace('.py', '')
    
    def _extract_steps(self, description: str) -> List[Dict]:
        """Extract workflow steps from description."""
        steps = []
        lines = description.split('\n')
        
        for line in lines:
            line = line.strip()
            # Look for numbered steps or bullet points
            import re
            match = re.match(r'^(\d+)\.\s*(.+)', line)
            if match:
                steps.append({
                    'number': int(match.group(1)),
                    'description': match.group(2)
                })
            elif line.startswith('-') or line.startswith('*'):
                steps.append({
                    'number': len(steps) + 1,
                    'description': re.sub(r'^[\-\*]\s*', '', line)
                })
        
        # If no structured steps found, split by sentences
        if not steps:
            sentences = re.split(r'[.!?]\s+', description)
            for i, sentence in enumerate(sentences[:10], 1):
                if len(sentence.strip()) > 20:  # Only meaningful sentences
                    steps.append({
                        'number': i,
                        'description': sentence.strip()
                    })
        
        return steps
    
    def _generate_mermaid_diagram(self, call_sequence: List[str], repo_map: Dict) -> str:
        """Generate Mermaid sequence diagram for workflow."""
        if not call_sequence:
            return ""
        
        lines = ["sequenceDiagram"]
        
        # Extract participant names (simplified - use file names)
        participants = {}
        for i, file_path in enumerate(call_sequence[:10]):  # Limit to 10 steps
            # Get class name from file
            info = repo_map.get(file_path, {})
            defs = info.get('definitions', [])
            class_name = defs[0].get('name', file_path.split('/')[-1]) if defs else file_path.split('/')[-1]
            
            participant_id = f"P{i}"
            participants[file_path] = participant_id
            lines.append(f"    participant {participant_id} as {class_name}")
        
        # Add interactions
        for i in range(len(call_sequence) - 1):
            current = call_sequence[i]
            next_file = call_sequence[i + 1]
            
            current_id = participants.get(current, f"P{i}")
            next_id = participants.get(next_file, f"P{i+1}")
            
            lines.append(f"    {current_id}->>{next_id}: calls")
        
        return '\n'.join(lines)

