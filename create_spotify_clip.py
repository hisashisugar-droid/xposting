#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


RSS_URL = "https://anchor.fm/s/9bb1c5d8/podcast/rss"
CLIP_SECONDS = 15.0
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
TIMEOUT = 45
STATE_PATH = Path(__file__).with_name("clip_state.json")
DEFAULT_COVER_PATH = Path(__file__).with_name("assets") / "clip_cover.png"
ASSET_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_OUTPUT_DIR = Path(__file__).with_name("clip_outputs")
USER_AGENT = "ningenradio-spotify-clips/1.0"


@dataclass
class Episode:
    guid: str
    title: str
    pub_date: str
    episode_url: str
    audio_url: str
    audio_type: str


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                return response.read()
        except (TimeoutError, URLError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    if last_error:
        raise last_error
    raise RuntimeError(f"Failed to fetch {url}")


def download(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                with destination.open("wb") as output:
                    shutil.copyfileobj(response, output)
            return
        except (TimeoutError, URLError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    if last_error:
        raise last_error
    raise RuntimeError(f"Failed to download {url}")


def latest_episode(rss_url: str) -> Episode:
    root = ET.fromstring(fetch_bytes(rss_url))
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("RSS channel not found.")

    items = channel.findall("item")
    if not items:
        raise RuntimeError("No podcast episodes found in RSS feed.")

    def item_date(item: ET.Element) -> float:
        pub_date = (item.findtext("pubDate") or "").strip()
        try:
            return parsedate_to_datetime(pub_date).timestamp()
        except Exception:
            return 0.0

    item = max(items, key=item_date)
    enclosure = item.find("enclosure")
    if enclosure is None or not enclosure.attrib.get("url"):
        raise RuntimeError("Latest RSS item does not contain an audio enclosure URL.")

    title = (item.findtext("title") or "podcast episode").strip()
    guid = (item.findtext("guid") or item.findtext("link") or title).strip()
    return Episode(
        guid=guid,
        title=title,
        pub_date=(item.findtext("pubDate") or "").strip(),
        episode_url=(item.findtext("link") or "").strip(),
        audio_url=enclosure.attrib["url"].strip(),
        audio_type=enclosure.attrib.get("type", "").strip(),
    )


def resolve_binary(name: str) -> str:
    candidates = [
        shutil.which(name),
        f"/opt/homebrew/bin/{name}",
        f"/usr/local/bin/{name}",
        f"/usr/bin/{name}",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit(f"Required binary '{name}' was not found. Install ffmpeg first.")


def run(cmd: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, check=True, text=True, capture_output=capture_output)
    except subprocess.CalledProcessError as exc:
        if capture_output and exc.stderr:
            print(exc.stderr, file=sys.stderr)
        raise


def ffprobe_duration(path: Path) -> float:
    result = run(
        [
            resolve_binary("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
    )
    return float(result.stdout.strip())


def choose_start(duration: float, clip_seconds: float) -> float:
    if duration <= clip_seconds:
        return 0.0

    max_start = duration - clip_seconds
    lead_margin = min(max(10.0, duration * 0.10), max_start)
    tail_margin = min(max(10.0, duration * 0.10), max_start - lead_margin)
    latest_start = duration - clip_seconds - tail_margin
    if latest_start <= lead_margin:
        lead_margin = max_start * 0.25
        latest_start = max_start * 0.75
    if latest_start <= lead_margin:
        return max_start / 2.0
    return random.SystemRandom().uniform(lead_margin, latest_start)


def extension_from_audio_url(url: str, audio_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".mp3", ".m4a", ".aac", ".wav", ".ogg"}:
        return suffix
    if "mp4" in audio_type or "m4a" in audio_type:
        return ".m4a"
    if "mpeg" in audio_type or "mp3" in audio_type:
        return ".mp3"
    return ".audio"


def slugify(value: str, limit: int = 72) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "-", value)
    value = re.sub(r"\s+", "_", value).strip("._- ")
    if not value:
        return "spotify_clip"
    return value[:limit].rstrip("._- ")


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"processed_guids": [], "clips": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_cover_path(path: Path) -> Path:
    if path.exists():
        return path
    if path != DEFAULT_COVER_PATH:
        raise SystemExit(f"Cover image not found: {path}")

    assets_dir = DEFAULT_COVER_PATH.parent
    candidates = sorted(
        candidate
        for candidate in assets_dir.iterdir()
        if candidate.is_file()
        and not candidate.name.startswith(".")
        and candidate.suffix.lower() in ASSET_IMAGE_EXTENSIONS
    )
    if candidates:
        return candidates[0]
    raise SystemExit(f"Cover image not found: {path}")


def write_github_output(values: dict[str, Any]) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as output:
        for key, value in values.items():
            text = str(value).replace("\n", " ").strip()
            output.write(f"{key}={text}\n")


def create_video(cover_path: Path, audio_path: Path, output_path: Path, start: float) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    video_filter = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},format=yuv420p"
    )
    run(
        [
            resolve_binary("ffmpeg"),
            "-y",
            "-loop",
            "1",
            "-framerate",
            "30",
            "-i",
            str(cover_path),
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{CLIP_SECONDS:.3f}",
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            video_filter,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a 15-second Spotify Clips promo video.")
    parser.add_argument("--rss-url", default=RSS_URL)
    parser.add_argument("--cover", type=Path, default=DEFAULT_COVER_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--state", type=Path, default=STATE_PATH)
    parser.add_argument("--force", action="store_true", help="Create a clip even if this episode is already processed.")
    args = parser.parse_args()

    cover_path = resolve_cover_path(args.cover)

    episode = latest_episode(args.rss_url)
    state = load_state(args.state)
    processed_guids = set(state.get("processed_guids", []))
    if episode.guid in processed_guids and not args.force:
        print(f"Latest episode already processed: {episode.title}")
        write_github_output(
            {
                "clip_created": "false",
                "episode_title": episode.title,
                "episode_guid": episode.guid,
            }
        )
        return 0

    work_dir = args.output_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    audio_path = work_dir / f"latest{extension_from_audio_url(episode.audio_url, episode.audio_type)}"
    download(episode.audio_url, audio_path)

    duration = ffprobe_duration(audio_path)
    start = choose_start(duration, CLIP_SECONDS)
    filename = f"{slugify(episode.title)}_clip.mp4"
    output_path = args.output_dir / filename
    create_video(cover_path, audio_path, output_path, start)

    stat = output_path.stat()
    clip_record = {
        "guid": episode.guid,
        "title": episode.title,
        "pub_date": episode.pub_date,
        "episode_url": episode.episode_url,
        "audio_url": episode.audio_url,
        "clip_path": str(output_path),
        "clip_filename": output_path.name,
        "clip_seconds": CLIP_SECONDS,
        "audio_duration_seconds": round(duration, 3),
        "clip_start_seconds": round(start, 3),
        "file_size_bytes": stat.st_size,
        "created_at_unix": int(time.time()),
    }
    state.setdefault("processed_guids", [])
    if episode.guid not in state["processed_guids"]:
        state["processed_guids"].append(episode.guid)
    state.setdefault("clips", []).append(clip_record)
    state["latest_clip"] = clip_record
    save_state(args.state, state)

    metadata_path = args.output_dir / "latest_clip.json"
    metadata_path.write_text(json.dumps(clip_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Created clip: {output_path}")
    print(f"Episode: {episode.title}")
    print(f"Clip start: {start:.3f}s / duration: {duration:.3f}s")
    write_github_output(
        {
            "clip_created": "true",
            "clip_path": output_path,
            "clip_filename": output_path.name,
            "metadata_path": metadata_path,
            "episode_title": episode.title,
            "episode_guid": episode.guid,
            "episode_url": episode.episode_url,
            "pub_date": episode.pub_date,
            "clip_start_seconds": f"{start:.3f}",
            "clip_seconds": f"{CLIP_SECONDS:.0f}",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
