"""
OpenAI-compatible client for local LLMs.
"""

import openai
from typing import List, Dict, Optional
import time
import requests
from openai import APIError, APIConnectionError, APITimeoutError


class LocalLLMClient:
    """Client for interacting with local LLM via OpenAI-compatible API."""
    
    def __init__(self, api_base: str, api_key: str, model: str,
                 temperature: float, max_tokens: int,
                 timeout: int, max_retries: int, retry_backoff_base: int, test_message: str):
        """
        Initialize local LLM client.
        
        Args:
            api_base: Base URL for LLM API (e.g., http://localhost:11434/v1 for Ollama)
            api_key: API key (can be dummy for local LLMs)
            model: Model name as recognized by the server
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts on failure
            retry_backoff_base: Base for exponential backoff (wait_time = retry_backoff_base ** attempt)
            test_message: Message used for connection test
        """
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self.test_message = test_message
        
        # Configure OpenAI client
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=api_base,
            timeout=timeout
        )
    
    def query(self, prompt: str, system_message: Optional[str]) -> str:
        """
        Query the LLM with a prompt.
        
        Args:
            prompt: User prompt
            system_message: System message (None for no system message)
        
        Returns:
            LLM response text
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                
                return response.choices[0].message.content.strip()
            
            except APIConnectionError as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_backoff_base ** attempt
                    print(f"LLM connection error, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise ConnectionError(f"LLM connection failed after {self.max_retries} attempts. Check api_base ({self.api_base}) and ensure the server is running.") from e
            except APITimeoutError as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_backoff_base ** attempt
                    print(f"LLM request timeout, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise TimeoutError(f"LLM request timed out after {self.max_retries} attempts (timeout={self.timeout}s).") from e
            except APIError as e:
                # API errors (e.g., invalid model, rate limit) - don't retry
                raise ValueError(f"LLM API error: {e}. Check model name ({self.model}) and API configuration.") from e
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_backoff_base ** attempt
                    print(f"LLM request failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(f"LLM request failed after {self.max_retries} attempts: {e}") from e
    
    def query_stream(self, prompt: str, system_message: Optional[str]):
        """
        Query the LLM with streaming response.
        
        Args:
            prompt: User prompt
            system_message: System message (None for no system message)
        
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
        
        except APIConnectionError as e:
            raise ConnectionError(f"LLM streaming connection failed. Check api_base ({self.api_base}) and ensure the server is running.") from e
        except APITimeoutError as e:
            raise TimeoutError(f"LLM streaming request timed out (timeout={self.timeout}s).") from e
        except APIError as e:
            raise ValueError(f"LLM streaming API error: {e}. Check model name ({self.model}) and API configuration.") from e
        except Exception as e:
            raise RuntimeError(f"LLM streaming request failed: {e}") from e
    
    def test_connection(self) -> bool:
        """Test if LLM server is accessible."""
        try:
            response = self.query(self.test_message, None)
            return len(response) > 0
        except Exception as e:
            print(f"LLM connection test failed: {e}")
            return False

