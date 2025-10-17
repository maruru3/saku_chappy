"""
Saku Chappy - LINE Bot with ChatGPT Integration
Pipedream から GitHub Actions へ移植したLINE Bot

GitHub Actions + FastAPI + SQLite で動作
"""

import os
import hmac
import hashlib
import base64
import json
import sqlite3
import logging
from typing import Any
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ===== 環境変数 =====
ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
SYS_PROMPT = os.getenv("SYSTEM_PROMPT", "あなたはLINE上で丁寧に応答する日本語アシスタントです。")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

# SQLiteデータベースパス
DB_PATH = Path(__file__).parent / "line_chat_history.db"

# FastAPIアプリ
app = FastAPI(title="Saku Chappy LINE Bot", version="1.0.0")


# ===== データベース初期化 =====
def init_db() -> None:
    """会話履歴用のSQLiteテーブルを初期化"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_id ON chat_history(user_id)
    """)
    conn.commit()
    conn.close()


init_db()


# ===== データストア操作 =====
async def get_history(user_id: str) -> list[dict[str, str]]:
    """会話履歴を取得（最新20件 = 10往復）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 20",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    # 新しい順に取得したので逆順にして返す
    history = [{"role": role, "content": content} for role, content in reversed(rows)]
    return history


async def save_to_history(user_id: str, role: str, content: str) -> None:
    """会話履歴に追加"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)",
        (user_id, role, content)
    )
    conn.commit()
    conn.close()


async def reset_history(user_id: str) -> None:
    """会話履歴をリセット"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


async def get_history_count(user_id: str) -> int:
    """会話履歴の件数を取得"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM chat_history WHERE user_id = ?",
        (user_id,)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ===== 署名検証 =====
def verify_signature(body: bytes, signature: str) -> bool:
    """LINE署名を検証"""
    if not CHANNEL_SECRET:
        return True  # シークレット未設定時はスキップ（開発用）

    computed = base64.b64encode(
        hmac.new(CHANNEL_SECRET.encode(), body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(signature, computed)


# ===== LINEコンテンツ取得 =====
async def fetch_line_content(message_id: str, retry_count: int = 3) -> tuple[bytes, str]:
    """LINE画像/音声コンテンツを取得（リトライ機能付き）"""
    import asyncio

    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

    logger.info(f"LINE content fetch: message_id={message_id}")
    logger.info(f"URL: {url}")
    logger.info(f"Token prefix: {ACCESS_TOKEN[:20]}..." if ACCESS_TOKEN else "No token")

    last_error = None

    for attempt in range(retry_count):
        try:
            if attempt > 0:
                wait_time = attempt * 0.5  # 0.5秒, 1秒と待機時間を増やす
                logger.info(f"Retry {attempt + 1}/{retry_count} after {wait_time}s wait...")
                await asyncio.sleep(wait_time)

            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.get(url, headers=headers)

                logger.info(f"LINE response (attempt {attempt + 1}): status={res.status_code}, headers={dict(res.headers)}")

                if res.status_code == 200:
                    mime = res.headers.get("content-type", "application/octet-stream")
                    logger.info(f"Success: size={len(res.content)} bytes, mime={mime}")
                    return res.content, mime

                # 404の場合は詳細なエラー情報を記録
                error_body = res.text[:500] if res.text else "No body"
                last_error = f"Status {res.status_code}: {error_body}"
                logger.warning(f"Attempt {attempt + 1} failed: {last_error}")

        except Exception as e:
            last_error = str(e)
            logger.warning(f"Attempt {attempt + 1} exception: {last_error}")

    # すべてのリトライが失敗
    logger.error(f"All {retry_count} attempts failed. Last error: {last_error}")
    raise HTTPException(
        status_code=502,
        detail=f"LINE content取得に失敗しました（{retry_count}回試行）。\n\n考えられる原因:\n1. アクセストークンの権限不足\n2. メッセージIDが無効\n\n最後のエラー: {last_error}"
    )


# ===== ChatGPT API =====
async def chat_gpt(messages: list[dict[str, Any]]) -> str:
    """ChatGPT APIを呼び出し"""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(url, headers=headers, json=payload)
        data = res.json()

        if "error" in data:
            raise HTTPException(
                status_code=502,
                detail=data["error"].get("message", "OpenAI API error")
            )

        return (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
            or "すみません、応答できませんでした。"
        )


# ===== DALL-E 3 画像生成 =====
async def generate_image_with_dalle(prompt: str) -> str:
    """DALL-E 3で画像を生成してURLを返す"""
    url = "https://api.openai.com/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "quality": "standard",
    }

    logger.info(f"DALL-E 3画像生成開始: prompt={prompt[:100]}...")

    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.post(url, headers=headers, json=payload)
        data = res.json()

        if "error" in data:
            logger.error(f"DALL-E 3エラー: {data['error']}")
            raise HTTPException(
                status_code=502,
                detail=data["error"].get("message", "DALL-E 3 API error")
            )

        image_url = data.get("data", [{}])[0].get("url", "")
        logger.info(f"DALL-E 3画像生成完了: url={image_url}")
        return image_url


# ===== LINE返信 =====
async def reply_to_line(reply_token: str, text: str) -> None:
    """LINEにテキストメッセージを返信"""
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:4999]}],
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(url, headers=headers, json=payload)


