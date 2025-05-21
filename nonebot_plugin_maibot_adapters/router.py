import asyncio
from maim_message import (
    Router,
    RouteConfig,
    TargetConfig,
)
from .config import Config
from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot,MessageSegment,Message
from nonebot import get_bot

from .util import base64_to_image


config = Config()

# 配置路由config 
# 从RouteConfig类构建route_config实例
route_config = RouteConfig( 
    #根据TargetConfig类构建一个合法的route_config
    route_config={
        config.platfrom: TargetConfig( 
            url= config.url ,
            token=None,  # 如果需要token验证则在这里设置
        ),
    #     # 可配置多个平台连接
    #     "platform2": TargetConfig(
    #         url="ws://127.0.0.1:19000/ws",
    #         token="your_auth_token_here",  # 示例：带认证token的连接 
    #     ),
    }
)

# 使用刚刚构建的route_config,从类Router创建路由器实例router
router = Router(route_config)

async def main():
    # 使用实例router的方法注册消息处理器
    router.register_class_handler(message_handler) #message_handler示例见下方

    try:
        # 启动路由器（会自动连接所有配置的平台）
        router_task = asyncio.create_task(router.run())

        # 等待连接建立
        await asyncio.sleep(2)

        # 保持运行直到被中断
        await router_task

    finally:
        print("正在关闭连接...")
        await router.stop()
        print("已关闭所有连接")


async def message_handler(message):
    """
    一个作为示例的消息处理函数
    从mmc发来的消息将会进入此函数
    你需要解析消息，并且向指定平台捏造合适的消息发送
    如将mmc的MessageBase消息转换为onebotV11协议消息发送到QQ
    或者根据其他协议发送到其他平台
    """
    try:
        # logger.info(f"收到请求数据: {json_data}")

        message_info = message.get('message_info', {})
        message_segment = message.get('message_segment', {})
        group_id = message_info.get('group_info', {}).get('group_id')
        user_id = message_info.get('user_info', {}).get('user_id')

        bot: Bot = get_bot()
        # logger.info("开始处理消息")

        # 初始化消息链和回复ID
        message_chain = Message()
        reply_msg_id = None
        poke_user_id = None

        # 处理seglist类型的复合消息
        if message_segment.get('type') == 'seglist':
            for segment in message_segment.get('data', []):
                seg_type = segment.get('type')
                seg_data = segment.get('data')

                if seg_type == 'reply':
                    reply_msg_id = seg_data  # 记录被回复的消息ID
                if seg_type == 'at':
                    message_chain += MessageSegment.at(seg_data)
                if seg_type == 'poke':
                    poke_user_id = seg_data
                elif seg_type == 'text':
                    message_chain += MessageSegment.text(seg_data)
                elif seg_type == 'image':
                    image_path = "base64://" + seg_data
                    message_chain = MessageTemplate("{}").format(f"[CQ:image,file={image_path},subType=0]")
                elif seg_type == 'emoji':
                    # 处理表情消息（示例）
                    # message_chain += MessageSegment.face(id=int(seg_data))
                    image_path = "base64://" + seg_data
                    message_chain = MessageTemplate("{}").format(f"[CQ:image,file={image_path},subType=1]")
        else:
            # 处理单一类型消息
            seg_type = message_segment.get('type')
            seg_data = message_segment.get('data', '')
            if seg_type == 'at':
                message_chain += MessageSegment.at(seg_data)
            if seg_type == 'poke':
                poke_user_id = seg_data
            if seg_type == 'text':
                message_chain += MessageSegment.text(seg_data)
            elif seg_type == 'image':
                image_path = "base64://" + seg_data
                message_chain = MessageTemplate("{}").format(f"[CQ:image,file={image_path},subType=0]")
            elif seg_type == 'emoji':
                image_path = "base64://" + seg_data
                message_chain = MessageTemplate("{}").format(f"[CQ:image,file={image_path},subType=1]")

        # 添加回复引用（如果存在）
        if reply_msg_id:
            message_chain = MessageSegment.reply(reply_msg_id) + message_chain

        # 发送戳一戳（如果存在）
        if poke_user_id:
            if group_id:
                await bot.call_api("group_poke", user_id=poke_user_id, group_id=group_id)
            else:
                await bot.call_api("friend_poke", user_id=poke_user_id)

        # 发送消息
        if group_id:
            await bot.send_msg(
                message_type="group",
                group_id=group_id,
                message=message_chain
            )
        else:
            await bot.send_msg(
                message_type="private",
                user_id=user_id,
                message=message_chain
            )

        return {"status": "success"}
    
    except Exception as e:
        logger.error(f"处理请求时出错: {str(e)}")
        return {"status": "error", "message": str(e)}

