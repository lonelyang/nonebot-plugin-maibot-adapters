#!/bin/sh
set -e  # 遇到错误立即退出

# 目标目录
TARGET_DIR="/adapters/src/plugins"

# 如果目标目录为空，则从备份目录复制初始内容
if [ -z "$(ls -A $TARGET_DIR)" ]; then
  echo "检测到空目录，正在初始化 $TARGET_DIR..."
  cp -r /backup/nonebot_plugin_maibot_adapters $TARGET_DIR/
  echo "初始化完成"
fi

# 执行 Dockerfile 中的 CMD 或 docker run 传入的命令
exec "$@"