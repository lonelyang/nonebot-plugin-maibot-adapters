from nonebot import logger
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    PrivateMessageEvent,
    GroupMessageEvent,
    PokeNotifyEvent,
    NoticeEvent,

)
from maim_message import UserInfo, GroupInfo, Seg ,BaseMessageInfo,MessageBase,FormatInfo,TemplateInfo
from .config import Config
from .util import local_file_to_base64,download_image_url
from .router import router

import httpx
import time
import re
import asyncio
import json
import base64



config = Config()

# 定义日志配置

class ChatBot:
    def __init__(self):
        self.bot = None  # bot 实例引用
        self._started = False
        self.client = httpx.AsyncClient(timeout=60)  # 创建异步HTTP客户端
        self.format_info = FormatInfo(
            # 消息内容中包含的Seg的type列表
            content_format=["text", "image", "emoji", "at", "poke", "reply"],
            # 消息发出后，期望最终的消息中包含的消息类型，可以帮助某些plugin判断是否向消息中添加某些消息类型
            accept_format=["text", "image", "emoji", "reply"],
        )

    async def _ensure_started(self):
        """确保所有任务已启动"""
        if not self._started:
            self._started = True

    async def handle_message(self, event: MessageEvent, bot: Bot) -> None:
        """处理收到的消息"""

        message_content = ''

        self.bot = bot  # 更新 bot 实例
        if isinstance(event, PrivateMessageEvent):
            try:
                user_info = UserInfo(
                    user_id=event.user_id,
                    user_nickname=(await bot.get_stranger_info(user_id=event.user_id, no_cache=True))["nickname"],
                    user_cardname=None,
                    user_titlename=None,
                    platform=config.platfrom,
                )
            except Exception as e:
                logger.error(f"获取陌生人信息失败: {e}")
                return
            logger.debug(user_info)

            message_content = event.get_plaintext()

            # group_info = GroupInfo(group_id=0, group_name="私聊", platform=config.platfrom)
            group_info = None

        # 处理群聊消息
        else:
            # 白名单处理逻辑
            if len(config.allow_group_list) != 0:
                if event.group_id not in config.allow_group_list:
                    return

            user_info = UserInfo(
                user_id=event.user_id,
                user_nickname=event.sender.nickname,
                user_cardname=event.sender.card or None,
                user_titlename=event.sender.title or None,
                platform=config.platfrom,
            )
            
            group_info = GroupInfo(group_id=event.group_id, 
                                   group_name=(await bot.get_group_info(group_id = event.group_id,no_cache=True))["group_name"], 
                                   platform=config.platfrom)
            
            #这里是at信息的处理逻辑 可能会比较混乱，但是暂时没找到更好的解决方式
            msg = str(event.raw_message)
            logger.info(f"{msg}")
            qq_ids = list(set(re.findall(r'\[CQ:at,qq=(\d+)\]', msg)))
            if not qq_ids:  # 没有 @ 消息
                message_content = msg
            else:
                # 获取用户昵称，失败时提供默认值
                nicknames = {}
                for qq in qq_ids:
                    try:
                        info = await bot.get_stranger_info(user_id=int(qq))
                        nicknames[qq] = info.get("nickname", f"用户{qq}")
                    except Exception:
                        nicknames[qq] = f"用户{qq}"

                # 替换 @ 消息，避免 KeyError
                message_content = re.sub(
                    r'\[CQ:at,qq=(\d+)\]',
                    lambda m: f'@{nicknames.get(m.group(1), f"用户{m.group(1)}")}（id:{m.group(1)}）',
                    msg
                )
            
        
        message_info = BaseMessageInfo(
                platform = config.platfrom,
                message_id = event.message_id,
                time = time.time(),
                group_info = group_info,
                user_info = user_info,
                format_info=self.format_info,
        )

        message_seg = Seg(  
                    type = 'text',
                    data = message_content,  
            )


        message_base = MessageBase(message_info,message_seg,raw_message=message_content)

        await self.message_process(message_base)

    async def handle_group_announcement(self, event: MessageEvent, bot: Bot) -> None:
        """处理收到的消息"""

        self.bot = bot  # 更新 bot 实例
            #白名单处理逻辑
        if len(config.allow_group_list) != 0 :
            if event.group_id not in config.allow_group_list:
                return

        message_content = ""
        for segment in event.message:
            if segment.type == "json":
                try:

                    data = json.loads(segment.data["data"].replace("&#44;", ","))
                    mannounce = data["meta"]["mannounce"]
                    title = base64.b64decode(mannounce["title"]).decode("utf-8") if mannounce.get("title") else ""
                    text = base64.b64decode(mannounce["text"]).decode("utf-8") if mannounce.get("text") else ""
                    
                    message_content += f"{event.sender.nickname}({event.user_id})发布了【{title}】：\n{text}"

                    
                except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as e:
                    print(f"解析群公告失败: {e}")

            
        group_info = GroupInfo(group_id=event.group_id, 
                                group_name=(await bot.get_group_info(group_id = event.group_id,no_cache=True))["group_name"], 
                                platform=config.platfrom)
        
        user_info = UserInfo(
            user_id=event.user_id,
            user_nickname=event.sender.nickname,
            user_cardname=event.sender.card or None,
            user_titlename=event.sender.title or None,
            platform=config.platfrom,
        )

        message_info = BaseMessageInfo(
                platform = config.platfrom,
                message_id = event.message_id,
                time = time.time(),
                group_info = group_info,
                user_info = user_info,
                format_info=self.format_info,
        )

        message_seg = Seg(  
                    type = 'text',
                    data = message_content,  
            )


        message_base = MessageBase(message_info,message_seg,raw_message=message_content)

        await self.message_process(message_base)

    async def handle_notice(self, event: NoticeEvent, bot: Bot) -> None:
        """处理收到的通知"""
        if isinstance(event, PokeNotifyEvent):
            # 戳一戳 通知
            # 不处理其他人的戳戳
            if not event.is_tome():
                return

            #白名单处理逻辑
            if len(config.allow_group_list) != 0 :
                if event.group_id not in config.allow_group_list:
                    return

            nickname = (await bot.get_login_info())["nickname"]

            raw_message = f"[戳了戳]{nickname}"  # 默认类型
            print(event.model_extra)
            info = event.model_extra
            poke_type = info.get("action", "戳了戳")  # 使用 'action' 字段
            custom_poke_message = info.get("suffix", "")  # 使用 'suffix' 字段
            raw_message = f"[{poke_type}]{nickname}{custom_poke_message}"

            raw_message += "（这是一个类似摸摸头的友善行为，而不是恶意行为，请不要作出攻击发言）"

            user_info = UserInfo(
                user_id=event.user_id,
                user_nickname=(await bot.get_stranger_info(user_id=event.user_id, no_cache=True))["nickname"],
                user_cardname=None,
                user_titlename=None,
                platform=config.platfrom,
            )

            if event.group_id:
                group_info = GroupInfo(group_id=event.group_id, 
                        group_name=(await bot.get_group_info(group_id = event.group_id,no_cache=True))["group_name"], 
                        platform=config.platfrom)
            else:
                group_info = None

            message_info = BaseMessageInfo(
                    platform = config.platfrom,
                    message_id = None,
                    time = time.time(),
                    group_info= group_info,
                    user_info = user_info,
                    format_info=self.format_info,
            )

            message_seg = Seg(
                    type = 'text',
                    data = raw_message,  
            )

            message_base = MessageBase(message_info,message_seg,raw_message=raw_message)

            await self.message_process(message_base)

        # 处理撤回消息存储的逻辑，先放着不动
        # elif isinstance(event, GroupRecallNoticeEvent) or isinstance(event, FriendRecallNoticeEvent):
        #     user_info = UserInfo(
        #         user_id=event.user_id,
        #         user_nickname=get_user_nickname(event.user_id) or None,
        #         user_cardname=get_user_cardname(event.user_id) or None,
        #         platform=config.platfrom,
        #     )

        #     if isinstance(event, GroupRecallNoticeEvent):
        #         group_info = GroupInfo(group_id=event.group_id, group_name=None, platform=config.platfrom)
        #     else:
        #         group_info = None

        #     chat = await chat_manager.get_or_create_stream(
        #         platform=user_info.platform, user_info=user_info, group_info=group_info
        #     )

        #     await self.storage.store_recalled_message(event.message_id, time.time(), chat)

    async def handle_image_message(self, event: MessageEvent, bot: Bot) -> None:
        """修复后的图片消息处理器"""
        self.bot = bot
        
        #白名单处理逻辑
        if len(config.allow_group_list) != 0 :
            if event.group_id not in config.allow_group_list:
                return

        # 公共信息处理（移到循环外）
        try:
            if isinstance(event, PrivateMessageEvent):
                user_info = UserInfo(
                    user_id=event.user_id,
                    user_nickname=(await bot.get_stranger_info(user_id=event.user_id))["nickname"],
                    user_cardname=None,
                    user_titlename=None,
                    platform=config.platfrom
                )
                group_info = None
            else:
                user_info = UserInfo(
                    user_id=event.user_id,
                    user_nickname=event.sender.nickname,
                    user_cardname=event.sender.card or None,
                    user_titlename=event.sender.title or None,
                    platform=config.platfrom
                )
                # 获取群信息添加默认值

                group_info = GroupInfo(group_id=event.group_id, 
                        group_name=(await bot.get_group_info(group_id = event.group_id,no_cache=True))["group_name"], 
                        platform=config.platfrom)

        except Exception as e:
            logger.error(f"基础信息获取失败: {e}")
            return

        seg_list = []
        # 处理图片段
        for segment in event.message:
            if segment.type == "image":
                # 获取真实图片数据（根据协议适配器实现）
                image_file = segment.data.get("file")
                # image_file = segment.data.get("file")
                image_url = segment.data.get("url")
                subtype = segment.data.get("sub_type")
                try:
                    # 这里是私人emoji和图片
                    image_data = await asyncio.wait_for(bot.get_image(file=image_file), timeout=2)  # 2s不响应自动切换一个解决方式
                    file_path = image_data["file"]
                    base64_str = local_file_to_base64(file_path)
                    if base64_str is None:  # 本地文件读取不到
                        base64_str = await download_image_url(image_url)
                    # 这里是私人emoji和图片--暂时直接全部使用url下载
                    # image_data = await asyncio.wait_for(bot.get_image(file=image_file),timeout=2)#2s不响应自动切换一个解决方式
                    # file_path = image_data["file"]
                    # base64_str = local_file_to_base64(file_path)
                    # if base64_str is None: #本地文件读取不到
                    base64_str = await download_image_url(image_url)
                    subtype = str(subtype)  # 确保类型一致性
                    if subtype == "0":  # 图片
                        image_type = 'image'
                    else:
                        image_type = 'emoji'
                except asyncio.TimeoutError:
                    #这里是商店的emoji
                    image_type = 'emoji'
                    logger.info("切换url下载")
                    base64_str = await download_image_url(image_url)
                    #下载并且转换为base64

                # logger.info(image_type)
                seg_list.append(Seg(type = image_type,data = base64_str))
            elif segment.type == "text" :
                seg_list.append(Seg(type = "text",data = str(segment.data.get("text",""))))
            elif segment.type == "at" :
                seg_at_id = str(segment.data.get("qq",""))
                user_nickname=(await bot.get_stranger_info(user_id=seg_at_id))["nickname"]
                seg_list.append(Seg(type = "text",data = f"@{user_nickname}({seg_at_id})"))
            else:
                continue

        if len(seg_list) == 1:
            message_content = seg_list[0]
        else :
            message_content = Seg(type="seglist",data = seg_list)

        message_info = BaseMessageInfo(
            platform = config.platfrom,
            message_id = event.message_id,
            time = time.time(),
            group_info= group_info,
            user_info = user_info,
            format_info=self.format_info,
        )
        message_base = MessageBase(message_info,message_content,raw_message="")   
        
        await self.message_process(message_base)    

    async def handle_reply_message(self, event: MessageEvent, bot: Bot) -> None:
        """处理收到的消息"""

        self.bot = bot  # 更新 bot 实例
        if isinstance(event, PrivateMessageEvent):
            try:
                user_info = UserInfo(
                    user_id=event.user_id,
                    user_nickname=(await bot.get_stranger_info(user_id=event.user_id, no_cache=True))["nickname"],
                    user_cardname=None,
                    user_titlename=None,
                    platform=config.platfrom,
                )
            except Exception as e:
                logger.error(f"获取陌生人信息失败: {e}")
                return
            logger.debug(user_info)
            group_info = None

        # 处理群聊消息
        else:
            #白名单处理逻辑
            if len(config.allow_group_list) != 0 :
                if event.group_id not in config.allow_group_list:
                    return

            user_info = UserInfo(
                user_id=event.user_id,
                user_nickname=event.sender.nickname,
                user_cardname=event.sender.card or None,
                user_titlename=event.sender.title or None,
                platform=config.platfrom,
            )
            
            group_info = GroupInfo(group_id=event.group_id, 
                                   group_name=(await bot.get_group_info(group_id = event.group_id,no_cache=True))["group_name"], 
                                   platform=config.platfrom)

        message_content = f"回复{event.reply.sender.nickname}({event.reply.sender.user_id})的消息({event.reply.message or ''})，说："
        # message_content += f"-{event.reply.sender.nickname}(id{event.reply.user_id}):{event.reply.message}\n回复了以下信息："
        message_content+=event.get_plaintext()
        # logger.info(f"\n\n\n{message_content}\n\n\n")

        message_info = BaseMessageInfo(
                platform = config.platfrom,
                message_id = event.message_id,
                time = time.time(),
                group_info = group_info,
                user_info = user_info,
                format_info=self.format_info,
        )

        message_seg = Seg(  
                    type = 'text',
                    data = message_content,  
            )


        message_base = MessageBase(message_info,message_seg,raw_message=event.get_plaintext())

        await self.message_process(message_base)

    async def handle_forward_message(self, event: MessageEvent, bot: Bot) -> None:
        """专用于处理合并转发的消息处理器"""

        #白名单处理逻辑
        if len(config.allow_group_list) != 0 :
            if event.group_id not in config.allow_group_list:
                return
        # 获取合并转发消息的详细信息
        print("massage_id_forward", event.get_message())
        info = str(event.get_message())
        forward_id = info.split("id=")[1].split("]")[0]
        forward_info = await bot.get_forward_msg(id=forward_id)
        print("forward_info", forward_info)
        messages = forward_info["message"]

        # 构建合并转发消息的文本表示
        processed_messages = []
        
        for node in messages:
            # 提取发送者昵称
            nickname = node["data"].get("nickname", "未知用户")

            # 递归处理消息内容
            message_content = await self.process_message_segments(node["data"]["content"], layer=0, bot=bot)

            # 拼接为【昵称】+ 内容
            processed_messages.append(f"{nickname}：{message_content}")

        # 组合所有消息
        combined_message = "\n".join(processed_messages)
        combined_message = f"转发了消息：\n{combined_message}"

        # 构建用户信息（使用转发消息的发送者）
        user_info = UserInfo(
            user_id=event.user_id,
            user_nickname=event.sender.nickname,
            user_cardname=event.sender.card if hasattr(event.sender, "card") else None,
            user_titlename=event.sender.title if hasattr(event.sender, "title") else None,
            platform=config.platfrom,
        )

        # 构建群聊信息（如果是群聊）
        group_info = None
        if isinstance(event, GroupMessageEvent):
            group_info = GroupInfo(group_id=event.group_id, 
                    group_name=(await bot.get_group_info(group_id = event.group_id,no_cache=True))["group_name"], 
                    platform=config.platfrom)

        # 创建消息对象
        message_info = BaseMessageInfo(
                platform = config.platfrom,
                message_id = event.message_id,
                time = time.time(),
                group_info= group_info,
                user_info = user_info,
                format_info=self.format_info,
        )
        # logger.info (event.get_message())
        message_seg = Seg(
                type = 'text',
                data = combined_message,  
        )

        message_base = MessageBase(message_info,message_seg,raw_message=combined_message)

        # 进入标准消息处理流程
        await self.message_process(message_base)

    async def process_message_segments(self, segments: list, layer: int, bot: Bot) -> str:
        """递归处理消息段"""
        parts = []
        for seg in segments:
            part = await self.process_segment(seg, layer + 1, bot)
            parts.append(part)
        return "".join(parts)

    async def process_segment(self, seg: dict, layer: int, bot: Bot) -> str:
        """处理单个消息段"""
        seg_type = seg["type"]
        if layer > 3:
            # 防止有那种100层转发消息炸飞麦麦
            return "【转发消息】"
        if seg_type == "text":
            return seg["data"]["text"]
        elif seg_type == "image":
            return "[图片]"
        elif seg_type == "face":
            return "[表情]"
        elif seg_type == "at":
            return f"@{seg['data'].get('qq', '未知用户')}"
        elif seg_type == "forward":
            # 递归处理嵌套的合并转发消息
            forward_id = seg["data"].get("id", "")
            forward_info = await bot.get_forward_msg(id=forward_id)
            nested_nodes = forward_info["message"]
            nested_messages = []
            nested_messages.append("合并转发消息内容：")
            for node in nested_nodes:
                nickname = node["data"].get("nickname", "未知用户")
                content = await self.process_message_segments(node["data"]["content"], layer=layer, bot=bot)
                # nested_messages.append('-' * layer)
                nested_messages.append(f"{'--' * layer}【{nickname}】{content}")
            # nested_messages.append(f"{'--' * layer}合并转发第【{layer}】层结束")
            return "\n".join(nested_messages)
        else:
            return f"[{seg_type}]"

    async def message_process(self, message_base: MessageBase) -> None:
        await router.send_message(message_base)


# 创建全局ChatBot实例
chat_bot = ChatBot()
