#!/usr/bin/env python3
"""Generate a standards-compliant RSS 2.0 feed from the VCU News AI topic."""

from __future__ import annotations

import argparse
import email.utils
import html
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

SOURCE_URL = "https://news.vcu.edu/topics/artificialintelligence"
USER_AGENT = "VCU-AI-RSS/1.0 (+https://github.com/)"
MAX_PAGES = 10
MAX_ITEMS = 3


@dataclass(frozen=True)
class Story:
    title: str
    url: str
    published: datetime
    summary: str = ""


class ArticlePageParser(HTMLParser):
    """Extract an article subhead, preferring the page's meta description."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta_description = ""
        self._in_subhead = False
        self._subhead_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs_list)
        classes = set((attrs.get("class") or "").split())
        if tag == "meta" and (attrs.get("name") or "").lower() == "description":
            self.meta_description = " ".join((attrs.get("content") or "").split())
        elif tag == "div" and "subheads" in classes:
            self._in_subhead = True

    def handle_data(self, data: str) -> None:
        if self._in_subhead:
            self._subhead_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self._in_subhead:
            self._in_subhead = False

    @property
    def summary(self) -> str:
        fallback = " ".join("".join(self._subhead_parts).split())
        return self.meta_description or fallback


class TopicPageParser(HTMLParser):
    """Extract story links, dates, and titles only from the topic results list."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.stories: list[Story] = []
        self.next_url: str | None = None
        self._in_results = False
        self._in_story_list = False
        self._in_story_link = False
        self._in_date = False
        self._story_url = ""
        self._date_parts: list[str] = []
        self._title_parts: list[str] = []

    @staticmethod
    def _classes(attrs: dict[str, str | None]) -> set[str]:
        return set((attrs.get("class") or "").split())

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs_list)
        classes = self._classes(attrs)
        if tag == "section" and attrs.get("id") == "results":
            self._in_results = True
        elif self._in_results and tag == "ul" and "block-link" in classes:
            self._in_story_list = True
        elif self._in_story_list and tag == "a" and attrs.get("href"):
            self._in_story_link = True
            self._story_url = urllib.parse.urljoin(self.base_url, attrs["href"] or "")
            self._date_parts = []
            self._title_parts = []
        elif self._in_story_link and tag == "p":
            self._in_date = "stories-date" in classes
        elif tag == "a" and attrs.get("id") == "btnMore" and attrs.get("href"):
            self.next_url = urllib.parse.urljoin(self.base_url, attrs["href"] or "")

    def handle_data(self, data: str) -> None:
        if not self._in_story_link:
            return
        if self._in_date:
            self._date_parts.append(data)
        elif data.strip():
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._in_story_link:
            self._in_date = False
        elif tag == "a" and self._in_story_link:
            date_text = " ".join("".join(self._date_parts).split())
            title = " ".join("".join(self._title_parts).split())
            if self._story_url and date_text and title:
                self.stories.append(Story(title, self._story_url, parse_vcu_date(date_text)))
            self._in_story_link = False
        elif tag == "ul" and self._in_story_list:
            self._in_story_list = False
        elif tag == "section" and self._in_results:
            self._in_results = False


def parse_vcu_date(value: str) -> datetime:
    normalized = value.replace("Sept.", "Sep")
    normalized = re.sub(r"\b(Jan|Feb|Mar|Apr|Aug|Sep|Oct|Nov|Dec)\.", r"\1", normalized)
    for pattern in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(normalized, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    raise ValueError(f"Unrecognized VCU News date: {value!r}")


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"VCU News returned HTTP {response.status} for {url}")
        return response.read().decode(response.headers.get_content_charset() or "utf-8")


def fetch_summary(url: str) -> str:
    parser = ArticlePageParser()
    parser.feed(fetch(url))
    return parser.summary


