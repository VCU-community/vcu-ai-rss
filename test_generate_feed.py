import unittest
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

from generate_feed import Story, TopicPageParser, build_rss, parse_vcu_date, validate_rss


class GeneratorTests(unittest.TestCase):
    def test_parser_extracts_only_topic_stories_and_next_page(self):
        page = '''<section id="results"><ul class="block-link"><li>
        <a href="/article/example"><img alt="Ignored image text">
        <p class="stories-date angle-psuedo-element">Feb. 5, 2026</p>
        <p>An AI &amp; research story</p></a></li></ul></section>
        <a id="btnMore" href="/topics/artificialintelligence?p=2">Load more</a>'''
        parser = TopicPageParser("https://news.vcu.edu/topics/artificialintelligence")
        parser.feed(page)
        self.assertEqual(len(parser.stories), 1)
        self.assertEqual(parser.stories[0].title, "An AI & research story")
        self.assertEqual(parser.stories[0].url, "https://news.vcu.edu/article/example")
        self.assertEqual(parser.next_url, "https://news.vcu.edu/topics/artificialintelligence?p=2")

    def test_abbreviated_date(self):
        self.assertEqual(parse_vcu_date("Sept. 8, 2025"), datetime(2025, 9, 8, tzinfo=timezone.utc))

    def test_rss_is_well_formed_and_complete(self):
        stories = [Story("A & B", "https://news.vcu.edu/article/a", datetime(2026, 7, 1, tzinfo=timezone.utc))]
        payload = build_rss(stories, "https://example.github.io/vcu-ai-rss/rss.xml")
        validate_rss(payload, 1)
        root = ET.fromstring(payload)
        self.assertEqual(root.findtext("./channel/item/title"), "A & B")


if __name__ == "__main__":
    unittest.main()
