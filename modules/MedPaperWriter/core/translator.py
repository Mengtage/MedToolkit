"""
学术翻译服务
使用LLM进行高质量的中英文互译
"""

from core.llm_client import LLMClient
from typing import Optional, Callable
import re


class AcademicTranslator:
    """学术翻译器"""
    
    def __init__(self):
        self.llm = LLMClient()
    
    def translate_to_english(self, text: str, context: str = "") -> str:
        """
        将中文翻译成学术英语
        
        Args:
            text: 要翻译的中文文本
            context: 研究背景/主题（可选）
            
        Returns:
            英文翻译结果
        """
        if not text or not text.strip():
            return ""
        
        system_prompt = "You are a professional medical/academic translator. Translate the given Chinese text into fluent, natural academic English.\n\nRequirements:\n- Maintain scientific accuracy and terminology\n- Use appropriate academic vocabulary\n- Preserve original meaning and structure\n- Do not add extra content\n- Keep statistical values, numbers, and formulas unchanged\n- Ensure proper grammar and sentence structure\n- For medical terms, use standard English medical terminology"

        user_prompt = f"Please translate this into academic English:\n{text}\n\n{'-' * 50}\nContext/Research Topic (for reference):\n{context if context else 'Not provided'}"

        try:
            result, _ = self.llm.generate(
                system_prompt=system_prompt,
                prompt=user_prompt,
                max_tokens=4096,
                temperature=0.3
            )
            return result.strip()
        except Exception as e:
            print(f"[Translator] English translation failed: {e}")
            return text
    
    def translate_to_chinese(self, text: str, context: str = "") -> str:
        """
        将英文翻译成学术中文
        
        Args:
            text: 要翻译的英文文本
            context: 研究背景/主题（可选）
            
        Returns:
            中文翻译结果
        """
        if not text or not text.strip():
            return ""
        
        system_prompt = "You are a professional medical/academic translator. Translate the given English text into fluent, natural academic Chinese.\n\nRequirements:\n- Maintain scientific accuracy and terminology\n- Use appropriate academic vocabulary\n- Preserve original meaning and structure\n- Do not add extra content\n- Keep statistical values, numbers, and formulas unchanged\n- Ensure proper grammar and sentence structure\n- For medical terms, use standard Chinese medical terminology"

        user_prompt = f"Please translate this into academic Chinese:\n{text}\n\n{'-' * 50}\nContext/Research Topic (for reference):\n{context if context else 'Not provided'}"

        try:
            result, _ = self.llm.generate(
                system_prompt=system_prompt,
                prompt=user_prompt,
                max_tokens=4096,
                temperature=0.3
            )
            return result.strip()
        except Exception as e:
            print(f"[Translator] Chinese translation failed: {e}")
            return text
    
    def translate_outline_title(self, title: str, context: str = "") -> str:
        """
        翻译提纲标题（更简洁）
        
        Args:
            title: 中文标题
            context: 研究背景
            
        Returns:
            英文标题
        """
        if not title or not title.strip():
            return ""
        
        system_prompt = "You are a professional academic translator. Translate the given Chinese section title into concise, standard academic English.\n\nRequirements:\n- Use standard academic section heading conventions\n- Keep concise (1-10 words usually)\n- Maintain meaning\n- Common structure examples:\n  - \"引言\" -> \"Introduction\"\n  - \"方法\" -> \"Methods\"\n  - \"结果\" -> \"Results\"\n  - \"讨论\" -> \"Discussion\"\n  - \"结论\" -> \"Conclusion\"\n  - \"资料与方法\" -> \"Materials and Methods\"\n  - \"研究对象\" -> \"Study Participants\"\n  - \"统计分析\" -> \"Statistical Analysis\"\n  - \"纳入标准\" -> \"Inclusion Criteria\"\n  - \"排除标准\" -> \"Exclusion Criteria\"\n  - \"研究设计\" -> \"Study Design\""

        user_prompt = f"Translate this section title into English: {title}"
        
        try:
            result, _ = self.llm.generate(
                system_prompt=system_prompt,
                prompt=user_prompt,
                max_tokens=256,
                temperature=0.2
            )
            return result.strip()
        except Exception as e:
            print(f"[Translator] Title translation failed: {e}")
            return title


# 全局翻译器实例
translator = AcademicTranslator()