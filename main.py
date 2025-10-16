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


# ===== LINE返信 =====
async def reply_to_line(reply_token: str, text: str) -> None:
    """LINEに返信"""
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
                        "content": SYS_PROMPT + " 画像が送られたら日本語で簡潔に説明してください。",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "この画像を日本語で3行以内で説明して。"},
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
                # アニメーションスタンプの場合は静止画を取得
                if sticker_resource_type == "ANIMATION":
                    sticker_url = f"https://stickershop.line-scdn.net/stickershop/v1/sticker/{sticker_id}/android/sticker.png"
                else:
                    sticker_url = f"https://stickershop.line-scdn.net/stickershop/v1/sticker/{sticker_id}/android/sticker.png"

                logger.info(f"Sticker URL: {sticker_url}")

                # スタンプ画像をGPT-4oで分析
                messages = [
                    {
                        "role": "system",
                        "content": SYS_PROMPT + " スタンプが送られたら、その画像を見て感情や内容を読み取り、適切に返事をしてください。",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "このスタンプの感情や意味を読み取って、適切に返事をしてください。"},
                            {
                                "type": "image_url",
                                "image_url": {"url": sticker_url},
                            },
                        ],
                    },
                ]

                logger.info("OpenAI APIにスタンプ画像を送信中...")
                reply_text = await chat_gpt(messages)
                logger.info(f"スタンプ処理完了: reply_length={len(reply_text)}")

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

            # 返信
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
