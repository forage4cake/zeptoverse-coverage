
#!/usr/bin/env python3
"""Collect and verify public Zeptoverse media mentions."""

import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

OUT = "data/mentions.json"
TERM = re.compile(r"\bzeptoverse\b", re.I)

HEADERS = {
    "User-Agent": "ZeptoverseCoverageBot/1.0 (public media index)"
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def sentence(text, limit=360):
    text = re.sub(r"\s+", " ", text or "").strip()

    if not text:
        return "The source page contains a verified mention of Zeptoverse."

    match = re.search(r".+?[.!?](?:\s|$)", text)
    result = match.group(0).strip() if match else text

    return result[:limit].rstrip()


def source_name(url):
    host = (urlparse(url).hostname or "").lower()
    host = host.replace("www.", "")

    known = {
        "bbc.co.uk": "BBC News",
        "bbc.com": "BBC News",
        "theguardian.com": "The Guardian",
        "reddit.com": "Reddit",
        "news.google.com": "Google News",
        "news.yahoo.com": "Yahoo News",
        "bing.com": "Bing News",
        "bsky.app": "Bluesky",
        "ycombinator.com": "Hacker News",
    }

    for domain, name in known.items():
        if host == domain or host.endswith("." + domain):
            return name

    return host or "Online source"


def rss_urls(url):
    try:
        response = SESSION.get(url, timeout=25)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "xml")
        results = []

        for link in soup.find_all("link"):
            address = link.get("href") or link.get_text(strip=True)

            if address.startswith("http"):
                results.append(address)

        print(f"RSS source returned {len(results)} links.")
        return results

    except Exception as exc:
        print(f"RSS source unavailable: {exc}")
        return []


def google_news_urls(region):
    query = quote('"Zeptoverse"')
    url = (
        "https://news.google.com/rss/search?"
        f"q={query}&hl={region['language']}"
        f"&gl={region['country']}"
        f"&ceid={region['edition']}"
    )

    results = rss_urls(url)
    print(f"Google News {region['country']}: {len(results)} results.")
    return results


def bing_news_urls():
    query = quote('"Zeptoverse"')
    url = (
        "https://www.bing.com/news/search?"
        f"q={query}&format=rss"
    )

    results = rss_urls(url)
    print(f"Bing News: {len(results)} results.")
    return results


def gdelt_urls():
    query = quote('"zeptoverse"')

    api = (
        "https://api.gdeltproject.org/api/v2/doc/doc?"
        f"query={query}&mode=ArtList&format=json"
        "&maxrecords=250&sort=DateDesc"
    )

    try:
        response = SESSION.get(api, timeout=45)
        response.raise_for_status()

        data = response.json()
        articles = data.get("articles", [])

        urls = [
            article.get("url")
            for article in articles
            if article.get("url")
        ]

        print(f"GDELT: {len(urls)} results.")
        return urls

    except Exception as exc:
        print(f"GDELT unavailable: {exc}")
        return []


def reddit_urls():
    url = (
        "https://www.reddit.com/search.rss?"
        'q=%22zeptoverse%22&sort=new'
    )

    results = rss_urls(url)
    print(f"Reddit: {len(results)} results.")
    return results


def hacker_news_urls():
    url = (
        "https://hn.algolia.com/api/v1/search?"
        "query=zeptoverse&tags=story"
    )

    try:
        response = SESSION.get(url, timeout=25)
        response.raise_for_status()

        data = response.json()
        results = []

        for hit in data.get("hits", []):
            address = hit.get("url")

            if address:
                results.append(address)

        print(f"Hacker News: {len(results)} results.")
        return results

    except Exception as exc:
        print(f"Hacker News unavailable: {exc}")
        return []


