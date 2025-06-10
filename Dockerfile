# 使用官方 Python 基礎映像
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 複製需求文件
COPY requirements.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式碼
COPY . .

# 暴露 Streamlit 預設端口
EXPOSE 8501

# 啟動 Streamlit 應用
CMD ["streamlit", "run", "rate_limiter/dashboard.py", "--server.address", "0.0.0.0", "--server.port", "8501"]