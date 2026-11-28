FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --system bisarx \
    && useradd --system --gid bisarx --home-dir /app bisarx \
    && mkdir -p /app/data && chown bisarx:bisarx /app/data
COPY app_config.py auth.py chat_engine.py database.py main.py models.py schemas.py whatsapp_bot.py ./
COPY *.csv *.pdf ./
COPY static ./static
USER bisarx
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
