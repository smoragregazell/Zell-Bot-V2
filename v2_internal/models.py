"""
Modelos Pydantic para chat_v2
"""
from pydantic import BaseModel


class ChatV2Request(BaseModel):
    conversation_id: str
    user_message: str
    zToken: str
    userName: str

