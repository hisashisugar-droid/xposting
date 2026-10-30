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
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


RSS_URL = "https://anchor.fm/s/9bb1c5d8/podcast/rss"
APPLE_SHOW_PAGE_URL = "https://podcasts.apple.com/jp/podcast/%E3%83%8B%E3%83%B3%E3%82%B2%E3%83%B3%E5%BA%83%E5%91%8A%E7%A4%BE-%E4%BA%BA%E6%96%87%E7%9F%A5%E3%81%A7%E5%AD%A6%E3%81%B6%E3%83%9E%E3%83%BC%E3%82%B1%E3%83%86%E3%82%A3%E3%83%B3%E3%82%B0/id1630515609"
APPLE_SHOW_API_URL = (
    "https://amp-api.podcasts.apple.com/v1/catalog/jp/podcasts/1630515609"
    "?extend=editorialArtwork%2CfeedUrl%2CsellerInfo%2Cupsell%2CuserRating"
    "&extend%5Bpodcast-channels%5D=availableShowCount%2CeditorialArtwork%2C"
    "subscriptionArtwork%2CsubscriptionBrandLogoArtwork%2CsubscriptionOffers%2CwordmarkArtwork"
    "&include=artists%2Cchannel%2Cepisodes%2Cgenres%2Cparticipants%2Creviews%2Ctrailers"
    "&include%5Bartists%5D=podcasts&include%5Bpodcast-channels%5D=podcasts"
    "&views=listeners-also-subscribed%2Cchannel-top-paid-shows"
    "&limit%5Bepisodes%5D=15&limit%5Btrailers%5D=15&sort%5Btrailers%5D=-releaseDate"
    "&with=entitlements%2ChlsVideo%2CshowHero&l=ja"
)
APPLE_SHOW_ID = "1630515609"
APPLE_COUNTRY = "JP"
STATE_PATH = Path(__file__).with_name("state.json")
APPLE_SHOW_HTML_PATH = Path(__file__).with_name("apple_show.html")
TIMEOUT = 20
X_WEIGHT_LIMIT = 280
URL_WEIGHT = 23
RETRYABLE_ERRORS = (TimeoutError, URLError)
SIGNATURE = "ポッドキャスト「ニンゲン広告社」"
HOOK_DISPLAY_LIMIT = 45
NOTICE_MARKERS = (
    "コラボ",
    "最終回",
    "ゲスト",
    "お知らせ",
    "おしらせ",
    "告知",
    "配信開始",
    "リリース",
)
BANNED_WORDS = (
    "衝撃",
    "完全版",
    "絶対",
    "ヤバい",
    "やばい",
    "保存版",
    "驚愕",
    "必見",
    "神回",
)


class DuplicateTweetError(RuntimeError):
    pass


def add_retry_marker(text: str, attempt: int) -> str:
    return "\n".join([text, f"再送 {attempt + 1}"])


def fetch_text(url: str, headers: Optional[Dict[str, str]] = None) -> str:
    request = Request(url, headers=headers or {})
    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                return response.read().decode("utf-8")
        except RETRYABLE_ERRORS as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    assert last_error is not None
    raise last_error


def fetch_json(url: str, headers: Optional[Dict[str, str]] = None) -> dict:
    return json.loads(fetch_text(url, headers=headers))


def fetch_response(
    url: str,
    data: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    method: Optional[str] = None,
):
    request = Request(url, data=data, headers=headers or {}, method=method)
    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            return urlopen(request, timeout=TIMEOUT)
        except RETRYABLE_ERRORS as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    assert last_error is not None
    raise last_error


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


def normalize_title_for_comparison(value: str) -> str:
    normalized = re.sub(r"\s+", "", value).lower()
    normalized = re.sub(r"#\d+$", "", normalized)
    return re.sub(r"[「」『』【】（）()、。！？!?・…]", "", normalized)


def extract_topic(text: str) -> Optional[str]:
    cleaned = strip_html(text)
    match = re.search(r"「([^」]{1,20})」", cleaned)
    if match:
        return match.group(1).strip()
    return None


def build_catchy_summary(
    title: str, description: str, target_length: int = 70
) -> tuple[str, str]:
    cleaned = strip_html(description).replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    parts = [
        part.strip()
        for part in re.findall(r"[^。！？!?]+[。！？!?]+|[^。！？!?]+$", cleaned)
        if part.strip()
    ]

    first_content_index = 0
    while (
        first_content_index < len(parts)
        and is_title_restatement(title, parts[first_content_index])
    ):
        first_content_index += 1
    content_parts = parts[first_content_index:]

    used_count = 1
    if content_parts:
        hook = content_parts[0]
        if len(hook) < 20 and len(content_parts) > 1:
            hook += content_parts[1]
            used_count = 2
    elif parts:
        hook = ""
        used_count = 0
    else:
        hook = title.strip()
        used_count = 0

    hook = hook[:target_length].rstrip()
    if hook.endswith("、"):
        hook = hook[:-1] + "。"

    supplement = content_parts[used_count] if len(content_parts) > used_count else ""
    return hook, supplement


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


def record_post_status(state: dict, **fields) -> None:
    history = state.setdefault("post_history", [])
    history.append(fields)
    state["post_history"] = history[-25:]


def refresh_apple_show_cache() -> bool:
    try:
        html = fetch_text(APPLE_SHOW_PAGE_URL, headers={"User-Agent": "Mozilla/5.0"})
    except Exception:
        return False
    APPLE_SHOW_HTML_PATH.write_text(html, encoding="utf-8")
    return True


def latest_episode() -> dict:
    sources = [
        ("RSS", _latest_episode_from_rss),
        ("Apple HTML cache", _latest_episode_from_apple_html_cache),
        ("Apple API", _latest_episode_from_apple_api),
    ]
    errors = []
    for source_name, loader in sources:
        try:
            episode = loader()
            episode["source"] = source_name
            print(f"Episode source: {source_name}")
            return episode
        except Exception as exc:
            errors.append(f"{source_name}: {exc}")
    raise RuntimeError(" / ".join(errors))


def latest_episode_from_rss_or_cache() -> dict:
    """Prefer RSS when it is reachable, but fall back to the local Apple cache."""
    sources = [
        ("RSS", _latest_episode_from_rss),
        ("Apple HTML cache", _latest_episode_from_apple_html_cache),
        ("Apple API", _latest_episode_from_apple_api),
    ]
    errors = []
    for source_name, loader in sources:
        try:
            episode = loader()
            episode["source"] = source_name
            print(f"Episode source: {source_name}")
            return episode
        except Exception as exc:
            errors.append(f"{source_name}: {exc}")
    raise RuntimeError(" / ".join(errors))


def _latest_episode_from_rss() -> dict:
    episodes = _episodes_from_rss(limit=1)
    if not episodes:
        raise RuntimeError("No episode item found in RSS feed.")
    return episodes[0]


def _episodes_from_rss(limit: int = 3) -> list[dict]:
    # Anchor's CDN can serve a stale feed for the bare URL. A cache-busting
    # query and no-cache headers ensure scheduled runs see newly published episodes.
    rss_url = f"{RSS_URL}?refresh={int(time.time())}"
    root = ET.fromstring(
        fetch_text(
            rss_url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )
    )
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("RSS channel not found.")
    episodes = []
    for item in channel.findall("item")[:limit]:
        episodes.append(
            {
                "guid": (item.findtext("guid") or item.findtext("title") or "").strip(),
                "title": (item.findtext("title") or "").strip(),
                "description": item.findtext("description") or "",
                "rss_episode_url": (item.findtext("link") or "").strip(),
                "pub_date": (item.findtext("pubDate") or "").strip(),
            }
        )
    return episodes


