"""FastAPI wrapper for gosuslugi-api library.

Provides REST endpoints for testing and using GIS GKH public API.
"""

import logging
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from gosuslugi_api.clients import GosUslugiAPIClient

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="GIS GKH API",
    description="Public API wrapper for dom.gosuslugi.ru",
    version="1.0.0",
)

client = GosUslugiAPIClient(timeout=15, keep_alive=True, rate_limit=0.5)


@app.get("/")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/organizations/search")
def search_organizations(
    query: str = Query(..., description="INN, OGRN, or name"),
    region: Optional[str] = Query(None, description="Region name, e.g. 'Республика Марий Эл'"),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
):
    """Search management companies and HOAs."""
    try:
        region_names = [region] if region else None
        result = client.search_organizations(
            query=query,
            region_names=region_names,
            page=page,
            per_page=per_page,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/organizations/{guid}")
def get_organization(guid: str):
    """Get organization details by GUID."""
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
    """Get houses managed by organization."""
    try:
        return client.get_houses_by_org(guid, page=page, per_page=per_page)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/houses/{guid}/management")
def get_house_management(guid: str):
    """Get house management details by GIS GKH GUID."""
    try:
        return client.get_home_management(guid)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/houses/{guid}/info")
def get_house_info(guid: str):
    """Get house characteristics (year, floors, area) by GIS GKH GUID."""
    try:
        return client.get_house_info(guid)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/fias/houses/{fias_guid}")
def get_fias_house(fias_guid: str):
    """Look up FIAS house data by FIAS objectguid (UUID)."""
    try:
        return client.get_actual_houses(fias_guid)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
