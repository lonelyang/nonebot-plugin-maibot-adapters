from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

from nonebot import on_message,on_notice
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot,MessageEvent,NoticeEvent
from .bot import chat_bot

import threading
import sys

__plugin_meta__ = PluginMetadata(
    name="maim-fastapi",
    description="",
    usage="",
    config=Config,
)
    
config = get_plugin_config(Config)

msg_in = on_message(priority=5)
notice_matcher = on_notice(priority=1)

@notice_matcher.handle()
async def _(bot: Bot, event: NoticeEvent):
    logger.debug(f"收到通知：{event}")
    await chat_bot.handle_notice(event, bot)

@msg_in.handle()
async def _(bot: Bot, event: MessageEvent):
    # 处理合并转发消息
    if "forward" in event.message:
        await chat_bot.handle_forward_message(event, bot)
    elif any(segment.type in {"image", "emoji"} for segment in event.message):  
        await chat_bot.handle_image_message(event, bot)
    elif event.reply:
        await chat_bot.handle_reply_message(event,bot)
    else:
        await chat_bot.handle_message(event, bot)

def run():
    import asyncio
    from .router import main
    asyncio.run(main())


try:
    # 在单独线程中运行 FastAPI
    api_thread = threading.Thread(target=run, daemon=True)
    api_thread.start()
except KeyboardInterrupt:
    print("\n程序正在退出...")
    sys.exit(0)
