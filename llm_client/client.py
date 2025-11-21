"""
OpenAI-compatible client for local LLMs.
"""

import openai
from typing import List, Dict, Optional
import time


class LocalLLMClient:
    """Client for interacting with local LLM via OpenAI-compatible API."""
    
    def __init__(self, api_base: str, api_key: str, model: str,
                 temperature: float = 0.1, max_tokens: int = 4000,
                 timeout: int = 300):
        """
        Initialize local LLM client.
        
        Args:
            api_base: Base URL for LLM API (e.g., http://localhost:11434/v1 for Ollama)
            api_key: API key (can be dummy for local LLMs)
            model: Model name as recognized by the server
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
        """
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        
        # Configure OpenAI client
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=api_base,
            timeout=timeout
        )
    
    def query(self, prompt: str, system_message: str = None,
              max_retries: int = 3) -> str:
        """
        Query the LLM with a prompt.
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            max_retries: Maximum retry attempts on failure
        
        Returns:
            LLM response text
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                
                return response.choices[0].message.content.strip()
            
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"LLM request failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"LLM request failed after {max_retries} attempts: {e}")
    
    def query_stream(self, prompt: str, system_message: str = None):
        """
        Query the LLM with streaming response.
        
        Yields:
            Response chunks
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        
        except Exception as e:
            raise Exception(f"LLM streaming request failed: {e}")
    
    def test_connection(self) -> bool:
        """Test if LLM server is accessible."""
        try:
            response = self.query("Say 'OK' if you can read this.")
            return len(response) > 0
        except Exception as e:
            print(f"LLM connection test failed: {e}")
            return False

