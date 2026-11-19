"""
缓存模块
提供 LLM 响应缓存，减少重复 API 调用
"""

import hashlib
import json
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from collections import OrderedDict

from config.settings import settings
from services.logger import logger


class MemoryCache:
    """内存缓存 - LRU 淘汰策略"""

    def __init__(self, max_size: int = 100, ttl: int = 3600):
        """
        Args:
            max_size: 最大缓存条目数
            ttl: 缓存生存时间（秒），默认1小时
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def _make_key(self, messages: list, temperature: float, max_tokens: int) -> str:
        """生成缓存键"""
        content = json.dumps({
            "messages": messages,
            "temperature": round(temperature, 2),
            "max_tokens": max_tokens
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, messages: list, temperature: float, max_tokens: int) -> Optional[str]:
        """获取缓存内容"""
        key = self._make_key(messages, temperature, max_tokens)

        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            if time.time() - entry["time"] > self.ttl:
                # 缓存过期
                del self._cache[key]
                return None

            # LRU: 移动到末尾（最近使用）
            self._cache.move_to_end(key)
            logger.debug("Cache hit", key=key[:16])
            return entry["content"]

    def set(self, messages: list, temperature: float, max_tokens: int, content: str):
        """设置缓存"""
        key = self._make_key(messages, temperature, max_tokens)

        with self._lock:
            # 淘汰最旧的条目
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            self._cache[key] = {
                "content": content,
                "time": time.time()
            }
            logger.debug("Cache set", key=key[:16])

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
        logger.info("Cache cleared")

    def stats(self) -> dict:
        """获取缓存统计"""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl": self.ttl
            }


class FileCache:
    """文件缓存 - 持久化缓存"""

    def __init__(self, cache_dir: Optional[Path] = None, ttl: int = 86400):
        """
        Args:
            cache_dir: 缓存目录
            ttl: 缓存生存时间（秒），默认24小时
        """
        self.cache_dir = cache_dir or (settings.BASE_DIR / "data" / "cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self._lock = threading.Lock()

    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        # 使用子目录避免单目录文件过多
        subdir = key[:2]
        cache_subdir = self.cache_dir / subdir
        cache_subdir.mkdir(exist_ok=True)
        return cache_subdir / f"{key}.json"

    def _make_key(self, messages: list, temperature: float, max_tokens: int) -> str:
        """生成缓存键"""
        content = json.dumps({
            "messages": messages,
            "temperature": round(temperature, 2),
            "max_tokens": max_tokens
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, messages: list, temperature: float, max_tokens: int) -> Optional[str]:
        """获取缓存内容"""
        key = self._make_key(messages, temperature, max_tokens)
        cache_path = self._get_cache_path(key)

        with self._lock:
            if not cache_path.exists():
                return None

            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    entry = json.load(f)

                if time.time() - entry["time"] > self.ttl:
                    cache_path.unlink(missing_ok=True)
                    return None

                logger.debug("File cache hit", key=key[:16])
                return entry["content"]

            except Exception as e:
                logger.warning(f"Cache read failed: {e}", key=key[:16])
                return None

    def set(self, messages: list, temperature: float, max_tokens: int, content: str):
        """设置缓存"""
        key = self._make_key(messages, temperature, max_tokens)
        cache_path = self._get_cache_path(key)

        with self._lock:
            try:
                entry = {
                    "content": content,
                    "time": time.time(),
                    "key": key
                }
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(entry, f, ensure_ascii=False)
                logger.debug("File cache set", key=key[:16])

            except Exception as e:
                logger.warning(f"Cache write failed: {e}", key=key[:16])

    def clear(self):
        """清空所有缓存"""
        with self._lock:
            count = 0
            for subdir in self.cache_dir.iterdir():
                if subdir.is_dir():
                    for f in subdir.iterdir():
                        f.unlink()
                        count += 1
                    subdir.rmdir()
            logger.info(f"File cache cleared", removed_files=count)

    def stats(self) -> dict:
        """获取缓存统计"""
        count = 0
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir():
                count += len(list(subdir.iterdir()))
        return {
            "size": count,
            "ttl": self.ttl,
            "cache_dir": str(self.cache_dir)
        }


# 全局缓存实例
memory_cache = MemoryCache(max_size=100, ttl=3600)
file_cache = FileCache(ttl=86400)
