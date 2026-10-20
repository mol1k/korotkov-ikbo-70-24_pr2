import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

MP4_SIGNATURE = b"ftyp"
SIGNATURE_START = 4
SIGNATURE_END = 8
DEFAULT_TIME = 1.0
DEFAULT_WIDTH = 320
MIN_TIME = 0.0
MIN_WIDTH = 16
MAX_WIDTH = 3840
JPEG_QUALITY = 3
EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_FFMPEG_ERROR = 2
FFMPEG_ENV = "FFMPEG_PATH"


class ThumbnailError(Exception):

    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def find_ffmpeg():
    path = os.environ.get(FFMPEG_ENV) or shutil.which("ffmpeg")
    if path is None:
        raise ThumbnailError(
            "ffmpeg не найден: установите его или задайте FFMPEG_PATH",
            EXIT_FFMPEG_ERROR)
    return path


def check_mp4(data):
    if not data:
        raise ThumbnailError("пустые входные данные", EXIT_INPUT_ERROR)
    if data[SIGNATURE_START:SIGNATURE_END] != MP4_SIGNATURE:
        raise ThumbnailError(
            "входные данные не являются файлом MP4", EXIT_INPUT_ERROR)


def build_command(ffmpeg, source, output, moment, width):
    return [
        ffmpeg, "-v", "error", "-y",
        "-ss", str(moment), "-i", source,
        "-frames:v", "1", "-vf", f"scale={width}:-2",
        "-q:v", str(JPEG_QUALITY), "-f", "image2", output,
    ]


def run_ffmpeg(command):
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != EXIT_OK:
        message = completed.stderr.strip() or "неизвестная ошибка"
        raise ThumbnailError(f"ffmpeg: {message}", EXIT_FFMPEG_ERROR)


def make_thumbnail(data, output, moment=DEFAULT_TIME, width=DEFAULT_WIDTH):
    check_mp4(data)
    ffmpeg = find_ffmpeg()
    folder = os.path.dirname(os.path.abspath(output))
    os.makedirs(folder, exist_ok=True)
    if os.path.exists(output):
        os.remove(output)
    with tempfile.TemporaryDirectory() as temp:
        source = os.path.join(temp, "input.mp4")
        with open(source, "wb") as file:
            file.write(data)
        run_ffmpeg(build_command(ffmpeg, source, output, moment, width))
    if not os.path.isfile(output):
        raise ThumbnailError(
            f"в видео нет кадра на позиции {moment} с", EXIT_INPUT_ERROR)
    return {
        "output": output,
        "size": os.path.getsize(output),
        "time": moment,
        "width": width,
    }


def moment_type(text):
    value = float(text)
    if value < MIN_TIME:
        raise argparse.ArgumentTypeError("время не может быть отрицательным")
    return value


def width_type(text):
    value = int(text)
    if not MIN_WIDTH <= value <= MAX_WIDTH:
        raise argparse.ArgumentTypeError(
            f"ширина должна быть от {MIN_WIDTH} до {MAX_WIDTH}")
    return value


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Миниатюра JPEG для видео MP4 из стандартного ввода")
    parser.add_argument("output", help="путь к файлу JPEG")
    parser.add_argument(
        "--time", type=moment_type, default=DEFAULT_TIME,
        help="момент кадра в секундах (по умолчанию 1.0)")
    parser.add_argument(
        "--width", type=width_type, default=DEFAULT_WIDTH,
        help="ширина миниатюры в пикселях (по умолчанию 320)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    data = sys.stdin.buffer.read()
    try:
        info = make_thumbnail(data, args.output, args.time, args.width)
    except ThumbnailError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return error.code
    print(json.dumps(info, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