def bluesky_mentions():
    """Collect publicly searchable Bluesky posts."""

    api = (
        "https://public.api.bsky.app/xrpc/"
        "app.bsky.feed.searchPosts"
    )

    try:
        response = SESSION.get(
            api,
            params={"q": "zeptoverse", "limit": 100},
            timeout=25
        )

        response.raise_for_status()
        data = response.json()

        results = []

        for post in data.get("posts", []):
            record = post.get("record", {})
            text = record.get("text", "")

            if not TERM.search(text):
                continue

            author = post.get("author", {})
            handle = author.get("handle", "")
            uri = post.get("uri", "")

            parts = uri.split("/")

            if len(parts) < 5 or not handle:
                continue

            rkey = parts[-1]
            address = (
                f"https://bsky.app/profile/{handle}/post/{rkey}"
            )

            created = record.get("createdAt", "")[:10]

            results.append({
                "url": address,
                "title": "Bluesky discussion mentioning Zeptoverse",
                "source": "Bluesky",
                "summary": sentence(text),
                "date": created,
                "image": "",
                "image_license": "",
            })

        print(f"Bluesky: {len(results)} verified posts.")
        return results

    except Exception as exc:
        print(f"Bluesky unavailable: {exc}")
        return []

def youtube_mentions():
    """Find public YouTube videos mentioning Zeptoverse."""

    url = "https://www.youtube.com/feeds/videos.xml?search_query=%22zeptoverse%22"

    try:
        response = SESSION.get(url, timeout=25)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "xml")
        results = []

        for entry in soup.find_all("entry"):
            title_node = entry.find("title")
            link_node = entry.find("link")

            description_node = entry.find(
                lambda tag: tag.name and
                tag.name.split(":")[-1] == "description"
            )

            title = (
                title_node.get_text(" ", strip=True)
                if title_node else ""
            )

            description = (
                description_node.get_text(" ", strip=True)
                if description_node else ""
            )

            link = link_node.get("href") if link_node else ""

            if not link or not TERM.search(title + " " + description):
                continue

            published = entry.find("published")

            results.append({
                "url": link,
                "title": title or "YouTube video mentioning Zeptoverse",
                "source": "YouTube",
                "summary": sentence(description or title),
                "date": published.get_text(strip=True)[:10] if published else "",
                "image": "",
                "image_license": ""
            })

        print(f"YouTube: {len(results)} verified videos.")
        return results

    except Exception as exc:
        print(f"YouTube unavailable: {exc}")
        return []


def podcast_mentions():
    """Search Apple's public podcast episode directory."""

    url = "https://itunes.apple.com/search"

    try:
        response = SESSION.get(
            url,
            params={
                "term": "Zeptoverse",
                "media": "podcast",
                "entity": "podcastEpisode",
                "limit": 50
            },
            timeout=25
        )

        response.raise_for_status()
        data = response.json()

        results = []

        for episode in data.get("results", []):
            title = episode.get("trackName", "")
            show = episode.get("collectionName", "")
            description = episode.get("description", "")

            combined = f"{title} {show} {description}"

            if not TERM.search(combined):
                continue

            link = (
                episode.get("trackViewUrl")
                or episode.get("episodeUrl")
            )

            if not link:
                continue

            release = episode.get("releaseDate", "")[:10]

            results.append({
                "url": link,
                "title": title or "Podcast episode mentioning Zeptoverse",
                "source": "Apple Podcasts",
                "summary": sentence(description or title),
                "date": release,
                "image": "",
                "image_license": ""
            })

        print(f"Podcasts: {len(results)} verified episodes.")
        return results

    except Exception as exc:
        print(f"Podcast search unavailable: {exc}")
        return []
