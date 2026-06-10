#!/usr/bin/env python3
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


DEFAULT_TO = "hisashi.sugar@gmail.com"
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = "587"
DEFAULT_SMTP_USE_SSL = "0"


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


def smtp_address() -> str:
    return env("SMTP_USERNAME") or env("SMTP_FROM") or env("GMAIL_ADDRESS") or DEFAULT_TO


def smtp_password() -> str:
    password = env("SMTP_PASSWORD") or env("GMAIL_APP_PASSWORD")
    if not password:
        raise RuntimeError("Missing SMTP_PASSWORD or GMAIL_APP_PASSWORD.")
    return password


def build_message() -> EmailMessage:
    to_address = env("EMAIL_TO", DEFAULT_TO)
    from_address = env("SMTP_FROM") or env("SMTP_USERNAME") or env("GMAIL_ADDRESS") or DEFAULT_TO

    episode_title = env("EPISODE_TITLE", "最新回")
    pub_date = env("EPISODE_PUB_DATE")
    episode_url = env("EPISODE_URL")
    clip_download_url = require_env("CLIP_DOWNLOAD_URL")
    clip_filename = env("CLIP_FILENAME", "spotify_clip.mp4")
    clip_start_seconds = env("CLIP_START_SECONDS")
    clip_seconds = env("CLIP_SECONDS", "15")
    github_run_url = env("GITHUB_RUN_URL")

    subject = f"Spotify Clips用ショート動画ができました: {episode_title}"
    lines = [
        "Spotify Clips用のショート動画を作成しました。",
        "",
        f"エピソード: {episode_title}",
    ]
    if pub_date:
        lines.append(f"公開日時: {pub_date}")
    if episode_url:
        lines.append(f"エピソードURL: {episode_url}")
    if clip_start_seconds:
        lines.append(f"切り出し位置: {clip_start_seconds}秒あたりから{clip_seconds}秒")
    else:
        lines.append(f"長さ: {clip_seconds}秒")
    lines.extend(
        [
            "",
            f"ダウンロード: {clip_download_url}",
            f"ファイル名: {clip_filename}",
        ]
    )
    if github_run_url:
        lines.extend(["", f"GitHub Actions実行ログ: {github_run_url}"])

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_address
    message["To"] = to_address
    message.set_content("\n".join(lines))
    return message


def send(message: EmailMessage) -> None:
    host = env("SMTP_HOST", DEFAULT_SMTP_HOST)
    port = int(env("SMTP_PORT", DEFAULT_SMTP_PORT))
    username = smtp_address()
    password = smtp_password()
    use_ssl = env("SMTP_USE_SSL", DEFAULT_SMTP_USE_SSL).lower() in {"1", "true", "yes"}

    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
            server.login(username, password)
            server.send_message(message)
        return

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(username, password)
        server.send_message(message)


def main() -> int:
    message = build_message()
    send(message)
    print(f"Sent clip email to {message['To']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
