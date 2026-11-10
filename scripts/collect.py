#!/usr/bin/env python3
"""Collect exact-word Zeptoverse mentions and write a verified JSON feed."""
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

OUT = "data/mentions.json"
TERM = re.compile(r"\bzeptoverse\b", re.I)
HEADERS = {"User-Agent": "ZeptoverseCoverageBot/1.0 (public-interest media index)"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Deliberately conservative: only image-specific CC0/public-domain/CC BY
# declarations in structured ImageObject metadata are accepted automatically.
# Other licences require manual review because their conditions can vary.
ALLOWED_LICENSE_MARKERS = (
    "creativecommons.org/publicdomain/zero/",
    "creativecommons.org/publicdomain/mark/",
    "creativecommons.org/licenses/by/",
)


def sentence(text, limit=360):
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return "The source page contains a verified mention of zeptoverse."
    match = re.search(r".+?[.!?](?:\s|$)", text)
    result = match.group(0).strip() if match else text
    return result[:limit].rstrip()


def source_name(url, title=""):
    host = (urlparse(url).hostname or "").lower().replace("www.", "")
    known = {
        "bbc.com": "BBC News",
        "bbc.co.uk": "BBC News",
        "theguardian.com": "The Guardian",
        "reddit.com": "Reddit",
        "cam.ac.uk": "University of Cambridge",
        "wired.com": "WIRED",
    }
    for domain, name in known.items():
        if host == domain or host.endswith("." + domain):
            return name
    return host or "Online source"


def normalise_url(value, base_url):
    if isinstance(value, dict):
        value = value.get("url") or value.get("contentUrl") or value.get("@id")
    if not isinstance(value, str) or not value.strip():
        return ""
    return urljoin(base_url, value.strip())


def walk_json(value):
    """Yield dictionaries nested inside JSON-LD structures."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def licensed_image_from_jsonld(soup, page_url):
    """Return an image only when its own ImageObject declares an allowed licence."""
    og = soup.find("meta", property="og:image")
    og_url = normalise_url(og.get("content") if og else "", page_url)

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue

        for item in walk_json(data):
            item_type = item.get("@type", [])
            if isinstance(item_type, str):
                item_type = [item_type]
            if not any(str(t).lower().endswith("imageobject") for t in item_type):
                continue

            image_url = normalise_url(item.get("contentUrl") or item.get("url") or item.get("@id"), page_url)
            if not image_url:
                continue
