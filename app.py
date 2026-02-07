"""FastAPI wrapper for gosuslugi-api library.

Provides REST endpoints for testing and using GIS GKH public API,
plus update endpoints for automatic daily data refresh.
"""

import logging

from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from gosuslugi_api.clients import GosUslugiAPIClient
import updater

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="ГИС ЖКХ API",
    description="Обёртка над публичным API dom.gosuslugi.ru + автообновление данных",
    version="1.1.0",
)

client = GosUslugiAPIClient(timeout=15, keep_alive=True, rate_limit=0.5)


@app.get("/")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/organizations/search")
def search_organizations(
    query: str = Query(..., description="ИНН, ОГРН или название. Для фильтрации по городу добавьте его в запрос."),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
):
    """Поиск управляющих компаний и ТСЖ."""
    try:
        return client.search_organizations(
            query=query,
            page=page,
            per_page=per_page,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/organizations/{guid}")
def get_organization(guid: str):
    """Детали организации по GUID."""
    try:
        return client.get_organization(guid)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/organizations/{guid}/houses")
def get_houses_by_org(
    guid: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
):
    """Дома под управлением организации."""
    try:
        return client.get_houses_by_org(guid, page=page, per_page=per_page)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/houses/{guid}/management")
def get_house_management(guid: str):
    """Детали управления домом по GIS GKH GUID."""
    try:
        return client.get_home_management(guid)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/houses/{guid}/info")
def get_house_info(guid: str):
    """Характеристики дома (год, этажи, площадь) по GIS GKH GUID."""
    try:
        return client.get_house_info(guid)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/fias/houses/{fias_guid}")
def get_fias_house(fias_guid: str):
    """ФИАС-lookup дома по objectguid (UUID)."""
    try:
        return client.get_actual_houses(fias_guid)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ============ Update endpoints ============

def _check_not_running():
    """Raise if an update is already running."""
    status = updater.get_status()
    if status["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail=f"Update already running: {status['type']} "
                   f"(progress: {status['progress']}/{status['total']})",
        )


@app.post("/update/organizations")
def start_update_organizations(background_tasks: BackgroundTasks):
    """Обновить организации (УК, ТСЖ) из ГИС ЖКХ."""
    _check_not_running()
    background_tasks.add_task(updater.update_organizations)
    return {"status": "started", "type": "organizations"}


@app.post("/update/houses")
def start_update_houses(background_tasks: BackgroundTasks):
    """Обновить дома по всем организациям."""
    _check_not_running()
    background_tasks.add_task(updater.update_houses)
    return {"status": "started", "type": "houses"}


@app.post("/update/house_info")
def start_update_house_info(
    background_tasks: BackgroundTasks,
    chunk: int = Query(1, ge=1, description="Номер чанка (1-based)"),
    total_chunks: int = Query(1, ge=1, description="Всего чанков"),
    delay: float = Query(1.5, ge=0, description="Задержка между запросами (сек)"),
):
    """Обновить характеристики домов + капремонт (чанками)."""
    _check_not_running()
    if chunk > total_chunks:
        raise HTTPException(status_code=400, detail="chunk > total_chunks")
    background_tasks.add_task(updater.update_house_info, chunk, total_chunks, delay)
    return {"status": "started", "type": "house_info", "chunk": chunk, "total_chunks": total_chunks}


@app.post("/update/management")
def start_update_management(
    background_tasks: BackgroundTasks,
    chunk: int = Query(1, ge=1, description="Номер чанка (1-based)"),
    total_chunks: int = Query(1, ge=1, description="Всего чанков"),
    delay: float = Query(1.5, ge=0, description="Задержка между запросами (сек)"),
):
    """Обновить управление домами + связи с организациями (чанками)."""
    _check_not_running()
    if chunk > total_chunks:
        raise HTTPException(status_code=400, detail="chunk > total_chunks")
    background_tasks.add_task(updater.update_management, chunk, total_chunks, delay)
    return {"status": "started", "type": "management", "chunk": chunk, "total_chunks": total_chunks}


@app.get("/update/status")
def get_update_status():
    """Статус текущего/последнего обновления."""
    return updater.get_status()
