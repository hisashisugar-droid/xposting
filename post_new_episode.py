#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import unicodedata
import uuid
from html import unescape
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qsl, quote, urlencode, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


RSS_URL = "https://anchor.fm/s/9bb1c5d8/podcast/rss"
APPLE_SHOW_ID = "1630515609"
APPLE_COUNTRY = "JP"
STATE_PATH = Path(__file__).with_name("state.json")
TIMEOUT = 20
X_WEIGHT_LIMIT = 280
URL_WEIGHT = 23


def fetch_text(url: str, headers: Optional[Dict[str, str]] = None) -> str:
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8")


def fetch_json(url: str, headers: Optional[Dict[str, str]] = None) -> dict:
    return json.loads(fetch_text(url, headers=headers))


def fetch_response(
    url: str,
    data: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    method: Optional[str] = None,
):
    request = Request(url, data=data, headers=headers or {}, method=method)
    return urlopen(request, timeout=TIMEOUT)


def strip_html(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def summarize(text: str, limit: int = 92) -> str:
    cleaned = strip_html(text).replace("\n", " ")
    parts = [part.strip() for part in re.split(r"(?<=[。！？!?])", cleaned) if part.strip()]
    summary = ""
    for part in parts:
        candidate = (summary + part).strip()
        if len(candidate) <= limit:
            summary = candidate
        else:
            break
    if not summary:
        summary = cleaned[:limit]
    if len(summary) > limit:
        summary = summary[: max(0, limit - 1)].rstrip() + "…"
    return summary


def display_title(title: str) -> str:
    return re.sub(r"\s*#\d+\s*$", "", title).strip()


def extract_topic(text: str) -> Optional[str]:
    cleaned = strip_html(text)
    match = re.search(r"「([^」]{1,20})」", cleaned)
    if match:
        return match.group(1).strip()
    return None


def build_catchy_summary(title: str, description: str, target_length: int) -> str:
    cleaned = strip_html(description).replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    parts = [part.strip() for part in re.split(r"(?<=[。！？!?])", cleaned) if part.strip()]

    opener = ""
    topic = extract_topic(description)
    if topic:
        opener = f"今回のテーマは「{topic}」。"
    elif title:
        opener = f"{display_title(title)}を深掘り。"

    summary = opener
    used = set()
    for part in parts:
        normalized = part.strip()
        if not normalized or normalized in used:
            continue
        candidate = f"{summary}{normalized}"
        if len(candidate) <= target_length:
            summary = candidate
            used.add(normalized)
        else:
            break

    if not summary:
        summary = cleaned[:target_length]

    if len(summary) > target_length:
        summary = summary[: max(0, target_length - 1)].rstrip() + "…"
    return summary


def weighted_length(text: str) -> int:
    total = 0
    for part in re.split(r"(https?://\S+)", text):
        if not part:
            continue
        if re.match(r"^https?://\S+$", part):
            total += URL_WEIGHT
            continue
        for ch in part:
            total += 1 if unicodedata.east_asian_width(ch) in {"F", "W", "A"} else 0.5
    return int(total * 2) // 2 if total % 1 else int(total)


def trim_to_weight(text: str, max_weight: int) -> str:
    current = ""
    for ch in text:
        candidate = current + ch
        if weighted_length(candidate) > max_weight:
            break
        current = candidate
    return current.rstrip()


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"posted_guids": []}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def latest_episode() -> dict:
    root = ET.fromstring(fetch_text(RSS_URL, headers={"User-Agent": "Mozilla/5.0"}))
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("RSS channel not found.")
    item = channel.find("item")
    if item is None:
        raise RuntimeError("No episode item found in RSS feed.")
    title = (item.findtext("title") or "").strip()
    description = item.findtext("description") or ""
    guid = (item.findtext("guid") or title).strip()
    spotify_episode_url = (item.findtext("link") or "").strip()
    pub_date = (item.findtext("pubDate") or "").strip()
    return {
        "guid": guid,
        "title": title,
        "description": description,
        "rss_episode_url": spotify_episode_url,
        "pub_date": pub_date,
    }


