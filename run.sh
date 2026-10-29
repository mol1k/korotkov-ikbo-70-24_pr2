#!/bin/sh
set -e
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
PORT="${PORT:-8000}"
export PYTHON

usage() {
    echo "Использование: ./run.sh КОМАНДА"
    echo "  install      установить зависимости из requirements.txt"
    echo "  samples      создать примеры видео в examples/media (нужен ffmpeg)"
    echo "  examples     запустить утилиту на 4 примерах и 2 ошибочных входах"
    echo "  thumbnail    утилита: ./run.sh thumbnail OUT.jpg [--time T]"
    echo "               [--width W] < VIDEO.mp4"
    echo "  server       HTTP API с реальной генерацией миниатюр"
    echo "  server-test  HTTP API в тестовом режиме (без ffmpeg)"
    echo "  demo-api     демонстрация API через клиент (сервер запущен)"
    echo "  test         тесты MBT (hypothesis) и отчёт coverage"
    echo "  lint         проверка кода flake8 (PEP8, имена, сложность)"
    echo "Переменные окружения: PYTHON, PORT (8000), FFMPEG_PATH."
}

case "$1" in
    install) "$PYTHON" -m pip install -r requirements.txt ;;
    samples) ./examples/make_samples.sh ;;
    examples) ./examples/run_examples.sh ;;
    thumbnail) shift; "$PYTHON" -m src.thumbnail "$@" ;;
    server) "$PYTHON" -m src.server --port "$PORT" ;;
    server-test) "$PYTHON" -m src.server --port "$PORT" --test-mode ;;
    demo-api)
        "$PYTHON" -m examples.api_demo "http://127.0.0.1:$PORT" ;;
    test)
        "$PYTHON" -m coverage run -m unittest discover -s tests -t . -v
        "$PYTHON" -m coverage report
        ;;
    lint) "$PYTHON" -m flake8 src tests examples ;;
    *) usage ;;
esac
