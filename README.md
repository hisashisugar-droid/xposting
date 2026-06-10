# ニンゲン広告社 X 自動投稿

RSSの新着回を監視して、未投稿のエピソードだけをXへ自動投稿します。
GitHub Actions に載せると、PCが起動していなくても月曜・水曜の朝に自動投稿できます。

## 投稿フォーマット

```text
🔥更新🔥
{更新回タイトル}
{RSS概要の短い要約}
Spotify: {短縮URL}
Apple: {短縮URL}
```

## ファイル

- `post_new_episode.py`: 監視と投稿の本体
- `run_post.sh`: `.env` を読んで本体を起動するランナー
- `.github/workflows/podcast-x-post.yml`: GitHub Actions の定期実行ワークフロー
- `create_spotify_clip.py`: RSS最新回から15秒音声を抜き出し、縦長MP4を作るスクリプト
- `create_clip_issue.py`: 生成したMP4のダウンロードリンクをGitHub Issueで通知するスクリプト
- `.github/workflows/spotify-clips.yml`: Spotify Clips用動画を毎週水曜正午に生成するワークフロー
- `assets/`: Clips動画に使う静止画
- `clip_state.json`: Clips生成済みエピソードの記録
- `wake_observer.swift`: スリープ復帰時に投稿チェックを走らせる監視
- `com.hacshun.ningenradio.wake-check.plist`: `launchd` 用のLaunchAgent定義
- `state.json`: 投稿済みエピソードを記録する状態ファイル
- `.env.example`: 必要な環境変数の例

## 必要な環境変数

- `X_CONSUMER_KEY`
- `X_CONSUMER_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`
- `XGD_API_KEY` (`x.gd` で短縮URLを作る場合)

X APIのユーザーコンテキストで投稿するため、X Appの資格情報が必要です。

## GitHub Actions での運用

このプロジェクトは GitHub Actions でそのまま動かせます。
ワークフローは [podcast-x-post.yml](/Users/hacshun/Documents/Codex/2026-04-18-x-rss-spotify-apple-podcast-url/.github/workflows/podcast-x-post.yml) にあります。

GitHub 側で必要な Repository Secrets:

- `X_CONSUMER_KEY`
- `X_CONSUMER_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`
- `XGD_API_KEY`

スケジュール:

- 日本時間の月曜 17:00
- 日本時間の水曜 17:00

実装上は GitHub Actions の cron が UTC 基準なので、ワークフローでは `月曜 08:00 UTC` と `水曜 08:00 UTC` に設定しています。

GitHub Actions での初回セットアップ:

1. このディレクトリを GitHub リポジトリとして push する
2. GitHub の `Settings` → `Secrets and variables` → `Actions` で上記5つの Secrets を追加する
3. `Actions` タブで `Podcast X Post` を開く
4. `Run workflow` で手動実行して疎通確認する

`state.json` は投稿済みGUIDを保持するため、Actions 実行後に自動コミットされます。
これによって、同じエピソードの重複投稿を防ぎます。

## Spotify Clips 自動生成

毎週水曜の正午にRSSの最新回を確認し、最新回の音声から途中の15秒をランダムに抜き出して、Spotify Clips向けの縦長MP4を作成します。
映像は `assets/clip_cover.png`、または `assets/` 内の画像ファイルを使った静止画です。

出力仕様:

- 長さ: 15秒
- 解像度: 1080 x 1920 px
- 比率: 9:16 縦長
- 形式: MP4
- 音声: RSS enclosure の音声をAACに変換して含める

GitHub Actions ワークフロー:

- ファイル: `.github/workflows/spotify-clips.yml`
- スケジュール: 日本時間 水曜 12:00
- UTC cron: `0 3 * * 3`
- 生成物: GitHub Actions artifactとして14日間保持
- 通知: artifactのダウンロードURLをGitHub Issueで通知

GitHub 側で追加のRepository Secretは不要です。
ワークフロー内の `GITHUB_TOKEN` で通知Issueを作成します。

通知Issueには以下が入ります。

- `@hisashisugar-droid` へのメンション
- エピソードタイトル
- artifactのダウンロードURL
- GitHub Actions実行ログURL
- 音声の切り出し位置

同じ最新回への重複生成を防ぐため、生成済みGUIDは `clip_state.json` に保存され、成功後に自動コミットされます。
手動で再生成したい場合は、Actionsの `Spotify Clips` → `Run workflow` で `force` を有効にします。

### カバー画像

動画の静止画は、まず `assets/clip_cover.png` を探します。
このファイルがない場合は、`assets/` 内の `.jpg` `.jpeg` `.png` `.webp` のいずれかを自動で使います。
別の写真を使う場合は、`assets/clip_cover.png` として置くか、`assets/` 内の画像を差し替えてください。
縦長写真ならそのまま中央クロップ、横長写真なら9:16に中央クロップされます。

### ローカルテスト

ローカルで試すには `ffmpeg` と `ffprobe` が必要です。

```bash
cd /Users/hacshun/Documents/Codex/2026-04-18-x-rss-spotify-apple-podcast-url
python3 create_spotify_clip.py --force
```

生成されたMP4は `clip_outputs/` に出ます。

## 手動テスト

```bash
cd /Users/hacshun/Documents/Codex/2026-04-18-x-rss-spotify-apple-podcast-url
export DRY_RUN=1
python3 post_new_episode.py
```

実投稿する場合は `DRY_RUN` を外した上で、上記4つのX環境変数をセットしてください。

`.env` を置く場合は、`.env.example` をコピーして値を入れた上で `./run_post.sh` を実行してください。

## スリープ復帰時チェック

`wake_observer.swift` を `launchd` のLaunchAgentとして常駐させると、Macのスリープ復帰時にも `run_post.sh` を実行します。
実行物は `~/Library/Application Support/NingenRadioXPost` に配置して使う想定です。

配置先:

- `~/Library/LaunchAgents/com.hacshun.ningenradio.wake-check.plist`

読み込み例:

```bash
mkdir -p ~/Library/LaunchAgents
cp /Users/hacshun/Documents/Codex/2026-04-18-x-rss-spotify-apple-podcast-url/com.hacshun.ningenradio.wake-check.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.hacshun.ningenradio.wake-check.plist
```

標準出力と標準エラーは、この作業ディレクトリ内のログファイルに出ます。
