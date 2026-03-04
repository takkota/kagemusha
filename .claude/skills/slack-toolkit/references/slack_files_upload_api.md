# Slack Files Upload V2 API

ファイルをSlackチャンネルにアップロードする。3ステップのAPIフローで構成される。

## Step 1: files.getUploadURLExternal

アップロード用の一時URLを取得する。

### エンドポイント

GET `https://slack.com/api/files.getUploadURLExternal`

### ヘッダー

- `Authorization: Bearer ${SLACK_USER_TOKEN}`

### パラメータ

- `filename` (string, required): ファイル名
- `length` (number, required): ファイルサイズ（バイト）

### レスポンス (200)

```json
{
  "ok": true,
  "upload_url": "https://files.slack.com/upload/v1/...",
  "file_id": "F01ABCDEF"
}
```

## Step 2: ファイルアップロード

Step 1で取得した `upload_url` にファイルをPOSTする。

### リクエスト

POST `{upload_url}`

- `Content-Type: multipart/form-data`
- `file`: アップロードするファイル

```bash
curl -s -X POST "$UPLOAD_URL" -F "file=@${FILE_PATH}"
```

## Step 3: files.completeUploadExternal

アップロードを完了し、チャンネルに共有する。

### エンドポイント

POST `https://slack.com/api/files.completeUploadExternal`

### ヘッダー

- `Authorization: Bearer ${SLACK_USER_TOKEN}`
- `Content-Type: application/json`

### リクエストボディ

- `files` (array, required): アップロードしたファイルの情報
  - `id` (string, required): Step 1で取得した `file_id`
  - `title` (string, optional): ファイルのタイトル
- `channel_id` (string, required): 共有先のチャンネルID
- `initial_comment` (string, optional): ファイルと一緒に投稿するメッセージ
- `thread_ts` (string, optional): スレッドに投稿する場合の親メッセージのタイムスタンプ

### レスポンス (200)

```json
{
  "ok": true,
  "files": [
    {
      "id": "F01ABCDEF",
      "title": "data.csv"
    }
  ]
}
```

### エラー例

- `invalid_auth`: トークンが無効
- `channel_not_found`: チャンネルIDが不正
- `not_in_channel`: チャンネルに参加していない
- `file_not_found`: file_idが不正または期限切れ
