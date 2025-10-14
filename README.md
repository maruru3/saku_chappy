# 🤖 Saku Chappy - LINE Bot with ChatGPT

Pipedream から GitHub + Render.com へ移植した LINE Bot アプリケーション

## ✨ 機能

- ✅ **テキスト会話**: ChatGPT (gpt-4o) による自然な日本語対話
- ✅ **画像認識**: 送信した画像を GPT-4o Vision で説明
- ✅ **音声認識**: Whisper API で音声を文字起こし & 要約
- ✅ **会話履歴管理**: SQLite で最大10往復の会話を記憶
- ✅ **コマンド**:
  - `リセット` または `/reset`: 会話履歴をクリア
  - `/history`: 会話履歴の件数を確認

## 🏗️ アーキテクチャ

```
LINE Webhook → Render.com (FastAPI) → OpenAI API
                      ↓
                  SQLite DB
```

## 📦 技術スタック

- **Python 3.11+**
- **FastAPI**: Web フレームワーク
- **httpx**: 非同期 HTTP クライアント
- **SQLite**: 会話履歴の永続化
- **Render.com**: 無料ホスティング

## 🚀 デプロイ手順

### 1. GitHubリポジトリの準備

このリポジトリをフォークまたはクローン：

```bash
git clone https://github.com/maruru3/saku_chappy.git
cd saku_chappy
```

### 2. LINE Developersでの設定

1. [LINE Developers Console](https://developers.line.biz/console/) にログイン
2. 新規プロバイダー/チャネルを作成（Messaging API）
3. 以下の情報を取得:
   - **Channel Access Token** (長期)
   - **Channel Secret**

### 3. OpenAI APIキーの取得

1. [OpenAI Platform](https://platform.openai.com/) でアカウント作成
2. API Keys から新しいキーを生成

### 4. Render.comでのデプロイ

#### 4-1. Render.comアカウント作成

1. [Render.com](https://render.com/) にアクセス
2. GitHubアカウントでサインアップ（無料）

#### 4-2. Web Serviceの作成

1. Render ダッシュボードで **"New +"** → **"Web Service"** をクリック
2. GitHubリポジトリ `maruru3/saku_chappy` を選択
3. 以下の設定を入力:

| 項目 | 値 |
|------|-----|
| **Name** | `saku-chappy` (任意) |
| **Region** | `Singapore` (日本に最も近い) |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | `Free` |

#### 4-3. 環境変数の設定

"Environment" セクションで以下を追加:

| Key | Value |
|-----|-------|
| `LINE_CHANNEL_ACCESS_TOKEN` | （LINEで取得したトークン） |
| `LINE_CHANNEL_SECRET` | （LINEで取得したシークレット） |
| `OPENAI_API_KEY` | （OpenAIで取得したAPIキー） |
| `SYSTEM_PROMPT` | `あなたはLINE上で丁寧に応答する日本語アシスタントです。` |

#### 4-4. デプロイ実行

"Create Web Service" をクリック → 自動デプロイ開始

デプロイ完了後、以下のようなURLが発行されます:
```
https://saku-chappy.onrender.com
```

### 5. LINE Webhook URLの設定

1. LINE Developers Console に戻る
2. チャネル設定 → **Messaging API設定**
3. **Webhook URL** に以下を入力:
   ```
   https://saku-chappy.onrender.com/webhook
   ```
4. **Webhook の利用**: オンにする
5. **検証** ボタンで接続テスト（成功すればOK）

### 6. 動作確認

1. LINE公式アカウントを友だち追加
2. メッセージを送信 → ChatGPTが返信すれば成功！

## 🧪 ローカル開発

```bash
# 仮想環境作成
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# パッケージインストール
pip install -r requirements.txt

# 環境変数を .env ファイルに設定
cat > .env << EOF
LINE_CHANNEL_ACCESS_TOKEN=your_token
LINE_CHANNEL_SECRET=your_secret
OPENAI_API_KEY=your_key
SYSTEM_PROMPT=あなたはLINE上で丁寧に応答する日本語アシスタントです。
EOF

# サーバー起動
uvicorn main:app --reload

# 別ターミナルでテスト
curl http://localhost:8000/health
```

## 📝 プロジェクト構成

```
saku_chappy/
├── main.py                 # FastAPIアプリケーション本体
├── requirements.txt        # Pythonパッケージ
├── render.yaml            # Render.com設定（オプション）
├── .gitignore             # Git除外設定
├── README.md              # このファイル
└── line_chat_history.db   # SQLite DB (自動生成、gitignore済)
```

## 🔧 カスタマイズ

### システムプロンプトの変更

環境変数 `SYSTEM_PROMPT` を変更することで、Botの性格をカスタマイズできます:

```bash
# 例: フレンドリーな関西弁Bot
SYSTEM_PROMPT="あなたは関西弁で話すフレンドリーなアシスタントやで！"
```

### 会話履歴の保存件数を変更

[main.py:67](main.py#L67) の `LIMIT 20` を変更:

```python
# 最新30件（15往復）に変更
cursor.execute(
    "SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 30",
    (user_id,)
)
```

### GPTモデルの変更

[main.py:157](main.py#L157) のモデル名を変更:

```python
payload = {
    "model": "gpt-4o-mini",  # より安価なモデル
    "messages": messages,
    "temperature": 0.7,      # より創造的な応答
}
```

## 🐛 トラブルシューティング

### デプロイが失敗する

- Render.comのログを確認: Dashboard → Service → Logs
- Python 3.11以上が使われているか確認

### Webhook接続テストが失敗する

1. Render.comのURLが正しいか確認
2. `/health` エンドポイントにアクセス: `https://your-app.onrender.com/health`
3. 環境変数が正しく設定されているか確認

### Botが応答しない

1. LINE Webhook URLが正しいか確認
2. Render.comのログでエラーを確認
3. OpenAI APIキーが有効か確認（残高があるか）

### 15分後に反応が遅くなる

- Render.comの無料プランは15分無通信でスリープします
- 初回リクエストで自動起動（10〜30秒かかる場合あり）
- 有料プラン ($7/月) でスリープ無効化可能

## 📄 ライセンス

MIT License

## 🤝 コントリビューション

Issue・Pull Request 歓迎です！

## 📮 サポート

問題があれば [GitHub Issues](https://github.com/maruru3/saku_chappy/issues) で報告してください。
