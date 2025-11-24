"""
Process issue detection analyzer.
"""

from typing import Dict, List
from llm_client import LocalLLMClient


class ProcessIssueDetector:
    """Detects issues in workflows and processes."""
    
    def __init__(self, llm_client: LocalLLMClient, system_message: str,
                 fallback_description_length: int, default_workflow_name: str,
                 no_steps_message: str):
        """
        Initialize process issue detector.
        
        Args:
            llm_client: LLM client instance
            system_message: System message for LLM prompts
            fallback_description_length: Fallback description truncation length
            default_workflow_name: Default workflow name when name is not available
            no_steps_message: Message when workflow has no steps
        """
        self.llm_client = llm_client
        self.system_message = system_message
        self.fallback_description_length = fallback_description_length
        self.default_workflow_name = default_workflow_name
        self.no_steps_message = no_steps_message
    
    def analyze_workflow(self, workflow: Dict) -> List[Dict]:
        """
        Analyze a workflow for potential issues.
        
        Args:
            workflow: Workflow definition from WorkflowAnalyzer
        
        Returns:
            List of issues: [{type, severity, description, suggestion}]
        """
        description = workflow.get('description', '')
        name = workflow.get('name', self.default_workflow_name)
        steps = workflow.get('steps', [])
        
        prompt = f"""Analyze the following workflow description for potential issues, gaps, or problems.

Workflow: {name}

Description:
{description}

Steps:
{self._format_steps(steps)}

Please identify:
1. Missing steps or error handling
2. Potential failure points
3. Security concerns
4. Data consistency issues
5. Performance bottlenecks
6. Race conditions or concurrency problems
7. Missing validations or checks
8. Incomplete rollback/compensation logic

For each issue found, provide:
- Issue type
- Severity (high/medium/low)
- Description
- Suggestion for improvement

If no issues are found, respond with "No issues found."
"""
        
        try:
            response = self.llm_client.query(
                prompt,
                system_message=self.system_message
            )
            
            issues = self._parse_issues(response, workflow.get('name', self.default_workflow_name))
            return issues
        
        except Exception as e:
            print(f"Error analyzing workflow {name}: {e}")
            return []
    
    def _format_steps(self, steps: List[Dict]) -> str:
        """Format workflow steps for prompt."""
        if not steps:
            return self.no_steps_message
        
        return '\n'.join([f"{step.get('number', i+1)}. {step.get('description', '')}" 
                         for i, step in enumerate(steps)])
    
    def _parse_issues(self, response: str, workflow_name: str) -> List[Dict]:
        """Parse LLM response into structured issues."""
        issues = []
        
        if 'no issues found' in response.lower():
            return issues
        
        lines = response.split('\n')
        current_issue = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Extract severity
            severity = 'medium'
            if any(word in line.lower() for word in ['high', 'critical', 'severe']):
                severity = 'high'
            elif any(word in line.lower() for word in ['low', 'minor']):
                severity = 'low'
            
            # Extract issue type
            issue_type = 'general'
            if 'error handling' in line.lower() or 'exception' in line.lower():
                issue_type = 'error_handling'
            elif 'security' in line.lower() or 'vulnerability' in line.lower():
                issue_type = 'security'
            elif 'performance' in line.lower() or 'bottleneck' in line.lower():
                issue_type = 'performance'
            elif 'concurrency' in line.lower() or 'race' in line.lower():
                issue_type = 'concurrency'
            elif 'validation' in line.lower() or 'check' in line.lower():
                issue_type = 'validation'
            elif 'rollback' in line.lower() or 'compensation' in line.lower():
                issue_type = 'transaction'
            
            # New issue if line starts with number or bullet
            import re
            if re.match(r'^[\d\-\*•]', line):
                if current_issue:
                    issues.append(current_issue)
                current_issue = {
                    'workflow': workflow_name,
                    'type': issue_type,
                    'severity': severity,
                    'description': line,
                    'suggestion': ''
                }
            elif current_issue:
                # Continue building current issue
                if 'suggestion' in current_issue:
                    if not current_issue['suggestion']:
                        current_issue['suggestion'] = line
                    else:
                        current_issue['description'] += ' ' + line
                else:
                    current_issue['description'] += ' ' + line
        
        if current_issue:
            issues.append(current_issue)
        
        # If parsing failed, create single issue
        if not issues and response:
            issues.append({
                'workflow': workflow_name,
                'type': 'general',
                'severity': 'medium',
                'description': response[:self.fallback_description_length],
                'suggestion': ''
            })
        
        return issues

