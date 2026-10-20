#!/bin/sh
set -e
cd "$(dirname "$0")"
FFMPEG="${FFMPEG_PATH:-ffmpeg}"
mkdir -p media

make() {
    "$FFMPEG" -v error -y -f lavfi -i "$1" -t "$2" -pix_fmt yuv420p \
        -c:v libx264 "media/$3"
    echo "создан media/$3"
}

make "testsrc=size=640x360:rate=25" 5 testsrc.mp4
make "smptehdbars=size=1280x720:rate=25" 4 bars_hd.mp4
make "testsrc2=size=360x640:rate=25" 3 vertical.mp4
make "mandelbrot=size=480x360:rate=25" 4 mandelbrot.mp4
echo "это не видео" > media/not_video.mp4
echo "создан media/not_video.mp4"
