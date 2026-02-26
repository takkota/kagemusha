# Kagemusha

Slackメンション・DM・スレッドリプライを監視し、自分宛のメッセージを検知したら `prompt_template.md` に基づいてClaude CLIを自動実行する常駐アプリ。

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env.example` をコピーして `.env` を作成し、各値を設定する。

```bash
cp .env.example .env
```

| 環境変数 | 必須 | 説明 |
|----------|------|------|
| `SLACK_USER_TOKEN` | Yes | Slack User OAuth Token (`xoxp-...`) |
| `SLACK_USER_NAME` | Yes | 自分のSlack表示名 |
| `SLACK_CHANNEL_IDS` | No | 監視対象チャンネルID（カンマ区切り、未設定時は全参加チャンネル） |
| `POLL_INTERVAL` | No | ポーリング間隔（秒、デフォルト60） |
| `SEARCH_BUFFER_SECONDS` | No | Search APIのインデックス遅延対策バッファ（秒、デフォルト180） |
| `THREAD_TRACK_DAYS` | No | メンションされたスレッドの追跡期間（日、デフォルト5） |
| `STATE_FILE` | No | 状態ファイルパス（デフォルト `.slack_monitor_state.json`） |

### 3. Slack User Tokenの必要スコープ

- `channels:history`, `channels:read`
- `groups:history`, `groups:read`
- `im:history`, `im:read`
- `mpim:history`, `mpim:read`
- `users:read`, `search:read`

### 4. 前提条件

- Python 3.6+
- [Claude CLI](https://github.com/anthropics/claude-code) がPATHに存在すること

## 起動

```bash
./run.sh
# or
python -m monitor.main
```

`Ctrl+C` または `SIGTERM` でグレースフルシャットダウン。

## 動作概要

ポーリング間隔ごとに以下の3段階で新着メッセージを検知:

1. **Search API** — `search.messages` で@メンションを横断検索
2. **スレッド追跡** — メンションされたスレッドの後続リプライを検知
3. **DMポーリング** — DM/self-DMの新着メッセージを検知

検知したメッセージごとにプロンプトテンプレートで `claude -p` を実行。処理済みメッセージはJSONファイルに記録し、TTLベースの重複排除で再処理を防止。

## プロンプトテンプレート

| ファイル | 説明 |
|----------|------|
| `prompt_template.md` | デフォルトテンプレート（git管理、直接編集しない） |
| `prompt_template.local.md` | ローカルオーバーライド（gitignore、カスタマイズ用） |

カスタマイズする場合:

```bash
cp prompt_template.md prompt_template.local.md
# prompt_template.local.md を編集
```

テンプレート内のプレースホルダー:
- `{{channel_id}}` — SlackチャンネルID
- `{{message_ts}}` — メッセージのタイムスタンプ

## ディレクトリ構成

```
kagemusha/
├── monitor/
│   ├── main.py           # ポーリングループ & オーケストレーション
│   ├── config.py         # .env読み込み、バリデーション
│   ├── slack_client.py   # Slack SDK ラッパー
│   ├── state.py          # JSON状態管理（処理済みID、スレッド追跡）
│   ├── skill_invoker.py  # claude CLIサブプロセス起動
│   └── message_filter.py # メッセージ分類（bot/system/self判定）
├── workspace/            # claude CLI実行ディレクトリ
│   └── .claude -> ../.claude
├── .claude/
│   └── skills/           # Claude Codeスキル
│       └── slack-toolkit/    # Slack操作ツールキット
├── prompt_template.md
├── run.sh
└── .env
```

### workspace/ ディレクトリ

`claude -p` は `workspace/` をカレントディレクトリとして実行される。プロジェクトルートの開発用 `CLAUDE.md` が読み込まれるのを回避するため。`.claude` へのシンボリックリンクによりスキルや設定は利用可能。
