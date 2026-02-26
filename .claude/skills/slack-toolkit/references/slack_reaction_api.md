# Slack Reactions API

## reactions.add

メッセージにリアクションを追加する。

### エンドポイント

POST `https://slack.com/api/reactions.add`

### ヘッダー

- `Authorization: Bearer ${SLACK_USER_TOKEN}`
- `Content-Type: application/json`

### リクエストボディ

- `channel` (string, required): チャンネルID
- `timestamp` (string, required): メッセージのタイムスタンプ
- `name` (string, required): 絵文字名（コロンなし、例: `eyes`）

### レスポンス (200)

```json
{
  "ok": true
}
```

### エラー例

- `already_reacted`: 既にリアクション済み
- `invalid_name`: 存在しない絵文字名
- `no_item_specified`: channel/timestampが不正

### チャンネルIDとタイムスタンプの取得

SlackメッセージリンクのURLフォーマット:
```
https://xxx.slack.com/archives/{channel_id}/p{timestamp_without_dot}
```

- `channel_id`: URLの`/archives/`以降の部分（例: `C01ABCDEF`）
- `timestamp`: `p`以降の数値にドットを挿入（例: `p1234567890123456` → `1234567890.123456`）
  - 先頭10桁の後にドットを挿入する