def collect_stories(source_url: str = SOURCE_URL) -> list[Story]:
    stories_by_url: dict[str, Story] = {}
    page_url: str | None = source_url
    visited: set[str] = set()

    while page_url and page_url not in visited and len(visited) < MAX_PAGES:
        visited.add(page_url)
        parser = TopicPageParser(page_url)
        parser.feed(fetch(page_url))
        for story in parser.stories:
            stories_by_url[story.url] = story
        if len(stories_by_url) >= MAX_ITEMS:
            break
        page_url = parser.next_url

    if not stories_by_url:
        raise RuntimeError("No stories were found. The VCU News page structure may have changed.")
    selected = sorted(stories_by_url.values(), key=lambda story: story.published, reverse=True)[:MAX_ITEMS]
    return [Story(story.title, story.url, story.published, fetch_summary(story.url)) for story in selected]


def build_rss(stories: list[Story], feed_url: str, generated_at: datetime | None = None) -> bytes:
    generated_at = generated_at or datetime.now(timezone.utc)
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    for name, value in (
        ("title", "VCU News: Artificial intelligence"),
        ("link", SOURCE_URL),
        ("description", "Artificial intelligence stories published by VCU News."),
        ("language", "en-us"),
        ("lastBuildDate", email.utils.format_datetime(generated_at)),
        ("generator", "VCU AI RSS generator"),
        ("ttl", "360"),
    ):
        ET.SubElement(channel, name).text = value
    atom_link = ET.SubElement(channel, "atom:link")
    atom_link.set("href", feed_url)
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    for story in stories:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = story.title
        ET.SubElement(item, "link").text = story.url
        guid = ET.SubElement(item, "guid", {"isPermaLink": "true"})
        guid.text = story.url
        ET.SubElement(item, "pubDate").text = email.utils.format_datetime(story.published)
        read_more = f'Read “{story.title}” on VCU News.'
        ET.SubElement(item, "description").text = (
            f"{story.summary}\n\n{read_more}" if story.summary else read_more
        )

    xml_body = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
    return xml_body.replace(b'<rss version="2.0">', b'<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">', 1)


def validate_rss(payload: bytes, expected_items: int) -> None:
    root = ET.fromstring(payload)
    if root.tag != "rss" or root.attrib.get("version") != "2.0":
        raise RuntimeError("Generated document is not RSS 2.0.")
    items = root.findall("./channel/item")
    if len(items) != expected_items:
        raise RuntimeError(f"Generated {len(items)} items; expected {expected_items}.")
    for item in items:
        for required in ("title", "link", "guid", "pubDate"):
            if not (item.findtext(required) or "").strip():
                raise RuntimeError(f"An RSS item is missing {required}.")


def write_status_page(path: Path, feed_url: str, item_count: int, generated_at: datetime) -> None:
    safe_url = html.escape(feed_url, quote=True)
    status = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>VCU AI RSS feed</title></head><body>
<main><h1>VCU AI RSS feed</h1><p>This feed contains {item_count} VCU News stories.</p>
<p><a href="{safe_url}">Open rss.xml</a></p>
<p>Last generated: <time datetime="{generated_at.isoformat()}">{generated_at:%Y-%m-%d %H:%M UTC}</time></p>
<p>Source: <a href="{SOURCE_URL}">VCU News artificial intelligence topic</a></p></main>
</body></html>
"""
    path.write_text(status, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="public")
    parser.add_argument("--feed-url", required=True)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        stories = collect_stories()
        generated_at = datetime.now(timezone.utc)
        payload = build_rss(stories, args.feed_url, generated_at)
        validate_rss(payload, len(stories))
        (output_dir / "rss.xml").write_bytes(payload)
        write_status_page(output_dir / "index.html", args.feed_url, len(stories), generated_at)
    except (OSError, RuntimeError, ValueError, urllib.error.URLError, ET.ParseError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Generated {len(stories)} RSS items in {output_dir / 'rss.xml'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
