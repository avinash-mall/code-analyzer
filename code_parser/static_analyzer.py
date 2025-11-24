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
    
    def __init__(self, semgrep_path: str, semgrep_timeout: int, sonarqube_path: str,
                 default_rule_id: str, default_severity: str, default_line: int):
        """
        Initialize static analyzer.
        
        Args:
            semgrep_path: Path to semgrep executable
            semgrep_timeout: Timeout for semgrep execution (seconds)
            sonarqube_path: Path to sonarqube scanner (use empty string if not used)
            default_rule_id: Default rule ID when check_id is not available
            default_severity: Default severity when severity is not available
            default_line: Default line number when line is not available
        """
        self.sonarqube_path = sonarqube_path if sonarqube_path else None
        self.semgrep_path = semgrep_path
        self.semgrep_timeout = semgrep_timeout
        self.default_rule_id = default_rule_id
        self.default_severity = default_severity
        self.default_line = default_line
    
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
                timeout=self.semgrep_timeout
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
                        'rule': result_item.get('check_id', self.default_rule_id),
                        'message': result_item.get('message', ''),
                        'severity': result_item.get('extra', {}).get('severity', self.default_severity),
                        'line': result_item.get('start', {}).get('line', self.default_line),
                        'type': self._categorize_issue(result_item.get('check_id', ''))
                    })
        
        except FileNotFoundError:
            print("Semgrep not found. Install with: pip install semgrep")
        except subprocess.TimeoutExpired:
            print("Semgrep analysis timed out")
        except Exception as e:
            print(f"Error running Semgrep: {e}")
        
        return findings
    
    def run_sonarqube(self, codebase_path: str, sonarqube_url: str = None, 
                     sonarqube_token: str = None, project_key: str = None) -> Dict[str, List[Dict]]:
        """
        Run SonarQube analysis using sonar-scanner CLI or REST API.
        
        Args:
            codebase_path: Path to the codebase to analyze
            sonarqube_url: SonarQube server URL (e.g., http://localhost:9000)
            sonarqube_token: SonarQube authentication token
            project_key: SonarQube project key
            
        Returns:
            Dictionary mapping file paths to list of findings
        """
        findings = {}
        
        if not sonarqube_url:
            print("SonarQube URL not configured. Skipping SonarQube analysis.")
            return findings
        
        try:
            # Try using sonar-scanner CLI if path is provided
            if self.sonarqube_path and os.path.exists(self.sonarqube_path):
                # Create sonar-project.properties if it doesn't exist
                sonar_properties_path = os.path.join(codebase_path, 'sonar-project.properties')
                if not os.path.exists(sonar_properties_path):
                    properties_content = f"""sonar.projectKey={project_key or 'codebase-analysis'}
sonar.sources=.
sonar.host.url={sonarqube_url}
"""
                    if sonarqube_token:
                        properties_content += f"sonar.login={sonarqube_token}\n"
                    
                    with open(sonar_properties_path, 'w') as f:
                        f.write(properties_content)
                
                # Run sonar-scanner
                result = subprocess.run(
                    [self.sonarqube_path, '-Dproject.settings=sonar-project.properties'],
                    cwd=codebase_path,
                    capture_output=True,
                    text=True,
                    timeout=self.semgrep_timeout
                )
                
                if result.returncode != 0:
                    print(f"SonarQube scanner returned error: {result.stderr}")
                
                # Fetch issues from SonarQube REST API
                if sonarqube_url and project_key:
                    findings = self._fetch_sonarqube_issues(
                        sonarqube_url, 
                        project_key or 'codebase-analysis',
                        sonarqube_token
                    )
            
            # Alternative: Use REST API directly if no scanner available
            elif sonarqube_url and project_key:
                findings = self._fetch_sonarqube_issues(
                    sonarqube_url,
                    project_key,
                    sonarqube_token
                )
                
        except FileNotFoundError:
            print("SonarQube scanner not found. Try using REST API or install sonar-scanner.")
        except subprocess.TimeoutExpired:
            print("SonarQube analysis timed out")
        except Exception as e:
            print(f"Error running SonarQube: {e}")
        
        return findings
    
    def _fetch_sonarqube_issues(self, sonarqube_url: str, project_key: str, 
                               token: str = None) -> Dict[str, List[Dict]]:
        """Fetch issues from SonarQube REST API."""
        findings = {}
        
        try:
            import requests
            
            # Construct API URL
            api_url = f"{sonarqube_url.rstrip('/')}/api/issues/search"
            params = {
                'componentKeys': project_key,
                'resolved': 'false',
                'ps': 500  # Page size
            }
            
            headers = {}
            if token:
                headers['Authorization'] = f'Bearer {token}'
            
            # Make API request
            response = requests.get(api_url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                for issue in data.get('issues', []):
                    file_path = issue.get('component', '').replace(f"{project_key}:", '')
                    
                    # Skip if not a file-level issue
                    if ':' not in issue.get('component', ''):
                        continue
                    
                    # Extract relative path
                    if os.path.sep in file_path:
                        file_path = file_path.split(os.path.sep, 1)[-1]
                    
                    if file_path not in findings:
                        findings[file_path] = []
                    
                    findings[file_path].append({
                        'rule': issue.get('rule', self.default_rule_id),
                        'message': issue.get('message', ''),
                        'severity': issue.get('severity', self.default_severity).lower(),
                        'line': issue.get('line', self.default_line),
                        'type': self._categorize_issue(issue.get('rule', ''))
                    })
            else:
                print(f"SonarQube API error: {response.status_code} - {response.text}")
                
        except ImportError:
            print("requests library required for SonarQube REST API. Install with: pip install requests")
        except Exception as e:
            print(f"Error fetching SonarQube issues: {e}")
        
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
    
    def run_all(self, codebase_path: str, sonarqube_url: str = None,
                sonarqube_token: str = None, project_key: str = None) -> Dict[str, List[Dict]]:
        """Run all available static analysis tools."""
        all_findings = {}
        
        # Run Semgrep
        print("  > Running Semgrep analysis...")
        semgrep_findings = self.run_semgrep(codebase_path)
        for file_path, issues in semgrep_findings.items():
            if file_path not in all_findings:
                all_findings[file_path] = []
            all_findings[file_path].extend(issues)
        print(f"  > Semgrep found {sum(len(issues) for issues in semgrep_findings.values())} issues.")
        
        # Run SonarQube if configured
        if self.sonarqube_path or sonarqube_url:
            print("  > Running SonarQube analysis...")
            sonar_findings = self.run_sonarqube(
                codebase_path, 
                sonarqube_url=sonarqube_url,
                sonarqube_token=sonarqube_token,
                project_key=project_key
            )
            for file_path, issues in sonar_findings.items():
                if file_path not in all_findings:
                    all_findings[file_path] = []
                all_findings[file_path].extend(issues)
            print(f"  > SonarQube found {sum(len(issues) for issues in sonar_findings.values())} issues.")
        
        return all_findings

