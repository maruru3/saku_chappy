# 🔧 画像404エラーの完全解決ガイド

## 現在の状態

```
✅ Webhook: 正常に届いている
✅ メッセージID: 取得できている (583412371386269715)
✅ 署名検証: 成功している
❌ 画像コンテンツ取得: 404エラー
```

**根本原因**: Channel Access Token に **画像コンテンツ取得の権限がない**

---

## 🚨 必ず実行してください

### 解決策1: Channel Access Token を完全に再発行（推奨）

#### 手順

1. [LINE Developers Console](https://developers.line.biz/console/) にログイン
2. チャネルを選択
3. **「チャネル基本設定」** タブを開く
4. 下にスクロールして **「チャネルアクセストークン」** セクションを探す

#### ⚠️ 重要: 古いトークンを削除してから新規発行

5. 既存のトークンの横にある **「削除」** ボタンをクリック
6. 確認ダイアログで **「削除」** を確定
7. **「発行」** ボタンをクリック
8. **新しいトークンが表示されます**（これは1回しか表示されません！）
9. トークンをコピー

#### Render.comで環境変数を更新

10. [Render Dashboard](https://dashboard.render.com/) を開く
11. `saku-chappy` サービスをクリック
12. 左メニュー **Environment** をクリック
13. `LINE_CHANNEL_ACCESS_TOKEN` を探す
14. **Edit** をクリック
15. 新しいトークンを貼り付け
16. **Save Changes** をクリック

→ 自動的に再デプロイが始まります（2〜3分）

---

### 解決策2: チャネルの権限設定を確認

#### LINE Developers Console

1. **「チャネル基本設定」** タブ
2. **「チャネルの種類」** を確認
   - ✅ `Messaging API` であること

3. **「アサーション署名キー」** セクション（もしあれば）
   - これは無視してOK

#### LINE Official Account Manager

1. LINE Developers Console → **Messaging API設定** タブ
2. **「LINE Official Account Manager」** リンクをクリック
3. **設定** → **応答設定**

**必須の設定**:
```
✅ チャット: オン  ← 重要！
❌ 応答メッセージ: オフ  ← 重要！
✅ Webhook: オン
```

**「チャット」がオフだと画像の送受信ができません！**

---

## 🔍 なぜ404エラーが起きるのか？

### LINE APIの仕様

1. ユーザーが画像を送信
2. LINEサーバーに画像が一時保存される
3. Webhookでメッセージイベントが送信される（✅ これは届いている）
4. Botが `/v2/bot/message/{messageId}/content` にアクセス
5. **トークンに権限がないと404が返る** ← ここで失敗

### トークンの権限（スコープ）

Channel Access Tokenには以下のスコープが必要：
- `chat:read` - メッセージ読み取り
- `chat:write` - メッセージ送信
- **`profile` - ユーザープロフィール（画像含む）**

古いトークンや手動で発行したトークンは、これらのスコープが不足している可能性があります。

---

## ✅ 確認チェックリスト

### LINE Developers Console

- [ ] チャネルの種類: `Messaging API`
- [ ] Channel Access Token: 削除→新規発行済み
- [ ] トークンをRender.comに設定済み
- [ ] Webhook URL: `https://saku-chappy.onrender.com/webhook`
- [ ] Webhook検証: 成功（緑のチェックマーク）

### LINE Official Account Manager

- [ ] チャット: **オン**
- [ ] 応答メッセージ: **オフ**
- [ ] Webhook: **オン**
- [ ] 応答モード: Bot または Webhook

### Render.com

- [ ] 環境変数 `LINE_CHANNEL_ACCESS_TOKEN`: 新しいトークン
- [ ] 環境変数 `LINE_CHANNEL_SECRET`: 設定済み
- [ ] 環境変数 `OPENAI_API_KEY`: 設定済み
- [ ] デプロイ完了: "Your service is live 🎉"

---

## 🧪 テスト手順

### 1. デプロイ完了を確認

Render.com の Logs タブで:
```
==> Your service is live 🎉
```
が表示されるまで待つ（2〜3分）

### 2. ヘルスチェック

ブラウザで以下にアクセス:
```
https://saku-chappy.onrender.com/health
```

以下が表示されればOK:
```json
{
  "status": "ok",
  "has_line_token": true,
  "has_openai_key": true,
  "has_channel_secret": true
}
```

### 3. テキストメッセージ

LINEで:
```
こんにちは
```
→ ChatGPTの返信が来ればOK

### 4. 画像メッセージ（本題）

LINEで画像を送信

**成功パターン**:
```
この画像には○○が写っています...
```

**失敗パターン**:
```
申し訳ございません。処理中にエラーが発生しました。
```
→ まだトークンの権限不足

---

## 🔧 それでも解決しない場合

### 最終手段: チャネルを再作成

1. **新しいチャネルを作成**
   - LINE Developers Console
   - プロバイダーを選択
   - 「チャネルを作成」
   - Messaging API を選択

2. **新しいトークンとシークレットを取得**

3. **Render.comの環境変数を更新**

4. **LINE Webhook URLを設定**

5. **新しいBotを友だち追加**

---

## 📊 デバッグ情報

もし上記で解決しない場合、以下の情報を収集してください:

### LINE Developers Console

1. **Messaging API設定** → **Webhook送信ログ**
   - 最新の画像送信時のログ
   - リクエストボディ
   - レスポンスステータス

2. **チャネル基本設定**
   - チャネルID（公開してもOK）
   - チャネルの種類
   - プランアイコン

### Render.com Logs

画像送信時のログ全体（既に提供済み）

### LINE Official Account Manager

スクリーンショット:
- 応答設定画面
- チャット設定画面

---

## 📞 サポート

GitHub Issues で質問できます:
[https://github.com/maruru3/saku_chappy/issues](https://github.com/maruru3/saku_chappy/issues)

以下の情報を添えてください:
- Render.com のログ（トークン部分は隠す）
- LINE設定のスクリーンショット（トークン部分は隠す）
- エラーメッセージ

---

## 🎉 成功したら

画像認識が動作したら、ぜひ:
- GitHubリポジトリに ⭐ Star をつける
- Issuesで「解決しました！」と報告
- 他の人のために解決方法を共有

頑張ってください！
