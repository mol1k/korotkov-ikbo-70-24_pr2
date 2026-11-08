Веб-приложение для асинхронной генерации миниатюр JPEG из видео MP4
==================================================================

Практическая работа №2, вариант 7.
Дисциплина «Прикладная разработка серверных частей веб-приложений на
языке Питон».

Коротков Дмитрий Максимович, группа ИКБО-70-24.

Тема курсовой работы: веб-приложение с HTTP API для асинхронной
генерации миниатюры в формате JPEG для файлов в формате MP4.


1. Общее описание
-----------------

Вычислительная задача приложения - получить из видео MP4 один кадр и
сохранить его уменьшенную копию (миниатюру) в формате JPEG. Кадр
извлекается с помощью ffmpeg.

Работа выполняется в три этапа:

- этап 1: утилита командной строки src/thumbnail.py - принимает видео
  через стандартный ввод и сохраняет миниатюру на диск;
- этап 2: HTTP API на FastAPI для управления задачами генерации
  миниатюр, клиент API и тестирование на основе модели (MBT);
- этап 3: хранение данных в документ-ориентированной СУБД TinyDB.

Требования: Python 3.10 или новее и ffmpeg.

Установка ffmpeg:

    brew install ffmpeg          (macOS, Homebrew)
    conda install ffmpeg         (Anaconda)
    sudo apt install ffmpeg      (Ubuntu, Debian)

Если ffmpeg установлен не в стандартное место, путь к нему задаётся
переменной окружения FFMPEG_PATH.


2. Утилита командной строки (этап 1)
------------------------------------

Файл src/thumbnail.py. Утилита читает видео MP4 из стандартного ввода,
извлекает кадр в заданный момент времени, уменьшает его до заданной
ширины (высота подбирается с сохранением пропорций) и сохраняет
результат в файл JPEG.

Запуск:

    python -m src.thumbnail ВЫХОД.jpg [--time СЕКУНДЫ] [--width ПИКСЕЛИ] < ВИДЕО.mp4

Параметры:

- ВЫХОД.jpg - путь к файлу миниатюры; папки создаются автоматически;
- --time - момент кадра в секундах, по умолчанию 1.0, не меньше 0;
- --width - ширина миниатюры, по умолчанию 320, от 16 до 3840.

При успехе утилита печатает в стандартный вывод JSON со сведениями о
результате (путь, размер файла в байтах, момент кадра, ширина) и
завершается с кодом 0.

Коды завершения:

    0 - миниатюра создана
    1 - ошибка входных данных: пустой ввод, данные не MP4, в видео нет
        кадра в указанный момент
    2 - ошибка ffmpeg: ffmpeg не найден или не смог обработать видео

Функции модуля:

- make_thumbnail(data, output, moment, width) - создать миниатюру из
  байтов видео, вернуть словарь со сведениями о результате;
- check_mp4(data) - проверить, что данные непустые и содержат сигнатуру
  MP4 (блок ftyp);
- find_ffmpeg() - найти ffmpeg (переменная FFMPEG_PATH или PATH);
- build_command(...) - собрать команду ffmpeg;
- run_ffmpeg(command) - выполнить ffmpeg, при ошибке возбудить
  ThumbnailError;
- main(argv) - точка входа командной строки.

Видео сначала записывается во временный файл: файл MP4 из стандартного
ввода нельзя читать с произвольной позиции, а служебный блок moov часто
находится в конце файла.

Пример видео для демонстрации создаёт скрипт examples/make_samples.sh
(генерирует 4 тестовых ролика средствами ffmpeg и один файл, не
являющийся видео). Сами ролики и миниатюры в репозиторий не входят,
так как это двоичные файлы.