async def reply_image_to_line(reply_token: str, image_url: str, preview_url: str = None) -> None:
    """LINEに画像メッセージを返信"""
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "image",
                "originalContentUrl": image_url,
                "previewImageUrl": preview_url or image_url,
            }
        ],
    }

    logger.info(f"LINE画像返信: image_url={image_url}")

    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.post(url, headers=headers, json=payload)
        logger.info(f"LINE画像返信レスポンス: status={res.status_code}")
        if res.status_code != 200:
            logger.error(f"LINE画像返信エラー: {res.text}")


# ===== Webhookエンドポイント =====
@app.post("/webhook")
async def webhook(
    request: Request,
    x_line_signature: str = Header(None, alias="x-line-signature"),
):
    """LINE Webhook エンドポイント"""

    # Bodyを取得
    body = await request.body()

    # テストイベント（events: []）の判定
    try:
        body_obj = json.loads(body.decode("utf-8"))
        is_test = isinstance(body_obj.get("events"), list) and len(body_obj["events"]) == 0
    except Exception:
        is_test = False

    # 署名検証
    if not is_test:
        if not x_line_signature:
            raise HTTPException(status_code=401, detail="Missing signature header")

        if not verify_signature(body, x_line_signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    # イベント処理
    try:
        body_obj = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    events = body_obj.get("events", [])
    results = []

    for event in events:
        if event.get("type") != "message":
            continue

        msg_type = event.get("message", {}).get("type")
        user_id = event.get("source", {}).get("userId", "unknown")
        reply_token = event.get("replyToken")

        try:
            reply_text = ""

            # ===== テキストメッセージ =====
            if msg_type == "text":
                user_text = event.get("message", {}).get("text", "")

                # リセットコマンド
                if user_text in ["リセット", "/reset"]:
                    await reset_history(user_id)
                    reply_text = "会話履歴をリセットしました！新しい会話を始めましょう。"

                # 履歴確認コマンド
                elif user_text == "/history":
                    count = await get_history_count(user_id)
                    reply_text = f"現在{count // 2}件の会話履歴があります。\n「リセット」または「/reset」で履歴をクリアできます。"

                # 通常会話
                else:
                    history = await get_history(user_id)
                    messages = [
                        {"role": "system", "content": SYS_PROMPT},
                        *history,
                        {"role": "user", "content": user_text},
                    ]
                    reply_text = await chat_gpt(messages)

                    # 履歴保存
                    await save_to_history(user_id, "user", user_text)
                    await save_to_history(user_id, "assistant", reply_text)

            # ===== 画像メッセージ =====
            elif msg_type == "image":
                logger.info(f"画像メッセージを受信: user_id={user_id}")
                logger.info(f"Event data: {json.dumps(event, ensure_ascii=False)}")

                message_id = event.get("message", {}).get("id")
                logger.info(f"Message ID: {message_id}")

                if not message_id:
                    raise ValueError("Message ID not found in event")

                # LINEから画像を取得
                content, mime = await fetch_line_content(message_id)
                logger.info(f"画像取得成功: size={len(content)} bytes, mime={mime}")

                # Base64エンコード
                b64_image = base64.b64encode(content).decode()
                logger.info(f"Base64エンコード完了: length={len(b64_image)}")

                messages = [
                    {
                        "role": "system",
                        "content": SYS_PROMPT + """

画像が送られたら、以下の形式で対応してください：

1. **問題の画像の場合**（数学、英語、プログラミングなど）:
   - 問題を理解して、丁寧な解説を提供
   - 回答例を示す
   - 解き方の手順を説明
   - 重要なポイントを指摘

2. **一般的な画像の場合**:
   - 画像の内容を簡潔に説明

判断基準:
- 文字や数式が多い → 問題の可能性が高い
- 「問」「解答」「問題」などの文字がある → 問題
- 教科書やノートの写真 → 問題の可能性あり

【重要】表記ルール:

▼ 数式の書き方
• LaTeX形式（\\(, \\), \\[, \\], $など）は絶対に使わない
• バックスラッシュ（\\）は一切使わない
• 累乗: x² または x^2
• 分数: 1/2
• 根号: √
• プレーンテキストで読みやすく

▼ 箇条書きの書き方
• ハイフン（-）やアスタリスク（*）は使わない
• 代わりに「•」（黒丸）または数字を使う
• 例: • 項目1　• 項目2

▼ 数式の良い例・悪い例
❌ 悪い例: \\(x^2 + 2x + 1\\)
✅ 良い例: x² + 2x + 1 または x^2 + 2x + 1
❌ 悪い例: - 計算手順（行頭にハイフン）
✅ 良い例: • 計算手順 または 1. 計算手順""",
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """この画像を分析してください。

もし問題（数学、英語、プログラミングなど）であれば:
1. 問題の内容を確認
2. 解き方の手順を説明
3. 回答例を提示
4. 重要なポイントを指摘

一般的な画像であれば、内容を簡潔に説明してください。""",
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{b64_image}"},
                            },
                        ],
                    },
                ]

                logger.info("OpenAI APIに画像を送信中...")
                reply_text = await chat_gpt(messages)
                logger.info(f"画像処理完了: reply_length={len(reply_text)}")

            # ===== スタンプメッセージ =====
            elif msg_type == "sticker":
                logger.info(f"スタンプメッセージを受信: user_id={user_id}")

                # スタンプ情報を取得
                sticker_id = event.get("message", {}).get("stickerId")
                package_id = event.get("message", {}).get("packageId")
                sticker_resource_type = event.get("message", {}).get("stickerResourceType", "STATIC")

                logger.info(f"Sticker: packageId={package_id}, stickerId={sticker_id}, type={sticker_resource_type}")

                # スタンプ画像URL（LINEの公式スタンプ画像URL）
                sticker_url = f"https://stickershop.line-scdn.net/stickershop/v1/sticker/{sticker_id}/android/sticker.png"
                logger.info(f"Sticker URL: {sticker_url}")

                # ステップ1: スタンプ画像をGPT-4oで分析
                analysis_messages = [
                    {
                        "role": "system",
                        "content": """あなたはスタンプ画像を分析し、それに応じた画像生成プロンプトを作成する専門家です。

スタンプの感情や雰囲気を読み取り、それに応えるような画像の説明を英語で簡潔に出力してください。

【重要】出力形式:
- 英語のプロンプトのみ出力（1-2文、最大70単語）
- 日本語の説明は不要
- DALL-E 3で生成しやすいシンプルな描写
- 感情を視覚的に表現

例:
- 喜び → "A cheerful cartoon character jumping with joy, bright colors, happy atmosphere"
- 悲しみ → "A cute character sitting under rain clouds, soft pastel colors, melancholic mood"
- 愛情 → "Two adorable characters hugging with hearts around them, warm pink tones"
- 応援 → "An energetic character cheering with pom-poms, vibrant colors, motivational scene"
""",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "このスタンプの感情を読み取り、それに応える画像のプロンプトを英語で作成してください。"},
                            {
                                "type": "image_url",
                                "image_url": {"url": sticker_url},
                            },
                        ],
                    },
                ]

                logger.info("OpenAI APIにスタンプ画像を送信して分析中...")
                dalle_prompt = await chat_gpt(analysis_messages)
                logger.info(f"画像生成プロンプト: {dalle_prompt}")

                # ステップ2: DALL-E 3で画像を生成
                try:
                    generated_image_url = await generate_image_with_dalle(dalle_prompt)
                    logger.info(f"スタンプ応答画像生成完了: {generated_image_url}")

                    # 画像で返信
                    await reply_image_to_line(reply_token, generated_image_url)
                    logger.info("スタンプに対して画像で返信しました")

                    # 返信済みなのでreply_textは空にしてスキップ
                    reply_text = None

                except Exception as dalle_error:
                    logger.error(f"DALL-E 3画像生成エラー: {dalle_error}")
                    # DALL-E失敗時はテキストで返信
                    reply_text = f"スタンプありがとう！（画像生成中にエラーが発生しました: {str(dalle_error)[:100]}）"

            # ===== 音声メッセージ =====
            elif msg_type == "audio":
                message_id = event.get("message", {}).get("id")
                content, _ = await fetch_line_content(message_id)

                # Whisper APIで文字起こし
                url = "https://api.openai.com/v1/audio/transcriptions"
                headers = {"Authorization": f"Bearer {OPENAI_KEY}"}
                files = {"file": ("audio.m4a", content, "audio/mp4")}
                data = {"model": "whisper-1"}

                async with httpx.AsyncClient(timeout=60.0) as client:
                    res = await client.post(url, headers=headers, files=files, data=data)
                    transcription = res.json()

                text = transcription.get("text", "(音声の文字起こしに失敗しました)")

                messages = [
                    {"role": "system", "content": SYS_PROMPT},
                    {"role": "user", "content": f"次の文字起こしを要約してください：\n{text}"},
                ]
                reply_text = await chat_gpt(messages)

            # ===== その他 =====
            else:
                reply_text = "現在はテキスト・画像・音声・スタンプに対応しています。"

            # 返信（reply_textがNoneでない場合のみ）
            if reply_text is not None:
                await reply_to_line(reply_token, reply_text)
            results.append({"ok": True, "type": msg_type, "userId": user_id})

        except Exception as e:
            logger.error(f"エラー発生: type={msg_type}, user={user_id}, error={str(e)}", exc_info=True)

            # エラーをユーザーに通知
            error_msg = f"申し訳ございません。処理中にエラーが発生しました。\n\nエラー詳細: {str(e)[:200]}"
            try:
                await reply_to_line(reply_token, error_msg)
            except Exception as reply_error:
                logger.error(f"エラー返信も失敗: {str(reply_error)}")

            results.append(
                {"ok": False, "type": msg_type, "error": str(e), "userId": user_id}
            )

    return {"status": 200, "results": results}


# ===== ヘルスチェック =====
@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "name": "Saku Chappy LINE Bot",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "webhook": "/webhook",
            "health": "/health",
        },
    }


@app.get("/health")
async def health():
    """ヘルスチェック"""
    return {
        "status": "ok",
        "has_line_token": bool(ACCESS_TOKEN),
        "has_openai_key": bool(OPENAI_KEY),
        "has_channel_secret": bool(CHANNEL_SECRET),
        "db_path": str(DB_PATH),
        "db_exists": DB_PATH.exists(),
    }
