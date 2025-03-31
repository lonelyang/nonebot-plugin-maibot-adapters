FROM nonebot/nb-cli:latest
LABEL authors="infinitycat233"

WORKDIR /adapters

COPY maim_message /appdata/maim_message
RUN pip install -e /appdata/maim_message -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
RUN pip install nonebot-adapter-onebot nonebot2[fastapi] nonebot2[websockets] -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple

COPY test .

EXPOSE 18002

ENTRYPOINT ["nb", "run", "--reload"]