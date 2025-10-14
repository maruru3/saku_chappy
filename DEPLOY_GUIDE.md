# 🚀 Saku Chappy デプロイ完全ガイド

このガイドに従えば、初心者でも5分でLINE Botをデプロイできます！

## 📋 事前準備

### 必要なもの
- ✅ GitHubアカウント（無料）
- ✅ LINEアカウント
- ✅ OpenAI APIアカウント（クレジットカード必要、$5〜）

---

## ステップ1: LINE Developersでの設定 (5分)

### 1-1. LINE Developers Consoleにログイン

1. [LINE Developers Console](https://developers.line.biz/console/) にアクセス
2. LINEアカウントでログイン

### 1-2. プロバイダーの作成

1. 「作成」ボタンをクリック
2. プロバイダー名を入力（例: `マイBot開発`）

### 1-3. チャネルの作成

1. 「Messaging API」を選択
2. 以下を入力:
   - **チャネル名**: `Saku Chappy`
   - **チャネル説明**: `ChatGPT連携LINE Bot`
   - **大業種**: `個人`
   - **小業種**: `個人（その他）`
3. 利用規約に同意して「作成」

### 1-4. 必要な情報を取得

#### Channel Secret の取得
1. 「チャネル基本設定」タブ
2. **Channel Secret** をコピー → メモ帳に保存

#### Channel Access Token の取得
1. 「Messaging API設定」タブ
2. 下にスクロールして **Channel access token (long-lived)** を探す
3. 「発行」ボタンをクリック
4. 表示されたトークンをコピー → メモ帳に保存

⚠️ **重要**: これらは絶対に公開しないでください！

---

## ステップ2: OpenAI APIキーの取得 (3分)

### 2-1. OpenAIアカウント作成

1. [OpenAI Platform](https://platform.openai.com/) にアクセス
2. 「Sign up」でアカウント作成

### 2-2. クレジット購入

1. 左メニュー「Settings」→「Billing」
2. 「Add payment method」でクレジットカード登録
3. 最低 $5 をチャージ（初回は$5推奨）

💡 **参考料金**:
- テキスト会話: 約 $0.01/100往復
- 画像認識: 約 $0.01/枚
- 音声認識: 約 $0.006/分

### 2-3. APIキー生成

1. 左メニュー「API keys」
2. 「Create new secret key」をクリック
3. 名前を入力（例: `LINE Bot`）
4. 表示されたキーをコピー → メモ帳に保存

⚠️ **一度しか表示されません！必ず保存してください**

---

## ステップ3: Render.comでのデプロイ (5分)

### 3-1. Render.comアカウント作成

1. [Render.com](https://render.com/) にアクセス
2. 「Get Started For Free」をクリック
3. 「GitHub」でサインアップ

### 3-2. GitHubリポジトリを接続

1. Render ダッシュボードで「New +」→「Web Service」をクリック
2. 「Connect a repository」でGitHubを選択
3. `maruru3/saku_chappy` を検索して「Connect」

### 3-3. サービス設定

以下の項目を入力:

| 項目 | 値 | 説明 |
|------|-----|------|
| **Name** | `saku-chappy` | 任意の名前（URLになります） |
| **Region** | `Singapore` | 日本に最も近いリージョン |
| **Branch** | `main` | デプロイするブランチ |
| **Runtime** | `Python 3` | 自動検出されます |
| **Build Command** | `pip install -r requirements.txt` | 自動入力済み |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` | 重要！ |
| **Instance Type** | `Free` | 無料プラン |

### 3-4. 環境変数の設定

「Environment」セクションで「Add Environment Variable」をクリックし、以下を**すべて**追加:

#### ✅ 環境変数1
- **Key**: `LINE_CHANNEL_ACCESS_TOKEN`
- **Value**: （ステップ1-4でコピーしたLINEトークン）

#### ✅ 環境変数2
- **Key**: `LINE_CHANNEL_SECRET`
- **Value**: （ステップ1-4でコピーしたLINEシークレット）

#### ✅ 環境変数3
- **Key**: `OPENAI_API_KEY`
- **Value**: （ステップ2-3でコピーしたOpenAIキー）

#### ✅ 環境変数4
- **Key**: `SYSTEM_PROMPT`
- **Value**: `あなたはLINE上で丁寧に応答する日本語アシスタントです。`

### 3-5. デプロイ開始

1. 「Create Web Service」をクリック
2. デプロイ開始（3〜5分かかります）
3. ログに `Application startup complete` が表示されれば成功！

### 3-6. デプロイ完了後のURL確認

画面左上に表示されるURLをコピー（例）:
```
https://saku-chappy.onrender.com
```

---

## ステップ4: LINE Webhook URLの設定 (2分)

### 4-1. Webhook URLの設定

1. [LINE Developers Console](https://developers.line.biz/console/) に戻る
2. 作成したチャネルを選択
3. 「Messaging API設定」タブ
4. 下にスクロールして **Webhook URL** を探す
5. 以下の形式で入力:
   ```
   https://saku-chappy.onrender.com/webhook
   ```
   （`saku-chappy` の部分はRender.comで設定した名前）
6. 「更新」をクリック

### 4-2. Webhook検証

1. **Webhook URL** の横の「検証」ボタンをクリック
2. 「成功」と表示されればOK！

❌ **失敗する場合**:
- URLの最後に `/webhook` がついているか確認
- Render.comのデプロイが完了しているか確認
- 5分待ってから再試行

### 4-3. Webhookを有効化

1. **Webhookの利用** をオンにする（トグルボタン）

### 4-4. 応答メッセージをオフにする

1. 同じページの下の方にある **応答メッセージ** を探す
2. 「編集」をクリック
3. **応答メッセージ** を「オフ」にする
4. 保存

---

## ステップ5: 動作確認 (1分)

### 5-1. Bot を友だち追加

1. LINE Developers Console の「Messaging API設定」タブ
2. **QRコード** をスマホのLINEで読み取る
3. 友だち追加

### 5-2. テストメッセージを送信

LINEで以下を試してみましょう:

1. **テキスト**: `こんにちは`
   - → ChatGPTが返信すれば成功！

2. **画像送信**: 何でもいいので画像を送る
   - → GPT-4oが画像を説明

3. **音声送信**: ボイスメッセージを送る
   - → Whisperで文字起こし＋要約

4. **コマンド**: `/history`
   - → 会話履歴の件数を表示

---

## 🎉 完成！

おめでとうございます！あなただけのLINE Botが完成しました。

---

## 📊 料金について

### Render.com（無料）
- ✅ 完全無料
- ⚠️ 15分無通信でスリープ（次のメッセージで自動起動、10〜30秒かかる）
- 💡 有料プラン: $7/月でスリープなし

### OpenAI API（従量課金）
- gpt-4o (テキスト): 約 $0.01/100往復
- gpt-4o-vision (画像): 約 $0.01/枚
- whisper (音声): 約 $0.006/分

**例**: 1日10回会話 → 月$3程度

---

## 🔧 カスタマイズ

### Botの性格を変える

Render.com の環境変数 `SYSTEM_PROMPT` を変更:

**例**:
```
関西弁で話すフレンドリーなアシスタントやで！
```

### より安価なモデルに変更

[main.py:157](main.py#L157) を編集:
```python
"model": "gpt-4o-mini",  # gpt-4oの1/10の料金
```

→ GitHub にプッシュすると Render.com が自動再デプロイ

---

## ❓ トラブルシューティング

### Botが返信しない

1. **Render.comのログ確認**:
   - Dashboard → Service → Logs
   - エラーメッセージがないか確認

2. **環境変数の確認**:
   - すべて正しく設定されているか
   - 余分なスペースが入っていないか

3. **OpenAI残高確認**:
   - [Usage](https://platform.openai.com/usage) でクレジットが残っているか

### Webhook検証が失敗する

1. URLに `/webhook` がついているか
2. Render.comのデプロイが完了しているか（ログ確認）
3. 以下のURLに直接アクセスしてみる:
   ```
   https://saku-chappy.onrender.com/health
   ```
   → `{"status":"ok"}` が表示されればOK

### 初回の返信が遅い

- Render.com無料プランは15分でスリープします
- 初回リクエストで起動するため10〜30秒かかります
- **解決策**: 有料プラン ($7/月) にアップグレード

---

## 📮 サポート

問題が解決しない場合:

1. [GitHub Issues](https://github.com/maruru3/saku_chappy/issues) で質問
2. エラーログを添付してください

---

## 🚀 次のステップ

- [ ] OpenAI APIの使用量をモニタリング
- [ ] Botの性格をカスタマイズ
- [ ] 有料プランでスリープを無効化
- [ ] 他の機能を追加（例: 画像生成、Web検索など）

頑張ってください！ 🎉
