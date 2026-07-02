#!/usr/bin/env python3
"""RSS Feed Generator for Yandex.Zen — «Деловой Инсайд»

Reads HTML articles from /articles/, extracts metadata, builds RSS 2.0 XML.
Compatible with Yandex.Zen requirements: full-text in description, absolute URLs.
"""

import json, os, re, sys
from datetime import datetime, timezone
from html import escape
from hashlib import md5

SITE_URL = os.environ.get("SITE_URL", "https://shalaxxx-maker.github.io/delovoy-insaid")
ARTICLES_DIR = os.path.join(os.path.dirname(__file__), "articles")
RSS_FILE = os.path.join(os.path.dirname(__file__), "rss.xml")
MANIFEST_FILE = os.path.join(ARTICLES_DIR, "manifest.json")

def extract_meta(html_path):
    """Extract title, date, description from HTML article."""
    with open(html_path, encoding="utf-8") as f:
        html = f.read()
    
    # Title from <title>
    title_match = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
    title = title_match.group(1).strip() if title_match else "Деловой Инсайд"
    
    # Date from meta div
    date_match = re.search(r'<div class="meta">\s*(.*?)\s*•', html, re.DOTALL)
    raw_date = date_match.group(1).strip() if date_match else None
    
    # Parse Russian date or use file modification time
    pub_date = None
    if raw_date:
        months_ru = {
            "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
            "мая": 5, "июня": 6, "июля": 7, "августа": 8,
            "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
        }
        for name, num in months_ru.items():
            pattern = rf"(\d{{1,2}})\s+{name}\s+(\d{{4}})"
            m = re.search(pattern, raw_date)
            if m:
                day, year = int(m.group(1)), int(m.group(2))
                pub_date = datetime(year, num, day, 9, 0, 0, tzinfo=timezone.utc)
                break
    
    if pub_date is None:
        pub_date = datetime.fromtimestamp(os.path.getmtime(html_path), tz=timezone.utc)
    
    # Extract body content (everything inside <div class="container">)
    body_match = re.search(r'<div class="container">(.*?)</div>\s*</body>', html, re.DOTALL)
    body = body_match.group(1).strip() if body_match else ""
    
    # Make image URLs absolute
    body = re.sub(r'src="(?!https?://)([^"]+)"', rf'src="{SITE_URL}/\1"', body)
    body = re.sub(r'src="https://images\.unsplash\.com/', 'src="https://images.unsplash.com/', body)
    
    # Description (first 300 chars, strip HTML for plain text)
    plain_desc = re.sub(r'<[^>]+>', ' ', body)
    plain_desc = re.sub(r'\s+', ' ', plain_desc).strip()[:300]
    
    return {
        "title": title,
        "date": pub_date,
        "description": plain_desc,
        "body": body,
        "file": os.path.basename(html_path)
    }

def build_rss():
    """Build RSS 2.0 XML from all articles."""
    articles = []
    
    if not os.path.isdir(ARTICLES_DIR):
        os.makedirs(ARTICLES_DIR)
    
    for fname in sorted(os.listdir(ARTICLES_DIR), reverse=True):
        if not fname.endswith(".html"):
            continue
        fpath = os.path.join(ARTICLES_DIR, fname)
        try:
            meta = extract_meta(fpath)
            articles.append(meta)
        except Exception as e:
            print(f"⚠️  Skipping {fname}: {e}", file=sys.stderr)
    
    # Build RSS XML
    rss_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    items_xml = []
    for a in articles[:30]:  # Last 30 articles in RSS
        pub_date_str = a["date"].strftime("%a, %d %b %Y %H:%M:%S GMT")
        guid = md5(a["title"].encode()).hexdigest()
        article_url = f"{SITE_URL}/articles/{a['file']}"
        
        item = f"""    <item>
      <title>{escape(a['title'])}</title>
      <link>{article_url}</link>
      <guid isPermaLink="false">{guid}</guid>
      <pubDate>{pub_date_str}</pubDate>
      <description><![CDATA[{a['body']}]]></description>
    </item>"""
        items_xml.append(item)
    
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Деловой Инсайд</title>
    <link>{SITE_URL}</link>
    <description>Независимый бизнес-обозреватель. Ежедневная аналитика рынков, франшиз и предпринимательства.</description>
    <language>ru</language>
    <lastBuildDate>{rss_date}</lastBuildDate>
    <atom:link href="{SITE_URL}/rss.xml" rel="self" type="application/rss+xml"/>
    <image>
      <url>{SITE_URL}/favicon.svg</url>
      <title>Деловой Инсайд</title>
      <link>{SITE_URL}</link>
    </image>
{chr(10).join(items_xml)}
  </channel>
</rss>"""
    
    with open(RSS_FILE, "w", encoding="utf-8") as f:
        f.write(rss)
    print(f"✅ RSS: {len(items_xml)} articles → {RSS_FILE}")
    
    # Build manifest.json
    manifest = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "articles": [
            {
                "title": a["title"],
                "date": a["date"].strftime("%d %B %Y"),
                "file": a["file"],
                "description": a["description"]
            }
            for a in articles
        ]
    }
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"✅ Manifest: {len(articles)} entries → {MANIFEST_FILE}")

if __name__ == "__main__":
    build_rss()
