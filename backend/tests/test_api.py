import re

import pytest
from fastapi.testclient import TestClient

from app.api.deps import SESSION_COOKIE, session_token
from app.core.config import get_settings
from app.core.db import session_scope
from app.main import app
from app.models import MediaItem, Person, Platform, Source, Tag, TagKind, User, Viewpoint


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def data():
    """Two people; karpathy has 3 viewpoints (one a repeat), lecun has 1."""
    with session_scope() as db:
        ai = Tag(kind=TagKind.domain, slug="ai", name="ai")
        nvda = Tag(kind=TagKind.ticker, slug="nvda", name="NVDA")
        ids = {}
        for slug, name in (("karpathy", "Andrej Karpathy"), ("yann-lecun", "Yann LeCun")):
            p = Person(slug=slug, name=name, domains=["ai"])
            db.add(p)
            db.flush()
            src = Source(person_id=p.id, platform=Platform.youtube, handle=f"@{slug}")
            db.add(src)
            db.flush()
            item = MediaItem(
                source_id=src.id,
                platform=Platform.youtube,
                external_id=f"vid-{slug}",
                url=f"https://www.youtube.com/watch?v={slug}",
                title="Talk",
            )
            db.add(item)
            db.flush()
            ids[slug] = (p.id, item.id)

        def add(slug, claim, tags, **kw):
            pid, iid = ids[slug]
            v = Viewpoint(
                person_id=pid,
                media_item_id=iid,
                claim=claim,
                summary="s",
                quote="q",
                tags=tags,
                **kw,
            )
            db.add(v)
            db.flush()
            return v.id

        first = add("karpathy", "Agents need reliability more than intelligence", [ai])
        add("karpathy", "GPU supply will stay tight through 2027", [ai, nvda], quote_timestamp=95)
        add("karpathy", "Agents need reliability", [ai], repeat_of_id=first)
        add("yann-lecun", "Autoregressive LLMs are a dead end for reasoning", [ai])


def claims(resp):
    assert resp.status_code == 200, resp.text
    return [v["claim"] for v in resp.json()["items"]]


def test_feed_newest_first_and_hides_repeats(client, data):
    assert claims(client.get("/api/viewpoints")) == [
        "Autoregressive LLMs are a dead end for reasoning",
        "GPU supply will stay tight through 2027",
        "Agents need reliability more than intelligence",
    ]
    assert len(claims(client.get("/api/viewpoints?include_repeats=true"))) == 4


def test_feed_filters(client, data):
    assert len(claims(client.get("/api/viewpoints?person=karpathy"))) == 2
    assert claims(client.get("/api/viewpoints?tag=nvda")) == [
        "GPU supply will stay tight through 2027"
    ]
    assert claims(client.get("/api/viewpoints?person=karpathy&tag=nvda&tag=ai")) == [
        "GPU supply will stay tight through 2027"
    ]
    assert len(claims(client.get("/api/viewpoints?domain=ai"))) == 3
    assert claims(client.get("/api/viewpoints?q=autoregress")) == [
        "Autoregressive LLMs are a dead end for reasoning"
    ]
    assert claims(client.get("/api/viewpoints?q=%22%3A(")) == claims(client.get("/api/viewpoints"))


def test_feed_pagination(client, data):
    page1 = client.get("/api/viewpoints?limit=2").json()
    assert len(page1["items"]) == 2 and page1["next_cursor"]
    page2 = client.get(f"/api/viewpoints?limit=2&cursor={page1['next_cursor']}").json()
    assert len(page2["items"]) == 1 and page2["next_cursor"] is None


def test_timestamp_deep_link(client, data):
    [v] = client.get("/api/viewpoints?tag=nvda").json()["items"]
    assert v["quote_url"] == "https://www.youtube.com/watch?v=karpathy&t=95s"
    assert client.get(f"/api/viewpoints/{v['id']}").json()["claim"] == v["claim"]
    assert client.get("/api/viewpoints/99999").status_code == 404


def test_search_keyword_only_without_embeddings(client, data):
    r = client.get("/api/search?q=agents reliability")
    assert [v["claim"] for v in r.json()] == ["Agents need reliability more than intelligence"]


def test_people_and_tags(client, data):
    people = client.get("/api/people").json()
    assert [(p["slug"], p["viewpoint_count"]) for p in people] == [
        ("karpathy", 2),
        ("yann-lecun", 1),
    ]
    detail = client.get("/api/people/karpathy").json()
    assert detail["sources"][0]["handle"] == "@karpathy"
    assert client.get("/api/people/nobody").status_code == 404
    assert [t["slug"] for t in client.get("/api/tags").json()] == ["ai", "nvda"]
    assert [t["slug"] for t in client.get("/api/tags?q=nv").json()] == ["nvda"]


def test_magic_link_flow(client, monkeypatch):
    sent = {}
    monkeypatch.setattr(
        "app.api.auth.send_email", lambda to, subj, html, text: sent.update(text=text)
    )
    assert client.post("/api/auth/magic-link", json={"email": "Ana@Example.com"}).status_code == 204
    token = re.search(r"token=(\S+)", sent["text"]).group(1)

    assert client.get("/api/auth/me").status_code == 401
    r = client.get(f"/api/auth/verify?token={token}", follow_redirects=False)
    assert r.status_code == 303 and SESSION_COOKIE in r.cookies
    assert client.get("/api/auth/me").json()["email"] == "ana@example.com"
    assert client.get("/api/auth/verify?token=garbage").status_code == 400


def test_admin_guard(client, data, monkeypatch):
    with session_scope() as db:
        admin, user = User(email="boss@example.com"), User(email="u@example.com")
        db.add_all([admin, user])
        db.flush()
        admin_tok, user_tok = session_token(admin.id), session_token(user.id)
    monkeypatch.setattr(get_settings(), "admin_emails", ["boss@example.com"])
    body = {"platform": "blog", "handle": "https://example.com/feed"}

    assert client.post("/api/people/karpathy/sources", json=body).status_code == 401
    client.cookies.set(SESSION_COOKIE, user_tok)
    assert client.post("/api/people/karpathy/sources", json=body).status_code == 403
    client.cookies.set(SESSION_COOKIE, admin_tok)
    r = client.post("/api/people/karpathy/sources", json=body)
    assert r.status_code == 200
    assert client.post("/api/people/karpathy/sources", json=body).status_code == 409
    sid = r.json()["id"]
    r = client.patch(f"/api/people/karpathy/sources/{sid}", json={"active": False})
    assert r.json()["active"] is False
    r = client.post("/api/people", json={"name": "New Person", "slug": "new-person"})
    assert r.status_code == 200 and r.json()["sources"] == []


def test_guest_viewpoint_shows_host(client, data):
    with session_scope() as db:
        guest = Person(slug="noam-brown", name="Noam Brown", domains=["ai"], auto_added=True)
        db.add(guest)
        db.flush()
        item = db.query(MediaItem).filter_by(external_id="vid-karpathy").one()
        db.add(
            Viewpoint(
                person_id=guest.id, media_item_id=item.id, claim="guest", summary="s", quote="q"
            )
        )
    [v] = client.get("/api/viewpoints?person=noam-brown").json()["items"]
    assert v["person"]["slug"] == "noam-brown" and v["via"]["slug"] == "karpathy"
    own = client.get("/api/viewpoints?person=karpathy").json()["items"]
    assert all(x["via"] is None for x in own)
    assert client.get("/api/people/noam-brown").json()["auto_added"] is True
