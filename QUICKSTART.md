# Quick Start Guide

## Prerequisites

1. Python 3.8 or higher
2. A local LLM server (Ollama or vLLM)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up a local LLM:

### Option A: Using Ollama (Recommended for beginners)

```bash
# Install Ollama from https://ollama.com
# Then pull a code model:
ollama pull codellama:7b
# Or for better quality (requires more RAM):
ollama pull codellama:34b

# Start Ollama server (usually runs automatically)
ollama serve
```

### Option B: Using vLLM (For better performance)

```bash
pip install vllm
python -m vllm.entrypoints.openai.api_server \
    --model codellama/CodeLlama-7b-Instruct-hf \
    --port 8000
```

3. Configure the system:

```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your LLM settings
```

For Ollama, the default config should work:
```yaml
llm:
  api_base: "http://localhost:11434/v1"
  model: "codellama:7b"  # or codellama:34b
```

For vLLM:
```yaml
llm:
  api_base: "http://localhost:8000/v1"
  model: "codellama/CodeLlama-7b-Instruct-hf"
```

## Usage

### Basic Analysis

```bash
python main.py --codebase /path/to/your/codebase
```

This will:
1. Parse and index your codebase
2. Run all analysis modules
3. Generate an HTML report
4. Start a web server to view results

### Without Web UI

```bash
python main.py --codebase /path/to/your/codebase --no-ui
```

The HTML report will be generated in `reports/analysis_report.html`

### Custom Config

```bash
python main.py --codebase /path/to/codebase --config my_config.yaml
```

## Viewing Results

1. **Web UI**: The server starts automatically at `http://127.0.0.1:5000`
2. **HTML File**: Open `reports/analysis_report.html` in your browser
3. **PDF**: If WeasyPrint is installed, a PDF is also generated

## Troubleshooting

### LLM Connection Failed

- Ensure your LLM server is running
- Check the `api_base` URL in config.yaml
- For Ollama, verify with: `curl http://localhost:11434/api/tags`
- For vLLM, check the server logs

### Out of Memory

- Use a smaller model (e.g., `codellama:7b` instead of `34b`)
- Reduce `max_tokens` in config.yaml
- Process fewer files (the code limits files per module for demo)

### Tree-sitter Parsing Issues

- Install tree-sitter-languages: `pip install tree-sitter-languages`
- The system will fall back to regex-based parsing if Tree-sitter fails

## Example Output

The report includes:
- **Summary**: Overview of issues found
- **Code Review**: Bugs and code quality issues
- **Documentation**: Generated docs for each file
- **Business Logic**: Extracted business rules and processes
- **Workflows**: Defined process flows
- **Process Issues**: Issues in workflows

## Next Steps

- Customize analysis modules in `config.yaml`
- Adjust file limits in `main.py` for larger codebases
- Add custom static analysis tools
- Fine-tune prompts in analyzer modules

