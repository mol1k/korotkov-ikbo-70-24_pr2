import argparse

import uvicorn

from src.app import create_app
from src.runner import FakeRunner, SubprocessRunner
from src.service import ThumbnailService
from src.storage import MemoryStorage

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_MEDIA = "examples/media"
DEFAULT_OUTPUT = "data/thumbnails"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="HTTP API генерации миниатюр JPEG для видео MP4")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--media", default=DEFAULT_MEDIA,
                        help="папка с видео MP4")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help="папка для миниатюр")
    parser.add_argument("--test-mode", action="store_true",
                        help="не запускать реальную генерацию миниатюр")
    return parser.parse_args(argv)


def build_app(args):
    if args.test_mode:
        runner = FakeRunner()
    else:
        runner = SubprocessRunner(args.media, args.output)
    return create_app(ThumbnailService(MemoryStorage(), runner))


def main():
    args = parse_args()
    uvicorn.run(build_app(args), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
