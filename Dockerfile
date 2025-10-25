FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PATH="/opt/venv/bin:$PATH"
ENV PORT=8000

EXPOSE 8000
CMD ["python", "bot.py"]
