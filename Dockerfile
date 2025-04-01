FROM infinitycat/adapter-bottom:latest
LABEL authors="infinitycat233"

WORKDIR /adapters

COPY maim_message /maim_message
RUN pip install -e /maim_message
RUN pip install nonebot-adapter-onebot nonebot2[fastapi] nonebot2[websockets]

COPY nonebot_plugin_maibot_adapters /adapters/src/plugins/nonebot_plugin_maibot_adapters

EXPOSE 18002

ENTRYPOINT ["nb", "run", "--reload"]