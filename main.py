import os
from fastapi import FastAPI, Request, HTTPException
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from google import genai

app = FastAPI()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get('X-Line-Signature', '')
    body = await request.body()
    body_str = body.decode('utf-8')

    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature.")
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text
    reply_token = event.reply_token

    from google import genai
import os

# 初始化 Gemini Client
ai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 定義要嘗試的模型清單（依優先順序排序：最新模型優先，後面接備用模型）
candidate_models = [
    'gemini-3.5-flash-lite',
    'gemini-3.8-flash',
    'gemini-3.1-pro-preview',
]

prompt = f"你是一個貼心的個人秘書與多領域專家。請以簡潔、專業且親切的語氣回覆以下訊息：\n\n{user_message}"

reply_text = None

# 自動迴圈嘗試清單中的模型，直到成功為止
for model_name in candidate_models:
    try:
        response = ai_client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        reply_text = response.text
        break  # 成功取得回覆就跳出迴圈
    except Exception as e:
        # 如果遇到 503 超載、404 模型不存在等錯誤，印出紀錄並自動換下一個模型嘗試
        print(f"Model {model_name} failed with error: {e}, trying next...")
        continue

# 如果所有模型都失敗，給予友善提示
if not reply_text:
    reply_text = "目前 AI 伺服器流量較大或正在忙碌中，請稍後再傳訊息試試看！"

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=ai_reply_text)]
            )
        )
