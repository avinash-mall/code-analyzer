# AI-Powered Codebase Analysis System

An offline, local LLM-powered system for comprehensive codebase analysis including code review, documentation generation, business logic extraction, workflow definition, and process issue detection.

## Features

- **Multi-language Support**: Java, Python, JavaScript, and more via Tree-sitter
- **Local LLM Integration**: Works with Ollama, vLLM, or any OpenAI-compatible API
- **Comprehensive Analysis**:
  - Automated code review and bug detection (with static analysis integration)
  - Documentation generation (file and method level with cross-references)
  - Business logic extraction (with semantic clustering)
  - Workflow definition (with Mermaid diagrams)
  - Process issue detection
  - Cross-file issue detection
- **Advanced Features**:
  - Static analysis tool integration (Semgrep, SonarQube)
  - Vector embeddings for semantic code search (RAG)
  - Code viewer with line numbers and anchors
  - Interactive web UI with progress tracking
- **Interactive Web UI**: Browse results with hyperlinked navigation
- **PDF Export**: Generate shareable PDF reports

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up a local LLM (choose one):

**Option A: Ollama**
```bash
# Install Ollama from https://ollama.com
ollama pull codellama:34b
# Or use a smaller model: ollama pull codellama:7b
```

**Option B: vLLM**
```bash
pip install vllm
python -m vllm.entrypoints.openai.api_server --model codellama/CodeLlama-34b-Instruct-hf --port 8000
```

3. Configure the system:
```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your LLM endpoint settings
```

4. Run analysis:
```bash
python main.py --codebase /path/to/your/codebase
```

5. View results:
```bash
# The web UI will start automatically, or open analysis_report.html in a browser
```

## Configuration

Edit `config.yaml` to configure:
- LLM endpoint (Ollama, vLLM, or custom)
- Model name
- Analysis options
- Output paths

## Architecture

- `code_parser/`: AST parsing and code indexing
- `llm_client/`: Local LLM integration
- `analyzers/`: Analysis modules (review, docs, business logic, etc.)
- `ui/`: Web interface and report generation
- `main.py`: Main orchestration script

## License

MIT