def lookup_spotify_episode_url(rss_episode_url: str) -> str:
    html = fetch_text(rss_episode_url, headers={"User-Agent": "Mozilla/5.0"})
    match = re.search(
        r'"spotifyUrl":"(https:\\u002F\\u002Fopen\.spotify\.com\\u002Fepisode\\u002F[^"]+)"',
        html,
    )
    if not match:
        return rss_episode_url
    return match.group(1).replace("\\u002F", "/")


def lookup_apple_episode_url(title: str) -> str:
    api_url = (
        "https://itunes.apple.com/lookup?"
        + urlencode(
            {
                "id": APPLE_SHOW_ID,
                "entity": "podcastEpisode",
                "country": APPLE_COUNTRY,
                "limit": 200,
            }
        )
    )
    data = fetch_json(api_url, headers={"User-Agent": "Mozilla/5.0"})
    normalized_target = normalize_title(title)
    candidates = []
    for item in data.get("results", []):
        episode_title = item.get("trackName")
        episode_url = item.get("trackViewUrl")
        if not episode_title or not episode_url:
            continue
        score = title_similarity(normalized_target, normalize_title(episode_title))
        candidates.append((score, episode_url, episode_title))
    if not candidates:
        raise RuntimeError("Apple Podcast episode URL could not be found.")
    best_score, best_url, best_title = max(candidates, key=lambda item: item[0])
    if best_score < 0.7:
        raise RuntimeError(f"Apple episode match was too weak: {best_title}")
    parsed = urlparse(best_url)
    query = dict(parse_qsl(parsed.query))
    episode_id = query.get("i")
    if episode_id:
        return f"https://podcasts.apple.com/jp/podcast/id{APPLE_SHOW_ID}?i={episode_id}"
    return best_url.replace("&uo=4", "")


def xgd_auth_header() -> str:
    auth_key = "xacas"
    with fetch_response(
        "https://x.gd/api/V1/auth",
        data=b"",
        headers={"User-Agent": "Mozilla/5.0"},
        method="POST",
    ) as response:
        body = json.loads(response.read().decode("utf-8"))
        encoded = response.headers[auth_key]

    shift = next((int(ch) for ch in body["result"]["s"] if ch.isdigit()), 0)
    rotated = "".join(
        chr((ord(ch) - 97 - shift + 26) % 26 + 97)
        if "a" <= ch <= "z"
        else chr((ord(ch) - 65 - shift + 26) % 26 + 65)
        if "A" <= ch <= "Z"
        else ch
        for ch in encoded
    )
    padded = rotated[::-1] + "=" * ((4 - len(rotated[::-1]) % 4) % 4)
    return base64.b64decode(padded).decode("utf-8")


def xgd_shorten_url(url: str) -> str:
    api_key = os.getenv("XGD_API_KEY")
    if not api_key:
        return url

    payload = urlencode({"url": url, "key": api_key}).encode("utf-8")
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "xacas": xgd_auth_header(),
    }
    try:
        with fetch_response(
            "https://x.gd/api/V1/shorten",
            data=payload,
            headers=headers,
            method="POST",
        ) as response:
            body = json.loads(response.read().decode("utf-8"))
        xid = body.get("result", {}).get("xid")
        return f"https://x.gd/{xid}" if xid else url
    except Exception:
        return url


def normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"\s+", "", title)
    title = re.sub(r"[!！?？:：#＃〜~\-‐ー]", "", title)
    return title


def title_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if left in right or right in left:
        return min(len(left), len(right)) / max(len(left), len(right))
    left_chars = set(left)
    right_chars = set(right)
    if not left_chars or not right_chars:
        return 0.0
    overlap = len(left_chars & right_chars)
    return overlap / max(len(left_chars), len(right_chars))


