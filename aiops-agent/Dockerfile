FROM python:3.11-slim

WORKDIR /app

# 安全设置：创建普通运行用户，不以root运行
RUN groupadd -r aiops && useradd -r -g aiops aiops

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 拷贝代码与配置模板
COPY . .

# 目录权限
RUN mkdir -p /app/logs /app/reports /app/ssh-keys && \
    chown -R aiops:aiops /app

USER aiops

EXPOSE 8000

# 启动FastAPI服务
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
