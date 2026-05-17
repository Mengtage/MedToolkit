"""
LLM Client Module
DeepSeek API integration for MedToolkit
"""

import os
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


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
    """DeepSeek API Client with token tracking"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "deepseek-chat",
        temperature: float = 0.7
    ):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DeepSeek API key not found. Please set DEEPSEEK_API_KEY in .env file.")

        self.model = model
        self.default_temperature = temperature
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )
        self.token_usage = TokenUsage()

    def chat(
        self,
        messages: list,
        temperature: Optional[float] = None,
        max_tokens: int = 4000
    ) -> tuple[str, dict]:
        """
        Send chat completion request

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response

        Returns:
            Tuple of (response_text, usage_info)
        """
        temp = temperature if temperature is not None else self.default_temperature

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temp,
                max_tokens=max_tokens
            )

            content = response.choices[0].message.content

            usage_info = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            self.token_usage.update(usage_info)

            return content, usage_info

        except Exception as e:
            raise LLMError(f"API call failed: {str(e)}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 4000
    ) -> tuple[str, dict]:
        """
        Simple text generation interface

        Args:
            prompt: User prompt
            system_prompt: System prompt for context
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            Tuple of (response_text, usage_info)
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        return self.chat(messages, temperature, max_tokens)

    def reset_usage(self):
        """Reset token usage counter"""
        self.token_usage = TokenUsage()


class LLMError(Exception):
    """Custom exception for LLM errors"""
    pass


class ExpertFactory:
    """Factory for creating expert prompts"""

    @staticmethod
    def get_qa_expert_prompt(progress: str = "", collected_info: str = "") -> str:
        """Get QA expert system prompt"""
        return f"""你是一位资深医学研究方法学专家，擅长通过追问来发现有价值的研究问题。

任务：基于用户提供的研究领域，进行漏斗式追问，逐步聚焦到具体的学术问题。

追问原则：
1. 提问要有层次，从广泛到具体
2. 每个问题要说明提问的理由
3. 每次最多提问2个问题
4. 注意挖掘研究空白和创新点
5. 语言用中文，专业且友好
6. 禁止编造不存在的文献或数据

交互规则：
- 根据用户回答调整追问方向
- 如果用户回答模糊，适当追问澄清
- 当研究问题明确时，提示用户确认并总结

当前进度：[{progress}]
已收集信息：
{collected_info}

请开始追问或总结研究问题。"""

    @staticmethod
    def get_outline_expert_prompt(research_question: str, study_type: str = "综述") -> str:
        """Get outline expert system prompt"""
        return f"""你是一位SCI论文结构专家，擅长为综述和研究论文设计提纲。

任务：基于研究问题，生成3级标题的详细论文提纲。

提纲结构规范：
1. 使用数字编号（一级1. 二级1.1 三级1.1.1）
2. 每级标题要精准、学术化
3. 综述提纲通常包含：引言、方法、结果、讨论、结论
4. 根据研究问题特点调整结构
5. 提纲应该详细，覆盖全面但不过于冗余

研究问题：{research_question}
研究类型：{study_type}

请生成详细的3级标题提纲，格式示例：
1. 引言
   1.1 研究背景
      1.1.1 疾病概述
      1.1.2 当前治疗现状
   1.2 研究意义
      1.2.1 临床需求
      1.2.2 科学价值
2. 方法
   ... (以此类推)"""

    @staticmethod
    def get_writer_expert_prompt(
        chapter_name: str,
        language: str = "中文",
        background: str = "",
        outline: str = "",
        section_title: str = ""
    ) -> str:
        """Get writer expert system prompt"""
        return f"""你是一位严谨的医学论文撰写专家，擅长撰写符合SCI标准的论文。

任务：根据提纲撰写{section_title}部分内容。

语言模式：{language}
研究背景：
{background}

本章提纲：
{outline}

写作规范：
1. 严禁捏造文献或数据
2. 如需引用但不确定，标注"[待引用-文献主题]"
3. 避免绝对化表述（如"证明"、"确保"等）
4. 使用客观、学术化的语言
5. 每段150-300字
6. 每句话尽量引用相关文献，格式为（作者，年份）

格式要求（中文）：
- 字体：宋体，小四
- 行距：1.5倍
- 首行缩进2字符

格式要求（英文）：
- 字体：Times New Roman，12号
- 行距：1.5倍

请撰写{section_title}的详细内容。"""

    @staticmethod
    def get_rct_writer_prompt(
        chapter: str,
        language: str = "中文",
        study_info: str = "",
        analysis_results: str = ""
    ) -> str:
        """Get RCT paper writer prompt"""
        return f"""你是一位严谨的医学论文撰写专家，擅长撰写符合SCI标准的RCT论文。

任务：撰写RCT论文的{chapter}部分。

语言模式：{language}

研究信息：
{study_info}

统计分析结果：
{analysis_results}

写作规范：
1. 严禁捏造文献或数据
2. 如需引用但不确定，标注"[待引用-文献主题]"
3. 避免绝对化表述
4. 使用客观、学术化的语言
5. RCT论文方法部分要详细，可重复
6. 结果部分要客观呈现数据

格式要求：
- 中文：宋体小四，1.5倍行距，首行缩进2字符
- 英文：Times New Roman 12号，1.5倍行距

请撰写{chapter}部分。"""
