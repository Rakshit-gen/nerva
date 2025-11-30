"""
LLM service using Ollama (local Llama-3) or HuggingFace Inference API.
"""
import json
from typing import Optional, List, Dict, Any
import httpx

from app.core.config import settings

# Try to import huggingface_hub for the new API
try:
    from huggingface_hub import InferenceClient
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False


class LLMService:
    """
    LLM service supporting Ollama (local) and HuggingFace Inference API.
    Uses Llama-3 as the primary model.
    """
    
    def __init__(self, use_ollama: bool = True):
        """
        Initialize LLM service.
        
        Args:
            use_ollama: Use local Ollama instance (recommended for free usage)
        """
        self.use_ollama = use_ollama
        
        # Ollama config
        self.ollama_url = settings.OLLAMA_BASE_URL
        self.ollama_model = settings.OLLAMA_MODEL
        
        # HuggingFace config
        self.hf_token = settings.HF_API_TOKEN
        self.hf_model = settings.HF_LLM_MODEL
        
        # Initialize HuggingFace client with timeout
        self._hf_client = None
        if HF_HUB_AVAILABLE and self.hf_token:
            # Set timeout to prevent hanging (120 seconds)
            self._hf_client = InferenceClient(
                token=self.hf_token,
                timeout=120.0,  # 2 minute timeout
            )
        
        self._http_client = None
    
    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._http_client is None:
            # Increased timeout to 180s for large script generation
            # But we'll also reduce max_tokens to speed things up
            self._http_client = httpx.Client(timeout=180.0)
        return self._http_client
    
    def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        stop_sequences: List[str] = None,
    ) -> str:
        """
        Generate text completion.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stop_sequences: Stop generation on these strings
            
        Returns:
            Generated text
        """
        if self.use_ollama:
            return self._generate_ollama(
                prompt, system_prompt, max_tokens, temperature, stop_sequences
            )
        else:
            return self._generate_hf(
                prompt, system_prompt, max_tokens, temperature, stop_sequences
            )
    
    def _generate_ollama(
        self,
        prompt: str,
        system_prompt: str = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        stop_sequences: List[str] = None,
    ) -> str:
        """Generate using local Ollama instance."""
        client = self._get_client()
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        
        if stop_sequences:
            payload["options"]["stop"] = stop_sequences
        
        try:
            response = client.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("message", {}).get("content", "")
            
        except httpx.HTTPError as e:
            print(f"Ollama error: {e}")
            # Fallback to HuggingFace
            return self._generate_hf(prompt, system_prompt, max_tokens, temperature, stop_sequences)
    
    def _generate_hf(
        self,
        prompt: str,
        system_prompt: str = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        stop_sequences: List[str] = None,
    ) -> str:
        """Generate using HuggingFace Inference API."""
        import time
        
        # Use the new huggingface_hub InferenceClient if available
        if self._hf_client:
            # Build messages for chat completion
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Retry logic for rate limits and timeouts
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    print(f"🔄 [LLM] Calling HuggingFace API (attempt {attempt + 1}/{max_retries})...")
                    start_time = time.time()
                    
                    # Use chat completion API with timeout
                    try:
                        # Set a timeout using threading to prevent hanging
                        import threading
                        import queue
                        
                        response_queue = queue.Queue()
                        error_queue = queue.Queue()
                        
                        def make_request():
                            try:
                                result = self._hf_client.chat_completion(
                                    messages=messages,
                                    model=self.hf_model,
                                    max_tokens=max_tokens,
                                    temperature=temperature,
                                )
                                response_queue.put(result)
                            except Exception as e:
                                error_queue.put(e)
                        
                        # Run in thread with timeout
                        thread = threading.Thread(target=make_request, daemon=True)
                        thread.start()
                        thread.join(timeout=120.0)  # 2 minute hard timeout
                        
                        if thread.is_alive():
                            # Thread is still running, request timed out
                            print(f"⏱️  [LLM] Request timed out after 120 seconds")
                            raise TimeoutError("HuggingFace API request timed out after 120 seconds")
                        
                        # Check for errors
                        if not error_queue.empty():
                            error = error_queue.get()
                            raise error
                        
                        # Get response
                        if response_queue.empty():
                            raise RuntimeError("HuggingFace API returned no response")
                        
                        response = response_queue.get()
                            
                    except TimeoutError as timeout_error:
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 10
                            print(f"⏱️  [LLM] API timeout, waiting {wait_time}s before retry...")
                            time.sleep(wait_time)
                            continue
                        else:
                            raise RuntimeError(f"HuggingFace API timeout after {max_retries} attempts: {timeout_error}")
                    except Exception as api_error:
                        # Check for timeout or connection errors
                        error_str = str(api_error).lower()
                        if any(keyword in error_str for keyword in ["timeout", "timed out", "connection", "network"]):
                            if attempt < max_retries - 1:
                                wait_time = (attempt + 1) * 10
                                print(f"⏱️  [LLM] API timeout/connection error, waiting {wait_time}s before retry...")
                                time.sleep(wait_time)
                                continue
                            else:
                                raise RuntimeError(f"HuggingFace API timeout after {max_retries} attempts: {api_error}")
                        raise
                    
                    elapsed = time.time() - start_time
                    print(f"✅ [LLM] API call completed in {elapsed:.1f}s")
                    
                    # Extract the response text
                    if hasattr(response, 'choices') and response.choices:
                        content = response.choices[0].message.content
                        if not content or len(content.strip()) == 0:
                            raise RuntimeError("HuggingFace API returned empty response")
                        return content
                    elif hasattr(response, 'generated_text'):
                        return response.generated_text
                    else:
                        # Try to extract from string representation
                        response_str = str(response)
                        if response_str and len(response_str.strip()) > 0:
                            return response_str
                        raise RuntimeError(f"HuggingFace API returned invalid response format: {type(response)}")
                    
                except RuntimeError:
                    # Re-raise RuntimeErrors (our custom errors)
                    raise
                except Exception as e:
                    error_str = str(e).lower()
                    # Check for rate limits
                    if "429" in str(e) or "rate limit" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 10
                            print(f"⏸️  [LLM] Rate limited, waiting {wait_time}s before retry...")
                            time.sleep(wait_time)
                            continue
                        else:
                            raise RuntimeError(f"HuggingFace API rate limit exceeded after {max_retries} attempts")
                    # Check for authentication errors
                    elif "401" in str(e) or "unauthorized" in error_str or "token" in error_str:
                        raise RuntimeError(f"HuggingFace API authentication failed. Please check your HF_API_TOKEN: {e}")
                    # Check for model errors
                    elif "model" in error_str or "not found" in error_str:
                        raise RuntimeError(f"HuggingFace model error: {e}")
                    # Other errors
                    else:
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 5
                            print(f"⚠️  [LLM] API error (attempt {attempt + 1}), waiting {wait_time}s before retry: {e}")
                            time.sleep(wait_time)
                            continue
                        else:
                            raise RuntimeError(f"HuggingFace API error after {max_retries} attempts: {e}")
        
        # Fallback to direct HTTP if huggingface_hub not available
        client = self._get_client()
        
        # Format prompt for instruction format
        if system_prompt:
            full_prompt = f"<s>[INST] {system_prompt}\n\n{prompt} [/INST]"
        else:
            full_prompt = f"<s>[INST] {prompt} [/INST]"
        
        headers = {}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
        
        # Try the new router API first
        hf_url = f"https://router.huggingface.co/hf-inference/models/{self.hf_model}/v1/chat/completions"
        
        payload = {
            "model": self.hf_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
                "temperature": temperature,
        }
        
        if system_prompt:
            payload["messages"].insert(0, {"role": "system", "content": system_prompt})
        
        try:
            response = client.post(hf_url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            if "choices" in result and result["choices"]:
                return result["choices"][0]["message"]["content"]
            return str(result)
            
        except httpx.HTTPError as e:
            raise RuntimeError(f"HuggingFace API error: {e}")
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """
        Multi-turn chat completion.
        
        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            
        Returns:
            Assistant response
        """
        if self.use_ollama:
            return self._chat_ollama(messages, max_tokens, temperature)
        else:
            # Convert to single prompt for HF
            prompt_parts = []
            system_prompt = None
            
            for msg in messages:
                if msg["role"] == "system":
                    system_prompt = msg["content"]
                elif msg["role"] == "user":
                    prompt_parts.append(f"User: {msg['content']}")
                elif msg["role"] == "assistant":
                    prompt_parts.append(f"Assistant: {msg['content']}")
            
            prompt = "\n".join(prompt_parts)
            return self._generate_hf(prompt, system_prompt, max_tokens, temperature)
    
    def _chat_ollama(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Chat using Ollama."""
        client = self._get_client()
        
        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        
        try:
            response = client.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("message", {}).get("content", "")
            
        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama chat error: {e}")
    
    def close(self):
        """Clean up resources."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None
