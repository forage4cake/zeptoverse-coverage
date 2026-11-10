            desc = next((p for p in paragraphs if TERM.search(p)), "")
            if not desc:
                desc = next((p for p in paragraphs if len(p) > 60), "")

        date = ""
        for key in ("article:published_time", "datePublished", "pubdate"):
            tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
            if tag and tag.get("content"):
                date = tag["content"][:10]
                break
        if not date:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or script.get_text())
                    for item in walk_json(data):
                        if item.get("datePublished"):
                            date = str(item["datePublished"])[:10]
                            break
                except Exception:
                    pass
                if date:
                    break

        image_url, image_license, image_credit = licensed_image_from_jsonld(soup, response.url)
        canonical = soup.find("link", rel="canonical")
        final_url = urljoin(response.url, canonical.get("href")) if canonical and canonical.get("href") else response.url

        return {
            "url": final_url,
            "title": title or "Zeptoverse mention",
            "source": source_name(final_url),
            "summary": sentence(desc),
            "date": date,
            "image": image_url,
            "image_license": image_license,
            "image_credit": image_credit,
        }
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
        urls = [item.get("url") for item in articles if item.get("url")]
        print(f"GDELT returned {len(urls)} article URLs.")
        return urls
    except requests.RequestException as exc:
        print(f"GDELT request failed: {exc}")
        return []
    except Exception as exc:
        print(f"GDELT search error: {exc}")
        return []


def reddit_urls():
    url = "https://www.reddit.com/search.rss?q=%22zeptoverse%22&sort=new"
    try:
        response = SESSION.get(url, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "xml")
        return [
            item.get_text(strip=True)
            for item in soup.find_all("link")
            if item.get_text(strip=True).startswith("http")
        ]
    except Exception as exc:
        print(f"Reddit RSS unavailable: {exc}")
        return []


def main():
    os.makedirs("data", exist_ok=True)
    try:
        with open(OUT, encoding="utf-8") as file:
            old = json.load(file)
    except Exception:
        old = {"mentions": []}

    existing = {item.get("url"): item for item in old.get("mentions", [])}
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

    items = sorted(existing.values(), key=lambda item: item.get("date") or "", reverse=True)[:500]
    payload = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "mentions": items,
    }
    with open(OUT, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    print(f"Feed now contains {len(items)} verified items.")


if __name__ == "__main__":
    main()
