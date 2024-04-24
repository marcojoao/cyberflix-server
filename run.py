import os

from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from lib.web_worker import WebWorker

SERVER_VERSION = "0.3.0"

worker = WebWorker()


app = FastAPI()

project_dir = os.path.join(app.root_path, "web/")
app.mount("/static", StaticFiles(directory=project_dir), name="static")
templates = Jinja2Templates(directory=project_dir)


@app.get("/health", tags=["Health"])
async def health_check():
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
    headers = {"Cache-Control": f"max-age={cache_age}"}
    response = templates.TemplateResponse("index.html", {"request": request}, headers=headers)
    return response


@app.get("/configure")
@app.get("/c/{configs}/configure")
async def configure(configs: str | None = None):
    return RedirectResponse(url="/", status_code=302)


@app.get("/favicon.ico")
async def favicon():
    return FileResponse("./web/favicon.png", media_type="image/vnd.microsoft.icon")


@app.get("/logo.png")
async def logo():
    return FileResponse("./web/assets/assets/logo.png", media_type="image/png")


@app.get("/background.png")
async def background():
    return FileResponse("./web/assets/assets/bg_image.jpeg", media_type="image/jpeg")


@app.get("/manifest.json")
@app.get("/c/{configs}/manifest.json")
async def manifest(
    configs: str | None = None,
):
    manifest = worker.get_configured_manifest(configs)
    manifest.update({"server_version": SERVER_VERSION})
    return __json_response(manifest)


@app.get("/web_config.json")
async def web_config():
    config = worker.get_web_config()
    return __json_response(config)


@app.post("/regix_config")
async def regix_config(config: str = Form(...)):
    if config is None:
        return Response(status_code=500)
    return __json_response({"id": worker.set_user_config(config)})


@app.get("/get_trakt_url")
async def trakt_url():
    url = {"url": worker.get_trakt_auth_url()}
    cache_age = 60 * 60 * 12  # 12 hours
    headers = {
        "Cache-Control": f"max-age={cache_age},stale-while-revalidate={cache_age},stale-if-error={cache_age},public"
    }
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
    cache_age = 60 * 60 * 12  # 12 hours
    headers = {
        "Cache-Control": f"max-age={cache_age},stale-while-revalidate={cache_age},stale-if-error={cache_age},public"
    }
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

    metas = worker.get_configured_catalog(id=id, extras=extras, config=configs)
    cache_age = 60 * 60 * 12  # 12 hours
    headers = {
        "Cache-Control": f"max-age={cache_age},stale-while-revalidate={cache_age},stale-if-error={cache_age},public"
    }
    return __json_response(metas, extra_headers=headers)


if __name__ == "__main__":
    import uvicorn

    port = os.environ.get("APP_PORT", 8000)
    if isinstance(port, str):
        port = int(port)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info", timeout_keep_alive=600)
