#!/bin/sh
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
OUT=examples/output
mkdir -p "$OUT"

run() {
    echo "\$ python -m src.thumbnail $* < examples/media/$IN"
    "$PYTHON" -m src.thumbnail "$@" < "examples/media/$IN"
    echo "код завершения: $?"
    echo
}

echo "Пример 1. Кадр на 1-й секунде, ширина по умолчанию 320"
IN=testsrc.mp4 run "$OUT/testsrc.jpg"

echo "Пример 2. Видео 1280x720, кадр на 2-й секунде, ширина 480"
IN=bars_hd.mp4 run "$OUT/bars_hd.jpg" --time 2 --width 480

echo "Пример 3. Вертикальное видео 360x640, ширина 180"
IN=vertical.mp4 run "$OUT/vertical.jpg" --width 180

echo "Пример 4. Фрактал, кадр на 3.5 с, ширина 640"
IN=mandelbrot.mp4 run "$OUT/mandelbrot.jpg" --time 3.5 --width 640

echo "Ошибка 1. На вход подан не MP4"
IN=not_video.mp4 run "$OUT/bad.jpg"

echo "Ошибка 2. Позиция кадра за пределами видео"
IN=vertical.mp4 run "$OUT/late.jpg" --time 60
