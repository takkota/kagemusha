---
name: slack-toolkit
description: >
  Slack基本操作のツールキット。メッセージリンク解析、メッセージ読み取り、メッセージ送信、ファイルアップロード、リアクション追加の機能を提供する。
---

# Slack Toolkit

Slack操作に必要な基本機能を提供するツールキット。

## メッセージリンク解析

SlackメッセージリンクのURLからチャンネルIDとタイムスタンプを抽出する。

**URL形式:**
```
https://xxx.slack.com/archives/{channel_id}/p{timestamp_without_dot}
```

- `channel_id`: `/archives/` 以降の部分（例: `C01ABCDEF`）
- `timestamp`: `p` 以降の数値の先頭10桁の後にドットを挿入（例: `p1234567890123456` → `1234567890.123456`）

## メッセージ読み取り

| MCP | ツール | 用途 |
|-----|--------|------|
| claude_ai_Slack | `slack_read_thread` | スレッド全体を取得 |
| claude_ai_Slack | `slack_read_channel` | チャンネルの周辺メッセージを取得 |

- スレッドの場合は `slack_read_thread` を使用
- スレッドでない場合は `slack_read_channel` で周辺メッセージを取得

## メッセージ送信

| MCP | ツール | 用途 |
|-----|--------|------|
| claude_ai_Slack | `slack_send_message` | Slackにメッセージを送信・返信 |

## 添付画像のダウンロードと解析

Slackメッセージに画像ファイルが添付されている場合、`scripts/download_slack_files.sh` を使用してローカルにダウンロードし、Readツールで画像を閲覧・解析できる。

**使用方法:**

```bash
scripts/download_slack_files.sh <channel_id> <message_timestamp>
```

- ダウンロードされた画像は `/tmp/slack_files/<timestamp>/` に保存される
- スクリプトはダウンロードしたファイルのパスを1行ずつ出力する
- 画像ファイル（image/png, image/jpeg, image/gif, image/webp等）のみを対象とする
- 画像がない場合は "No image files found in this message." と出力される

**運用フロー:**

1. `slack_read_thread` や `slack_read_channel` でメッセージを読み取った際に、画像添付の存在を示す情報があれば本スクリプトを実行する
2. 出力されたファイルパスをReadツールで読み取り、画像の内容を解析する
3. 解析結果をSlackへの回答に反映する

## ファイルアップロード

Slack MCPにはファイルアップロードツールがないため、`scripts/upload_file.sh` を使用してSlack files.uploadV2 APIを直接呼び出す。
環境変数 `SLACK_USER_TOKEN` が必要。

**使用方法:**

```bash
scripts/upload_file.sh <channel_id> <file_path> [initial_comment] [thread_ts]
```

- `channel_id`: アップロード先のチャンネルID
- `file_path`: アップロードするファイルのパス
- `initial_comment`: ファイルと一緒に投稿するメッセージ（省略可）
- `thread_ts`: スレッドに投稿する場合の親メッセージのタイムスタンプ（省略可）
- APIの詳細は [references/slack_files_upload_api.md](references/slack_files_upload_api.md) を参照

## リアクション追加

Slack MCPにはリアクション追加ツールがないため、`scripts/add_reaction.sh` を使用してSlack APIを直接呼び出す。
環境変数 `SLACK_USER_TOKEN` が必要。

**使用方法:**

```bash
scripts/add_reaction.sh <channel_id> <message_timestamp> [emoji_name]
```

- デフォルトの絵文字は `eyes`
- APIの詳細は [references/slack_reaction_api.md](references/slack_reaction_api.md) を参照
