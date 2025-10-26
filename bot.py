from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def index():
    return "✅ Сервис жив, можно загружать бота", 200

@app.route("/ping")
def ping():
    return "pong", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Запускаю временный Flask на порту {port}...")
    app.run(host="0.0.0.0", port=port)