Демонстрация на 4 примерах (./run.sh examples):

    Пример 1. Кадр на 1-й секунде, ширина по умолчанию 320
    $ python -m src.thumbnail examples/output/testsrc.jpg < examples/media/testsrc.mp4
    {"output": "examples/output/testsrc.jpg", "size": 7138, "time": 1.0, "width": 320}
    код завершения: 0

    Пример 2. Видео 1280x720, кадр на 2-й секунде, ширина 480
    $ python -m src.thumbnail examples/output/bars_hd.jpg --time 2 --width 480 < examples/media/bars_hd.mp4
    {"output": "examples/output/bars_hd.jpg", "size": 6866, "time": 2.0, "width": 480}
    код завершения: 0

    Пример 3. Вертикальное видео 360x640, ширина 180
    $ python -m src.thumbnail examples/output/vertical.jpg --width 180 < examples/media/vertical.mp4
    {"output": "examples/output/vertical.jpg", "size": 8866, "time": 1.0, "width": 180}
    код завершения: 0

    Пример 4. Фрактал, кадр на 3.5 с, ширина 640
    $ python -m src.thumbnail examples/output/mandelbrot.jpg --time 3.5 --width 640 < examples/media/mandelbrot.mp4
    {"output": "examples/output/mandelbrot.jpg", "size": 46895, "time": 3.5, "width": 640}
    код завершения: 0

    Ошибка 1. На вход подан не MP4
    $ python -m src.thumbnail examples/output/bad.jpg < examples/media/not_video.mp4
    Ошибка: входные данные не являются файлом MP4
    код завершения: 1

    Ошибка 2. Позиция кадра за пределами видео
    $ python -m src.thumbnail examples/output/late.jpg --time 60 < examples/media/vertical.mp4
    Ошибка: в видео нет кадра на позиции 60.0 с
    код завершения: 1

Размеры полученных миниатюр: 320x180, 480x270, 180x320 и 640x480 -
высота везде подобрана по пропорциям исходного видео.


3. HTTP API (этап 2)
--------------------

Веб-приложение на FastAPI (src/app.py) управляет задачами генерации
миниатюр. Схема данных:

Client: id (int), time (int), platform (str) - клиент API.

Prompt: id (int), time (int), argument (str), client (int), tags (str),
stage (str) - задача на генерацию миниатюры. Поле argument - имя файла
MP4 в папке видео, client ссылается на Client.id, stage - состояние
задачи: queued, running, done или failed.

Result: id (int), time (int), result (str), stage (str), error (str),
prompt (int), cache_hit (int) - результат выполнения задачи. Поле
result - путь к миниатюре, error - текст ошибки, prompt ссылается на
Prompt.id, cache_hit равно 1, если миниатюра взята из кэша.

Обязательные поля: id, Prompt.client и Result.prompt, остальные могут
быть null.

Обработчики (таблица 7 варианта):

    1.1 PUT   /private/api/client-register/{id}   создать клиента
        параметры строки запроса: time, platform
    1.2 POST  /private/api/client-load            найти клиентов
        параметры строки запроса (фильтры): platform, time
    1.3 PATCH /private/api/client-alter/{id}      изменить клиента
        тело в JSON: {"time": ..., "platform": ...}
    2.1 PUT   /private/api/prompt-register/{id}   создать задачу
        параметры строки запроса: client (обязательный), time,
        argument, tags
    2.2 POST  /private/api/prompt-load/{client}   найти задачи клиента
        параметры строки запроса (фильтры): stage, tags, argument
    2.3 PATCH /private/api/prompt-alter/{id}      изменить задачу
        тело в JSON: {"time", "argument", "client", "tags", "stage"}
    3.1 POST  /private/api/result-load/{prompt}   найти результаты задачи
        параметры строки запроса (фильтры): stage, cache_hit
    4.1 POST  /private/api/report-load            отчёт по формуле (7)

Все обработчики возвращают JSON: запись, список записей или отчёт. В
теле PATCH передаются только изменяемые поля; неизвестные поля и
значения неверного типа отклоняются.

Обязательные заголовки. Все обработчики используют методы POST, PUT
или PATCH, поэтому проверяются оба заголовка, по порядку:

    Content-Type: text/json      иначе 415 Unsupported Media Type
    Accept-Language: ru-RU       иначе 406 Not Acceptable