def parse_page(url):
    try:
        response = SESSION.get(
            url,
            timeout=20,
            allow_redirects=True
        )

        if response.status_code >= 400 or not response.text:
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        text = soup.get_text(" ", strip=True)

        if not TERM.search(text):
            return None

        title = (
            soup.title.get_text(" ", strip=True)
            if soup.title else ""
        )

        for key in ("og:title", "twitter:title"):
            tag = (
                soup.find("meta", attrs={"property": key})
                or soup.find("meta", attrs={"name": key})
            )

            if tag and tag.get("content"):
                title = tag["content"].strip()
                break

        desc = ""

        for key in (
            "og:description",
            "description",
            "twitter:description"
        ):
            tag = (
                soup.find("meta", attrs={"property": key})
                or soup.find("meta", attrs={"name": key})
            )

            if tag and tag.get("content"):
                desc = tag["content"].strip()
                break

        if not desc:
            paragraphs = [
                p.get_text(" ", strip=True)
                for p in soup.find_all("p")
            ]

            desc = next(
                (p for p in paragraphs if TERM.search(p)),
                ""
            )

            if not desc:
                desc = next(
                    (p for p in paragraphs if len(p) > 60),
                    ""
                )

        date = ""

        for key in (
            "article:published_time",
            "datePublished",
            "pubdate"
        ):
            tag = (
                soup.find("meta", attrs={"property": key})
                or soup.find("meta", attrs={"name": key})
            )

            if tag and tag.get("content"):
                date = tag["content"][:10]
                break

        canonical = soup.find(
            "link",
            rel="canonical"
        )

        final_url = (
            canonical.get("href")
            if canonical and canonical.get("href")
            else response.url
        )

        # Images remain blank unless reuse permission
        # can be established through a separate review.
        return {
            "url": final_url,
            "title": title or "Zeptoverse mention",
            "source": source_name(final_url),
            "summary": sentence(desc),
            "date": date,
            "image": "",
            "image_license": ""
        }

    except Exception as exc:
        print(f"Could not verify {url}: {exc}")
        return None


def main():
    os.makedirs("data", exist_ok=True)

    try:
        with open(OUT, encoding="utf-8") as file:
            old = json.load(file)
    except Exception:
        old = {"mentions": []}

    existing = {
        item.get("url"): item
        for item in old.get("mentions", [])
    }

    regions = [
        {
            "country": "GB",
            "language": "en-GB",
            "edition": "GB:en"
        },
        {
            "country": "US",
            "language": "en-US",
            "edition": "US:en"
        },
        {
            "country": "CA",
            "language": "en-CA",
            "edition": "CA:en"
        },
        {
            "country": "AU",
            "language": "en-AU",
            "edition": "AU:en"
        },
        {
            "country": "IE",
            "language": "en-IE",
            "edition": "IE:en"
        }
    ]

    urls = []

    for region in regions:
        urls.extend(google_news_urls(region))

    urls.extend(bing_news_urls())
    urls.extend(gdelt_urls())
    urls.extend(reddit_urls())
    urls.extend(hacker_news_urls())

    urls = list(dict.fromkeys(urls))

    print(f"Total candidate URLs: {len(urls)}")

    # Add verified public Bluesky posts.
    for item in bluesky_mentions():
        if item["url"] not in existing:
            existing[item["url"]] = item
            print(f"Verified: Bluesky — {item['summary']}")
# Add verified YouTube videos.
    for item in youtube_mentions():
        if item["url"] not in existing:
            existing[item["url"]] = item
            print(f"Verified: YouTube — {item['title']}")

    # Add verified podcast episodes.
    for item in podcast_mentions():
        if item["url"] not in existing:
            existing[item["url"]] = item
            print(f"Verified: Podcast — {item['title']}")
    # Check external article pages.
    for url in urls:
        if url in existing:
            continue

        item = parse_page(url)

        if item:
            existing[item["url"]] = item

            print(
                f"Verified: {item['source']} — "
                f"{item['title']}"
            )

        time.sleep(0.4)

    # Preserve existing cards and put newest dates first.
    items = sorted(
        existing.values(),
        key=lambda item: item.get("date") or "",
        reverse=True
    )[:500]

    payload = {
        "updated_at": datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC"),
        "mentions": items
    }

    with open(OUT, "w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"Feed now contains {len(items)} verified items."
    )


if __name__ == "__main__":
    main()
