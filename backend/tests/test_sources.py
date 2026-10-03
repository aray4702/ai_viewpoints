import httpx
import respx

from app.models import Platform, Source
from app.sources.feeds import ArxivAdapter, BlogAdapter, PodcastAdapter, YouTubeAdapter
from app.sources.html import html_to_text

BLOG_FEED = """<?xml version="1.0"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>t</title>
<item><title>On scaling</title><link>https://example.com/scaling</link><guid>post-1</guid>
<pubDate>Wed, 01 Oct 2026 10:00:00 GMT</pubDate><description>short</description>
<content:encoded><![CDATA[<p>I think <b>scaling</b> works.</p><script>x()</script><p>Second para.</p>]]></content:encoded>
</item></channel></rss>"""

PODCAST_FEED = """<?xml version="1.0"?><rss version="2.0"><channel><title>p</title>
<item><title>Ep 1</title><link>https://pod.example/1</link><guid>ep1</guid>
<enclosure url="https://cdn.example/ep1.mp3" type="audio/mpeg" length="1"/></item>
<item><title>No audio</title><guid>ep2</guid></item></channel></rss>"""

YT_FEED = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015"
 xmlns:media="http://search.yahoo.com/mrss/">
<entry><id>yt:video:abc123</id><yt:videoId>abc123</yt:videoId><title>Talk</title>
<link rel="alternate" href="https://www.youtube.com/watch?v=abc123"/>
<published>2026-10-01T10:00:00+00:00</published>
<media:group><media:description>desc</media:description></media:group></entry>
<entry><id>yt:video:short1</id><yt:videoId>short1</yt:videoId><title>Short</title>
<link rel="alternate" href="https://www.youtube.com/shorts/short1"/></entry></feed>"""

ARXIV_FEED = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><id>http://arxiv.org/abs/2610.01234v2</id><title>A  Paper
 Title</title><summary> Abstract text. </summary><published>2026-10-01T00:00:00Z</published>
<link href="http://arxiv.org/abs/2610.01234v2" rel="alternate"/></entry></feed>"""


def src(platform, handle, cursor=None):
    return Source(platform=platform, handle=handle, cursor=cursor)


def test_html_to_text():
    assert html_to_text("<p>a &amp; b</p><style>x{}</style><p>c</p>") == "a & b\nc"


@respx.mock
def test_blog_uses_full_content_and_etag():
    respx.get("https://example.com/feed").mock(
        return_value=httpx.Response(200, text=BLOG_FEED, headers={"ETag": '"v1"'})
    )
    r = BlogAdapter().fetch_new(src(Platform.blog, "https://example.com/feed"))
    assert r.cursor == '"v1"'
    [item] = r.items
    assert item.external_id == "post-1"
    assert item.raw_text == "I think scaling works.\nSecond para."
    assert item.published_at.year == 2026


@respx.mock
def test_blog_not_modified():
    route = respx.get("https://example.com/feed").mock(return_value=httpx.Response(304))
    r = BlogAdapter().fetch_new(src(Platform.blog, "https://example.com/feed", cursor='"v1"'))
    assert r.items == [] and r.cursor == '"v1"'
    assert route.calls[0].request.headers["If-None-Match"] == '"v1"'


@respx.mock
def test_podcast_requires_audio():
    respx.get("https://pod.example/feed").mock(return_value=httpx.Response(200, text=PODCAST_FEED))
    [item] = PodcastAdapter().fetch_new(src(Platform.podcast, "https://pod.example/feed")).items
    assert item.extra["audio_url"] == "https://cdn.example/ep1.mp3"


@respx.mock
def test_youtube_resolves_handle_and_skips_shorts():
    YouTubeAdapter._channel_ids.clear()
    cid = "UC" + "a" * 22
    respx.get("https://www.youtube.com/@someone").mock(
        return_value=httpx.Response(200, text=f'..."externalId":"{cid}"...')
    )
    respx.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}").mock(
        return_value=httpx.Response(200, text=YT_FEED)
    )
    [item] = YouTubeAdapter().fetch_new(src(Platform.youtube, "@someone")).items
    assert item.external_id == "abc123"
    assert item.url == "https://www.youtube.com/watch?v=abc123"


@respx.mock
def test_arxiv_strips_version():
    respx.get(url__startswith="https://export.arxiv.org/api/query").mock(
        return_value=httpx.Response(200, text=ARXIV_FEED)
    )
    [item] = ArxivAdapter().fetch_new(src(Platform.arxiv, 'au:"Yann LeCun"')).items
    assert item.external_id == "2610.01234"
    assert item.title == "A Paper Title"
