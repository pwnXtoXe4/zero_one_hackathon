import re
import time
import urllib.request
from urllib.parse import urljoin, urlparse, urldefrag
from pathlib import Path
from datetime import datetime

import trafilatura

BASE = "https://sybilion.dev/docs/"
TARGET = Path(r"C:\Users\flori\OneDrive\Dokumente\hackathon\Zero One Hackathon\zero_one_hackathon\domainInfo.md")

def get_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")

def normalize(url):
    url = urljoin(BASE, url)
    url, _ = urldefrag(url)
    return url

def is_docs_url(url):
    p = urlparse(url)
    return p.scheme in ("http", "https") and p.netloc == "sybilion.dev" and p.path.startswith("/docs/")

seen = set()
queue = [BASE]
ordered = []

while queue and len(seen) < 200:
    url = queue.pop(0)
    url = normalize(url)

    if url in seen or not is_docs_url(url):
        continue

    seen.add(url)
    ordered.append(url)

    try:
        html = get_html(url)
    except Exception as e:
        print(f"SKIP {url}: {e}")
        continue

    for href in re.findall(r'href=["\']([^"\']+)["\']', html):
        next_url = normalize(href)
        if is_docs_url(next_url) and next_url not in seen and next_url not in queue:
            queue.append(next_url)

print(f"Found {len(ordered)} docs pages")

parts = []
parts.append(f"# Sybilion Docs\n\nSource: {BASE}\nGenerated: {datetime.now().isoformat(timespec='seconds')}\n\n")

for i, url in enumerate(ordered, start=1):
    print(f"[{i}/{len(ordered)}] {url}")

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        print(f"  no content")
        continue

    md = trafilatura.extract(
        downloaded,
        url=url,
        output_format="markdown",
        include_links=True,
        include_formatting=True,
    )

    if not md:
        print(f"  extraction empty")
        continue

    parts.append("\n\n---\n\n")
    parts.append(f"<!-- Source: {url} -->\n\n")
    parts.append(md.strip())
    parts.append("\n")
    time.sleep(0.2)

TARGET.write_text("".join(parts), encoding="utf-8")
print(f"\nWrote {TARGET}")
print(f"Size: {TARGET.stat().st_size} bytes")
