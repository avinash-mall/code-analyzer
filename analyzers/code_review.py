"""
Code review and bug detection analyzer.
"""

import re
from typing import Dict, List
from llm_client import LocalLLMClient


class CodeReviewAnalyzer:
    """Analyzes code for bugs, issues, and code quality problems."""
    
    def __init__(self, llm_client: LocalLLMClient):
        self.llm_client = llm_client
    
    def analyze_file(self, file_path: str, code: str, 
                    definitions: List[Dict], repo_summary: str = "") -> List[Dict]:
        """
        Analyze a file for code issues.
        
        Returns:
            List of issues: [{file, line, type, severity, description, suggestion}]
        """
        # Truncate code if too long
        max_code_length = 8000  # Approximate token limit
        code_snippet = code[:max_code_length] if len(code) > max_code_length else code
        
        # Format definitions for context
        defs_text = self._format_definitions(definitions)
        
        prompt = f"""Analyze the following code file and identify any potential bugs, errors, or bad practices.

File: {file_path}

Code structure:
{defs_text}

Code:
```{self._get_language_from_path(file_path)}
{code_snippet}
```

Please identify:
1. Potential bugs (null pointer exceptions, logic errors, etc.)
2. Security vulnerabilities
3. Code quality issues (code smells, anti-patterns)
4. Missing error handling
5. Concurrency issues
6. Performance problems

For each issue found, provide:
- Line number (if applicable)
- Issue type
- Severity (high/medium/low)
- Description
- Suggestion for fix

Format your response as a list, one issue per item. If no issues are found, respond with "No issues found."
"""
        
        if repo_summary:
            prompt = f"""Context about the codebase:
{repo_summary[:2000]}

{prompt}"""
        
        try:
            response = self.llm_client.query(
                prompt,
                system_message="You are an expert code reviewer. Be thorough but accurate. Only report real issues."
            )
            
            issues = self._parse_issues(response, file_path)
            return issues
        
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            return []
    
    def _format_definitions(self, definitions: List[Dict]) -> str:
        """Format definitions list for prompt."""
        if not definitions:
            return "No major definitions found."
        
        lines = []
        for defn in definitions[:20]:  # Limit to avoid too long context
            def_type = defn.get('type', 'unknown')
            name = defn.get('name', 'unknown')
            line = defn.get('line', '?')
            lines.append(f"  - {def_type}: {name} (line {line})")
        
        return '\n'.join(lines) if lines else "No definitions found."
    
    def _get_language_from_path(self, file_path: str) -> str:
        """Get language identifier from file path."""
        ext = file_path.split('.')[-1].lower()
        lang_map = {
            'java': 'java',
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'jsx': 'jsx',
            'tsx': 'tsx'
        }
        return lang_map.get(ext, 'text')
    
    def _parse_issues(self, response: str, file_path: str) -> List[Dict]:
        """Parse LLM response into structured issues."""
        issues = []
        
        # Try to extract issues from response
        # Look for patterns like "Line X:", "Issue:", etc.
        lines = response.split('\n')
        current_issue = None
        
        for line in lines:
            line = line.strip()
            if not line or line.lower() in ['no issues found.', 'no issues found']:
                continue
            
            # Try to extract line number
            line_match = re.search(r'line\s+(\d+)', line, re.IGNORECASE)
            line_num = int(line_match.group(1)) if line_match else None
            
            # Try to extract severity
            severity = 'medium'
            if re.search(r'\b(high|critical|severe)\b', line, re.IGNORECASE):
                severity = 'high'
            elif re.search(r'\b(low|minor)\b', line, re.IGNORECASE):
                severity = 'low'
            
            # Try to extract issue type
            issue_type = 'general'
            if re.search(r'\b(null|null pointer|npe)\b', line, re.IGNORECASE):
                issue_type = 'null_pointer'
            elif re.search(r'\b(security|vulnerability|injection)\b', line, re.IGNORECASE):
                issue_type = 'security'
            elif re.search(r'\b(error handling|exception)\b', line, re.IGNORECASE):
                issue_type = 'error_handling'
            elif re.search(r'\b(performance|slow|inefficient)\b', line, re.IGNORECASE):
                issue_type = 'performance'
            elif re.search(r'\b(concurrency|thread|race)\b', line, re.IGNORECASE):
                issue_type = 'concurrency'
            
            # If line starts with number or bullet, it's likely a new issue
            if re.match(r'^[\d\-\*•]', line):
                if current_issue:
                    issues.append(current_issue)
                current_issue = {
                    'file': file_path,
                    'line': line_num,
                    'type': issue_type,
                    'severity': severity,
                    'description': line,
                    'suggestion': ''
                }
            elif current_issue:
                # Continue building current issue
                if 'suggestion' in current_issue and not current_issue['suggestion']:
                    current_issue['suggestion'] = line
                else:
                    current_issue['description'] += ' ' + line
        
        if current_issue:
            issues.append(current_issue)
        
        # If parsing failed, create a single issue with the whole response
        if not issues and response and 'no issues' not in response.lower():
            issues.append({
                'file': file_path,
                'line': None,
                'type': 'general',
                'severity': 'medium',
                'description': response[:500],  # Truncate if too long
                'suggestion': ''
            })
        
        return issues

