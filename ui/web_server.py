"""
Flask web server for viewing analysis results.
"""

import os
from flask import Flask, send_from_directory
from pathlib import Path


class WebServer:
    """Web server for viewing analysis reports."""
    
    def __init__(self, report_dir: str, host: str, port: int,
                 default_html_filename: str):
        """
        Initialize web server.
        
        Args:
            report_dir: Directory containing reports
            host: Server host
            port: Server port
            default_html_filename: Default HTML filename to serve
        """
        self.report_dir_abs = os.path.abspath(report_dir)
        self.default_html_filename = default_html_filename
        
        self.app = Flask(
            __name__, 
            static_folder=self.report_dir_abs,
            static_url_path=''
        )
        
        self.host = host
        self.port = port
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up Flask routes."""
        
        @self.app.route('/')
        def index():
            """Serve the main report HTML."""
            return send_from_directory(self.report_dir_abs, self.default_html_filename)

        @self.app.route('/<path:filename>')
        def serve_report_files(filename):
            """Serve other files from the report directory (e.g., PDF)."""
            return send_from_directory(self.report_dir_abs, filename)

    def run(self, debug: bool):
        """Run the web server."""
        html_path = os.path.join(self.report_dir_abs, self.default_html_filename)
        if not os.path.exists(html_path):
            print(f"Warning: {self.default_html_filename} not found. Please run the analysis first.")
            return

        print(f"\n--- Web Server ---")
        print(f"Serving report from: {self.report_dir_abs}")
        print(f"View report at: http://{self.host}:{self.port}/")
        print(f"------------------")
        
        # Use werkzeug's run_simple to avoid auto-reloader issues in scripts
        from werkzeug.serving import run_simple
        run_simple(self.host, self.port, self.app, use_debugger=debug, use_reloader=debug)

