import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ARGUMENT_PATTERN = re.compile(r"[\w.-]+\.mp4")
ARGUMENT_ERROR = "аргумент должен быть именем файла .mp4 в папке видео"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TASK_TIMEOUT = 120
EXIT_OK = 0
DEFAULT_TIME = 1.0
DEFAULT_WIDTH = 320


@dataclass
class TaskOutcome:
    ok: bool
    result: str | None
    error: str | None


def check_argument(argument):
    if argument is None or not ARGUMENT_PATTERN.fullmatch(argument):
        return ARGUMENT_ERROR
    return None


def thumbnail_name(prompt_id):
    return f"prompt-{prompt_id}.jpg"


def failure(error):
    return TaskOutcome(False, None, error)


class FakeRunner:

    def run(self, prompt_id, argument):
        error = check_argument(argument)
        if error is not None:
            return failure(error)
        return TaskOutcome(True, thumbnail_name(prompt_id), None)


class SubprocessRunner:

    def __init__(self, media_dir, output_dir, moment=DEFAULT_TIME,
                 width=DEFAULT_WIDTH):
        self.media_dir = Path(media_dir)
        self.output_dir = Path(output_dir)
        self.moment = moment
        self.width = width

    def command(self, output):
        return [
            sys.executable, "-m", "src.thumbnail", str(output.resolve()),
            "--time", str(self.moment), "--width", str(self.width),
        ]

    def execute(self, source, output):
        try:
            with source.open("rb") as stream:
                return subprocess.run(
                    self.command(output), stdin=stream, cwd=PROJECT_ROOT,
                    capture_output=True, text=True, timeout=TASK_TIMEOUT)
        except subprocess.TimeoutExpired:
            return None

    def run(self, prompt_id, argument):
        error = check_argument(argument)
        if error is not None:
            return failure(error)
        source = self.media_dir / argument
        if not source.is_file():
            return failure(f"файл {argument} не найден в папке видео")
        output = self.output_dir / thumbnail_name(prompt_id)
        completed = self.execute(source, output)
        if completed is None:
            return failure("превышено время выполнения задачи")
        if completed.returncode != EXIT_OK:
            return failure(completed.stderr.strip())
        return TaskOutcome(True, str(output), None)
