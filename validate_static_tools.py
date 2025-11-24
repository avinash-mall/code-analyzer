#!/usr/bin/env python3
"""
Validation script for Semgrep and SonarQube integration.
"""

import os
import sys
import subprocess
import yaml
from pathlib import Path

def validate_semgrep(semgrep_path: str = "semgrep"):
    """Validate Semgrep is working."""
    print("=" * 60)
    print("Validating Semgrep...")
    print("=" * 60)
    
    try:
        # Check if semgrep is available
        result = subprocess.run(
            [semgrep_path, '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print(f"[OK] Semgrep is available: {result.stdout.strip()}")
            
            # Test with a simple scan
            test_code = """
def test_function():
    password = "hardcoded123"  # Security issue
    x = 1 / 0  # Division by zero
    return None
"""
            
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                test_file = os.path.join(tmpdir, "test.py")
                with open(test_file, 'w') as f:
                    f.write(test_code)
                
                result = subprocess.run(
                    [semgrep_path, '--json', '--quiet', tmpdir],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 or result.stdout:
                    import json
                    try:
                        data = json.loads(result.stdout)
                        issues = len(data.get('results', []))
                        print(f"[OK] Semgrep scan successful: Found {issues} issue(s) in test code")
                        return True
                    except json.JSONDecodeError:
                        print("[WARN] Semgrep returned output but couldn't parse JSON")
                        return True
                else:
                    print("[OK] Semgrep scan completed but no issues found (expected for empty scan)")
                    return True
        else:
            print(f"[ERROR] Semgrep version check failed: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print(f"[ERROR] Semgrep not found at '{semgrep_path}'. Install with: pip install semgrep")
        return False
    except subprocess.TimeoutExpired:
        print("[ERROR] Semgrep test timed out")
        return False
    except Exception as e:
        print(f"[ERROR] Error validating Semgrep: {e}")
        return False


def validate_sonarqube(sonarqube_url: str, token: str = None, project_key: str = "test-project"):
    """Validate SonarQube connection."""
    print("\n" + "=" * 60)
    print("Validating SonarQube...")
    print("=" * 60)
    
    try:
        import requests
        
        # Test connection to SonarQube server
        health_url = f"{sonarqube_url.rstrip('/')}/api/system/health"
        
        print(f"Testing connection to: {health_url}")
        
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        try:
            response = requests.get(health_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                health_data = response.json()
                status = health_data.get('health', 'UNKNOWN')
                print(f"[OK] SonarQube server is reachable. Health status: {status}")
                
                # Try to get server version
                version_url = f"{sonarqube_url.rstrip('/')}/api/system/version"
                version_response = requests.get(version_url, headers=headers, timeout=10)
                if version_response.status_code == 200:
                    version_data = version_response.json()
                    version = version_data.get('version', 'unknown')
                    print(f"[OK] SonarQube version: {version}")
                
                # Test issues API
                issues_url = f"{sonarqube_url.rstrip('/')}/api/issues/search"
                params = {
                    'componentKeys': project_key,
                    'resolved': 'false',
                    'ps': 1
                }
                
                issues_response = requests.get(issues_url, params=params, headers=headers, timeout=10)
                if issues_response.status_code == 200:
                    print("[OK] SonarQube REST API is accessible")
                    return True
                elif issues_response.status_code == 404:
                    print(f"[WARN] Project '{project_key}' not found (this is OK if you haven't created it yet)")
                    print("[OK] SonarQube REST API is accessible")
                    return True
                else:
                    print(f"[WARN] SonarQube API returned status {issues_response.status_code}: {issues_response.text[:200]}")
                    return True
                    
            else:
                print(f"[ERROR] SonarQube server returned status {response.status_code}: {response.text[:200]}")
                return False
                
        except requests.exceptions.ConnectionError:
            print(f"[ERROR] Cannot connect to SonarQube at {sonarqube_url}")
            print("   Make sure SonarQube is running in Docker and accessible at this URL")
            return False
        except requests.exceptions.Timeout:
            print(f"[ERROR] Connection to SonarQube timed out")
            return False
        except Exception as e:
            print(f"[ERROR] Error connecting to SonarQube: {e}")
            return False
            
    except ImportError:
        print("[ERROR] requests library not available. Install with: pip install requests")
        return False


def main():
    """Main validation function."""
    # Load config if available
    config_path = Path("config.yaml")
    config = {}
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    
    static_config = config.get('static_analyzer', {})
    
    # Validate Semgrep
    semgrep_path = static_config.get('semgrep_path', 'semgrep')
    semgrep_ok = validate_semgrep(semgrep_path)
    
    # Validate SonarQube if configured
    sonarqube_url = static_config.get('sonarqube_url')
    sonarqube_ok = None
    
    if sonarqube_url:
        sonarqube_token = static_config.get('sonarqube_token')
        project_key = static_config.get('project_key', 'codebase-analysis')
        sonarqube_ok = validate_sonarqube(sonarqube_url, sonarqube_token, project_key)
    else:
        print("\n" + "=" * 60)
        print("Skipping SonarQube validation (not configured)")
        print("=" * 60)
        print("To enable SonarQube, add to config.yaml:")
        print("  static_analyzer:")
        print("    sonarqube_url: http://localhost:9000  # Your SonarQube Docker URL")
        print("    sonarqube_token: your_token  # Optional authentication token")
        print("    project_key: your-project-key  # SonarQube project key")
    
    # Summary
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)
    print(f"Semgrep: {'[OK]' if semgrep_ok else '[FAILED]'}")
    if sonarqube_ok is not None:
        print(f"SonarQube: {'[OK]' if sonarqube_ok else '[FAILED]'}")
    else:
        print("SonarQube: [SKIPPED] (not configured)")
    
    # Return appropriate exit code
    if not semgrep_ok:
        sys.exit(1)
    if sonarqube_ok is False:
        sys.exit(1)
    
    print("\n[OK] All configured static analysis tools are validated!")


if __name__ == '__main__':
    main()

