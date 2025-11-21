"""
Business logic extraction analyzer.
"""

import re
from typing import Dict, List
from llm_client import LocalLLMClient


class BusinessLogicExtractor:
    """Extracts high-level business logic and rules from code."""
    
    def __init__(self, llm_client: LocalLLMClient):
        self.llm_client = llm_client
    
    def extract_from_file(self, file_path: str, code: str,
                         definitions: List[Dict]) -> Dict:
        """
        Extract business logic from a file.
        
        Returns:
            {
                'file': str,
                'business_rules': List[str],
                'processes': List[str],
                'domain_logic': str
            }
        """
        # Identify business-relevant methods
        business_methods = self._identify_business_methods(definitions, code)
        
        if not business_methods:
            return {
                'file': file_path,
                'business_rules': [],
                'processes': [],
                'domain_logic': 'No clear business logic identified.'
            }
        
        # Extract code for business methods
        method_snippets = self._extract_method_code(code, business_methods, file_path)
        
        prompt = f"""Analyze the following code file and extract the business logic, rules, and processes it implements.

File: {file_path}

Key business methods identified:
{self._format_methods(business_methods)}

Relevant code sections:
{method_snippets[:8000]}

Please identify and describe:
1. Business rules implemented (e.g., validation rules, calculation rules, approval rules)
2. Business processes/workflows (step-by-step operations)
3. Domain logic (how the code models real-world business concepts)
4. Important business decisions or branching logic

Write in business terms, not technical terms. Focus on WHAT the system does from a business perspective, not HOW it's implemented technically.
"""
        
        try:
            response = self.llm_client.query(
                prompt,
                system_message="You are a business analyst extracting business logic from code. Focus on business rules and processes, not technical implementation details."
            )
            
            # Parse response into structured format
            return self._parse_business_logic(response, file_path)
        
        except Exception as e:
            print(f"Error extracting business logic from {file_path}: {e}")
            return {
                'file': file_path,
                'business_rules': [],
                'processes': [],
                'domain_logic': f"Error: {e}"
            }
    
    def _identify_business_methods(self, definitions: List[Dict], code: str) -> List[Dict]:
        """Identify methods that likely contain business logic."""
        business_keywords = [
            'process', 'calculate', 'validate', 'approve', 'reject',
            'create', 'update', 'delete', 'submit', 'cancel',
            'order', 'payment', 'invoice', 'user', 'account',
            'business', 'rule', 'policy', 'workflow'
        ]
        
        business_methods = []
        
        for defn in definitions:
            if defn.get('type') in ['method', 'function']:
                name = defn.get('name', '').lower()
                # Check if method name suggests business logic
                if any(keyword in name for keyword in business_keywords):
                    business_methods.append(defn)
                # Also include public methods in service/manager classes
                elif 'service' in code.lower() or 'manager' in code.lower():
                    business_methods.append(defn)
        
        return business_methods[:10]  # Limit to top 10
    
    def _format_methods(self, methods: List[Dict]) -> str:
        """Format method list for prompt."""
        return '\n'.join([f"  - {m.get('name')} (line {m.get('line', '?')})" 
                         for m in methods])
    
    def _extract_method_code(self, code: str, methods: List[Dict], file_path: str) -> str:
        """Extract code snippets for specific methods."""
        lines = code.split('\n')
        snippets = []
        
        for method in methods:
            line_num = method.get('line', 0)
            if line_num and line_num <= len(lines):
                # Extract method code (next 50 lines or until next method)
                start_idx = line_num - 1
                end_idx = min(start_idx + 50, len(lines))
                snippet = '\n'.join(lines[start_idx:end_idx])
                snippets.append(f"Method {method.get('name')}:\n{snippet}\n")
        
        return '\n\n'.join(snippets)
    
    def _parse_business_logic(self, response: str, file_path: str) -> Dict:
        """Parse LLM response into structured business logic."""
        # Simple parsing - look for sections
        rules = []
        processes = []
        domain_logic = ""
        
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if 'business rule' in line.lower() or 'rule' in line.lower():
                current_section = 'rules'
            elif 'process' in line.lower() or 'workflow' in line.lower():
                current_section = 'processes'
            elif 'domain' in line.lower() or 'logic' in line.lower():
                current_section = 'domain'
            
            if line.startswith('-') or line.startswith('*') or line[0].isdigit():
                content = re.sub(r'^[\d\-\*•]\s*', '', line)
                if current_section == 'rules':
                    rules.append(content)
                elif current_section == 'processes':
                    processes.append(content)
            else:
                if current_section == 'domain':
                    domain_logic += line + ' '
        
        # If parsing failed, put everything in domain_logic
        if not rules and not processes:
            domain_logic = response
        
        return {
            'file': file_path,
            'business_rules': rules[:20],
            'processes': processes[:20],
            'domain_logic': domain_logic.strip() or response
        }
    
    def consolidate_business_logic(self, all_extractions: List[Dict],
                                  repo_summary: str = "") -> str:
        """Consolidate business logic from multiple files into overview."""
        if not all_extractions:
            return "No business logic extracted."
        
        # Prepare summary
        summary = "Business Logic Extracted from Codebase:\n\n"
        for ext in all_extractions[:20]:  # Limit files
            summary += f"File: {ext['file']}\n"
            if ext.get('business_rules'):
                summary += "Rules:\n" + '\n'.join([f"  - {r}" for r in ext['business_rules'][:5]])
            if ext.get('processes'):
                summary += "\nProcesses:\n" + '\n'.join([f"  - {p}" for p in ext['processes'][:5]])
            summary += "\n\n"
        
        prompt = f"""Based on the following business logic extracted from a codebase, provide a consolidated, high-level overview of the business domain and processes.

{summary[:6000]}

Please provide:
1. Overall business domain/purpose
2. Key business processes
3. Important business rules
4. Main entities/concepts

Write a clear, executive-level summary.
"""
        
        try:
            consolidated = self.llm_client.query(
                prompt,
                system_message="You are a business analyst creating a high-level business overview from code analysis."
            )
            return consolidated
        except Exception as e:
            return f"Error consolidating business_logic: {e}"

