# MiscHub｜杂具小栈 - Docker 镜像
FROM python:3.12-slim

WORKDIR /app

# 使用阿里云 apt 源（服务器在国内）
RUN sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# 安装基础依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 5000

# 使用 gunicorn 启动生产服务
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "--timeout", "60", "app:app"]