def _latest_episode_from_apple_api() -> dict:
    data = fetch_json(APPLE_SHOW_API_URL, headers={"User-Agent": "Mozilla/5.0"})
    included = data.get("data", [])
    if not included:
        raise RuntimeError("Apple API returned no show data.")
    # The Apple catalog payload exposes the most recent episodes in the show attributes.
    # We take the first episode entry because the endpoint sorts by newest release.
    show = included[0]
    relationships = show.get("relationships", {})
    episodes = relationships.get("episodes", {}).get("data", [])
    if not episodes:
        raise RuntimeError("Apple API returned no episodes.")
    episode_id = episodes[0].get("id")
    episode_url = (
        f"https://podcasts.apple.com/jp/podcast/id{APPLE_SHOW_ID}?i={episode_id}"
        if episode_id
        else ""
    )
    # Fetching the individual episode page gives us title/summary matching the post text.
    if not episode_url:
        raise RuntimeError("Apple API episode id missing.")
    html = fetch_text(episode_url, headers={"User-Agent": "Mozilla/5.0"})
    title_match = re.search(r'data-testid="episode-lockup-title">([^<]+)</span>', html)
    summary_match = re.search(
        r'data-testid="episode-content__summary".*?<!-- HTML_TAG_START -->(.*?)<!-- HTML_TAG_END -->',
        html,
        flags=re.S,
    )
    published_match = re.search(r'data-testid="episode-details__published-date".*?>([^<]+)</span>', html)
    title = unescape(title_match.group(1)).strip() if title_match else ""
    description = strip_html(summary_match.group(1)) if summary_match else ""
    pub_date = unescape(published_match.group(1)).strip() if published_match else ""
    if not title:
        raise RuntimeError("Apple episode title not found.")
    return {
        "guid": episode_id or title,
        "title": title,
        "description": description,
        "rss_episode_url": episode_url,
        "pub_date": pub_date,
    }


def _latest_episode_from_apple_html_cache() -> dict:
    if not APPLE_SHOW_HTML_PATH.exists():
        raise RuntimeError("Cached Apple HTML not found.")
    html = APPLE_SHOW_HTML_PATH.read_text(encoding="utf-8", errors="ignore")
    cache_match = re.search(
        r"<!-- CODEx_CACHE_BEGIN -->(.*?)<!-- CODEx_CACHE_END -->", html, flags=re.S
    )
    cache_html = cache_match.group(1) if cache_match else html
    title_match = re.search(r'data-testid="episode-lockup-title">([^<]+)</div>', cache_html)
    summary_match = re.search(
        r'data-testid="episode-content__summary".*?<!-- HTML_TAG_START -->(.*?)<!-- HTML_TAG_END -->',
        cache_html,
        flags=re.S,
    )
    url_match = re.search(r'href="(https://podcasts\.apple\.com/[^"]+\?i=\d+)"', cache_html)
    pub_date_match = re.search(
        r'data-testid="episode-details__published-date".*?>([^<]+)</span>', cache_html
    )
    if not title_match or not url_match:
        raise RuntimeError("Cached Apple HTML did not contain an episode.")
    title = unescape(title_match.group(1)).strip()
    description = strip_html(summary_match.group(1)) if summary_match else ""
    return {
        "guid": url_match.group(1),
        "title": title,
        "description": description,
        "rss_episode_url": url_match.group(1),
        "pub_date": unescape(pub_date_match.group(1)).strip() if pub_date_match else "",
    }


def lookup_spotify_episode_url(rss_episode_url: str) -> str:
    try:
        html = fetch_text(rss_episode_url, headers={"User-Agent": "Mozilla/5.0"})
    except Exception:
        return rss_episode_url
    episode_path = urlparse(rss_episode_url).path.rstrip("/")
    episode_path = re.sub(r"^/pod/show", "", episode_path)
    escaped_episode_path = episode_path.replace("/", "\\u002F")
    path_marker = f'"shareLinkPath":"{escaped_episode_path}"'
    marker_index = html.find(path_marker)
    if marker_index >= 0:
        episode_match = re.search(
            r'"spotifyUrl":"(https:\\u002F\\u002Fopen\.spotify\.com\\u002Fepisode\\u002F[^"]+)"',
            html[marker_index : marker_index + 2000],
        )
        if episode_match:
            return episode_match.group(1).replace("\\u002F", "/")
    match = re.search(
        r'"spotifyUrl":"(https:\\u002F\\u002Fopen\.spotify\.com\\u002Fepisode\\u002F[^"]+)"',
        html,
    )
    if not match:
        return rss_episode_url
    return match.group(1).replace("\\u002F", "/")


def lookup_apple_episode_url(title: str) -> str:
    try:
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
    except Exception:
        return f"https://podcasts.apple.com/jp/podcast/id{APPLE_SHOW_ID}"


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
    if os.getenv("ENABLE_XGD_SHORTENING", "").lower() not in {"1", "true", "yes"}:
        return url
    api_key = os.getenv("XGD_API_KEY")
    if not api_key:
        return url

    try:
        payload = urlencode({"url": url, "key": api_key}).encode("utf-8")
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "xacas": xgd_auth_header(),
        }
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


