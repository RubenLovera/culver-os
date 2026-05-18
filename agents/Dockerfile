FROM python:3.11-slim

WORKDIR /root/culver-os

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/admin_bot.py agents/
COPY tools/ tools/

CMD ["python3", "agents/admin_bot.py"]
