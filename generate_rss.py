#!/usr/bin/env python3
"""RSS Feed Generator for Yandex.Zen — «Деловой Инсайд»

Reads HTML articles from /articles/, extracts metadata, builds RSS 2.0 XML.
Dzen-compatible: filters SVG, adds content:encoded + media:content, unique GUIDs.
"""

import json, os, re, sys
from datetime import datetime, timezone
from html import escape
from hashlib import md5

SITE_URL = os.environ.get("SITE_URL", "https://shalaxxx-maker.github.io")
ARTICLES_DIR = os.path.join(os.path.dirname(__file__), "articles")
RSS_FILE = os.path.join(os.path.dirname(__file__), "rss.xml")
MANIFEST_FILE = os.path.join(ARTICLES_DIR, "manifest.json")
ERROR_LOG = os.path.join(os.path.dirname(__file__), "rss_errors.log")

# ---------- Dzen-compatible HTML tags ----------
ALLOWED_TAGS = {'p', 'a', 'b', 'i', 'u', 's', 'h1', 'h2', 'h3', 'h4',
                'blockquote', 'ul', 'li', 'ol', 'img', 'figure', 'figcaption',
                'br', 'strong', 'em', 'sub', 'sup'}

def log_error(article_file, reason):
    """Log blocked article to rss_errors.log."""
    ts = datetime.now(timezone.utc).isoformat()
    with open(ERROR_LOG, 'a', encoding='utf-8') as f:
        f.write(f"[{ts}] BLOCKED {article_file}: {reason}\n")

def has_svg(html_body):
    """Return True if the body contains SVG markup (hero-svg or inline <svg>)."""
    if re.search(r'hero-svg', html_body):
        return True
    if re.search(r'<svg\b', html_body):
        return True
    if re.search(r'data:image/svg', html_body):
        return True
    return False

def has_real_image(html_body):
    """Return True if at least one real <img> (not SVG, not data:) exists."""
    imgs = re.findall(r'<img[^>]+src="([^"]+)"', html_body)
    for src in imgs:
        if src.startswith('data:') or 'svg' in src.lower():
            continue
        return True
    figures = re.findall(r'<figure[^>]*>.*?<img[^>]+src="([^"]+)"', html_body, re.DOTALL)
    for src in figures:
        if src.startswith('data:') or 'svg' in src.lower():
            continue
        return True
    return False

def extract_image_urls(html_body):
    """Extract all real image URLs with their dimensions."""
    images = []
    # <img> tags
    for m in re.finditer(r'<img[^>]+src="([^"]+)"[^>]*>', html_body):
        src = m.group(1)
        if src.startswith('data:') or 'svg' in src.lower():
            continue
        tag = m.group(0)
        w = re.search(r'width="(\d+)"', tag)
        width = int(w.group(1)) if w else 700
        images.append({'url': src, 'width': width})
    return images

def strip_svg_and_classes(html_body):
    """Remove SVG blocks and strip CSS classes from HTML for Dzen compatibility."""
    # Remove entire hero-svg div block
    body = re.sub(r'<div[^>]*class="[^"]*hero-svg[^"]*"[^>]*>.*?</div>', '', html_body, flags=re.DOTALL)
    # Remove inline <svg> elements
    body = re.sub(r'<svg\b.*?</svg>', '', body, flags=re.DOTALL)
    # Remove <div class="..."> wrappers but keep inner content
    # (simplistic: strip class= attributes from all tags)
    body = re.sub(r'\s*class="[^"]*"', '', body)
    # Remove <div> and </div> tags, keep content
    body = re.sub(r'</?div[^>]*>', '', body)
    # Remove <span> and </span> tags, keep content
    body = re.sub(r'</?span[^>]*>', '', body)
    # Remove style= attributes
    body = re.sub(r'\s*style="[^"]*"', '', body)
    # Collapse whitespace
    body = re.sub(r'\n\s*\n', '\n', body)
    return body.strip()

def extract_meta(html_path):
    """Extract title, date, body from HTML article."""
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    # Title from <title>
    title_match = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
    title = title_match.group(1).strip() if title_match else "Деловой Инсайд"

    # Date from meta div
    date_match = re.search(r'<div class="meta">\s*(.*?)\s*•', html, re.DOTALL)
    raw_date = date_match.group(1).strip() if date_match else None

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

    # Extract body (everything inside <div class="container">)
    body_match = re.search(r'<div class="container">(.*?)</div>\s*</body>', html, re.DOTALL)
    raw_body = body_match.group(1).strip() if body_match else ""

    # Make image URLs absolute
    raw_body = re.sub(r'src="(?!https?://)([^"]+)"', rf'src="{SITE_URL}/\1"', raw_body)

    return {
        "title": title,
        "date": pub_date,
        "raw_body": raw_body,
        "file": os.path.basename(html_path)
    }

def build_rss():
    """Build Dzen-compatible RSS 2.0 XML from all articles."""
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
    blocked_count = 0
    seen_guids = set()

    for a in articles[:30]:
        raw_body = a["raw_body"]

        # === SVG FILTER ===
        if has_svg(raw_body):
            log_error(a["file"], "SVG found in body — article blocked from RSS")
            blocked_count += 1
            continue

        if not has_real_image(raw_body):
            log_error(a["file"], "No real image found — article blocked from RSS")
            blocked_count += 1
            continue

        # === Generate unique GUID from title + date ===
        date_str = a["date"].strftime("%Y-%m-%d")
        guid = md5(f"{a['title']}|{date_str}".encode()).hexdigest()

        # Skip duplicate GUIDs
        if guid in seen_guids:
            log_error(a["file"], f"Duplicate GUID {guid} — article blocked from RSS")
            blocked_count += 1
            continue
        seen_guids.add(guid)

        pub_date_str = a["date"].strftime("%a, %d %b %Y %H:%M:%S GMT")
        article_url = f"{SITE_URL}/articles/{a['file']}"

        # === Build Dzen-compatible body (strip SVG + classes) ===
        clean_body = strip_svg_and_classes(raw_body)

        # === Extract images for media:content ===
        images = extract_image_urls(raw_body)
        media_tags = []
        for img in images:
            media_tags.append(
                f'      <media:content url="{escape(img["url"])}" '
                f'type="image/jpeg" medium="image" width="{img["width"]}"/>'
            )

        # === Build description (first 300 chars, plain text) ===
        plain_desc = re.sub(r'<[^>]+>', ' ', clean_body)
        plain_desc = re.sub(r'\s+', ' ', plain_desc).strip()[:300]

        item = f"""    <item>
      <title>{escape(a['title'])}</title>
      <link>{article_url}</link>
      <guid isPermaLink="false">{guid}</guid>
      <pubDate>{pub_date_str}</pubDate>
      <description>{escape(plain_desc)}</description>
      <content:encoded><![CDATA[{clean_body}]]></content:encoded>
{chr(10).join(media_tags)}
    </item>"""
        items_xml.append(item)

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:media="http://search.yahoo.com/mrss/">
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
    if blocked_count > 0:
        print(f"⚠️  Blocked: {blocked_count} articles (see {ERROR_LOG})")

    # Build manifest.json
    manifest = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "articles": [
            {
                "title": a["title"],
                "date": a["date"].strftime("%d %B %Y"),
                "file": a["file"],
            }
            for a in articles
        ]
    }
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"✅ Manifest: {len(articles)} entries → {MANIFEST_FILE}")

if __name__ == "__main__":
    build_rss()
