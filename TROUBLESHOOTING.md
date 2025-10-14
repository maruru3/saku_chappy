# 🐛 トラブルシューティング - 画像が取得できない (404エラー)

## 問題の症状

画像を送信すると以下のエラーが返される：
```
申し訳ございません。処理中にエラーが発生しました。
エラー詳細: 502: LINE content fetch failed: 404
```

## 原因

LINE APIから画像コンテンツを取得する際に404エラーが発生しています。これは以下のいずれかが原因です：

1. **Channel Access Token が長期トークンではない**
2. **Webhookの再送信設定が原因**
3. **メッセージIDの有効期限切れ**

## 解決方法

### ✅ ステップ1: Channel Access Token の再発行

1. [LINE Developers Console](https://developers.line.biz/console/) にログイン
2. 該当のチャネルを選択
3. **Messaging API設定** タブを開く
4. **Channel access token (long-lived)** セクションまでスクロール
5. 既存のトークンがある場合は **「再発行」** をクリック
6. **新しいトークンをコピー**

### ✅ ステップ2: Render.com で環境変数を更新

1. [Render Dashboard](https://dashboard.render.com/) にアクセス
2. `saku-chappy` サービスを選択
3. 左メニューの **Environment** をクリック
4. `LINE_CHANNEL_ACCESS_TOKEN` を探す
5. **Edit** をクリックして、新しいトークンに置き換え
6. **Save Changes** をクリック

⚠️ **保存後、自動的に再デプロイされます（2〜3分）**

### ✅ ステップ3: LINE Bot の権限を確認

LINE Developers Console に戻って：

1. **Messaging API設定** タブ
2. **Bot情報** セクションで以下を確認:
   - ✅ **Bot のグループトーク参加**: オン
   - ✅ **友だち追加時あいさつ**: オフ（任意）
   - ✅ **自動応答メッセージ**: オフ（重要！）
   - ✅ **Webhook**: オン

### ✅ ステップ4: 再テスト

1. Render.comの再デプロイが完了するまで待つ（Logs で確認）
2. LINE Botに画像を再送信
3. 今度は画像の説明が返ってくるはずです

---

## 別の解決策: メッセージIDのデバッグ

上記で解決しない場合、以下を確認：

### デバッグ情報の確認

Render.com の **Logs** タブで以下を探す：

```
INFO:main:Message ID: 583136536086708246
INFO:main:URL: https://api.line.me/v2/bot/message/583136536086708246/content
INFO:main:Token prefix: <最初の20文字>...
```

### メッセージIDが表示されない場合

イベントの構造が想定と異なる可能性があります。ログで以下を探す：

```
INFO:main:Event data: {...}
```

このJSONを確認して、`message.id` の場所を特定してください。

---

## よくある質問

### Q: トークンを再発行したのに404が出る

**A**: 以下を確認してください：
1. Render.com で環境変数を **保存** したか
2. 再デプロイが完了したか（Logs で "Your service is live" を確認）
3. 古いトークンをコピーしていないか

### Q: テキストは動くが画像だけ動かない

**A**: Channel Access Token の **スコープ** が不足している可能性があります。トークンを再発行すると、通常は解決します。

### Q: 画像送信後、何も返信がない

**A**: Webhookのタイムアウトか、エラーハンドリングの問題です。Render.com の Logs を確認してください。

---

## さらに詳しいデバッグ

もし上記で解決しない場合、以下の情報を添えて Issue を作成してください：

1. Render.com のログ（画像送信時の全ログ）
2. LINE Developers Console のスクリーンショット（トークン部分は隠す）
3. 送信した画像のサイズと形式

[GitHub Issues](https://github.com/maruru3/saku_chappy/issues)
