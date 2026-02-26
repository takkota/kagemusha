# Slack Files API

## メッセージの添付ファイル取得

Slackメッセージに添付されたファイルは、`conversations.replies` または `conversations.history` APIのレスポンス内 `messages[].files[]` に含まれる。

### conversations.replies でファイル情報を取得

GET `https://slack.com/api/conversations.replies`

#### パラメータ

- `channel` (string, required): チャンネルID
- `ts` (string, required): スレッドの親メッセージのタイムスタンプ
- `limit` (number, optional): 取得するメッセージ数
- `inclusive` (boolean, optional): `ts` のメッセージ自体を含めるか

#### レスポンス内のファイル情報

```json
{
  "ok": true,
  "messages": [
    {
      "text": "メッセージ本文",
      "files": [
        {
          "id": "F01ABCDEF",
          "name": "screenshot.png",
          "title": "Screenshot",
          "mimetype": "image/png",
          "filetype": "png",
          "size": 123456,
          "url_private": "https://files.slack.com/files-pri/T.../screenshot.png",
          "url_private_download": "https://files.slack.com/files-tmb/T.../screenshot.png",
          "thumb_480": "https://files.slack.com/files-tmb/T.../screenshot_480.png"
        }
      ]
    }
  ]
}
```

### ファイルのダウンロード

`url_private` からファイルをダウンロードするには認証ヘッダーが必要。

```bash
curl -s -o output.png \
  -H "Authorization: Bearer ${SLACK_USER_TOKEN}" \
  "https://files.slack.com/files-pri/T.../screenshot.png"
```

### 主な画像MIMEタイプ

| mimetype | 拡張子 |
|----------|--------|
| image/png | .png |
| image/jpeg | .jpg, .jpeg |
| image/gif | .gif |
| image/webp | .webp |
| image/svg+xml | .svg |
