import base64
from pathlib import Path
import hashlib
import aiohttp
from nonebot import logger
import ssl
from PIL import Image
from io import BytesIO
from nonebot.adapters.onebot.v11 import MessageEvent
from typing import Union

def local_file_to_base64(file_path: str) -> Union[str, None]:
    """
    读取本地图片文件并转换为 Base64 字符串
    :param file_path: 图片文件路径
    :return: Base64 字符串，如果文件不存在则返回 None
    """
    #解决一下奇妙的分离部署问题
    try:
        # 尝试读取文件
        with open(file_path, "rb") as f:
            image_data = f.read()
        
        # 转换为 Base64
        base64_str = base64.b64encode(image_data).decode("utf-8")
        return base64_str
    
    except FileNotFoundError:
        # 文件不存在，返回 None
        logger.info("本地文件不存在，切换url下载")
        return None

def detect_image_type(data: bytes) -> str:
    """通过文件头识别常见图片格式"""
    if len(data) < 12:
        return "unknown"
    
    # 常见图片格式的魔数检测
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return "png"
    elif data.startswith(b'\xff\xd8'):
        return "jpeg"
    elif data[:6] in (b'GIF87a', b'GIF89a'):
        return "gif"
    elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return "webp"
    elif data.startswith(b'\x00\x00\x01\x00'):
        return "ico"
    elif data.startswith(b'BM'):
        return "bmp"
    else:
        return "unknown"

def base64_to_image(base64_str: str, save_dir: str = "data/images") -> str:
    """处理Base64字符串并保存为哈希命名的图片，非GIF格式转为单帧GIF"""
    try:
        # 解码Base64
        image_data = base64.b64decode(base64_str)
        
        # 检测图片类型
        image_type = detect_image_type(image_data)
        
        # 计算哈希值（基于原始数据）
        file_hash = hashlib.md5(image_data).hexdigest()
        
        # 构建保存路径
        save_dir_path = Path(save_dir).resolve()
        save_dir_path.mkdir(parents=True, exist_ok=True)
        
        # 如果是GIF，直接保存原文件
        if image_type == "gif":
            save_path = save_dir_path / f"{file_hash}.gif"
            if not save_path.exists():
                with open(save_path, "wb") as f:
                    f.write(image_data)
            return f"file:///{save_path.absolute().as_posix()}"
        
        # 对于非GIF格式，转换为单帧GIF
        else:
            # 使用Pillow打开图片并转换为GIF
            img = Image.open(BytesIO(image_data))
            
            # 处理透明度（如果是PNG等有透明通道的格式）
            if image_type == "png" and img.mode in ('RGBA', 'LA'):
                background = Image.new('RGBA', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background.convert('RGB')
            
            # 转换为GIF格式
            gif_buffer = BytesIO()
            img.save(gif_buffer, format='GIF')
            gif_data = gif_buffer.getvalue()
            
            # 计算转换后GIF的哈希值（基于转换后的数据）
            gif_hash = hashlib.md5(gif_data).hexdigest()
            save_path = save_dir_path / f"{gif_hash}.gif"
            
            if not save_path.exists():
                with open(save_path, "wb") as f:
                    f.write(gif_data)
            
            return f"file:///{save_path.absolute().as_posix()}"
    
    except Exception as e:
        raise ValueError(f"图片处理失败: {str(e)}")

async def download_image_url(url: str):
    """下载图片并返回 Base64，失败返回 None"""
    try:
        # 1. 配置 SSL 上下文（强制 TLS 1.2+，禁用弱加密）
        ssl_context = ssl.create_default_context()
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.set_ciphers("HIGH:!aNULL:!eNULL:!EXPORT:!DES:!MD5:!PSK:!RC4")

        # 2. 设置超时和浏览器 UA
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # 3. 发起请求
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ssl_context),
            timeout=aiohttp.ClientTimeout(total=10),
        ) as session:
            async with session.get(url, headers=headers) as resp:
                resp.raise_for_status()
                return base64.b64encode(await resp.read()).decode("utf-8")

    except Exception as e:
        logger.error(f"图片下载失败: {str(e)}")
        return None
    
    
def is_group_announcement(event: MessageEvent) -> bool:
    for segment in event.message:
        if segment.type == "json":
            data = segment.data.get("data", "")
            if '"app":"com.tencent.mannounce"' in data:
                return True
    return False
