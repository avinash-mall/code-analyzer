"""
Setup script for code-analyzer package.
"""

from setuptools import setup, find_packages

setup(
    name="code-analyzer",
    version="1.0.0",
    description="AI-Powered Codebase Analysis System",
    author="",
    packages=find_packages(),
    install_requires=[
        "flask>=3.0.0",
        "openai>=1.0.0",
        "tree-sitter>=0.20.0",
        "tree-sitter-languages>=1.0.0",
        "networkx>=3.0",
        "jinja2>=3.1.0",
        "pygments>=2.15.0",
        "markdown>=3.4.0",
        "weasyprint>=59.0",
        "sentence-transformers>=2.2.0",
        "chromadb>=0.4.0",
        "tqdm>=4.65.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "code-analyzer=main:main",
        ],
    },
)

