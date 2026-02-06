"""FastAPI wrapper for gosuslugi-api library.

Provides REST endpoints for testing and using GIS GKH public API.
"""

import logging

from fastapi import FastAPI, Query, HTTPException
from gosuslugi_api.clients import GosUslugiAPIClient

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="ГИС ЖКХ API",
    description="Обёртка над публичным API dom.gosuslugi.ru",
    version="1.0.0",
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
