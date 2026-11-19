"""
内容清洗模块
清理Agent输出中的Markdown标志、引导词和无关内容
"""

import re
from typing import List


class ContentCleaner:
    """内容清洗器"""
    
    # 需要移除的引导词模式（保留常量以兼容旧调用，但不再做行内前缀裁剪）
    INTRODUCTION_PATTERNS = [
        r"^以下是.*?[：:]\s*",
        r"^这是.*?[：:]\s*",
        r"^本章节.*?[：:]\s*",
        r"^根据.*?[，,]\s*",
        r"^基于.*?[，,]\s*",
        r"^我将.*?[：:]\s*",
        r"^我为您.*?[：:]\s*",
        r"^为您撰写.*?[：:]\s*",
        r"^撰写.*?[：:]\s*",
        r"^生成.*?[：:]\s*",
        r"^以下是.*?内容[：:]\s*",
        r"^这是.*?内容[：:]\s*",
        r"^抱歉[，,].*?[。.]\s*",
        r"^很抱歉[，,].*?[。.]\s*",
        r"^无法.*?[。.]\s*",
        r"^原因如下[：:]\s*",
        r"^为确保.*?[，,]\s*",
        r"^请提供.*?[。.]\s*",
        r"^收到.*?后.*?[。.]\s*",
    ]

    # 只删除"整行都是引导语"的行，绝不做行内前缀裁剪。
    # 旧实现在任意行上执行 ^这是.*?[：:] 这类正则，遇到
    # "这是……（正文很长）……结论：……" 会把整段正文删掉——审查报告 3.5 节
    # 指出的正是这种脆弱后处理。
    LEAD_IN_RE = re.compile(
        r"^(以下是|这是|本章节|本节|我将|我为您|为您撰写|撰写|生成|原因如下)[^：:\n]{0,30}[：:]\s*$"
    )
    REFUSAL_RE = re.compile(r"^(抱歉|很抱歉|无法|请提供|收到|为确保)[^。\n]{0,40}[。]\s*$")
    
    # Markdown标志模式
    MARKDOWN_PATTERNS = [
        r"^#+\s+",  # 标题标志 # ## ### 等
        r"\*\*([^*]+)\*\*",  # 加粗 **text**
        r"\*([^*]+)\*",  # 斜体 *text*
        r"__([^_]+)__",  # 加粗 __text__
        r"_([^_]+)_",  # 斜体 _text_
        r"`([^`]+)`",  # 行内代码 `code`
        r"```[\s\S]*?```",  # 代码块 ```code```
        r"~~([^~]+)~~",  # 删除线 ~~text~~
        r"\[([^\]]+)\]\([^\)]+\)",  # 链接 [text](url)
        r"!\[([^\]]+)\]\([^\)]+\)",  # 图片 ![alt](url)
        r"^\s*[-*+]\s+",  # 无序列表 - * +
        r"^\s*\d+\.\s+",  # 有序列表 1. 2.
        r"^\s*>\s+",  # 引用 >
        r"^---+\s*$",  # 分隔线 ---
        r"^\*\*\*+\s*$",  # 分隔线 ***
    ]
    
    def clean_content(self, content: str) -> str:
        """
        清洗内容
        
        Args:
            content: 原始内容
            
        Returns:
            清洗后的内容
        """
        if not content or not content.strip():
            return ""
        
        # 1. 移除引导词
        cleaned = self._remove_introduction(content)
        
        # 2. 移除Markdown标志
        cleaned = self._remove_markdown(cleaned)
        
        # 3. 清理多余空行
        cleaned = self._clean_empty_lines(cleaned)
        
        # 4. 清理特殊字符
        cleaned = self._clean_special_chars(cleaned)
        
        return cleaned.strip()
    
    def _remove_introduction(self, content: str) -> str:
        """移除整行引导语（不做行内前缀裁剪，避免误删正文段落）"""
        kept_lines = []

        for line in content.split('\n'):
            stripped = line.strip()
            if stripped and len(stripped) <= 80 and (
                self.LEAD_IN_RE.match(stripped) or self.REFUSAL_RE.match(stripped)
            ):
                continue
            kept_lines.append(line)

        return '\n'.join(kept_lines).strip('\n')
    
    def _remove_markdown(self, content: str) -> str:
        """移除Markdown标志"""
        # 移除标题标志
        content = re.sub(r"^#+\s+", "", content, flags=re.MULTILINE)
        
        # 移除加粗标志，保留内容
        content = re.sub(r"\*\*([^*]+)\*\*", r"\1", content)
        content = re.sub(r"__([^_]+)__", r"\1", content)
        
        # 移除斜体标志，保留内容
        content = re.sub(r"\*([^*]+)\*", r"\1", content)
        content = re.sub(r"_([^_]+)_", r"\1", content)
        
        # 移除行内代码标志，保留内容
        content = re.sub(r"`([^`]+)`", r"\1", content)
        
        # 移除代码块
        content = re.sub(r"```[\s\S]*?```", "", content)
        
        # 移除删除线标志，保留内容
        content = re.sub(r"~~([^~]+)~~", r"\1", content)
        
        # 移除链接，保留文本
        content = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", content)
        
        # 移除图片标记
        content = re.sub(r"!\[([^\]]+)\]\([^\)]+\)", "", content)
        
        # 移除列表标志
        content = re.sub(r"^\s*[-*+]\s+", "", content, flags=re.MULTILINE)
        content = re.sub(r"^\s*\d+\.\s+", "", content, flags=re.MULTILINE)
        
        # 移除引用标志
        content = re.sub(r"^\s*>\s+", "", content, flags=re.MULTILINE)
        
        # 移除分隔线
        content = re.sub(r"^---+\s*$", "", content, flags=re.MULTILINE)
        content = re.sub(r"^\*\*\*+\s*$", "", content, flags=re.MULTILINE)
        
        return content
    
    def _clean_empty_lines(self, content: str) -> str:
        """清理多余空行"""
        # 移除连续的空行（保留最多一个）
        content = re.sub(r"\n\s*\n\s*\n+", "\n\n", content)
        
        # 移除行首行尾的空行
        content = content.strip()
        
        return content
    
    def _clean_special_chars(self, content: str) -> str:
        """清理特殊字符"""
        # 移除多余的空格（保留必要的空格）
        content = re.sub(r"  +", " ", content)
        
        # 移除行尾空格
        content = re.sub(r" +\n", "\n", content)
        
        return content
    
    def is_valid_content(self, content: str) -> bool:
        """
        检查内容是否有效
        
        Args:
            content: 内容
            
        Returns:
            是否有效
        """
        if not content or not content.strip():
            return False
        
        # 检查是否包含错误提示
        error_patterns = [
            r"抱歉.*?无法",
            r"无法.*?生成",
            r"无法.*?撰写",
            r"原因如下",
            r"请提供.*?缺失",
            r"统计分析结果.*?为空",
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return False
        
        # 检查内容长度（至少50字）
        if len(content.strip()) < 50:
            return False
        
        return True


# 全局清洗器实例
cleaner = ContentCleaner()