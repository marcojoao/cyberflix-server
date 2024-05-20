import os

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from lib import env
from lib.web_worker import WebWorker

SERVER_VERSION = "0.3.3"

worker = WebWorker()
app = FastAPI()

project_dir = os.path.join(app.root_path, "web/")
app.mount("/static", StaticFiles(directory=project_dir), name="static")
templates = Jinja2Templates(directory=project_dir)


def add_cache_headers(max_age: int) -> dict:
    """Add cache control headers."""
    return {
        "Cache-Control": f"max-age={max_age}, stale-while-revalidate={max_age}, "
        f"stale-if-error={max_age}, public"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Check server health."""
    return JSONResponse({"status": "ok"}, status_code=200)


def __json_response(data: dict, extra_headers: dict[str, str] = {}, status_code: int = 200):
    response = JSONResponse(data, status_code=status_code)
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*",
    }
    headers.update(extra_headers)
    response.headers.update(headers)
    return response


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    cache_age = 60 * 60 * 2  # 2 hours
    headers = add_cache_headers(cache_age)
    response = templates.TemplateResponse("index.html", {"request": request}, headers=headers)
    return response


@app.get("/configure")
@app.get("/c/{configs}/configure")
async def configure(configs: str | None = None):
    return RedirectResponse(url="/", status_code=302)


def get_image_asset(image_path: str):
    cache_age = 60 * 60 * 12  # 12 hours
    headers = add_cache_headers(cache_age)
    media_type = "image/jpeg"
    if image_path.endswith(".ico"):
        media_type = "image/vnd.microsoft.icon"
    elif image_path.endswith(".png"):
        media_type = "image/png"

    return FileResponse(image_path, media_type=media_type, headers=headers)


@app.get("/favicon.ico")
async def favicon():
    return get_image_asset("./web/favicon.png")


@app.get("/logo.png")
async def logo():
    return get_image_asset("./web/assets/assets/logo.png")


@app.get("/background.png")
async def background():
    return get_image_asset("./web/assets/assets/bg_image.jpeg")


@app.get("/manifest.json")
@app.get("/c/{configs}/manifest.json")
async def manifest(
    request: Request,
    configs: str | None = None,
):
    referer = str(request.base_url)
    manifest = worker.get_configured_manifest(referer, configs)
    manifest.update({"server_version": SERVER_VERSION})
    return __json_response(manifest)


@app.get("/web_config.json")
async def web_config():
    config = worker.get_web_config()
    return __json_response(config)


@app.get("/get_trakt_url")
async def trakt_url():
    url = {"url": worker.get_trakt_auth_url()}
    cache_age = 60 * 60 * 4  # 4 hours
    headers = add_cache_headers(cache_age)
    return __json_response(url, extra_headers=headers)


@app.post("/get_trakt_access_token")
async def trakt_config(code: str = Form(...)):
    if code is None:
        return Response(status_code=500)
    access_token = worker.get_trakt_access_token(code)
    if access_token is None:
        return Response(status_code=500)
    return __json_response({"access_token": access_token})


@app.get("/meta/{type}/{id}.json")
@app.get("/c/{configs}/meta/{type}/{id}.json")
async def meta(type: str | None, id: str | None, configs: str | None = None):
    if id is None or type is None:
        return HTTPException(status_code=404, detail="Not found")
    meta = worker.get_meta(id=id, s_type=type, config=configs)
    cache_age = 60 * 60 * 4  # 4 hours
    headers = add_cache_headers(cache_age)
    return __json_response(meta, extra_headers=headers)


@app.get("/catalog/{type}/{id}.json")
@app.get("/catalog/{type}/{id}/{extras}.json")
async def catalog(type: str | None, id: str | None, extras: str | None = None):
    return await catalog_with_configs(configs=None, type=type, id=id, extras=extras)


@app.get("/c/{configs}/catalog/{type}/{id}.json")
@app.get("/c/{configs}/catalog/{type}/{id}/{extras}.json")
async def catalog_with_configs(
    configs: str | None, type: str | None, id: str | None, extras: str | None = None
):
    if id is None:
        return HTTPException(status_code=404, detail="Not found")

    metas = await worker.get_configured_catalog(id=id, extras=extras, config=configs)
    cache_age = 60 * 60 * 4  # 4 hours
    headers = add_cache_headers(cache_age)
    return __json_response(metas, extra_headers=headers)


if __name__ == "__main__":
    uvicorn.run(
        app,
        loop="uvloop",
        reload=False,
        host=env.APP_URL,
        port=env.APP_PORT,
        log_level=env.APP_LOG_LEVEL,
        timeout_keep_alive=env.APP_TIMEOUT,
    )
