#!/usr/bin/env python3
"""Collect exact-word Zeptoverse mentions and write a verified JSON feed."""
import json, os, re, time
from datetime import datetime, timezone
from urllib.parse import quote, urlparse
import requests
from bs4 import BeautifulSoup

OUT = "data/mentions.json"
TERM = re.compile(r"\bzeptoverse\b", re.I)
HEADERS = {"User-Agent": "ZeptoverseCoverageBot/1.0 (public-interest media index)"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

def sentence(text, limit=360):
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return "The source page contains a verified mention of zeptoverse."
    match = re.search(r".{1,}?[.!?](?:\s|$)", text)
    result = match.group(0).strip() if match else text
    return result[:limit].rstrip()

def source_name(url, title=""):
    host = (urlparse(url).hostname or "").lower().replace("www.", "")
    known = {"bbc.com":"BBC News", "bbc.co.uk":"BBC News",
             "theguardian.com":"The Guardian", "reddit.com":"Reddit",
             "cam.ac.uk":"University of Cambridge", "wired.com":"WIRED"}
    for domain, name in known.items():
        if host == domain or host.endswith("." + domain):
            return name
    return host or "Online source"

def parse_page(url):
    try:
        r = SESSION.get(url, timeout=18, allow_redirects=True)
        if r.status_code >= 400 or not r.text:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        # Require exact term in readable page text, not just URL or metadata.
        text = soup.get_text(" ", strip=True)
        if not TERM.search(text):
            return None
        title = (soup.title.get_text(" ", strip=True) if soup.title else "").strip()
        for key in ("og:title", "twitter:title"):
            tag = soup.find("meta", attrs={"property":key}) or soup.find("meta", attrs={"name":key})
            if tag and tag.get("content"):
                title = tag["content"].strip()
                break
        desc = ""
        for key in ("og:description", "description", "twitter:description"):
            tag = soup.find("meta", attrs={"property":key}) or soup.find("meta", attrs={"name":key})
            if tag and tag.get("content"):
                desc = tag["content"].strip()
                break
        if not desc:
            # Pick a short paragraph containing the term, then the first meaningful paragraph.
            paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
            desc = next((p for p in paragraphs if TERM.search(p)), "")
            if not desc:
                desc = next((p for p in paragraphs if len(p) > 60), "")
        date = ""
        for key in ("article:published_time", "datePublished", "pubdate"):
            tag = soup.find("meta", attrs={"property":key}) or soup.find("meta", attrs={"name":key})
            if tag and tag.get("content"):
                date = tag["content"][:10]
                break
        if not date:
            ld = soup.find("script", type="application/ld+json")
            if ld:
                try:
                    obj = json.loads(ld.string or ld.get_text())
                    objs = obj if isinstance(obj, list) else [obj]
                    for item in objs:
                        if isinstance(item, dict) and item.get("datePublished"):
                            date = str(item["datePublished"])[:10]
                            break
                except Exception:
                    pass
        # Only show images when an explicit CC/public-domain licence is declared.
        licence_url = ""
        for a in soup.find_all("a", href=True, rel=True):
            if "license" in [str(x).lower() for x in a.get("rel", [])]:
                href = a["href"]
                if "creativecommons.org/licenses/" in href or "creativecommons.org/publicdomain/" in href:
                    licence_url = href
                    break
        image_url = ""
        if licence_url:
            img = soup.find("meta", property="og:image")
            if img and img.get("content", "").startswith("https://"):
                image_url = img["content"]
        canonical = soup.find("link", rel="canonical")
        final_url = canonical.get("href") if canonical and canonical.get("href") else r.url
        return {"url": final_url, "title": title or "Zeptoverse mention",
                "source": source_name(final_url), "summary": sentence(desc),
                "date": date, "image": image_url, "image_license": licence_url}
    except Exception as exc:
        print(f"Could not verify {url}: {exc}")
        return None

def gdelt_urls():
    query = quote('"zeptoverse"')
    api = f"https://api.gdeltproject.org/api/v2/doc/doc?query={query}&mode=ArtList&format=json&maxrecords=250&sort=DateDesc"
    try:
        response = SESSION.get(api, timeout=45)
        print(f"GDELT HTTP status: {response.status_code}")
        response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            print("GDELT returned non-JSON content:")
            print(response.text[:500])
            return []

        articles = data.get("articles", [])
        urls = [x.get("url") for x in articles if x.get("url")]
        print(f"GDELT returned {len(urls)} article URLs.")
        return urls

def reddit_urls():
    url = "https://www.reddit.com/search.rss?q=%22zeptoverse%22&sort=new"
    try:
        xml = SESSION.get(url, timeout=20).text
        soup = BeautifulSoup(xml, "xml")
        return [x.get_text(strip=True) for x in soup.find_all("link") if x.get_text(strip=True).startswith("http")]
    except Exception as exc:
        print(f"Reddit RSS unavailable: {exc}")
        return []

def main():
    os.makedirs("data", exist_ok=True)
    try:
        with open(OUT, encoding="utf-8") as f:
            old = json.load(f)
    except Exception:
        old = {"mentions":[]}
    existing = {m.get("url"):m for m in old.get("mentions", [])}
    urls = list(dict.fromkeys(gdelt_urls() + reddit_urls()))
    print(f"Candidates found: {len(urls)}")
    for url in urls:
        if url in existing:
            continue
        item = parse_page(url)
        if item:
            existing[item["url"]] = item
            print(f"Verified: {item['source']} — {item['title']}")
        time.sleep(0.4)
    # Keep newest first, bounded feed size.
    items = sorted(existing.values(), key=lambda x: x.get("date") or "", reverse=True)[:500]
    payload = {"updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "mentions": items}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Feed now contains {len(items)} verified items.")

if __name__ == "__main__":
    main()
