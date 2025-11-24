# AI-Powered Codebase Analysis System

An offline, local LLM-powered system for comprehensive codebase analysis including code review, documentation generation, business logic extraction, workflow definition, and process issue detection.

## Features

- **Multi-language Support**: Java, Python, JavaScript, TypeScript, and more via Tree-sitter
- **Windows-Compatible**: Python AST parsing for Python files (no external dependencies), xhtml2pdf for PDF generation
- **Local LLM Integration**: Works with Ollama, vLLM, or any OpenAI-compatible API
- **Intelligent Code Chunking**: AST-based chunking by functions/classes (Python uses built-in AST, others use Tree-sitter) or size-based fallback
- **Comprehensive Analysis**:
  - Automated code review and bug detection (with static analysis integration)
  - Documentation generation (file and method level with cross-references)
  - Business logic extraction and workflow identification
  - Architecture overview generation
  - Cross-file issue detection
- **Advanced Features**:
  - **Static Analysis Integration**: Semgrep and SonarQube support
  - Vector embeddings for semantic code search (RAG) via ChromaDB
  - Code viewer with syntax highlighting and line numbers
  - Interactive web UI with hyperlinked navigation
- **Interactive Web UI**: Browse results with hyperlinked navigation between files and documentation
- **PDF Export**: Generate shareable PDF reports using xhtml2pdf (Windows-compatible) or WeasyPrint
- **Fully Configurable**: All settings in `config.yaml` with no hardcoded values

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note for Windows Users**: 
- Python files use Python's built-in AST module (no external dependencies needed)
- PDF generation uses xhtml2pdf which works on Windows without additional libraries
- Other languages may fall back to size-based chunking due to tree-sitter-languages compatibility issues on Windows

### 2. Set Up Local LLM

Choose one option:

**Option A: Ollama (Recommended for beginners)**

```bash
# Install Ollama from https://ollama.com
ollama pull deepseek-coder-v2:16b
# Or use a smaller model: ollama pull codellama:13b
# Or use a larger model: ollama pull codellama:34b

# Start Ollama (usually runs automatically)
ollama serve
```

**Option B: vLLM (Better performance for large models)**

```bash
pip install vllm
python -m vllm.entrypoints.openai.api_server \
    --model deepseek-ai/deepseek-coder-v2-instruct \
    --port 8000
```

### 3. Configure the System

The system uses `config.yaml` for all configuration. Copy the example file:

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` to set:

- **LLM Settings**: API base URL, model name, temperature, max tokens, retry settings
- **Parser Settings**: Chunking strategy, supported languages, AST node types
- **Analysis Settings**: Context limits, system messages, workflow keywords
- **Static Analysis**: Semgrep and SonarQube configuration
- **Output Settings**: Report directory, filenames

See [Configuration](#configuration) section for details.

### 4. (Optional) Set Up Static Analysis Tools

#### Semgrep

Semgrep is automatically installed with `pip install -r requirements.txt`. To verify:

```bash
semgrep --version
```

#### SonarQube (Docker)

If you want to use SonarQube for static analysis:

1. **Start SonarQube in Docker:**
```bash
docker run -d --name sonarqube -e SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true -p 9000:9000 sonarqube:latest
```

2. **Access SonarQube web interface:**
   - Open http://localhost:9000
   - Default credentials: `admin` / `admin`
   - Create a project and get the project key

3. **Generate an authentication token:**
   - Go to User > My Account > Security
   - Generate a token

4. **Update `config.yaml`:**
```yaml
static_analyzer:
  sonarqube_url: http://localhost:9000
  sonarqube_token: your_generated_token  # Optional
  project_key: your-project-key
  enabled: true
```

### 5. Run Analysis

```bash
python main.py /path/to/your/codebase
```

**Arguments:**
- `codebase`: Path to the codebase directory to analyze (positional, required)
- `--config PATH`: Path to configuration file (default: `config.yaml`)
- `--no-ui`: Generate report only, don't start web server

**Examples:**

```bash
# Basic usage
python main.py .

# Analyze specific directory
python main.py /path/to/project

# Use custom config file
python main.py . --config my_config.yaml