Проверка заголовков выполняется раньше всех остальных проверок.
Допускаются параметры и списки значений, например
"text/json; charset=utf-8" или "en-US, ru-RU;q=0.5".

Коды ответов:

    200 - успешно, тело в JSON
    404 - нет записи с указанным id или нет клиента, на которого
          ссылается задача
    406, 415 - нет обязательного заголовка (см. выше)
    409 - запись с таким id уже существует (повторный PUT)
    422 - неверный тип параметра или некорректное тело JSON

Асинхронное выполнение задач. Обработчик 2.1 сохраняет задачу со
стадией queued и сразу возвращает ответ, а генерация миниатюры
выполняется в фоне (BackgroundTasks FastAPI). Фоновая задача:

1. переводит задачу в стадию running;
2. ищет в кэше готовую миниатюру для того же argument - если она есть,
   новый результат ссылается на неё и получает cache_hit = 1;
3. иначе запускает утилиту этапа 1 через стандартный модуль subprocess:
   видео из папки media подаётся на стандартный ввод, миниатюра
   сохраняется в data/thumbnails/prompt-{id}.jpg;
4. сохраняет Result и переводит задачу в стадию done или failed.

Argument должен быть именем файла вида name.mp4 без пути: имена с
папками (например, ../secret.mp4) отклоняются, чтобы нельзя было
прочитать файл вне папки видео.

Тестовый режим (ключ --test-mode): вместо запуска утилиты используется
FakeRunner, который не обращается к ffmpeg и сразу возвращает имя
миниатюры prompt-{id}.jpg. Остальная логика (кэш, стадии, ошибки) та
же.

Отчёт 4.1 строится по формуле варианта:

    pi[C.platform, P.argument](
        (sigma[C.time >= now - 7 min] C)
        правое внешнее соединение [C.id = P.client]
        P
    )

- sigma отбирает клиентов, активных за последние 7 минут;
- правое внешнее соединение сохраняет все задачи; если клиент задачи
  не прошёл отбор, platform равно null;
- pi оставляет поля platform и argument и удаляет повторяющиеся строки.

Модули:

- src/app.py - маршруты FastAPI, проверка заголовков, разбор тела JSON,
  create_app(service) создаёт приложение;
- src/service.py - ThumbnailService: логика API, фоновая обработка
  задач, кэш, отчёт;
- src/storage.py - хранилище записей (get, insert, update, search,
  next_id): на этапе 2 - MemoryStorage в памяти, на этапе 3 -
  TinyStorage на TinyDB (раздел 4);
- src/runner.py - SubprocessRunner (запуск утилиты через subprocess)
  и FakeRunner (тестовый режим), проверка argument;
- src/errors.py - NotFoundError, ConflictError;
- src/server.py - запуск сервера uvicorn;
- src/client.py - клиент API.

Настройки сервера (python -m src.server):

    --host       адрес, по умолчанию 127.0.0.1
    --port       порт, по умолчанию 8000
    --media      папка с видео, по умолчанию examples/media
    --output     папка для миниатюр, по умолчанию data/thumbnails
    --db         файл базы TinyDB, по умолчанию data/db.json (этап 3)
    --test-mode  тестовый режим без реальной генерации

Клиент API (src/client.py) - класс ApiClient. Имена методов получены из
маршрутов таблицы 7 заменой «/» и «-» на «_»:

    private_api_client_register(uid, time=None, platform=None)
    private_api_client_load(platform=None, time=None)
    private_api_client_alter(uid, **changes)
    private_api_prompt_register(uid, client, time=None, argument=None,
                                tags=None)
    private_api_prompt_load(client, stage=None, tags=None, argument=None)
    private_api_prompt_alter(uid, **changes)
    private_api_result_load(prompt, stage=None, cache_hit=None)
    private_api_report_load()

