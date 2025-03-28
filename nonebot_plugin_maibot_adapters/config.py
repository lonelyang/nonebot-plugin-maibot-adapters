from pydantic import BaseModel


class Config(BaseModel):
    """Plugin Config Here"""
    Fastapi_url : str = "http://localhost:8000/api/message"  # 向麦麦bot发送消息的FastAPI地址 /
    Nickname :str = "" #你的bot昵称
    platfrom :str = "nonebot-qq" #建议不要动这里
