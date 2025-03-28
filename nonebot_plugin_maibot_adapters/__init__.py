from nonebot import get_plugin_config,get_app,get_bot
from nonebot.plugin import PluginMetadata

from .config import Config

from nonebot import on_message,on_notice,require
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot,MessageEvent,NoticeEvent,MessageSegment
from nonebot.drivers.fastapi import Request
from .bot import chat_bot
from .util import base64_to_image


__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-maibot-adapters",
    description="麦麦的nonebot适配器插件",
    usage="在config.py中设置好向麦麦发送消息的端口，在.env的PORT中设置好接受麦麦消息的端口",

    type="application",
    # 发布必填，当前有效类型有：`library`（为其他插件编写提供功能），`application`（向机器人用户提供功能）。
    homepage="{项目主页}",
    # 发布必填。
    config=Config,
    # 插件配置项类，如无需配置可不填写。
    supported_adapters={"~onebot.v11"},

)
config = get_plugin_config(Config)
require("maim_message")


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
    elif any(segment.type == "image" for segment in event.message):
        await chat_bot.handle_image_message(event, bot)
    else:
        await chat_bot.handle_message(event, bot)

app = get_app()

@app.post("/api/message")
async def handle_request(request: Request):
    try:
        # 接收并解析JSON数据
        json_data = await request.json()
        logger.info(f"收到请求数据: {json_data}")
        # 获取QQ Bot实例


        message_info = json_data.get('message_info', {})
        message_segment = json_data.get('message_segment', {})

        group_id = message_info.get('group_info', {}).get('group_id')
        user_id = message_info.get('user_info', {}).get('user_id')

        # user_nickname = message_info.get('user_info', {}).get('user_nickname', '用户')
        message_type = message_segment.get('type', '')
        message_content = message_segment.get('data', '')

        bot: Bot = get_bot()
        logger.info("\n\n\n\n收到消息啦")

        

        # 示例：向指定群发送消息（参数需要根据你的需求调整）
        if message_type == 'text':
            if group_id :
                await bot.send_msg(
                    message_type="group",  # 消息类型（group/private）
                    group_id=group_id,     # 替换为你的群号
                    message=message_content    # 要发送的内容
                )
            else :
                await bot.send_msg(
                    message_type="private",  # 消息类型（group/private）
                    user_id=user_id,    # 替换为你的群号
                    message=message_content    # 要发送的内容
                )
        if message_type == 'image' or message_type == 'emoji':
            image_path = base64_to_image(message_content)
            logger.info(f"{image_path}")
            if group_id :
                await bot.send_msg(
                    message_type="group",  # 消息类型（group/private）
                    group_id=group_id,     # 替换为你的群号
                    message=MessageSegment.image(file=image_path)    # 要发送的内容
                )
            else :
                await bot.send_msg(
                    message_type="private",  # 消息类型（group/private）
                    user_id=user_id,        # 替换为你的群号
                    message=MessageSegment.image(file=image_path)     # 要发送的内容
                )         
        else:
            #这里大概会是个file文件什么的，之后再说
            return 

        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"处理请求时发生错误: {str(e)}")
        return {"status": "error", "message": "内部服务器错误"}

