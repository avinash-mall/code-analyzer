"""
HTML and PDF report generation.
"""

import os
from pathlib import Path
from typing import Dict, List
from jinja2 import Template
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer_for_filename
from pygments.formatters import HtmlFormatter


class ReportGenerator:
    """Generates HTML and PDF reports from analysis results."""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.formatter = HtmlFormatter(style='colorful', linenos=True)
    
    def generate_html_report(self, results: Dict, output_file: str = "analysis_report.html") -> str:
        """
        Generate HTML report from analysis results.
        
        Args:
            results: Dictionary containing all analysis results
            output_file: Output HTML file name
        
        Returns:
            Path to generated HTML file
        """
        output_path = os.path.join(self.output_dir, output_file)
        
        # Prepare data for template
        template_data = self._prepare_template_data(results)
        
        # Get Pygments CSS
        pygments_css = self.formatter.get_style_defs()
        template_data['pygments_css'] = pygments_css
        
        # Load template
        html_template = self._get_html_template()
        template = Template(html_template)
        
        # Render
        html_content = template.render(**template_data)
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path
    
    def _prepare_template_data(self, results: Dict) -> Dict:
        """Prepare data structure for template rendering."""
        issues = results.get('code_review', {}).get('issues', [])
        docs = results.get('documentation', {}).get('docs', {})
        business_logic = results.get('business_logic', {})
        workflows = results.get('workflows', {}).get('workflows', [])
        process_issues = results.get('process_issues', {}).get('issues', [])
        
        # Group issues by file
        issues_by_file = {}
        for issue in issues:
            file_path = issue.get('file', 'unknown')
            if file_path not in issues_by_file:
                issues_by_file[file_path] = []
            issues_by_file[file_path].append(issue)
        
        # Group issues by severity
        issues_by_severity = {
            'high': [i for i in issues if i.get('severity') == 'high'],
            'medium': [i for i in issues if i.get('severity') == 'medium'],
            'low': [i for i in issues if i.get('severity') == 'low']
        }
        
        # Create file index for navigation
        all_files = set()
        all_files.update(issues_by_file.keys())
        all_files.update(docs.keys())
        all_files = sorted(all_files)
        
        return {
            'issues': issues,
            'issues_by_file': issues_by_file,
            'issues_by_severity': issues_by_severity,
            'total_issues': len(issues),
            'high_issues': len(issues_by_severity['high']),
            'medium_issues': len(issues_by_severity['medium']),
            'low_issues': len(issues_by_severity['low']),
            'documentation': docs,
            'business_logic': business_logic,
            'workflows': workflows,
            'process_issues': process_issues,
            'all_files': all_files,
            'code_formatter': self._format_code
        }
    
    def _format_code(self, code: str, language: str = None) -> str:
        """Format code with syntax highlighting."""
        try:
            if language:
                lexer = get_lexer_by_name(language)
            else:
                lexer = guess_lexer_for_filename("file.txt", code)
            return highlight(code, lexer, self.formatter)
        except:
            # Fallback: plain code
            return f'<pre><code>{code}</code></pre>'
    
    def _get_html_template(self) -> str:
        """Get HTML template for report."""
        return """<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Codebase Analysis Report</title>
        <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
        <script>mermaid.initialize({startOnLoad:true});</script>
        <style>
            {{ pygments_css|safe }}
            * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            text-align: center;
        }
        header h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }
        nav {
            background: #2c3e50;
            padding: 1rem;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        nav ul {
            list-style: none;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 1rem;
        }
        nav a {
            color: white;
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            transition: background 0.3s;
        }
        nav a:hover {
            background: rgba(255,255,255,0.1);
        }
        .content {
            padding: 2rem;
        }
        .section {
            margin-bottom: 3rem;
        }
        .section h2 {
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 0.5rem;
            margin-bottom: 1.5rem;
        }
        .section h3 {
            color: #555;
            margin-top: 1.5rem;
            margin-bottom: 1rem;
        }
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .card {
            background: #f8f9fa;
            padding: 1.5rem;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .card h3 {
            color: #667eea;
            margin: 0 0 0.5rem 0;
        }
        .card .number {
            font-size: 2rem;
            font-weight: bold;
            color: #333;
        }
        .issue {
            background: #fff;
            border-left: 4px solid #e74c3c;
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .issue.high { border-left-color: #e74c3c; }
        .issue.medium { border-left-color: #f39c12; }
        .issue.low { border-left-color: #3498db; }
        .issue-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }
        .severity-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: bold;
            text-transform: uppercase;
        }
        .severity-high { background: #e74c3c; color: white; }
        .severity-medium { background: #f39c12; color: white; }
        .severity-low { background: #3498db; color: white; }
        .file-link {
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }
        .file-link:hover {
            text-decoration: underline;
        }
        .doc-section {
            background: #fff;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .workflow {
            background: #fff;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border-radius: 8px;
            border-left: 4px solid #27ae60;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .workflow-steps {
            margin-top: 1rem;
            padding-left: 1.5rem;
        }
        .workflow-steps li {
            margin-bottom: 0.5rem;
        }
        code {
            background: #f4f4f4;
            padding: 0.2rem 0.4rem;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        pre {
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 4px;
            overflow-x: auto;
            margin: 1rem 0;
        }
        .toc {
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 2rem;
        }
        .toc ul {
            list-style: none;
            padding-left: 1rem;
        }
        .toc a {
            color: #667eea;
            text-decoration: none;
        }
        .toc a:hover {
            text-decoration: underline;
        }
        @media print {
            nav { display: none; }
            .section { page-break-inside: avoid; }
        }
        .mermaid {
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 4px;
            margin: 1rem 0;
            text-align: center;
        }
        .doc-link {
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }
        .doc-link:hover {
            text-decoration: underline;
        }
        .code-viewer {
            background: #f8f9fa;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 1rem;
            margin: 1rem 0;
            max-height: 500px;
            overflow-y: auto;
        }
        .code-line {
            display: flex;
            padding: 2px 0;
        }
        .code-line-number {
            color: #999;
            padding-right: 1rem;
            user-select: none;
            min-width: 50px;
        }
        .code-line-content {
            flex: 1;
        }
        .code-line.highlight {
            background: #fff3cd;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 Codebase Analysis Report</h1>
            <p>Comprehensive AI-Powered Code Analysis</p>
        </header>
        
        <nav>
            <ul>
                <li><a href="#summary">Summary</a></li>
                <li><a href="#code-review">Code Review</a></li>
                <li><a href="#documentation">Documentation</a></li>
                <li><a href="#business-logic">Business Logic</a></li>
                <li><a href="#workflows">Workflows</a></li>
                <li><a href="#process-issues">Process Issues</a></li>
            </ul>
        </nav>
        
        <div class="content">
            <!-- Summary Section -->
            <section id="summary" class="section">
                <h2>📊 Summary</h2>
                <div class="summary-cards">
                    <div class="card">
                        <h3>Total Issues</h3>
                        <div class="number">{{ total_issues }}</div>
                    </div>
                    <div class="card">
                        <h3>High Severity</h3>
                        <div class="number" style="color: #e74c3c;">{{ high_issues }}</div>
                    </div>
                    <div class="card">
                        <h3>Medium Severity</h3>
                        <div class="number" style="color: #f39c12;">{{ medium_issues }}</div>
                    </div>
                    <div class="card">
                        <h3>Low Severity</h3>
                        <div class="number" style="color: #3498db;">{{ low_issues }}</div>
                    </div>
                </div>
            </section>
            
            <!-- Code Review Section -->
            <section id="code-review" class="section">
                <h2>🔍 Code Review & Bug Detection</h2>
                {% if issues %}
                    <h3>Issues by File</h3>
                    {% for file_path, file_issues in issues_by_file.items() %}
                        <div class="doc-section">
                            <h4><a href="#file-{{ file_path|replace('/', '-') }}" class="file-link">{{ file_path }}</a></h4>
                            {% for issue in file_issues %}
                                <div class="issue {{ issue.severity }}">
                                    <div class="issue-header">
                                        <span class="severity-badge severity-{{ issue.severity }}">{{ issue.severity }}</span>
                                        {% if issue.line %}
                                            <span>Line {{ issue.line }}</span>
                                        {% endif %}
                                    </div>
                                    <p><strong>Type:</strong> {{ issue.type|replace('_', ' ')|title }}</p>
                                    <p><strong>Description:</strong> {{ issue.description }}</p>
                                    {% if issue.suggestion %}
                                        <p><strong>Suggestion:</strong> {{ issue.suggestion }}</p>
                                    {% endif %}
                                </div>
                            {% endfor %}
                        </div>
                    {% endfor %}
                {% else %}
                    <p>No issues found.</p>
                {% endif %}
            </section>
            
            <!-- Documentation Section -->
            <section id="documentation" class="section">
                <h2>📚 Documentation</h2>
                {% if documentation %}
                    {% for file_path, doc in documentation.items() %}
                        <div class="doc-section" id="file-{{ file_path|replace('/', '-') }}">
                            <h3>{{ file_path }}</h3>
                            <div>{{ doc.documentation|replace('\\n', '<br>')|safe }}</div>
                            {% if doc.code_snippet %}
                                <div class="code-viewer" id="code-{{ file_path|replace('/', '-') }}">
                                    <h4>Code:</h4>
                                    {{ code_formatter(doc.code_snippet, doc.language) }}
                                </div>
                            {% endif %}
                        </div>
                    {% endfor %}
                {% else %}
                    <p>No documentation generated.</p>
                {% endif %}
            </section>
            
            <!-- Business Logic Section -->
            <section id="business-logic" class="section">
                <h2>💼 Business Logic</h2>
                {% if business_logic %}
                    <div class="doc-section">
                        <h3>Overview</h3>
                        <div>{{ business_logic.get('overview', 'No overview available.')|replace('\\n', '<br>')|safe }}</div>
                    </div>
                    {% if business_logic.get('extractions') %}
                        <h3>Detailed Extractions</h3>
                        {% for extraction in business_logic.extractions[:10] %}
                            <div class="doc-section">
                                <h4>{{ extraction.file }}</h4>
                                <p>{{ extraction.domain_logic|replace('\\n', '<br>')|safe }}</p>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% else %}
                    <p>No business logic extracted.</p>
                {% endif %}
            </section>
            
            <!-- Workflows Section -->
            <section id="workflows" class="section">
                <h2>🔄 Workflows</h2>
                {% if workflows %}
                    {% for workflow in workflows %}
                        <div class="workflow">
                            <h3>{{ workflow.name }}</h3>
                            <p><strong>Entry Point:</strong> {{ workflow.entry_point }}</p>
                            <div>{{ workflow.description|replace('\\n', '<br>')|safe }}</div>
                            {% if workflow.steps %}
                                <h4>Steps:</h4>
                                <ol class="workflow-steps">
                                    {% for step in workflow.steps %}
                                        <li>{{ step.description }}</li>
                                    {% endfor %}
                                </ol>
                            {% endif %}
                            {% if workflow.mermaid_diagram %}
                                <h4>Workflow Diagram:</h4>
                                <div class="mermaid">
{{ workflow.mermaid_diagram }}
                                </div>
                            {% endif %}
                        </div>
                    {% endfor %}
                {% else %}
                    <p>No workflows defined.</p>
                {% endif %}
            </section>
            
            <!-- Process Issues Section -->
            <section id="process-issues" class="section">
                <h2>⚠️ Process Issues</h2>
                {% if process_issues %}
                    {% for issue in process_issues %}
                        <div class="issue {{ issue.severity }}">
                            <div class="issue-header">
                                <span class="severity-badge severity-{{ issue.severity }}">{{ issue.severity }}</span>
                                <span><strong>Workflow:</strong> {{ issue.workflow }}</span>
                            </div>
                            <p><strong>Type:</strong> {{ issue.type|replace('_', ' ')|title }}</p>
                            <p><strong>Description:</strong> {{ issue.description }}</p>
                            {% if issue.suggestion %}
                                <p><strong>Suggestion:</strong> {{ issue.suggestion }}</p>
                            {% endif %}
                        </div>
                    {% endfor %}
                {% else %}
                    <p>No process issues found.</p>
                {% endif %}
            </section>
        </div>
    </div>
    <script>
        // Poll for analysis status if interactive mode
        if (window.location.search.includes('interactive=true')) {
            setInterval(function() {
                fetch('/api/status')
                    .then(r => r.json())
                    .then(data => {
                        if (data.running) {
                            document.getElementById('analysis-status').style.display = 'block';
                            document.getElementById('progress-fill').style.width = data.progress + '%';
                            document.getElementById('status-message').textContent = data.message;
                        }
                    });
            }, 2000);
        }
    </script>
</body>
</html>"""
    
    def generate_pdf(self, html_file: str, pdf_file: str = "analysis_report.pdf") -> str:
        """
        Generate PDF from HTML report.
        
        Args:
            html_file: Path to HTML file
            pdf_file: Output PDF file name
        
        Returns:
            Path to generated PDF file
        """
        try:
            from weasyprint import HTML
            pdf_path = os.path.join(self.output_dir, pdf_file)
            HTML(filename=html_file).write_pdf(pdf_path)
            return pdf_path
        except ImportError:
            print("WeasyPrint not available. Install with: pip install weasyprint")
            print("Alternatively, use browser's Print to PDF on the HTML file.")
            return None
        except Exception as e:
            print(f"Error generating PDF: {e}")
            return None

