from flask import Flask
import threading

# Создаем простейший веб-сервер
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!", 200

def run_web_server():
    # Render сам устанавливает переменную окружения PORT, которую нужно использовать
    port = int(os.environ.get("PORT", 5000))
    # Запускаем сервер. Важно: host='0.0.0.0' - слушаем все входящие подключения
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    run_web_server()