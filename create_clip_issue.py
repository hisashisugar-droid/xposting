#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen


def env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def require_env(name: str) -> str:
    value = env(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def build_issue() -> dict[str, str]:
    episode_title = env("EPISODE_TITLE", "最新回")
    pub_date = env("EPISODE_PUB_DATE")
    episode_url = env("EPISODE_URL")
    clip_download_url = require_env("CLIP_DOWNLOAD_URL")
    clip_filename = env("CLIP_FILENAME", "spotify_clip.mp4")
    clip_start_seconds = env("CLIP_START_SECONDS")
    clip_seconds = env("CLIP_SECONDS", "15")
    github_run_url = env("GITHUB_RUN_URL")
    mention = env("NOTIFY_MENTION", "@hisashisugar-droid")

    title = f"Spotify Clips動画ができました: {episode_title}"
    lines = [
        f"{mention}",
        "",
        "Spotify Clips用のショート動画を作成しました。",
        "",
        f"- エピソード: {episode_title}",
    ]
    if pub_date:
        lines.append(f"- 公開日時: {pub_date}")
    if episode_url:
        lines.append(f"- エピソードURL: {episode_url}")
    if clip_start_seconds:
        lines.append(f"- 切り出し位置: {clip_start_seconds}秒あたりから{clip_seconds}秒")
    else:
        lines.append(f"- 長さ: {clip_seconds}秒")
    lines.extend(
        [
            f"- ファイル名: {clip_filename}",
            "",
            f"ダウンロード: {clip_download_url}",
        ]
    )
    if github_run_url:
        lines.append(f"GitHub Actions実行ログ: {github_run_url}")
    lines.append("")
    lines.append("artifactの保持期間はワークフロー設定に従います。")

    return {"title": title, "body": "\n".join(lines)}


def create_issue(payload: dict[str, str]) -> dict:
    repository = require_env("GITHUB_REPOSITORY")
    token = require_env("GITHUB_TOKEN")
    request = Request(
        f"https://api.github.com/repos/{repository}/issues",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "ningenradio-spotify-clips/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    issue = create_issue(build_issue())
    print(f"Created issue: {issue.get('html_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