# Generate report without web UI
python main.py . --no-ui
```

### 6. View Results

- **Web UI**: Automatically starts at `http://127.0.0.1:5001` (or configured port)
- **HTML Report**: Generated in `analysis_reports/analysis_report.html`
- **PDF Report**: Generated automatically using xhtml2pdf (Windows-compatible) or WeasyPrint if available

## Configuration

All configuration is in `config.yaml`. The system has **no hardcoded values** - everything is configurable.

### Main Configuration Sections

#### LLM Configuration

```yaml
llm:
  api_base: "http://localhost:11434/v1"  # Ollama: 11434, vLLM: 8000
  api_key: ""  # Dummy key for local LLMs (can be empty)
  model: "deepseek-coder-v2:16b"  # Model name as recognized by your server
  temperature: 0.1  # Lower = more deterministic
  max_tokens: 160000  # Maximum tokens in response
  timeout: 300  # Request timeout in seconds
  max_retries: 3  # Maximum retry attempts on failure
  retry_backoff_base: 2  # Exponential backoff multiplier
  test_message: "Say 'OK' if you can read this."  # Connection test message
```

#### Parser Configuration

```yaml
parser:
  max_chunk_lines: 300  # Maximum lines per code chunk
  chunk_by: "function_or_class"  # Chunking strategy: "function_or_class" or "size"
  supported_languages:  # Languages to initialize Tree-sitter parsers for
    - java
    - python
    - javascript
    - typescript
  language_map:  # Mapping of file extensions to language names
    ".java": "java"
    ".py": "python"
    ".js": "javascript"
    ".ts": "typescript"
    ".jsx": "javascript"
    ".tsx": "typescript"
  chunk_node_types:  # Top-level AST node types for chunking per language
    java:
      - class_declaration
      - interface_declaration
      - enum_declaration
    python:
      - class_definition
      - function_definition
    # ... more languages
  sub_chunk_types:  # Sub-chunk node types (e.g., methods within classes)
    java:
      - method_declaration
      - constructor_declaration
    # ... more languages
  default_values:  # Default values for parsing
    default_chunk_type: "text_chunk"
    default_node_name: "unnamed"
    default_chunk_name_format: "lines_{start_line}-{end_line}"
```

#### Analysis Configuration

```yaml
analysis:
  extensions: [.java, .py, .js, .ts, .jsx, .tsx, .go, .rb, .php, .cs]  # File types to analyze
  exclude: ["**/node_modules/**", "**/__pycache__/**", ...]  # Glob patterns to exclude
  max_file_size: 10000000  # 10MB - files larger than this will be skipped
  
  # Context limits for LLM prompts (in characters)
  context_limits:
    repo_summary: 1500  # Repository summary context length
    chunk_doc_truncate: 500  # Truncate chunk docs in file summary
    fallback_description: 500  # Fallback description length
    workflow_file_summary: 200  # Truncate file summary in workflow context
    architecture_file_summary: 250  # Truncate file summary in architecture context
    issue_description_key: 50  # Length of description used for issue deduplication key
  
  # File limits for context generation
  file_limits:
    repo_summary_max_files: 100  # Max files in repository summary
    workflow_context_max_files: 10  # Max files per workflow context
    architecture_context_max_files: 25  # Max files for architecture overview
    cross_file_max_references: 20  # Max references to check for cross-file analysis
  
  # System messages for LLM prompts (personas)
  system_messages:
    code_reviewer: "You are an expert code reviewer. Be thorough but accurate. Only report real issues."
    technical_writer: "You are an expert technical writer. Write a concise, accurate docstring or summary for the given code."
    software_architect: "You are a senior software architect. You can understand system design from its parts."
    business_analyst: "You are a business process analyst. You describe complex software workflows in simple business terms."
    process_analyst: "You are a process analyst reviewing workflows for issues. Be thorough but accurate."
    architect_overview: "You are an expert software architect. You can infer system architecture from its components."
  
  # Workflow detection keywords
  workflow_keywords:
    - order
    - payment
    - user
    - auth
    - report
    - product
    - cart
    - inventory
  
  # Cross-reference configuration
  cross_reference:
    min_symbol_length: 4  # Minimum symbol name length for cross-referencing
  
  # Summary display limits
  summary_display:
    max_methods_shown: 5  # Maximum number of methods to show per class in summary
    max_functions_shown: 10  # Maximum number of functions to show in summary
  
  # Default values for analysis
  default_values:
    default_chunk_type: "snippet"
    default_chunk_name: "unnamed"
    no_documentation_message: "No documentation could be generated for this file."
    # ... more defaults
```