Клиент сам добавляет обязательные заголовки (атрибут headers). При
коде ответа, отличном от 200, возбуждается ApiError с полями status и
detail. Метод send(method, route, params, content) отправляет
произвольный запрос.

    from src.client import ApiClient

    with ApiClient("http://127.0.0.1:8000") as api:
        api.private_api_client_register(1, time=1794900000, platform="macos")
        api.private_api_prompt_register(1, client=1, argument="testsrc.mp4")
        print(api.private_api_result_load(1))
        print(api.private_api_report_load())

Тестирование на основе модели. Файл tests/test_api_state_machine.py,
класс ApiStateMachine на основе RuleBasedStateMachine из hypothesis.

- Сложная система - приложение FastAPI в тестовом режиме, с которым
  тест работает только через ApiClient (транспорт - TestClient FastAPI).
- Упрощённая модель - tests/reference_model.py: словари записей и
  прямолинейная реализация кэша, стадий и отчёта.
- hypothesis генерирует последовательности правил (100 сценариев до 30
  шагов): регистрация, поиск и изменение клиентов и задач, загрузка
  результатов, отчёт, ошибки 404/409/422 и запросы с неполными
  заголовками (406/415). После каждого шага инвариант сравнивает список
  клиентов сервера с моделью.
- Шаг @initialize в начале каждого сценария создаёт клиента и две задачи
  с одним видео, вторая из которых обязана попасть в кэш.
- Время в тестах зафиксировано (now = 1760000000), чтобы отчёт был
  детерминированным.

Отчёт о покрытии на этапе 2 (хранилище в памяти):

    Name              Stmts   Miss Branch BrPart  Cover   Missing
    -------------------------------------------------------------
    src/__init__.py       0      0      0      0   100%
    src/app.py           86      0      4      0   100%
    src/client.py        53      0      2      0   100%
    src/errors.py         6      0      0      0   100%
    src/runner.py        31      0      4      0   100%
    src/service.py       76      0     16      0   100%
    src/storage.py       37      0      0      0   100%
    -------------------------------------------------------------
    TOTAL               289      0     26      0   100%

Из замера исключены утилита этапа 1 (src/thumbnail.py), запуск сервера
(src/server.py) и части, которые в тестовом режиме заменены
детерминированными: SubprocessRunner и функция текущего времени
current_time. Все 8 обработчиков HTTP API покрыты полностью.

