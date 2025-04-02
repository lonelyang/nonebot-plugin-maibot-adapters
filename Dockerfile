FROM infinitycat/adapter-bottom:latest
LABEL authors="infinitycat233"

WORKDIR /adapters

COPY maim_message /maim_message
RUN pip install -e /maim_message
RUN pip install nonebot-adapter-onebot nonebot2[fastapi] nonebot2[websockets]

COPY entrypoint.sh /entrypoint.sh
COPY nonebot_plugin_maibot_adapters /backup/nonebot_plugin_maibot_adapters
COPY nonebot_plugin_maibot_adapters /adapters/src/plugins/nonebot_plugin_maibot_adapters

VOLUME ["/adapters/src/plugins"]

EXPOSE 18002

RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

CMD ["nb", "run", "--reload"]