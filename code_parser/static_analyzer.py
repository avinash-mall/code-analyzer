"""
Static analysis tool integration (SonarQube, Semgrep, etc.)
"""

import subprocess
import json
import os
from typing import Dict, List, Optional
from pathlib import Path


class StaticAnalyzer:
    """Integrates with static analysis tools to find code issues."""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.sonarqube_path = self.config.get('sonarqube_path')
        self.semgrep_path = self.config.get('semgrep_path', 'semgrep')
    
    def run_semgrep(self, codebase_path: str) -> Dict[str, List[Dict]]:
        """
        Run Semgrep static analysis.
        
        Returns:
            Dictionary mapping file paths to list of findings
        """
        findings = {}
        
        try:
            # Run semgrep
            result = subprocess.run(
                [self.semgrep_path, '--json', '--quiet', codebase_path],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0 or result.stdout:
                data = json.loads(result.stdout)
                
                for result_item in data.get('results', []):
                    file_path = result_item.get('path', '')
                    # Make path relative
                    if os.path.isabs(file_path):
                        file_path = os.path.relpath(file_path, codebase_path)
                    
                    if file_path not in findings:
                        findings[file_path] = []
                    
                    findings[file_path].append({
                        'rule': result_item.get('check_id', 'unknown'),
                        'message': result_item.get('message', ''),
                        'severity': result_item.get('extra', {}).get('severity', 'medium'),
                        'line': result_item.get('start', {}).get('line', 0),
                        'type': self._categorize_issue(result_item.get('check_id', ''))
                    })
        
        except FileNotFoundError:
            print("Semgrep not found. Install with: pip install semgrep")
        except subprocess.TimeoutExpired:
            print("Semgrep analysis timed out")
        except Exception as e:
            print(f"Error running Semgrep: {e}")
        
        return findings
    
    def run_sonarqube(self, codebase_path: str) -> Dict[str, List[Dict]]:
        """
        Run SonarQube analysis (requires SonarQube server).
        This is a placeholder - full integration requires SonarQube setup.
        """
        findings = {}
        
        # Note: Full SonarQube integration requires:
        # 1. SonarQube server running
        # 2. sonar-scanner CLI tool
        # 3. Project configuration
        
        print("SonarQube integration requires server setup. Skipping.")
        return findings
    
    def _categorize_issue(self, rule_id: str) -> str:
        """Categorize issue by rule ID."""
        rule_lower = rule_id.lower()
        
        if 'security' in rule_lower or 'sqli' in rule_lower or 'xss' in rule_lower:
            return 'security'
        elif 'null' in rule_lower or 'npe' in rule_lower:
            return 'null_pointer'
        elif 'performance' in rule_lower or 'slow' in rule_lower:
            return 'performance'
        elif 'error' in rule_lower or 'exception' in rule_lower:
            return 'error_handling'
        else:
            return 'general'
    
    def run_all(self, codebase_path: str) -> Dict[str, List[Dict]]:
        """Run all available static analysis tools."""
        all_findings = {}
        
        # Run Semgrep
        semgrep_findings = self.run_semgrep(codebase_path)
        for file_path, issues in semgrep_findings.items():
            if file_path not in all_findings:
                all_findings[file_path] = []
            all_findings[file_path].extend(issues)
        
        # Run SonarQube if configured
        if self.sonarqube_path:
            sonar_findings = self.run_sonarqube(codebase_path)
            for file_path, issues in sonar_findings.items():
                if file_path not in all_findings:
                    all_findings[file_path] = []
                all_findings[file_path].extend(issues)
        
        return all_findings