Пример работы API (./run.sh server, затем ./run.sh demo-api):

    > регистрация клиента 1 (активен минуту назад)
      {"id": 1, "time": 1794903361, "platform": "macos"}
    > регистрация клиента 2 (активен час назад)
      {"id": 2, "time": 1794899821, "platform": "windows"}
    > повторная регистрация клиента 1
      ошибка 409: Client: запись с id=1 уже существует
    > поиск клиентов с platform=macos
      [{"id": 1, "time": 1794903361, "platform": "macos"}]
    > изменение клиента 2
      {"id": 2, "time": 1794899821, "platform": "linux"}
    > изменение клиента 2 с неверным типом поля
      ошибка 422: [{'type': 'int_type', 'loc': ['time'], 'msg': 'Input should be a valid integer'}]
    > задача 1: миниатюра для testsrc.mp4
      {"id": 1, "time": null, "argument": "testsrc.mp4", "client": 1, "tags": "demo", "stage": "queued"}
    > задача 2: миниатюра для mandelbrot.mp4
      {"id": 2, "time": null, "argument": "mandelbrot.mp4", "client": 2, "tags": "demo", "stage": "queued"}
    > задача 3: миниатюра для not_video.mp4
      {"id": 3, "time": null, "argument": "not_video.mp4", "client": 1, "tags": "demo", "stage": "queued"}
    > задача 4: миниатюра для ../secret.mp4
      {"id": 4, "time": null, "argument": "../secret.mp4", "client": 2, "tags": "demo", "stage": "queued"}
    > задача для несуществующего клиента 9
      ошибка 404: Client: запись с id=9 не найдена
    ... ждём 3 с, пока задачи выполнятся в фоне
    > повтор задачи 1 (берётся из кэша)
      {"id": 6, "time": null, "argument": "testsrc.mp4", "client": 2, "tags": null, "stage": "queued"}
    > задачи клиента 1
      [{"id": 1, "time": null, "argument": "testsrc.mp4", "client": 1, "tags": "demo", "stage": "done"}, {"id": 3, "time": null, "argument": "not_video.mp4", "client": 1, "tags": "demo", "stage": "failed"}]
    > результат задачи 1
      [{"id": 4, "time": 1794903421, "result": "data/thumbnails/prompt-1.jpg", "stage": "done", "error": null, "prompt": 1, "cache_hit": 0}]
    > результат задачи 2
      [{"id": 3, "time": 1794903421, "result": "data/thumbnails/prompt-2.jpg", "stage": "done", "error": null, "prompt": 2, "cache_hit": 0}]
    > результат задачи 3
      [{"id": 2, "time": 1794903421, "result": null, "stage": "failed", "error": "Ошибка: входные данные не являются файлом MP4", "prompt": 3, "cache_hit": 0}]
    > результат задачи 4
      [{"id": 1, "time": 1794903421, "result": null, "stage": "failed", "error": "аргумент должен быть именем файла .mp4 в папке видео", "prompt": 4, "cache_hit": 0}]
    > результат задачи 5
      ошибка 404: Prompt: запись с id=5 не найдена
    > результат задачи 6
      [{"id": 5, "time": 1794903424, "result": "data/thumbnails/prompt-1.jpg", "stage": "done", "error": null, "prompt": 6, "cache_hit": 1}]
    > изменение задачи 4: перенос к клиенту 1
      {"id": 4, "time": null, "argument": "../secret.mp4", "client": 1, "tags": "demo", "stage": "archived"}
    > отчёт по формуле (7)
      [{"platform": "macos", "argument": "testsrc.mp4"}, {"platform": null, "argument": "mandelbrot.mp4"}, {"platform": "macos", "argument": "not_video.mp4"}, {"platform": "macos", "argument": "../secret.mp4"}, {"platform": null, "argument": "testsrc.mp4"}]
    > запрос без Content-Type
      ошибка 415: требуется заголовок Content-Type: text/json
    > запрос без Accept-Language
      ошибка 406: требуется заголовок Accept-Language: ru-RU

Тот же API через curl:

    curl -X PUT "http://127.0.0.1:8000/private/api/client-register/1?platform=macos" \
         -H "Content-Type: text/json" -H "Accept-Language: ru-RU"
    {"id":1,"time":null,"platform":"macos"}

    curl -X PATCH "http://127.0.0.1:8000/private/api/client-alter/1" \
         -H "Content-Type: text/json" -H "Accept-Language: ru-RU" \
         -d '{"platform": "linux"}'
    {"id":1,"time":null,"platform":"linux"}

    curl -i -X POST "http://127.0.0.1:8000/private/api/report-load" \
         -H "Accept-Language: ru-RU"
    HTTP/1.1 415 Unsupported Media Type

Документация OpenAPI запущенного сервера: http://127.0.0.1:8000/docs
(отправлять запросы оттуда нельзя без заголовков, используйте клиент
или curl).


4. Хранение данных в TinyDB (этап 3)
------------------------------------

Хранилище в памяти MemoryStorage заменено на TinyStorage (src/storage.py)
на основе документ-ориентированной СУБД TinyDB (библиотека tinydb).
Данные сохраняются на диск в файл JSON (по умолчанию data/db.json) и
не теряются при перезапуске сервера.

Устройство:

- каждой сущности соответствует своя таблица TinyDB: Client, Prompt,
  Result;
- запись хранится как документ, его doc_id совпадает с полем id, поэтому
  поиск по id выполняется без перебора таблицы;
