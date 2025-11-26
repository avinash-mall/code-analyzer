"""
Code review and bug detection analyzer.
"""

import re
import json
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
                           language: str, repo_summary: str, 
                           static_findings: List[Dict] = None) -> List[Dict]:
        """
        Analyze a file's chunks for code issues.
        
        Args:
            file_path: Path to file
            chunks: List of code chunks from the parser
            language: The programming language of the file
            repo_summary: Repository summary for context
            static_findings: Optional list of static analysis findings for this file
        
        Returns:
            List of issues: [{file, line, type, severity, description, suggestion}]
        """
        all_issues = []
        static_findings = static_findings or []
        
        for i, chunk in enumerate(chunks):
            print(f"  - Analyzing chunk {i+1}/{len(chunks)} ({chunk['name']})...")
            
            chunk_text = chunk.get('text', '')
            if not chunk_text.strip():
                continue
            
            # Get static hints for this chunk's line range
            chunk_start = chunk.get('start_line', 0)
            chunk_end = chunk.get('end_line', 0)
            chunk_static_hints = self._get_static_hints_for_chunk(
                static_findings, chunk_start, chunk_end
            )
            
            prompt = self._build_prompt(file_path, chunk, language, repo_summary, chunk_static_hints)
            
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

    def _get_static_hints_for_chunk(self, static_findings: List[Dict], 
                                    chunk_start: int, chunk_end: int) -> str:
        """Extract static analysis hints for a specific chunk's line range."""
        if not static_findings:
            return ""
        
        relevant_findings = []
        for finding in static_findings:
            line = finding.get('line', 0)
            if chunk_start <= line <= chunk_end:
                relevant_findings.append(finding)
        
        # Limit to top 10 findings to avoid clutter
        relevant_findings = relevant_findings[:10]
        
        if not relevant_findings:
            return ""
        
        static_hints = "\nStatic analysis findings for this code section:\n"
        for finding in relevant_findings:
            severity = finding.get('severity', 'info').upper()
            line = finding.get('line', '?')
            message = finding.get('message', '')
            rule = finding.get('rule', 'unknown')
            static_hints += (
                f"- Line {line}: [{severity}] "
                f"{message} "
                f"({rule})\n"
            )
        static_hints += "\n"
        
        return static_hints
    
    def _build_prompt(self, file_path: str, chunk: Dict, language: str, 
                     repo_summary: str, static_hints: str = "") -> str:
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
{static_hints}
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
-   Description of the issue (keep under 3 sentences)
-   Suggestion for a fix

Return at most 10 of the most important issues. Prefer high severity problems.

IMPORTANT: Return ONLY valid JSON, no other text. Use this exact format:
[
  {{
    "line": <int or null>,
    "type": "<string>",
    "severity": "high|medium|low",
    "description": "<string>",
    "suggestion": "<string>"
  }}
]

If no issues are found, return an empty array: []
"""
        
        if repo_summary:
            prompt = f"""Brief codebase context:
{repo_summary[:self.repo_summary_context_limit]}

{prompt}"""
            
        return prompt

    def _parse_issues(self, response: str, file_path: str) -> List[Dict]:
        """Parse LLM response into structured issues. Tries JSON first, falls back to text parsing."""
        issues = []
        
        # Try JSON parsing first
        try:
            # Extract JSON from response (might be wrapped in markdown code blocks)
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                json_str = json_match.group(0)
                parsed_issues = json.loads(json_str)
                
                for issue in parsed_issues:
                    issues.append({
                        'file': file_path,
                        'line': issue.get('line'),
                        'type': issue.get('type', self.default_issue_type),
                        'severity': issue.get('severity', 'medium').lower(),
                        'description': issue.get('description', ''),
                        'suggestion': issue.get('suggestion', '')
                    })
                return issues
        except (json.JSONDecodeError, AttributeError, KeyError):
            # Fall back to text parsing
            pass
        
        # Fallback: text-based parsing (original logic)
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

