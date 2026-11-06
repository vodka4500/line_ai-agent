import os
import sys
from fastapi import FastAPI, Request, HTTPException
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from google import genai

# 1. 初始化 FastAPI 應用程式
app = FastAPI()

# 2. 從環境變數讀取金鑰
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 檢查環境變數是否設定完成
if not all([LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, GEMINI_API_KEY]):
    print("錯誤：請確保 LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, GEMINI_API_KEY 皆已於環境變數設定妥當。")
    sys.exit(1)

# 3. 初始化 LINE SDK 與 Google GenAI Client
handler = WebhookHandler(LINE_CHANNEL_SECRET)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)


# 4. 根路由（供 Render 健康檢查與避免 404）
@app.get("/")
def read_root():
    return {"status": "ok", "message": "LINE AI Assistant is running perfectly!"}


# 5. LINE Webhook 接收點
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing X-Line-Signature header")

    body = (await request.body()).decode("utf-8")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature. Check your channel secret.")

    return "OK"


# 6. 處理 LINE 文字訊息與 AI 自動切換邏輯
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent):
    # 抓取使用者輸入的文字
    user_message = event.message.text

    # 設定系統提示詞與使用者輸入
    prompt = (
        "你是一個貼心的個人秘書與多領域專家。"
        "請以簡潔、專業且親切的語氣回覆以下訊息：\n\n"
        f"{user_message}"
    )

    # 備援模型清單（由新至舊）
    candidate_models = [
        'gemini-3.8-flash',
        'gemini-3.5-flash-lite'
        'gemini-3.1-pro-preview',
    ]

    reply_text = None

    # 自動選擇與替換模型邏輯
    for model_name in candidate_models:
        try:
            response = ai_client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            reply_text = response.text
            if reply_text:
                break
        except Exception as e:
            # 遇到 503 (超載) 或 404 (無效模型) 時，記錄日誌並嘗試下一個模型
            print(f"[Model Warning] 嘗試模型 {model_name} 失敗: {e}，自動切換下一個模型...")
            continue

    # 若全部模型皆失敗時的備用訊息
    if not reply_text:
        reply_text = "抱歉，目前 AI 大腦伺服器忙碌中，請稍後再傳送訊息試試看！"

    # 回傳訊息給 LINE 使用者
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )
