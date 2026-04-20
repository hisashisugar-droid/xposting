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