def is_title_restatement(title: str, sentence: str) -> bool:
    a = normalize_title_for_comparison(title)
    b = normalize_title_for_comparison(sentence)
    if not a or not b:
        return False
    if b.startswith(a):
        return True
    if not sentence.rstrip().endswith(("?", "？")):
        return False
    return title_similarity(normalize_title(a), normalize_title(b)) >= 0.5


def lint_description(title: str, description: str) -> list[str]:
    cleaned = strip_html(description).replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    parts = [
        part.strip()
        for part in re.findall(r"[^。！？!?]+[。！？!?]+|[^。！？!?]+$", cleaned)
        if part.strip()
    ]
    first_sentence = parts[0] if parts else ""
    first_content_index = 0
    while (
        first_content_index < len(parts)
        and is_title_restatement(title, parts[first_content_index])
    ):
        first_content_index += 1
    opening_sentence = (
        parts[first_content_index] if first_content_index < len(parts) else ""
    )
    warnings = []

    common_terms = re.findall(r"[ァ-ヶー]{2,}|[一-龯々〆ヵヶ]{2,}", title)
    if (
        first_sentence.rstrip().endswith(("?", "？"))
        and not is_title_restatement(title, first_sentence)
        and any(term in first_sentence for term in common_terms)
    ):
        warnings.append(
            "[warn] 説明文の1文目がタイトルの言い換えになっています。"
            "冒頭の二重の原因になります"
        )

    if any(marker in opening_sentence for marker in NOTICE_MARKERS):
        warnings.append(
            "[warn] 説明文の1文目が告知です。フックに告知が選ばれます。"
            "問い→中身→告知の順にしてください"
        )

    banned_word = next((word for word in BANNED_WORDS if word in cleaned), None)
    if banned_word:
        warnings.append(f"[warn] 説明文に煽り語が含まれています: {banned_word}")

    return warnings


def print_description_warnings(title: str, description: str) -> None:
    for warning in lint_description(title, description):
        print(warning)


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
    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 403 and "duplicate content" in body.lower():
                raise DuplicateTweetError(body or exc.reason) from exc
            if exc.code in {429, 500, 502, 503, 504} and attempt < 2:
                last_error = exc
                time.sleep(2 + attempt * 2)
                continue
            raise RuntimeError(
                f"X API HTTP {exc.code}: {body or exc.reason}"
            ) from exc
        except RETRYABLE_ERRORS as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    assert last_error is not None
    raise last_error


def post_display_title(title: str) -> str:
    return display_title(title)


def _shorten_hook(hook: str, max_chars: int, add_ellipsis: bool = False) -> str:
    shortened = hook[:max_chars].rstrip()
    if shortened.endswith("、"):
        shortened = shortened[:-1] + "。"
    if add_ellipsis and len(hook) > max_chars:
        shortened += "…"
    return shortened


def _display_length(text: str) -> int:
    return sum(
        2 if unicodedata.east_asian_width(ch) in {"F", "W", "A"} else 1
        for ch in text
    )


def _compose_post_text(
    hook: str,
    title: str,
    supplement: str,
    spotify_url: str,
    apple_url: str,
    include_signature: bool,
    title_first: bool = False,
) -> str:
    title_line = title
    if title_first:
        lines = [title_line]
    else:
        lines = []
        if hook and hook not in {title, title_line}:
            lines.append(hook)
        lines.append(title_line)
    if supplement:
        lines.append(supplement)
    lines.append(f"Spotify: {spotify_url} / Apple: {apple_url}")
    if include_signature:
        lines.append(SIGNATURE)
    return "\n".join(lines)


def build_post_text(title: str, description: str, spotify_url: str, apple_url: str) -> str:
    shown_title = post_display_title(title)
    hook, supplement = build_catchy_summary(title, description)

    hook_matches_title = (
        bool(hook)
        and normalize_title_for_comparison(hook)
        == normalize_title_for_comparison(shown_title)
    )
    if hook_matches_title:
        hook = ""
    title_first = (
        not hook
        or bool(strip_html(description))
        and _display_length(hook) > HOOK_DISPLAY_LIMIT
        or hook.rstrip().endswith(("？", "?"))
    )
    if title_first:
        candidates = [
            (hook, hook, True),
            (hook, "", True),
            (hook, "", False),
        ]
    else:
        candidates = [
            (hook, supplement, True),
            (hook, "", True),
            (hook, "", False),
            (_shorten_hook(hook, 60), "", False),
            (_shorten_hook(hook, 45), "", False),
            (_shorten_hook(hook, 30, add_ellipsis=True), "", False),
        ]
    for candidate_hook, candidate_supplement, include_signature in candidates:
        text = _compose_post_text(
            candidate_hook,
            shown_title,
            candidate_supplement,
            spotify_url,
            apple_url,
            include_signature,
            title_first=title_first,
        )
        if weighted_length(text) <= X_WEIGHT_LIMIT:
            return text

    raise RuntimeError("Required post fields do not fit within X's 280-character limit.")