- поиск с фильтрами выполняется запросом Query().fragment(filters):
  документ подходит, если содержит все поля фильтра с теми же
  значениями;
- операции защищены блокировкой (threading.Lock): фоновые задачи
  выполняются в других потоках, а TinyDB не потокобезопасна.

Методы TinyStorage (тот же интерфейс, что был у MemoryStorage, поэтому
ThumbnailService и обработчики API не изменились):

    get(table, uid)               запись по id или None
    insert(table, record)         добавить запись
    update(table, uid, changes)   изменить поля записи
    search(table, filters)        записи с совпадающими полями
    next_id(table)                следующий свободный id
    close()                       закрыть файл базы

Настройка сервера: ключ --db задаёт файл базы данных:

    python -m src.server --db data/db.json

Чтобы начать с пустой базой, удалите папку data (или укажите другой
файл в --db).

Тесты MBT выполняются с TinyStorage: каждый сценарий hypothesis
создаёт свой временный файл базы и удаляет его в конце. Отчёт о
покрытии кода тестами на основе ветвей со слоем данных на TinyDB:

    Name              Stmts   Miss Branch BrPart  Cover   Missing
    -------------------------------------------------------------
    src/__init__.py       0      0      0      0   100%
    src/app.py           86      0      4      0   100%
    src/client.py        53      0      2      0   100%
    src/errors.py         6      0      0      0   100%
    src/runner.py        31      0      4      0   100%
    src/service.py       76      0     16      0   100%
    src/storage.py       37      0      0      0   100%
    -------------------------------------------------------------
    TOTAL               289      0     26      0   100%

Пример: данные сохраняются после перезапуска сервера. Сервер запущен,
выполнен ./run.sh demo-api, сервер остановлен и запущен снова:

    >>> после перезапуска сервера: client-load
    {'id': 1, 'time': 1794903675, 'platform': 'macos'}
    {'id': 2, 'time': 1794900135, 'platform': 'linux'}
    >>> result-load/6
    [{'id': 5, 'time': 1794903738, 'result': 'data/thumbnails/prompt-1.jpg', 'stage': 'done', 'error': None, 'prompt': 6, 'cache_hit': 1}]

Начало файла data/db.json:

    {"Client": {"1": {"id": 1, "time": 1794903675, "platform": "macos"},
    "2": {"id": 2, "time": 1794900135, "platform": "linux"}}, "Prompt":
    {"1": {"id": 1, "time": null, "argument": "testsrc.mp4", "client": 1,
    "tags": "demo", "stage": "done"}, ...


Сборка, запуск и тесты
----------------------

Сборка не требуется. Установка зависимостей (FastAPI, uvicorn, httpx, tinydb,
hypothesis, coverage, flake8, pep8-naming):

    ./run.sh install

Команды run.sh:

    ./run.sh samples       создать примеры видео в examples/media
    ./run.sh examples      утилита на 4 примерах и 2 ошибках
    ./run.sh thumbnail     утилита, например:
                           ./run.sh thumbnail out.jpg --width 200 < video.mp4
    ./run.sh server        HTTP API с реальной генерацией миниатюр
    ./run.sh server-test   HTTP API в тестовом режиме (без ffmpeg)
    ./run.sh demo-api      демонстрация API через клиент
                           (сервер должен быть запущен в другом окне)
    ./run.sh test          тесты MBT и отчёт о покрытии
    ./run.sh lint          проверка кода flake8

Порт сервера задаётся переменной PORT (по умолчанию 8000). Если
python3 в системе не тот, в который установлены зависимости, укажите
интерпретатор: export PYTHON=python.

Без run.sh (например, в Windows) из корня репозитория:

    python -m src.thumbnail out.jpg < video.mp4
    python -m src.server --port 8000 [--test-mode]
    python -m examples.api_demo http://127.0.0.1:8000
    python -m coverage run -m unittest discover -s tests -t . -v
    python -m coverage report
    python -m flake8 src tests examples
