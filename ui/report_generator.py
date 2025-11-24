"""
HTML and PDF report generation.
"""

import os
import markdown
from typing import Dict, List
from jinja2 import Environment, FileSystemLoader
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter


class ReportGenerator:
    """Generates HTML and PDF reports from analysis results."""
    
    def __init__(self, output_dir: str, pygments_style: str,
                 pygments_linenos: bool, code_not_found_message: str):
        """
        Initialize report generator.
        
        Args:
            output_dir: Output directory for reports
            pygments_style: Pygments code highlighting style
            pygments_linenos: Show line numbers in code blocks
            code_not_found_message: Message when code chunk cannot be found
        """
        self.output_dir = output_dir
        self.code_not_found_message = code_not_found_message
        os.makedirs(output_dir, exist_ok=True)
        self.formatter = HtmlFormatter(style=pygments_style, linenos=pygments_linenos, cssclass="code-highlight")
        
        # Setup Jinja2 environment
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))
        self.jinja_env.filters['markdown'] = lambda text: markdown.markdown(text, extensions=['fenced_code'])
    
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
        
        issues = results.get('code_review', [])
        documentation = results.get('documentation', {})
        workflows = results.get('workflows', {})
        architecture = results.get('architecture', "")
        
        # Group issues by file and severity
        issues_by_file = {}
        for issue in issues:
            file = issue.get('file', 'general')
            if file not in issues_by_file:
                issues_by_file[file] = []
            issues_by_file[file].append(issue)

        issues_by_severity = {
            'high': [i for i in issues if i.get('severity') == 'high'],
            'medium': [i for i in issues if i.get('severity') == 'medium'],
            'low': [i for i in issues if i.get('severity') == 'low']
        }
        
        # Prepare documentation, linking to code chunks
        docs_with_code = {}
        repo_map = results.get('repo_map', {})
        for file_path, doc_data in documentation.items():
            file_info = repo_map.get(file_path, {})
            language = file_info.get('language', 'text')
            
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

        return {
            'issues_by_file': issues_by_file,
            'issues_by_severity': issues_by_severity,
            'documentation': docs_with_code,
            'workflows': workflows,
            'architecture_overview': architecture,
            'all_files': sorted(repo_map.keys())
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

