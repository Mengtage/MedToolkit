"""
内容清洗模块
清理Agent输出中的Markdown标志、引导词和无关内容
"""

import re
from typing import List


class ContentCleaner:
    """内容清洗器"""
    
    # 需要移除的引导词模式
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
        """移除引导词"""
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # 检查是否包含引导词
            should_remove = False
            for pattern in self.INTRODUCTION_PATTERNS:
                if re.match(pattern, line.strip(), re.IGNORECASE):
                    should_remove = True
                    break
            
            # 如果整行都是引导词，跳过
            if should_remove and len(line.strip()) < 100:
                continue
            
            # 如果行首有引导词，移除引导词部分
            for pattern in self.INTRODUCTION_PATTERNS:
                match = re.match(pattern, line.strip(), re.IGNORECASE)
                if match:
                    line = line[match.end():]
                    break
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
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