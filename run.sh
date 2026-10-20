#!/bin/sh
set -e
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
export PYTHON

usage() {
    echo "Использование: ./run.sh КОМАНДА"
    echo "  install    установить зависимости из requirements.txt"
    echo "  samples    создать примеры видео в examples/media (нужен ffmpeg)"
    echo "  examples   запустить утилиту на 4 примерах и 2 ошибочных входах"
    echo "  thumbnail  утилита: ./run.sh thumbnail OUT.jpg [--time T]"
    echo "             [--width W] < VIDEO.mp4"
    echo "  lint       проверка кода flake8 (PEP8, имена, сложность)"
    echo "Переменные окружения: PYTHON, FFMPEG_PATH."
}

case "$1" in
    install) "$PYTHON" -m pip install -r requirements.txt ;;
    samples) ./examples/make_samples.sh ;;
    examples) ./examples/run_examples.sh ;;
    thumbnail) shift; "$PYTHON" -m src.thumbnail "$@" ;;
    lint) "$PYTHON" -m flake8 src tests ;;
    *) usage ;;
esac
