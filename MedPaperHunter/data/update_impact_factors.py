#!/usr/bin/env python3
"""
Impact Factor Update Script
自动从网络更新期刊影响因子数据

使用方法:
    python update_impact_factors.py
    
每年6-7月 Clarivate 会发布新的 JCR 影响因子，
此时运行此脚本可以自动下载最新数据。

注意事项:
    1. 需要网络连接
    2. 可能需要处理网络超时或反爬虫机制
    3. 建议定期（如每年7月）运行一次
"""

import csv
import logging
import sys
from pathlib import Path
from typing import Optional

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("请先安装所需库: pip install requests beautifulsoup4")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# JCR数据源URL (示例)
JCR_URLS = [
    "https://impactfactorforjournal.com/jcr-2025-latest-impact-factor-list/",
    "https://www.l4zzz.com/science-citation-index/jcr-2025-if-list.html",
]

# 输出文件
OUTPUT_FILE = Path(__file__).parent / "impact_factors.csv"


def fetch_webpage(url: str) -> Optional[str]:
    """获取网页内容"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"获取网页失败 {url}: {e}")
        return None


def parse_jcr_data(html: str) -> list[tuple[str, str]]:
    """解析JCR数据"""
    journals = []
    soup = BeautifulSoup(html, 'html.parser')
    
    # 尝试查找表格
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                # 尝试提取期刊名和影响因子
                journal_name = ""
                impact_factor = ""
                
                for i, cell in enumerate(cells):
                    text = cell.get_text(strip=True)
                    # 跳过排名列
                    if text.isdigit() and i == 0:
                        continue
                    
                    # 检查是否是影响因子（数字）
                    try:
                        float(text.replace(',', ''))
                        impact_factor = text
                    except ValueError:
                        if text and not text.startswith('Rank'):
                            # 可能是期刊名
                            if not journal_name:
                                journal_name = text
                    
                    # 如果同时有期刊名和影响因子，添加到列表
                    if journal_name and impact_factor:
                        journals.append((journal_name, impact_factor))
                        journal_name = ""
                        impact_factor = ""
    
    return journals


def load_existing_data() -> set[str]:
    """加载已存在的数据"""
    existing_journals = set()
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                journal = row.get('journal', '').strip().lower()
                if journal:
                    existing_journals.add(journal)
    return existing_journals


def update_impact_factors():
    """更新影响因子数据"""
    logger.info("开始更新影响因子数据...")
    
    all_journals = []
    existing_journals = load_existing_data()
    
    for url in JCR_URLS:
        logger.info(f"正在从 {url} 获取数据...")
        html = fetch_webpage(url)
        
        if html:
            journals = parse_jcr_data(html)
            logger.info(f"从 {url} 解析到 {len(journals)} 条期刊数据")
            all_journals.extend(journals)
    
    # 去重
    seen = set()
    unique_journals = []
    for journal, if_value in all_journals:
        journal_lower = journal.lower()
        if journal_lower not in seen and journal_lower not in existing_journals:
            seen.add(journal_lower)
            unique_journals.append((journal, if_value))
    
    logger.info(f"新增 {len(unique_journals)} 条期刊数据")
    
    # 合并并保存
    with open(OUTPUT_FILE, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for journal, if_value in unique_journals:
            writer.writerow([journal, if_value])
    
    logger.info(f"影响因子数据已更新到 {OUTPUT_FILE}")
    logger.info(f"总共 {len(existing_journals) + len(unique_journals)} 条期刊数据")


if __name__ == "__main__":
    update_impact_factors()