#### Static Analyzer Configuration

```yaml
static_analyzer:
  enabled: true  # Enable/disable static analysis
  semgrep_path: "semgrep"  # Path to semgrep executable
  semgrep_timeout: 300  # Timeout for semgrep execution (seconds)
  sonarqube_path: null  # Path to sonar-scanner CLI (optional, can use REST API instead)
  sonarqube_url: null  # SonarQube server URL (e.g., http://localhost:9000)
  sonarqube_token: null  # SonarQube authentication token (optional)
  project_key: "codebase-analysis"  # SonarQube project key
  default_values:  # Default values for static analysis results
    default_rule_id: "unknown"
    default_severity: "medium"
    default_line: 0
```

#### Content Index Configuration (RAG/Vector Search)

```yaml
content_index:
  embedding_model: "all-MiniLM-L6-v2"  # SentenceTransformer model for embeddings
  chunk_size: 500  # Approximate characters per chunk for indexing
  collection_name: "code_index"  # ChromaDB collection name
  collection_space: "cosine"  # ChromaDB distance metric (cosine, l2, ip)
  search_top_k: 5  # Default number of results to return from semantic search
```

#### Output Configuration

```yaml
output:
  report_dir: "analysis_reports"  # Directory for generated reports
  report_filename_base: "analysis_report"  # Base filename (generates .html and .pdf)
  default_html_filename: "analysis_report.html"
```

#### UI Configuration

```yaml
ui:
  host: "127.0.0.1"  # Web server host
  port: 5001  # Web server port
  debug: false  # Enable Flask debug mode
```

See `config.yaml` for all available configuration options with detailed comments.

## Architecture

```
code-analyzer/
├── code_parser/          # AST parsing and code indexing
│   ├── parser.py        # Tree-sitter based code parser with configurable chunking
│   ├── indexer.py       # Repository indexing and file discovery
│   ├── static_analyzer.py  # Semgrep & SonarQube integration
│   └── content_index.py # Vector embeddings and semantic search (RAG)
├── llm_client/          # Local LLM integration
│   └── client.py        # OpenAI-compatible client with retry logic
├── analyzers/           # Analysis modules
│   ├── code_review.py   # Code review analyzer (chunk-based)
│   ├── documentation.py # Documentation generator (parallel processing)
│   ├── workflow.py      # Workflow and architecture analyzer
│   └── cross_file_analyzer.py  # Cross-file issue detection
├── ui/                  # Web interface and reports
│   ├── templates/       # Jinja2 HTML templates
│   │   └── report_template.html
│   ├── web_server.py    # Flask web server
│   └── report_generator.py  # HTML/PDF report generation
├── main.py              # Main orchestration script
├── config.yaml          # Comprehensive configuration file
└── requirements.txt     # Python dependencies
```

## Analysis Pipeline

The system runs these steps automatically:

1. **Code Ingestion & Indexing**:
   - Recursively discover source files
   - Parse files with Tree-sitter (or Python's built-in AST for Python on Windows)
   - Chunk code by functions/classes (AST-based) or size (fallback)
   - Build repository map and symbol index

2. **LLM Initialization**:
   - Connect to local LLM server
   - Test connection with test message
   - Configure retry logic

3. **Analysis Modules** (run in parallel where possible):
   - **Code Review**: Analyze each chunk for bugs, issues, vulnerabilities
   - **Documentation Generation**: Generate docs for chunks, then synthesize file summaries
   - **Static Analysis**: Run Semgrep and SonarQube (if enabled)
   - **Workflow Identification**: Cluster files by keywords and generate workflow descriptions
   - **Architecture Overview**: Generate high-level system architecture description

4. **Report Generation**:
   - Compile all results into structured data
   - Generate HTML report with Jinja2 templates
   - Generate PDF report using xhtml2pdf (Windows-compatible) or WeasyPrint

5. **Web UI** (optional):
   - Start Flask server to serve interactive reports
   - Enable navigation between files, issues, and documentation

## Usage Examples

### Basic Analysis

```bash
python main.py /path/to/project
```

### Without Web UI

```bash
python main.py /path/to/project --no-ui
```

### Custom Configuration

```bash
python main.py /path/to/project --config my_config.yaml
```

### Analyze Current Directory

```bash
python main.py .
```

## Troubleshooting

### LLM Connection Failed

- **Error**: `ERROR: Could not connect to LLM server`
- **Solutions**:
  - Ensure your LLM server is running (`ollama serve` or vLLM server)
  - Check `api_base` URL in `config.yaml` matches your server port
  - Verify model name matches what's available on your server (`ollama list`)
  - Test connection: `curl http://localhost:11434/v1/models`
  - For Ollama, try pulling the model: `ollama pull deepseek-coder-v2:16b`

### Parser Warnings

- **Warning**: `Could not load parser for [language]` (common on Windows)
- **Impact**: 
  - Python files: Automatically uses Python's built-in AST module (fully functional)
  - Other languages: Falls back to size-based chunking (still functional but less semantic)
- **Solutions**:
  - **Python**: No action needed - system automatically uses Python's AST module on Windows
  - **Other languages**: System will still work with size-based chunking. For AST-based parsing:
    - Ensure `tree-sitter-languages` is installed: `pip install tree-sitter-languages`
    - Check that language is in `parser.supported_languages` in config
    - Note: There's a known issue with tree-sitter-languages on Windows for non-Python languages

### Semgrep Not Found

- **Error**: Semgrep executable not found
- **Solutions**:
  - Install with: `pip install semgrep`
  - Verify: `semgrep --version`
  - Check `semgrep_path` in `config.yaml` matches your installation
  - Or disable static analysis: `static_analyzer.enabled: false`

### SonarQube Connection Issues

- **Error**: Cannot connect to SonarQube
- **Solutions**:
  - Verify SonarQube is running: `docker ps` or check service status
  - Check URL accessibility: `curl http://localhost:9000/api/system/health`
  - Verify project key exists in SonarQube
  - Check authentication token if using one
  - Or disable SonarQube: `static_analyzer.sonarqube_url: null`

### Analysis Runs Very Slowly

- **Possible Causes**:
  - Large codebase being analyzed
  - LLM server is underpowered for the model size
  - Too many files in the codebase
- **Solutions**:
  - Use a smaller/faster model (e.g., `codellama:13b` instead of `codellama:34b`)
  - Reduce `file_limits` in config to analyze fewer files
  - Use GPU-accelerated LLM server (vLLM with CUDA)
  - Run with `--no-ui` to skip web server overhead

### Configuration Errors

- **Error**: Missing configuration value
- **Solutions**:
  - All configuration values are required (no fallbacks)
  - Check YAML syntax in `config.yaml` (use a YAML validator)
  - Verify all required sections are present
  - Compare with `config.yaml.example` if provided

### PDF Generation

- **Default**: PDF generation uses xhtml2pdf (automatically installed, Windows-compatible)
- **Fallback**: If xhtml2pdf fails, system tries WeasyPrint (if installed)
- **Windows Users**: xhtml2pdf works out of the box - no GTK+ libraries needed
- **Linux/Mac**: Can use either xhtml2pdf or WeasyPrint
- **Manual Option**: Use browser's Print to PDF feature on the HTML file if both libraries fail

## Performance Tips

1. **Model Selection**: Use smaller models (7B-13B) for faster analysis on CPU, larger models (16B-34B) for better quality with GPU
2. **Context Limits**: Reduce context limits in config for faster processing on very large codebases
3. **File Limits**: Adjust `file_limits` to analyze fewer files for quicker results
4. **Parallel Processing**: Documentation generation already uses parallel processing for chunks
5. **Chunking Strategy**: Using `function_or_class` (AST-based) is slower but more accurate than `size`-based chunking

## License

MIT
