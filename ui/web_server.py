"""
Flask web server for viewing analysis results.
"""

import os
from flask import Flask, send_file, send_from_directory
from pathlib import Path


class WebServer:
    """Web server for viewing analysis reports."""
    
    def __init__(self, report_dir: str = "reports", host: str = "127.0.0.1", port: int = 5000):
        self.app = Flask(__name__, static_folder=None)
        self.report_dir = report_dir
        self.host = host
        self.port = port
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up Flask routes."""
        
        @self.app.route('/')
        def index():
            """Serve main report HTML."""
            report_path = os.path.join(self.report_dir, 'analysis_report.html')
            if os.path.exists(report_path):
                return send_file(report_path)
            else:
                return "Report not found. Please run analysis first.", 404
        
        @self.app.route('/pdf')
        def pdf():
            """Serve PDF report."""
            pdf_path = os.path.join(self.report_dir, 'analysis_report.pdf')
            if os.path.exists(pdf_path):
                return send_file(pdf_path, mimetype='application/pdf')
            else:
                return "PDF not found.", 404
    
    def run(self, debug: bool = False):
        """Run the web server."""
        print(f"Starting web server at http://{self.host}:{self.port}")
        print(f"View report at: http://{self.host}:{self.port}/")
        self.app.run(host=self.host, port=self.port, debug=debug)