def percent_encode(value: str) -> str:
    return quote(str(value), safe="~-._")


def oauth1_header(method: str, url: str, extra_params: Dict[str, str]) -> str:
    consumer_key = require_env("X_CONSUMER_KEY")
    consumer_secret = require_env("X_CONSUMER_SECRET")
    access_token = require_env("X_ACCESS_TOKEN")
    access_secret = require_env("X_ACCESS_TOKEN_SECRET")

    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    signing_params = {**query_params, **extra_params, **oauth_params}
    normalized_params = "&".join(
        f"{percent_encode(key)}={percent_encode(signing_params[key])}"
        for key in sorted(signing_params)
    )
    signature_base = "&".join(
        [method.upper(), percent_encode(base_url), percent_encode(normalized_params)]
    )
    signing_key = f"{percent_encode(consumer_secret)}&{percent_encode(access_secret)}"
    digest = hmac.new(
        signing_key.encode("utf-8"),
        signature_base.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    oauth_params["oauth_signature"] = base64.b64encode(digest).decode("utf-8")
    return "OAuth " + ", ".join(
        f'{percent_encode(key)}="{percent_encode(value)}"'
        for key, value in sorted(oauth_params.items())
    )


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def post_to_x(text: str) -> dict:
    url = "https://api.twitter.com/2/tweets"
    body = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    auth_header = oauth1_header("POST", url, {})
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "User-Agent": "ningenradio-bot/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def build_post_text(title: str, summary: str, spotify_url: str, apple_url: str) -> str:
    shown_title = display_title(title)
    text = "\n".join(
        [
            "🔥更新🔥",
            shown_title,
            summary,
            f"Spotify: {spotify_url}",
            f"Apple: {apple_url}",
        ]
    )
    if weighted_length(text) <= X_WEIGHT_LIMIT:
        return text

    base_text = "\n".join(
        [
            "🔥更新🔥",
            shown_title,
            "",
            f"Spotify: {spotify_url}",
            f"Apple: {apple_url}",
        ]
    )
    remaining = X_WEIGHT_LIMIT - weighted_length(base_text)
    trimmed_summary = trim_to_weight(summary, max(20, remaining - 1))
    if trimmed_summary != summary:
        trimmed_summary = trim_to_weight(trimmed_summary + "…", max(20, remaining))
    return "\n".join(
        [
            "🔥更新🔥",
            shown_title,
            trimmed_summary,
            f"Spotify: {spotify_url}",
            f"Apple: {apple_url}",
        ]
    )


def main() -> int:
    state = load_state()
    episode = latest_episode()

    posted_guids = set(state.get("posted_guids", []))
    if episode["guid"] in posted_guids:
        print(f"Already posted: {episode['title']}")
        return 0

    title_for_post = display_title(episode["title"])
    spotify_url = xgd_shorten_url(lookup_spotify_episode_url(episode["rss_episode_url"]))
    apple_url = xgd_shorten_url(lookup_apple_episode_url(episode["title"]))
    fixed_parts_length = len(
        "\n".join(
            [
                "🔥更新🔥",
                title_for_post,
                "",
                f"Spotify: {spotify_url}",
                f"Apple: {apple_url}",
            ]
        )
    )
    target_summary_length = max(50, min(110, 280 - fixed_parts_length))
    summary = build_catchy_summary(episode["title"], episode["description"], target_summary_length)
    post_text = build_post_text(episode["title"], summary, spotify_url, apple_url)

    if os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}:
        print(post_text)
        return 0

    response = post_to_x(post_text)
    posted_guids.add(episode["guid"])
    state["posted_guids"] = sorted(posted_guids)
    state["last_post"] = {
        "guid": episode["guid"],
        "title": episode["title"],
        "pub_date": episode["pub_date"],
        "tweet_id": response.get("data", {}).get("id"),
    }
    save_state(state)
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
