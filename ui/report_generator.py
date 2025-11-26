"""
HTML and PDF report generation.
"""

import os
import markdown
import subprocess
import base64
import tempfile
from typing import Dict, List, Optional
from jinja2 import Environment, FileSystemLoader
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter


class ReportGenerator:
    """Generates HTML and PDF reports from analysis results."""
    
    def __init__(self, output_dir: str, pygments_style: str,
                 pygments_linenos: bool, code_not_found_message: str,
                 use_mermaid: bool = True):
        """
        Initialize report generator.
        
        Args:
            output_dir: Output directory for reports
            pygments_style: Pygments code highlighting style
            pygments_linenos: Show line numbers in code blocks
            code_not_found_message: Message when code chunk cannot be found
            use_mermaid: Whether to include Mermaid.js for diagrams (requires internet)
        """
        self.output_dir = output_dir
        self.code_not_found_message = code_not_found_message
        self.use_mermaid = use_mermaid
        os.makedirs(output_dir, exist_ok=True)
        self.formatter = HtmlFormatter(style=pygments_style, linenos=pygments_linenos, cssclass="code-highlight")
        
        # Check if mermaid-cli is available
        self.mermaid_cli_available = self._check_mermaid_cli()
        
        # Setup Jinja2 environment
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))
        self.jinja_env.filters['markdown'] = lambda text: markdown.markdown(text, extensions=['fenced_code'])
    
    def _check_mermaid_cli(self) -> bool:
        """Check if mermaid-cli (mmdc) is available."""
        try:
            subprocess.run(['mmdc', '--version'], 
                         capture_output=True, 
                         timeout=5,
                         check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def _render_mermaid(self, mermaid_code: str, name: str) -> Optional[str]:
        """
        Render Mermaid diagram to SVG image (base64 encoded).
        
        Args:
            mermaid_code: Mermaid diagram code
            name: Unique name for the diagram (used for temp file)
        
        Returns:
            HTML img tag with base64 SVG, or None if rendering fails
        """
        if not mermaid_code or not mermaid_code.strip():
            return None
        
        if not self.mermaid_cli_available:
            return None
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                mmd_path = os.path.join(tmpdir, f"{name}.mmd")
                svg_path = os.path.join(tmpdir, f"{name}.svg")
                
                # Write Mermaid code to file
                with open(mmd_path, "w", encoding="utf-8") as f:
                    f.write(mermaid_code)
                
                # Render to SVG using mermaid-cli
                result = subprocess.run(
                    ["mmdc", "-i", mmd_path, "-o", svg_path, "-b", "transparent"],
                    capture_output=True,
                    timeout=30,
                    check=True
                )
                
                # Read SVG and encode as base64
                with open(svg_path, "rb") as f:
                    svg_bytes = f.read()
                
                b64 = base64.b64encode(svg_bytes).decode("ascii")
                return f'<img src="data:image/svg+xml;base64,{b64}" alt="Workflow diagram" style="max-width: 100%; height: auto;" />'
        
        except Exception as e:
            print(f"  > Warning: Could not render Mermaid diagram '{name}': {e}")
            return None
    
    def generate_report(self, analysis_results: Dict, output_filename: str) -> str:
        """
        Generate HTML and PDF reports.
        
        Args:
            analysis_results: Dictionary containing all analysis results.
            output_filename: Base name for output files (without extension).
        
        Returns:
            Path to the generated HTML file.
        """
        html_path = self._generate_html(analysis_results, f"{output_filename}.html")
        print(f"HTML report generated at: {html_path}")
        
        pdf_path = self._generate_pdf(html_path, f"{output_filename}.pdf")
        if pdf_path:
            print(f"PDF report generated at: {pdf_path}")
            
        return html_path

    def _generate_html(self, results: Dict, output_file: str) -> str:
        """Generate HTML report from analysis results."""
        output_path = os.path.join(self.output_dir, output_file)
        
        template_data = self._prepare_template_data(results)
        
        pygments_css = self.formatter.get_style_defs('.code-highlight')
        template_data['pygments_css'] = pygments_css
        
        template = self.jinja_env.get_template('report_template.html')
        
        html_content = template.render(**template_data)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path
    
    def _prepare_template_data(self, results: Dict) -> Dict:
        """Prepare data structure for template rendering."""
        from collections import Counter
        
        issues = results.get('code_review', [])
        documentation = results.get('documentation', {})
        workflows = results.get('workflows', {})
        architecture = results.get('architecture', "")
        
        # Group issues by file
        issues_by_file = {}
        for issue in issues:
            file = issue.get('file', 'general')
            if file not in issues_by_file:
                issues_by_file[file] = []
            issues_by_file[file].append(issue)

        # Sort files and issues within each file by severity
        issues_by_file_sorted = {}
        for file_path in sorted(issues_by_file.keys()):
            file_issues = issues_by_file[file_path]
            # Sort high > medium > low
            severity_order = {'high': 0, 'medium': 1, 'low': 2}
            file_issues.sort(key=lambda i: severity_order.get(i.get('severity', 'medium'), 1))
            issues_by_file_sorted[file_path] = file_issues

        issues_by_severity = {
            'high': [i for i in issues if i.get('severity') == 'high'],
            'medium': [i for i in issues if i.get('severity') == 'medium'],
            'low': [i for i in issues if i.get('severity') == 'low']
        }
        
        # Compute top files by issue count
        issues_per_file = Counter()
        for issue in issues:
            issues_per_file[issue.get('file', 'unknown')] += 1
        top_files = issues_per_file.most_common(5)
        
        # Get top 5 high-severity issues
        top_high_issues = [i for i in issues if i.get('severity') == 'high'][:5]
        
        # Prepare documentation, linking to code chunks
        docs_with_code = {}
        repo_map = results.get('repo_map', {})
        for file_path, doc_data in documentation.items():
            file_info = repo_map.get(file_path, {})
            language = file_info.get('language', 'text')
            
            # Add summary field for documentation
            file_summary = doc_data.get('file_summary', '')
            if file_summary:
                first_line = file_summary.split('\n', 1)[0]
                short_summary = first_line[:140] + '…' if len(first_line) > 140 else first_line
                doc_data['summary'] = short_summary
            else:
                doc_data['summary'] = ''
            
            # Format chunk docs with highlighted code
            for chunk_doc in doc_data.get('chunk_docs', []):
                # Find original chunk text
                chunk_text = self.code_not_found_message
                for chunk in file_info.get('chunks', []):
                    if chunk['name'] == chunk_doc['name'] and chunk['start_line'] == chunk_doc['start_line']:
                        chunk_text = chunk['text']
                        break
                chunk_doc['code'] = self._format_code(chunk_text, language)

            docs_with_code[file_path] = doc_data

        # Sort documentation by file path
        docs_sorted = dict(sorted(docs_with_code.items(), key=lambda kv: kv[0]))

        # Normalize workflow data - handle both dict and string formats
        workflows_normalized = {}
        for name, workflow in workflows.items():
            if isinstance(workflow, dict):
                wf_copy = workflow.copy()
                # Render Mermaid diagram to SVG if available
                mermaid_diagram = wf_copy.get('diagram') or wf_copy.get('mermaid_diagram')
                if mermaid_diagram:
                    diagram_img = self._render_mermaid(mermaid_diagram, f"workflow_{name.replace(' ', '_')}")
                    wf_copy['diagram_img'] = diagram_img
                    # Keep original mermaid code for fallback
                    wf_copy['mermaid_diagram'] = mermaid_diagram
                workflows_normalized[name] = wf_copy
            else:
                # Legacy string format - convert to dict
                workflows_normalized[name] = {
                    'name': name,
                    'description': workflow,
                    'steps': [],
                    'diagram': None,
                    'diagram_img': None
                }

        return {
            'issues_by_file': issues_by_file_sorted,
            'issues_by_severity': issues_by_severity,
            'documentation': docs_sorted,
            'workflows': workflows_normalized,
            'architecture_overview': architecture,
            'all_files': sorted(repo_map.keys()),
            'top_files': top_files,
            'top_high_issues': top_high_issues,
            'use_mermaid': self.use_mermaid,
            'mermaid_cli_available': self.mermaid_cli_available
        }
    
    def _format_code(self, code: str, language: str) -> str:
        """Format code with syntax highlighting."""
        try:
            lexer = get_lexer_by_name(language)
            return highlight(code, lexer, self.formatter)
        except Exception:
            # Fallback for unknown languages
            return highlight(code, get_lexer_by_name('text'), self.formatter)

    def _generate_pdf(self, html_file: str, pdf_file: str) -> str:
        """Generate PDF from HTML report using xhtml2pdf (Windows-compatible)."""
        pdf_path = os.path.join(self.output_dir, pdf_file)
        
        # Try xhtml2pdf first (Windows-compatible, pure Python)
        try:
            from xhtml2pdf import pisa
            from io import BytesIO
            
            with open(html_file, 'r', encoding='utf-8') as html_file_handle:
                html_string = html_file_handle.read()
            
            # Create PDF
            result_file = open(pdf_path, "w+b")
            pdf = pisa.CreatePDF(
                BytesIO(html_string.encode('utf-8')),
                dest=result_file,
                encoding='utf-8'
            )
            result_file.close()
            
            if pdf.err:
                raise Exception(f"PDF generation error: {pdf.err}")
            
            return pdf_path
            
        except ImportError:
            # Fallback to WeasyPrint if xhtml2pdf is not available
            try:
                from weasyprint import HTML
                base_url = os.path.dirname(os.path.abspath(__file__))
                HTML(filename=html_file, base_url=base_url).write_pdf(pdf_path)
                return pdf_path
            except ImportError:
                print("\n" + "="*60)
                print("No PDF library found. Skipping PDF generation.")
                print("Install xhtml2pdf (recommended) or weasyprint for PDF support:")
                print("  pip install xhtml2pdf  # Windows-compatible")
                print("  pip install weasyprint  # Requires GTK+ on Windows")
                print("="*60 + "\n")
                return None
            except Exception as e:
                error_msg = str(e)
                if 'libgobject' in error_msg.lower() or 'gobject' in error_msg.lower() or 'gtk' in error_msg.lower():
                    print("\n" + "="*60)
                    print("WeasyPrint failed due to Windows GTK library issue.")
                    print("Try installing xhtml2pdf instead: pip install xhtml2pdf")
                    print("The HTML report is available and can be printed to PDF using your browser.")
                    print("="*60 + "\n")
                else:
                    print("\n" + "="*60)
                    print(f"Error generating PDF with WeasyPrint: {error_msg}")
                    print("Try installing xhtml2pdf instead: pip install xhtml2pdf")
                    print("="*60 + "\n")
                return None
        except Exception as e:
            error_msg = str(e)
            print("\n" + "="*60)
            print(f"Error generating PDF: {error_msg}")
            print("The HTML report is still available and can be printed to PDF using your browser.")
            print("="*60 + "\n")
            return None

