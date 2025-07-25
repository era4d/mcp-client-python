import asyncio
import httpx
import feedparser
import re
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
from fastmcp import FastMCP

# 初始化FastMCP服务器
mcp = FastMCP("rss")

async def fetch_url(url: str) -> str:
    """获取URL内容"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.text
        except Exception as e:
            return f"获取内容失败: {str(e)}"

def parse_rss(rss_content: str) -> List[Dict[str, Any]]:
    """解析RSS内容为文章列表"""
    feed = feedparser.parse(rss_content)
    articles = []
    
    for entry in feed.entries:
        article = {
            "title": entry.get("title", "无标题"),
            "link": entry.get("link", ""),
            "published": entry.get("published", "未知日期"),
            "summary": entry.get("summary", "无摘要"),
        }
        articles.append(article)
    
    return articles

async def fetch_article_content(url: str) -> str:
    """获取文章详细内容"""
    html = await fetch_url(url)
    soup = BeautifulSoup(html, 'html.parser')
    
    # 移除脚本和样式元素
    for script in soup(["script", "style"]):
        script.extract()
    
    # 尝试找到文章主体内容
    # 这里的选择器需要根据目标网站进行调整
    article_content = soup.find('article') or soup.find('div', class_='content') or soup.find('div', class_='article')
    
    if article_content:
        return article_content.get_text(strip=True)
    else:
        # 如果找不到特定元素，返回页面主体文本
        return soup.body.get_text(strip=True) if soup.body else "无法提取文章内容"

async def parse_secwiki_page(url: str) -> List[Dict[str, Any]]:
    """解析SecWiki页面，提取文章列表
    
    Args:
        url: SecWiki页面URL，如https://sec-wiki.com/news或https://sec-wiki.com/event
    """
    html = await fetch_url(url)
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    
    # 查找表格行，每行包含一篇文章
    rows = soup.select('tr')
    
    for row in rows:
        # 跳过表头行
        if row.find('th'):
            continue
        
        # 提取文章信息
        cells = row.find_all('td')
        if len(cells) >= 4:  # 确保有足够的单元格
            try:
                date = cells[0].get_text(strip=True)
                title_cell = cells[1]
                title = title_cell.get_text(strip=True)
                link = title_cell.find('a')['href'] if title_cell.find('a') else ""
                
                # 如果链接是相对路径，转换为绝对路径
                if link and not link.startswith('http'):
                    if link.startswith('/'):
                        link = f"https://sec-wiki.com{link}"
                    else:
                        link = f"https://sec-wiki.com/{link}"
                
                contributor = cells[2].get_text(strip=True)
                views = cells[3].get_text(strip=True)
                
                article = {
                    "title": title,
                    "link": link,
                    "date": date,
                    "contributor": contributor,
                    "views": views
                }
                
                articles.append(article)
            except Exception as e:
                # 跳过解析错误的行
                continue
    
    return articles

@mcp.tool()
async def get_rss_feed(url: str = "https://sec-wiki.com/news/rss") -> str:
    """获取RSS源的最新文章列表
    
    Args:
        url: RSS源URL，默认为https://sec-wiki.com/news/rss
    """
    rss_content = await fetch_url(url)
    articles = parse_rss(rss_content)
    
    if not articles:
        return "未找到任何文章"
    
    # 格式化输出
    result = "最新文章列表:\n\n"
    for i, article in enumerate(articles[:10], 1):  # 只显示前10篇
        result += f"{i}. {article['title']}\n"
        result += f"   链接: {article['link']}\n"
        result += f"   发布时间: {article['published']}\n\n"
    
    return result

@mcp.tool()
async def search_articles(keyword: str, url: str = "https://sec-wiki.com/news/rss") -> str:
    """搜索RSS源中包含关键词的文章
    
    Args:
        keyword: 搜索关键词
        url: RSS源URL，默认为https://sec-wiki.com/news/rss
    """
    rss_content = await fetch_url(url)
    articles = parse_rss(rss_content)
    
    if not articles:
        return "未找到任何文章"
    
    # 搜索包含关键词的文章
    matched_articles = []
    for article in articles:
        if keyword.lower() in article['title'].lower() or keyword.lower() in article['summary'].lower():
            matched_articles.append(article)
    
    if not matched_articles:
        return f"未找到包含关键词 '{keyword}' 的文章"
    
    # 格式化输出
    result = f"包含关键词 '{keyword}' 的文章:\n\n"
    for i, article in enumerate(matched_articles, 1):
        result += f"{i}. {article['title']}\n"
        result += f"   链接: {article['link']}\n"
        result += f"   发布时间: {article['published']}\n\n"
    
    return result

@mcp.tool()
async def get_article_content(article_url: str) -> str:
    """获取指定文章的详细内容
    
    Args:
        article_url: 文章URL
    """
    content = await fetch_article_content(article_url)
    
    # 限制内容长度，避免过长
    max_length = 2000
    if len(content) > max_length:
        content = content[:max_length] + "...\n\n(内容已截断，过长)"
    
    return content

@mcp.tool()
async def get_interesting_articles(keywords: List[str], url: str = "https://sec-wiki.com/news/rss") -> str:
    """获取包含感兴趣关键词的文章及其内容
    
    Args:
        keywords: 感兴趣的关键词列表
        url: RSS源URL，默认为https://sec-wiki.com/news/rss
    """
    rss_content = await fetch_url(url)
    articles = parse_rss(rss_content)
    
    if not articles:
        return "未找到任何文章"
    
    # 搜索包含关键词的文章
    interesting_articles = []
    for article in articles:
        for keyword in keywords:
            if keyword.lower() in article['title'].lower() or keyword.lower() in article['summary'].lower():
                interesting_articles.append(article)
                break
    
    if not interesting_articles:
        return f"未找到包含关键词 {', '.join(keywords)} 的文章"
    
    # 获取文章内容并格式化输出
    result = f"包含关键词 {', '.join(keywords)} 的文章:\n\n"
    for i, article in enumerate(interesting_articles[:3], 1):  # 限制为前3篇
        result += f"{i}. {article['title']}\n"
        result += f"   链接: {article['link']}\n"
        result += f"   发布时间: {article['published']}\n\n"
        
        # 获取文章内容
        content = await fetch_article_content(article['link'])
        # 限制内容长度
        max_length = 1000
        if len(content) > max_length:
            content = content[:max_length] + "...\n\n(内容已截断，过长)"
        
        result += f"   内容预览:\n{content}\n\n"
        result += "---\n\n"
    
    return result

@mcp.tool()
async def get_security_advisories(limit: int = 10) -> str:
    """获取SecWiki安全咨询列表
    
    Args:
        limit: 返回的咨询数量，默认为10
    """
    url = "https://sec-wiki.com/event"
    articles = await parse_secwiki_page(url)
    
    if not articles:
        return "未找到任何安全咨询"
    
    # 格式化输出
    result = "最新安全咨询列表:\n\n"
    for i, article in enumerate(articles[:limit], 1):
        result += f"{i}. {article['title']}\n"
        result += f"   发布日期: {article['date']}\n"
        result += f"   贡献者: {article['contributor']}\n"
        result += f"   浏览量: {article['views']}\n"
        if article['link']:
            result += f"   链接: {article['link']}\n"
        result += "\n"
    
    return result

@mcp.tool()
async def get_technical_articles(limit: int = 10) -> str:
    """获取SecWiki技术文章列表
    
    Args:
        limit: 返回的文章数量，默认为10
    """
    url = "https://sec-wiki.com/news"
    articles = await parse_secwiki_page(url)
    
    if not articles:
        return "未找到任何技术文章"
    
    # 格式化输出
    result = "最新技术文章列表:\n\n"
    for i, article in enumerate(articles[:limit], 1):
        result += f"{i}. {article['title']}\n"
        result += f"   发布日期: {article['date']}\n"
        result += f"   贡献者: {article['contributor']}\n"
        result += f"   浏览量: {article['views']}\n"
        if article['link']:
            result += f"   链接: {article['link']}\n"
        result += "\n"
    
    return result

@mcp.tool()
async def search_security_content(keyword: str, include_advisories: bool = True, include_articles: bool = True) -> str:
    """在SecWiki安全咨询和技术文章中搜索关键词
    
    Args:
        keyword: 搜索关键词
        include_advisories: 是否包含安全咨询，默认为True
        include_articles: 是否包含技术文章，默认为True
    """
    results = []
    
    if include_advisories:
        advisories = await parse_secwiki_page("https://sec-wiki.com/event")
        for advisory in advisories:
            if keyword.lower() in advisory['title'].lower():
                advisory['type'] = "安全咨询"
                results.append(advisory)
    
    if include_articles:
        articles = await parse_secwiki_page("https://sec-wiki.com/news")
        for article in articles:
            if keyword.lower() in article['title'].lower():
                article['type'] = "技术文章"
                results.append(article)
    
    if not results:
        return f"未找到包含关键词 '{keyword}' 的内容"
    
    # 格式化输出
    result = f"包含关键词 '{keyword}' 的内容:\n\n"
    for i, item in enumerate(results, 1):
        result += f"{i}. [{item['type']}] {item['title']}\n"
        result += f"   发布日期: {item['date']}\n"
        result += f"   贡献者: {item['contributor']}\n"
        result += f"   浏览量: {item['views']}\n"
        if item['link']:
            result += f"   链接: {item['link']}\n"
        result += "\n"
    
    return result

if __name__ == "__main__":
    # 初始化并运行服务器
    mcp.run(host="0.0.0.0", port=8080, path="/sse", transport="sse")
    # 注意：要使用SSE模式，需要通过servers.yaml配置