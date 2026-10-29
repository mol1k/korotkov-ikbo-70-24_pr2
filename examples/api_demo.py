import json
import sys
import time

from src.client import DEFAULT_URL, ApiClient, ApiError

WAIT_SECONDS = 3
HOUR = 3600
MINUTE = 60


def show(title, call, *args, **kwargs):
    print(f"> {title}")
    try:
        answer = call(*args, **kwargs)
    except ApiError as error:
        print(f"  ошибка {error.status}: {error.detail}")
        return None
    print("  " + json.dumps(answer, ensure_ascii=False))
    return answer


def register(api, now):
    show("регистрация клиента 1 (активен минуту назад)",
         api.private_api_client_register, 1, now - MINUTE, "macos")
    show("регистрация клиента 2 (активен час назад)",
         api.private_api_client_register, 2, now - HOUR, "windows")
    show("повторная регистрация клиента 1",
         api.private_api_client_register, 1)
    show("поиск клиентов с platform=macos",
         api.private_api_client_load, platform="macos")
    show("изменение клиента 2", api.private_api_client_alter, 2,
         platform="linux")
    show("изменение клиента 2 с неверным типом поля",
         api.private_api_client_alter, 2, time="вчера")


def run_tasks(api):
    tasks = [
        (1, 1, "testsrc.mp4"), (2, 2, "mandelbrot.mp4"),
        (3, 1, "not_video.mp4"), (4, 2, "../secret.mp4"),
    ]
    for uid, client, argument in tasks:
        show(f"задача {uid}: миниатюра для {argument}",
             api.private_api_prompt_register, uid, client,
             argument=argument, tags="demo")
    show("задача для несуществующего клиента 9",
         api.private_api_prompt_register, 5, 9, argument="testsrc.mp4")
    print(f"... ждём {WAIT_SECONDS} с, пока задачи выполнятся в фоне")
    time.sleep(WAIT_SECONDS)
    show("повтор задачи 1 (берётся из кэша)",
         api.private_api_prompt_register, 6, 2, argument="testsrc.mp4")
    time.sleep(1)


def inspect(api):
    show("задачи клиента 1", api.private_api_prompt_load, 1)
    for prompt in range(1, 7):
        show(f"результат задачи {prompt}",
             api.private_api_result_load, prompt)
    show("изменение задачи 4: перенос к клиенту 1",
         api.private_api_prompt_alter, 4, client=1, stage="archived")
    show("отчёт по формуле (7)", api.private_api_report_load)


def main():
    url = sys.argv[1] if sys.argv[1:] else DEFAULT_URL
    with ApiClient(url) as api:
        now = int(time.time())
        register(api, now)
        run_tasks(api)
        inspect(api)
        api.headers = {"Accept-Language": "ru-RU"}
        show("запрос без Content-Type", api.private_api_report_load)
        api.headers = {"Content-Type": "text/json"}
        show("запрос без Accept-Language", api.private_api_report_load)


if __name__ == "__main__":
    main()
