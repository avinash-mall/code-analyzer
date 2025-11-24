"""
Code review and bug detection analyzer.
"""

import re
from typing import Dict, List
from llm_client import LocalLLMClient


class CodeReviewAnalyzer:
    """Analyzes code for bugs, issues, and code quality problems."""
    
    def __init__(self, llm_client: LocalLLMClient, system_message: str, 
                 repo_summary_context_limit: int, issue_description_key_length: int,
                 default_issue_type: str, no_issues_message: str):
        """
        Initialize code review analyzer.
        
        Args:
            llm_client: LLM client instance
            system_message: System message for LLM prompts
            repo_summary_context_limit: Maximum characters for repository summary context
            issue_description_key_length: Length of description used for issue deduplication key
            default_issue_type: Default issue type when type cannot be determined
            no_issues_message: Message used in prompts when no issues found
        """
        self.llm_client = llm_client
        self.system_message = system_message
        self.repo_summary_context_limit = repo_summary_context_limit
        self.issue_description_key_length = issue_description_key_length
        self.default_issue_type = default_issue_type
        self.no_issues_message = no_issues_message
    
    def analyze_file_chunks(self, file_path: str, chunks: List[Dict], 
                           language: str, repo_summary: str) -> List[Dict]:
        """
        Analyze a file's chunks for code issues.
        
        Args:
            file_path: Path to file
            chunks: List of code chunks from the parser
            language: The programming language of the file
            repo_summary: Repository summary for context
        
        Returns:
            List of issues: [{file, line, type, severity, description, suggestion}]
        """
        all_issues = []
        
        for i, chunk in enumerate(chunks):
            print(f"  - Analyzing chunk {i+1}/{len(chunks)} ({chunk['name']})...")
            
            chunk_text = chunk.get('text', '')
            if not chunk_text.strip():
                continue
            
            prompt = self._build_prompt(file_path, chunk, language, repo_summary)
            
            try:
                response = self.llm_client.query(
                    prompt,
                    system_message=self.system_message
                )
                
                issues = self._parse_issues(response, file_path)
                all_issues.extend(issues)
            except Exception as e:
                print(f"    - Error analyzing chunk {chunk['name']}: {e}")
                continue
        
        return self._deduplicate_issues(all_issues)

    def _build_prompt(self, file_path: str, chunk: Dict, language: str, repo_summary: str) -> str:
        """Build the prompt for a single code chunk."""
        
        code_snippet = chunk['text']
        start_line = chunk['start_line']
        chunk_name = chunk['name']
        no_issues_msg = self.no_issues_message
        
        prompt = f"""Review the following code snippet and identify potential bugs, errors, or improvements.

File: {file_path}
Focus: {chunk_name} (lines {start_line}-{chunk['end_line']})

Code Snippet:
```{language}
{code_snippet}
```

Please identify:
1.  Potential bugs (null pointer exceptions, logic errors, etc.)
2.  Security vulnerabilities
3.  Code quality issues (code smells, anti-patterns)
4.  Missing error handling or validation
5.  Performance problems or inefficiencies

For each issue found, provide:
-   Line number (relative to the file, if possible, starting from {start_line})
-   Issue type (e.g., Bug, Vulnerability, Code Smell)
-   Severity (High/Medium/Low)
-   Description of the issue
-   Suggestion for a fix

Format your response as a list, one issue per item. If no issues are found, respond with "{no_issues_msg}".
"""
        
        if repo_summary:
            prompt = f"""Brief codebase context:
{repo_summary[:self.repo_summary_context_limit]}

{prompt}"""
            
        return prompt

    def _parse_issues(self, response: str, file_path: str) -> List[Dict]:
        """Parse LLM response into structured issues."""
        issues = []
        
        if self.no_issues_message.lower() in response.lower() or "no issues found" in response.lower():
            return issues
            
        # Split response into issue blocks. Issues often start with a number or bullet.
        issue_blocks = re.split(r'\n(?=\d+\.\s|\*\s|-\s)', response)
        
        for block in issue_blocks:
            if not block.strip():
                continue

            line_num_match = re.search(r'line\s+(\d+)', block, re.IGNORECASE)
            line_num = int(line_num_match.group(1)) if line_num_match else None
            
            severity_match = re.search(r'severity:\s*(high|medium|low)', block, re.IGNORECASE)
            severity = severity_match.group(1).lower() if severity_match else 'medium'
            
            issue_type_match = re.search(r'type:\s*(.+)', block, re.IGNORECASE)
            issue_type = issue_type_match.group(1).strip() if issue_type_match else self.default_issue_type

            desc_match = re.search(r'description:\s*([\s\S]+?)(?=suggestion:|$)', block, re.IGNORECASE)
            description = desc_match.group(1).strip() if desc_match else block
            
            sugg_match = re.search(r'suggestion:\s*([\s\S]+)', block, re.IGNORECASE)
            suggestion = sugg_match.group(1).strip() if sugg_match else ""

            # Clean up description
            description = re.sub(r'^(line|severity|type|suggestion):.*', '', description, flags=re.IGNORECASE | re.MULTILINE).strip()

            issues.append({
                'file': file_path,
                'line': line_num,
                'type': issue_type,
                'severity': severity,
                'description': description,
                'suggestion': suggestion
            })
            
        return issues
        
    def _deduplicate_issues(self, issues: List[Dict]) -> List[Dict]:
        """Deduplicate similar issues, especially those without line numbers."""
        unique_issues = []
        seen_signatures = set()
        
        for issue in issues:
            # Signature combines file, line (or a placeholder), and first N chars of description
            line_key = issue.get('line') or -1
            desc_key = issue.get('description', '')[:self.issue_description_key_length]
            signature = (issue['file'], line_key, desc_key)
            
            if signature not in seen_signatures:
                unique_issues.append(issue)
                seen_signatures.add(signature)
                
        return unique_issues