def build_episode_post(episode: dict) -> tuple[str, str, str]:
    spotify_url = xgd_shorten_url(lookup_spotify_episode_url(episode["rss_episode_url"]))
    apple_url = xgd_shorten_url(lookup_apple_episode_url(episode["title"]))
    post_text = build_post_text(
        episode["title"], episode["description"], spotify_url, apple_url
    )
    return post_text, spotify_url, apple_url


def main() -> int:
    state = load_state()
    refreshed = refresh_apple_show_cache()
    print(f"Apple cache refreshed: {str(refreshed).lower()}")
    dry_run = os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}
    if dry_run:
        try:
            episodes = _episodes_from_rss(limit=3)
            print("Episode source: RSS")
        except Exception:
            episodes = [latest_episode()]
        for index, episode in enumerate(episodes, start=1):
            post_text, spotify_url, apple_url = build_episode_post(episode)
            print(f"Episode {index}: {episode['title']}")
            print(f"Episode guid: {episode['guid']}")
            print(f"Spotify URL: {spotify_url}")
            print(f"Apple URL: {apple_url}")
            print(post_text)
            print_description_warnings(episode["title"], episode["description"])
            print(f"Weighted length: {weighted_length(post_text)}")
        return 0

    if os.getenv("PREFER_RSS", "").lower() in {"1", "true", "yes"}:
        episode = latest_episode_from_rss_or_cache()
    else:
        episode = latest_episode()
    print(f"Episode title: {episode['title']}")
    print(f"Episode guid: {episode['guid']}")

    posted_guids = set(state.get("posted_guids", []))
    if episode["guid"] in posted_guids:
        print(f"Already posted: {episode['title']}")
        return 0

    post_text, spotify_url, apple_url = build_episode_post(episode)
    print(f"Spotify URL: {spotify_url}")
    print(f"Apple URL: {apple_url}")

    if not episode.get("title") or not episode.get("description"):
        raise RuntimeError("Episode data is incomplete; refusing to post.")
    print_description_warnings(episode["title"], episode["description"])
    response = None
    for attempt in range(3):
        candidate_text = post_text if attempt == 0 else add_retry_marker(post_text, attempt)
        try:
            response = post_to_x(candidate_text)
            if attempt > 0:
                print(f"X repost succeeded on attempt {attempt + 1}")
            break
        except DuplicateTweetError as exc:
            print(f"X duplicate on attempt {attempt + 1}: {exc}")
            record_post_status(
                state,
                guid=episode["guid"],
                title=episode["title"],
                pub_date=episode["pub_date"],
                result="duplicate",
                message=str(exc),
            )
            posted_guids.add(episode["guid"])
            state["posted_guids"] = sorted(posted_guids)
            state.pop("last_error", None)
            state["last_post"] = {
                "guid": episode["guid"],
                "title": episode["title"],
                "pub_date": episode["pub_date"],
                "tweet_id": state.get("last_post", {}).get("tweet_id"),
            }
            save_state(state)
            print("Duplicate content treated as already posted.")
            return 0
    assert response is not None
    posted_guids.add(episode["guid"])
    state["posted_guids"] = sorted(posted_guids)
    state.pop("last_error", None)
    state["last_post"] = {
        "guid": episode["guid"],
        "title": episode["title"],
        "pub_date": episode["pub_date"],
        "tweet_id": response.get("data", {}).get("id"),
    }
    record_post_status(
        state,
        guid=episode["guid"],
        title=episode["title"],
        pub_date=episode["pub_date"],
        result="posted",
        tweet_id=state["last_post"]["tweet_id"],
    )
    save_state(state)
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        try:
            state = load_state()
            record_post_status(state, result="error", message=str(exc))
            state["last_error"] = str(exc)
            save_state(state)
        except Exception:
            pass
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
