from typing import Annotated

from fastapi import (
    APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request)
from fastapi.responses import JSONResponse
from pydantic import (
    BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError)

from src.errors import ConflictError, NotFoundError

JSON_MEDIA_TYPE = "text/json"
LANGUAGE = "ru-RU"
STATUS_UNSUPPORTED_MEDIA = 415
STATUS_NOT_ACCEPTABLE = 406
STATUS_NOT_FOUND = 404
STATUS_CONFLICT = 409
STATUS_UNPROCESSABLE = 422


def header_values(request, name):
    raw = request.headers.get(name, "")
    return [part.split(";")[0].strip() for part in raw.split(",")]


def check_headers(request: Request):
    if JSON_MEDIA_TYPE not in header_values(request, "content-type"):
        raise HTTPException(
            STATUS_UNSUPPORTED_MEDIA,
            f"требуется заголовок Content-Type: {JSON_MEDIA_TYPE}")
    if LANGUAGE not in header_values(request, "accept-language"):
        raise HTTPException(
            STATUS_NOT_ACCEPTABLE,
            f"требуется заголовок Accept-Language: {LANGUAGE}")


def get_service(request: Request):
    return request.app.state.service


SERVICE = Annotated[object, Depends(get_service)]


class ClientChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time: StrictInt | None = None
    platform: StrictStr | None = None


class PromptChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time: StrictInt | None = None
    argument: StrictStr | None = None
    client: StrictInt = None
    tags: StrictStr | None = None
    stage: StrictStr | None = None


async def read_changes(request, model):
    body = await request.body()
    try:
        changes = model.model_validate_json(body)
    except ValidationError as error:
        detail = error.errors(include_url=False, include_context=False,
                              include_input=False)
        raise HTTPException(STATUS_UNPROCESSABLE, detail) from None
    return changes.model_dump(exclude_unset=True)


def compact(**values):
    return {key: value for key, value in values.items() if value is not None}


router = APIRouter(
    prefix="/private/api", dependencies=[Depends(check_headers)])


@router.put("/client-register/{uid}")
def client_register(uid: int, service: SERVICE, time: int | None = None,
                    platform: str | None = None):
    return service.register_client(uid, time, platform)


@router.post("/client-load")
def client_load(service: SERVICE, platform: str | None = None,
                time: int | None = None):
    return service.load_clients(compact(platform=platform, time=time))


@router.patch("/client-alter/{uid}")
async def client_alter(uid: int, request: Request, service: SERVICE):
    changes = await read_changes(request, ClientChanges)
    return service.alter_client(uid, changes)


@router.put("/prompt-register/{uid}")
def prompt_register(uid: int, client: int, service: SERVICE,
                    tasks: BackgroundTasks, time: int | None = None,
                    argument: str | None = None, tags: str | None = None):
    prompt = service.register_prompt(uid, client, time, argument, tags)
    tasks.add_task(service.process_prompt, uid)
    return prompt


@router.post("/prompt-load/{client}")
def prompt_load(client: int, service: SERVICE, stage: str | None = None,
                tags: str | None = None, argument: str | None = None):
    filters = compact(stage=stage, tags=tags, argument=argument)
    return service.load_prompts(client, filters)


@router.patch("/prompt-alter/{uid}")
async def prompt_alter(uid: int, request: Request, service: SERVICE):
    changes = await read_changes(request, PromptChanges)
    return service.alter_prompt(uid, changes)


@router.post("/result-load/{prompt}")
def result_load(prompt: int, service: SERVICE, stage: str | None = None,
                cache_hit: int | None = None):
    filters = compact(stage=stage, cache_hit=cache_hit)
    return service.load_results(prompt, filters)


@router.post("/report-load")
def report_load(service: SERVICE):
    return service.report()


def error_handler(status):
    def handle(request, error):
        return JSONResponse({"detail": str(error)}, status_code=status)
    return handle


def create_app(service):
    app = FastAPI(title="Миниатюры JPEG для видео MP4")
    app.state.service = service
    app.include_router(router)
    app.add_exception_handler(NotFoundError, error_handler(STATUS_NOT_FOUND))
    app.add_exception_handler(ConflictError, error_handler(STATUS_CONFLICT))
    return app
