"""
LLM Client Module
DeepSeek API integration for MedPaperWriter
"""

import os
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

from services.cache import memory_cache, file_cache
from services.logger import logger

load_dotenv()


class LLMError(Exception):
    """Custom exception for LLM errors"""
    pass


class TokenUsage:
    """Token usage tracker"""

    def __init__(self):
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0

    def update(self, usage_dict: dict):
        """Update token counts from API response"""
        self.prompt_tokens += usage_dict.get("prompt_tokens", 0)
        self.completion_tokens += usage_dict.get("completion_tokens", 0)
        self.total_tokens = self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens
        }

    def estimate_cost(self) -> float:
        """Estimate cost based on DeepSeek pricing"""
        prompt_cost = self.prompt_tokens * 0.000001  # $0.001/1K tokens
        completion_cost = self.completion_tokens * 0.000001  # $0.001/1K tokens
        return prompt_cost + completion_cost


class LLMClient:
    """LLM API Client with token tracking - supports multiple models"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        if not self.api_key:
            raise ValueError("LLM API key not found. Please set LLM_API_KEY in .env file.")

        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
        self.model = model or os.getenv("LLM_MODEL", "deepseek-chat")
        self.default_temperature = temperature
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        self.token_usage = TokenUsage()

    def chat(
        self,
        messages: list,
        temperature: Optional[float] = None,
        max_tokens: int = 4000,
        stream: bool = False
    ) -> tuple[str, dict]:
        """
        Send chat completion request

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            stream: Whether to use streaming response

        Returns:
            Tuple of (response_text, usage_info)
        """
        temp = temperature if temperature is not None else self.default_temperature

        try:
            logger.debug(f"[llm_client] sending request to LLM API", model=self.model, temperature=temp, max_tokens=max_tokens, stream=stream, message_count=len(messages))

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temp,
                max_tokens=max_tokens,
                stream=stream
            )

            if stream:
                return self._handle_stream_response(response), {}
            else:
                content = response.choices[0].message.content
                usage_info = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
                self.token_usage.update(usage_info)
                logger.info(f"[llm_client] API response received", usage_info=usage_info)
                return content, usage_info

        except Exception as e:
            logger.error(f"[llm_client] API call failed", error=str(e), exc_info=True)
            raise LLMError(f"API call failed: {str(e)}")

    def _handle_stream_response(self, response):
        """处理流式响应，逐块生成内容"""
        full_content = ""
        for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    content_piece = delta.content
                    full_content += content_piece
                    yield content_piece
        
        # 流结束后更新 token 使用量
        if hasattr(response, '_response') and hasattr(response._response, 'usage'):
            usage = response._response.usage
            if usage:
                usage_info = {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens
                }
                self.token_usage.update(usage_info)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 4000,
        use_cache: bool = True
    ) -> tuple[str, dict]:
        """
        Simple text generation interface with caching

        Args:
            prompt: User prompt
            system_prompt: System prompt for context
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            use_cache: Whether to use response caching

        Returns:
            Tuple of (response_text, usage_info)
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        temp = temperature if temperature is not None else self.default_temperature

        # 尝试从缓存获取
        if use_cache and not temp >= 0.5:  # 仅缓存低温度（确定性）的响应
            cached = memory_cache.get(messages, temp, max_tokens)
            if cached:
                logger.info("Using cached response", temperature=temp)
                return cached, {"cached": True, "total_tokens": 0}

            cached = file_cache.get(messages, temp, max_tokens)
            if cached:
                logger.info("Using file cached response", temperature=temp)
                return cached, {"cached": True, "total_tokens": 0}

        # 调用 API
        content, usage = self.chat(messages, temp, max_tokens)

        # 写入缓存
        if use_cache and not temp >= 0.5:
            memory_cache.set(messages, temp, max_tokens, content)
            file_cache.set(messages, temp, max_tokens, content)

        return content, usage

    def reset_usage(self):
        """Reset token usage counter"""
        self.token_usage = TokenUsage()
