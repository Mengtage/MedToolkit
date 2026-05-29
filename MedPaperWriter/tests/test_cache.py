"""
缓存模块测试
"""

import pytest
import time
from services.cache import MemoryCache, FileCache


class TestMemoryCache:
    """内存缓存测试"""

    def setup_method(self):
        self.cache = MemoryCache(max_size=10, ttl=2)

    def test_set_and_get(self):
        """测试设置和获取缓存"""
        messages = [{"role": "user", "content": "Hello"}]
        self.cache.set(messages, 0.3, 100, "cached response")
        result = self.cache.get(messages, 0.3, 100)
        assert result == "cached response"

    def test_cache_miss(self):
        """测试缓存未命中"""
        messages = [{"role": "user", "content": "Hello"}]
        result = self.cache.get(messages, 0.3, 100)
        assert result is None

    def test_cache_expiry(self):
        """测试缓存过期"""
        messages = [{"role": "user", "content": "Hello"}]
        self.cache.set(messages, 0.3, 100, "cached response")
        time.sleep(3)  # 等待缓存过期
        result = self.cache.get(messages, 0.3, 100)
        assert result is None

    def test_lru_eviction(self):
        """测试LRU淘汰"""
        for i in range(15):
            messages = [{"role": "user", "content": f"Message {i}"}]
            self.cache.set(messages, 0.3, 100, f"response {i}")

        stats = self.cache.stats()
        assert stats["size"] <= 10  # 不超过最大容量

    def test_different_temperature(self):
        """测试不同温度生成不同缓存键"""
        messages = [{"role": "user", "content": "Hello"}]
        self.cache.set(messages, 0.3, 100, "low temp response")
        result = self.cache.get(messages, 0.7, 100)
        assert result is None  # 不同温度，缓存未命中

    def test_clear(self):
        """测试清空缓存"""
        messages = [{"role": "user", "content": "Hello"}]
        self.cache.set(messages, 0.3, 100, "response")
        self.cache.clear()
        stats = self.cache.stats()
        assert stats["size"] == 0


class TestFileCache:
    """文件缓存测试"""

    def setup_method(self):
        # 每个测试使用独立的缓存实例，避免相互影响
        import tempfile
        from pathlib import Path
        self._tmpdir = Path(tempfile.mkdtemp())
        self.cache = FileCache(cache_dir=self._tmpdir, ttl=2)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_set_and_get(self):
        """测试设置和获取缓存"""
        messages = [{"role": "user", "content": "Hello"}]
        self.cache.set(messages, 0.3, 100, "cached response")
        result = self.cache.get(messages, 0.3, 100)
        assert result == "cached response"

    def test_cache_miss(self):
        """测试缓存未命中"""
        messages = [{"role": "user", "content": "Hello"}]
        result = self.cache.get(messages, 0.3, 100)
        assert result is None

    def test_cache_expiry(self):
        """测试缓存过期"""
        messages = [{"role": "user", "content": "Hello"}]
        self.cache.set(messages, 0.3, 100, "cached response")
        time.sleep(3)  # 等待缓存过期
        result = self.cache.get(messages, 0.3, 100)
        assert result is None

    def test_clear(self):
        """测试清空缓存"""
        messages = [{"role": "user", "content": "Hello"}]
        self.cache.set(messages, 0.3, 100, "response")
        self.cache.clear()
        stats = self.cache.stats()
        assert stats["size"] == 0
