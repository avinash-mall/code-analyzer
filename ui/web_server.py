"""
Flask web server for viewing analysis results and triggering analysis.
"""

import os
import json
from flask import Flask, send_file, send_from_directory, request, jsonify, render_template_string
from pathlib import Path
import threading


class WebServer:
    """Web server for viewing analysis reports and triggering analysis."""
    
    def __init__(self, report_dir: str = "reports", host: str = "127.0.0.1", port: int = 5000):
        self.app = Flask(__name__, static_folder=None)
        self.report_dir = report_dir
        self.host = host
        self.port = port
        self.analysis_status = {'running': False, 'progress': 0, 'message': 'Ready'}
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
        
        @self.app.route('/api/status')
        def status():
            """Get analysis status."""
            return jsonify(self.analysis_status)
        
        @self.app.route('/api/analyze', methods=['POST'])
        def trigger_analysis():
            """Trigger analysis (placeholder - would need full integration)."""
            data = request.json
            codebase_path = data.get('codebase_path')
            
            if not codebase_path or not os.path.isdir(codebase_path):
                return jsonify({'error': 'Invalid codebase path'}), 400
            
            # In a real implementation, this would trigger analysis in background
            self.analysis_status = {
                'running': True,
                'progress': 0,
                'message': 'Analysis started...'
            }
            
            return jsonify({'status': 'started'})
    
    def update_status(self, progress: int, message: str):
        """Update analysis status."""
        self.analysis_status = {
            'running': progress < 100,
            'progress': progress,
            'message': message
        }
    
    def run(self, debug: bool = False):
        """Run the web server."""
        print(f"Starting web server at http://{self.host}:{self.port}")
        print(f"View report at: http://{self.host}:{self.port}/")
        self.app.run(host=self.host, port=self.port, debug=debug)

