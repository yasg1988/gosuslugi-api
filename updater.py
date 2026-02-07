"""Update logic for GIS ZhKH data from dom.gosuslugi.ru."""

import time
import logging
import threading
from datetime import datetime

from gosuslugi_api.clients import GosUslugiAPIClient
import database

logger = logging.getLogger(__name__)

# Thread-safe update state
_state_lock = threading.Lock()
_update_state = {
    "status": "idle",
    "type": None,
    "chunk": None,
    "total_chunks": None,
    "progress": None,
    "total": None,
    "started_at": None,
    "finished_at": None,
    "result": None,
    "errors": [],
}


def get_status():
    with _state_lock:
        return dict(_update_state)


def _set_state(**kwargs):
    with _state_lock:
        _update_state.update(kwargs)


def _reset_state(update_type, chunk=None, total_chunks=None):
    with _state_lock:
        _update_state.update({
            "status": "running",
            "type": update_type,
            "chunk": chunk,
            "total_chunks": total_chunks,
            "progress": 0,
            "total": None,
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "result": None,
            "errors": [],
        })


def _finish_state(result):
    with _state_lock:
        _update_state.update({
            "status": "done",
            "finished_at": datetime.utcnow().isoformat(),
            "result": result,
        })


def _fail_state(error):
    with _state_lock:
        _update_state.update({
            "status": "error",
            "finished_at": datetime.utcnow().isoformat(),
            "result": str(error),
        })


def _add_error(error):
    with _state_lock:
        errs = _update_state["errors"]
        if len(errs) < 50:
            errs.append(str(error))


def _get_chunk(items, chunk, total_chunks):
    """Split items into chunks and return the specified chunk (1-based)."""
    n = len(items)
    chunk_size = (n + total_chunks - 1) // total_chunks
    start = (chunk - 1) * chunk_size
    end = min(start + chunk_size, n)
    return items[start:end]


def _is_empty(data):
    """Check if API response is empty/useless."""
    if data is None:
        return True
    if isinstance(data, str) and not data.strip():
        return True
    if isinstance(data, dict) and not data:
        return True
    if isinstance(data, list) and not data:
        return True
    return False


# ============ Field extraction helpers ============

def _extract_org(search_item, detail=None):
    """Extract organization fields from search result + optional detail."""
    org = {
        "gis_guid": search_item.get("guid"),
        "full_name": search_item.get("fullName") or search_item.get("fullOrgName"),
        "short_name": search_item.get("shortName"),
        "inn": search_item.get("inn"),
        "ogrn": search_item.get("ogrn"),
        "kpp": search_item.get("kpp"),
        "org_type": None,
        "org_address": None,
        "postal_address": None,
        "factual_address": None,
        "phone": None,
        "fax": None,
        "email": None,
        "url": None,
        "chief_last_name": None,
        "chief_first_name": None,
        "chief_middle_name": None,
        "okopf_code": None,
        "okopf_name": None,
        "state_registration_date": None,
        "org_roles": None,
    }

    # Roles from search result
    roles = search_item.get("organizationRoles") or []
    if roles:
        role_names = []
        for r in roles:
            if isinstance(r, dict):
                role_names.append(r.get("roleName") or r.get("name") or "")
            elif isinstance(r, str):
                role_names.append(r)
        org["org_roles"] = "; ".join(filter(None, role_names)) or None

    # Chief name from search (may be a single string)
    chief_name = search_item.get("chiefName") or ""
    if chief_name:
        parts = chief_name.strip().split()
        if len(parts) >= 1:
            org["chief_last_name"] = parts[0]
        if len(parts) >= 2:
            org["chief_first_name"] = parts[1]
        if len(parts) >= 3:
            org["chief_middle_name"] = " ".join(parts[2:])

    # Enrich from detail response
    if detail and isinstance(detail, dict):
        org["full_name"] = detail.get("fullName") or org["full_name"]
        org["short_name"] = detail.get("shortName") or org["short_name"]
        org["org_type"] = detail.get("organizationType")
        org["phone"] = detail.get("phone")
        org["fax"] = detail.get("fax")
        org["email"] = detail.get("email")
        org["url"] = detail.get("url") or detail.get("site")
        org["okopf_code"] = detail.get("okopfCode")
        org["okopf_name"] = detail.get("okopfName")
        org["state_registration_date"] = detail.get("stateRegistrationDate")

        # Addresses (can be dict with formattedAddress or string)
        for field, key in [("org_address", "legalAddress"),
                           ("postal_address", "postalAddress"),
                           ("factual_address", "factualAddress")]:
            val = detail.get(key)
            if isinstance(val, dict):
                org[field] = val.get("formattedAddress")
            elif isinstance(val, str):
                org[field] = val

        # Chief from detail (separate fields override parsed name)
        if detail.get("chiefLastName"):
            org["chief_last_name"] = detail["chiefLastName"]
            org["chief_first_name"] = detail.get("chiefFirstName")
            org["chief_middle_name"] = detail.get("chiefMiddleName")

    return org


def _extract_house(item, fias_data=None):
    """Extract house fields from listing item + optional FIAS lookup."""
    house = {
        "gis_guid": item.get("guid"),
        "fias_guid": item.get("houseGuid"),
        "status": None,
        "formatted_address": None,
        "city": None,
        "street": None,
        "house_number": None,
        "building_number": None,
        "struct_number": None,
        "postal_code": None,
        "cadastre_number": None,
        "oktmo_code": None,
        "oktmo_name": None,
        "building_year": item.get("buildingYear") or item.get("builtYear"),
        "operation_year": item.get("operationYear"),
        "reconstruction_year": item.get("reconstructionYear"),
        "max_floor_count": item.get("maxFloorCount") or item.get("floorCount"),
        "deterioration": item.get("deterioration"),
        "deterioration_date": item.get("deteriorationDate"),
        "total_square": item.get("totalSquare"),
        "residential_square": item.get("residentialSquare"),
        "residential_premise_count": item.get("residentialPremiseCount"),
        "nonresidential_premise_count": item.get("nonresidentialPremiseCount"),
        "plan_series": item.get("planSeries"),
        "house_type_code": None,
        "house_type_name": None,
        "house_condition_code": None,
        "house_condition_name": None,
        "wall_material": item.get("wallMaterial"),
        "house_uid": item.get("houseUid") or item.get("uid"),
        "management_org_guid": None,
        "fias_objectguid": item.get("houseGuid"),
    }

    # Address (string or dict)
    addr = item.get("address")
    if isinstance(addr, dict):
        house["formatted_address"] = addr.get("formattedAddress")
        house["city"] = addr.get("city")
        house["street"] = addr.get("street")
        house["house_number"] = addr.get("houseNumber") or addr.get("house")
        house["building_number"] = addr.get("buildingNumber") or addr.get("building")
        house["struct_number"] = addr.get("structNumber") or addr.get("structure")
    elif isinstance(addr, str):
        house["formatted_address"] = addr

    # Status
    status = item.get("houseStatus")
    if isinstance(status, dict):
        house["status"] = status.get("name") or status.get("code")
    elif isinstance(status, str):
        house["status"] = status

    # House type
    ht = item.get("houseType")
    if isinstance(ht, dict):
        house["house_type_code"] = ht.get("code")
        house["house_type_name"] = ht.get("name")
    house["house_type_code"] = house["house_type_code"] or item.get("houseTypeCode")
    house["house_type_name"] = house["house_type_name"] or item.get("houseTypeName")

    # House condition
    hc = item.get("houseCondition")
    if isinstance(hc, dict):
        house["house_condition_code"] = hc.get("code")
        house["house_condition_name"] = hc.get("name")
    house["house_condition_code"] = house["house_condition_code"] or item.get("houseConditionCode")
    house["house_condition_name"] = house["house_condition_name"] or item.get("houseConditionName")

    # Management org
    mgmt_org = item.get("managementOrganization")
    if isinstance(mgmt_org, dict):
        house["management_org_guid"] = mgmt_org.get("guid")

    # Enrich from FIAS lookup
    if fias_data and isinstance(fias_data, list) and fias_data:
        fias = fias_data[0] if isinstance(fias_data[0], dict) else {}
        house["postal_code"] = house["postal_code"] or fias.get("postalCode")
        house["cadastre_number"] = house["cadastre_number"] or fias.get("cadastreNumber")
        house["oktmo_code"] = house["oktmo_code"] or fias.get("oktmo")
        house["oktmo_name"] = house["oktmo_name"] or fias.get("oktmoName")

    return house


def _extract_characteristics(gis_guid, info):
    """Extract house characteristics from house_info response."""
    if not info or not isinstance(info, dict):
        return None

    chars = {
        "gis_guid": gis_guid,
        "porch_count": info.get("porchCount"),
        "lift_count": info.get("liftCount"),
        "building_series_type": info.get("buildingSeriesType"),
        "premise_count": info.get("premiseCount"),
        "residential_premise_total_square": info.get("residentialPremiseTotalSquare"),
        "nonresidential_premise_total_square": info.get("nonresidentialPremiseTotalSquare"),
        "total_square": info.get("totalSquare"),
        "energy_efficiency_code": None,
        "energy_efficiency_name": None,
        "overhaul_fund_forming_code": None,
        "overhaul_fund_forming_name": None,
        "management_agreement_date": info.get("managementAgreementDate"),
        "management_agreement_type": info.get("managementAgreementType"),
        "last_update_date": info.get("lastUpdateDate"),
    }

    # Energy efficiency
    ee = info.get("energyEfficiency") or info.get("energyEfficiencyClass") or {}
    if isinstance(ee, dict):
        chars["energy_efficiency_code"] = ee.get("code")
        chars["energy_efficiency_name"] = ee.get("name")
    elif isinstance(ee, str):
        chars["energy_efficiency_name"] = ee

    # Overhaul fund forming summary (first active entry)
    fund_list = info.get("overhaulFundForming") or info.get("overhaulFundFormingList") or []
    if isinstance(fund_list, list) and fund_list:
        first = fund_list[0] if isinstance(fund_list[0], dict) else {}
        chars["overhaul_fund_forming_code"] = first.get("code") or first.get("fundFormingCode")
        chars["overhaul_fund_forming_name"] = first.get("name") or first.get("fundFormingName")

    return chars


def _extract_overhaul_funds(gis_guid, info):
    """Extract overhaul fund entries from house_info response."""
    if not info or not isinstance(info, dict):
        return []

    fund_list = info.get("overhaulFundForming") or info.get("overhaulFundFormingList") or []
    funds = []
    for f in fund_list:
        if not isinstance(f, dict):
            continue
        fund_attr = f.get("fundAttribute") or {}
        if not isinstance(fund_attr, dict):
            fund_attr = {}
        funds.append({
            "gis_guid": gis_guid,
            "fund_forming_code": f.get("code") or f.get("fundFormingCode"),
            "fund_forming_name": f.get("name") or f.get("fundFormingName"),
            "fund_attribute_code": fund_attr.get("code"),
            "fund_attribute_name": fund_attr.get("name"),
            "fund_attribute_tag": fund_attr.get("tag"),
            "status": f.get("status"),
            "start_date": f.get("startDate"),
            "end_date": f.get("endDate"),
        })

    return funds


def _extract_management(gis_guid, data):
    """Extract house management record from management response."""
    if not data or not isinstance(data, dict):
        return None

    record = {
        "gis_guid": gis_guid,
        "management_type_code": None,
        "management_type_name": None,
        "life_cycle_stage_code": None,
        "life_cycle_stage_name": None,
        "management_contract_date": data.get("managementContractDate"),
        "end_contract_date": data.get("endContractDate"),
        "management_org_role": data.get("managementOrgRole"),
    }

    # Management type (nested dict or flat)
    mt = data.get("managementType") or {}
    if isinstance(mt, dict):
        record["management_type_code"] = mt.get("code")
        record["management_type_name"] = mt.get("name")
    record["management_type_code"] = record["management_type_code"] or data.get("managementTypeCode")
    record["management_type_name"] = record["management_type_name"] or data.get("managementTypeName")

    # Life cycle stage
    lcs = data.get("lifeCycleStage") or {}
    if isinstance(lcs, dict):
        record["life_cycle_stage_code"] = lcs.get("code")
        record["life_cycle_stage_name"] = lcs.get("name")
    record["life_cycle_stage_code"] = record["life_cycle_stage_code"] or data.get("lifeCycleStageCode")
    record["life_cycle_stage_name"] = record["life_cycle_stage_name"] or data.get("lifeCycleStageName")

    return record


# ============ Main update functions ============

def update_organizations():
    """Fetch and upsert all organizations for Yoshkar-Ola."""
    _reset_state("organizations")
    api = GosUslugiAPIClient(timeout=15, keep_alive=True, rate_limit=1.0)

    try:
        all_orgs = []
        page = 1
        per_page = 50

        while True:
            logger.info(f"Fetching organizations page {page}...")
            raw = api.search_organizations("Йошкар-Ола", page=page, per_page=per_page)

            # Response can be list or dict with elements/items
            if isinstance(raw, dict):
                items = raw.get("elements") or raw.get("items") or raw.get("coll") or []
            elif isinstance(raw, list):
                items = raw
            else:
                items = []

            if not items:
                break

            for item in items:
                if not isinstance(item, dict):
                    continue
                guid = item.get("guid")
                if not guid:
                    continue
                try:
                    detail = None
                    try:
                        detail = api.get_organization(guid)
                    except Exception as e:
                        logger.warning(f"Failed to get org detail {guid}: {e}")

                    org = _extract_org(item, detail)
                    if org["gis_guid"]:
                        all_orgs.append(org)
                except Exception as e:
                    _add_error(f"org {guid}: {e}")
                    logger.error(f"Error processing org {guid}: {e}")

            _set_state(progress=len(all_orgs))

            if len(items) < per_page:
                break
            page += 1

        _set_state(total=len(all_orgs))
        count = database.upsert_organizations(all_orgs)
        _finish_state(f"Upserted {count} organizations")
        logger.info(f"Organizations update done: {count}")

    except Exception as e:
        logger.error(f"Organizations update failed: {e}")
        _fail_state(e)
        raise


def update_houses():
    """Fetch and upsert all houses from all organizations."""
    _reset_state("houses")
    api = GosUslugiAPIClient(timeout=15, keep_alive=True, rate_limit=1.0)

    try:
        org_guids = database.get_all_org_guids()
        _set_state(total=len(org_guids))
        logger.info(f"Fetching houses for {len(org_guids)} organizations...")

        all_houses = {}  # gis_guid -> house dict (deduplicate)

        for i, org_guid in enumerate(org_guids):
            try:
                for item in api.get_all_houses_by_org(org_guid, per_page=100):
                    gis_guid = item.get("guid")
                    if not gis_guid or gis_guid in all_houses:
                        continue

                    # FIAS lookup for postal code, cadastre, OKTMO
                    fias_data = None
                    fias_guid = item.get("houseGuid")
                    if fias_guid:
                        try:
                            fias_data = api.get_actual_houses(fias_guid)
                        except Exception as e:
                            logger.warning(f"FIAS lookup failed for {fias_guid}: {e}")

                    house = _extract_house(item, fias_data)
                    if house["gis_guid"]:
                        all_houses[house["gis_guid"]] = house

            except Exception as e:
                _add_error(f"org {org_guid}: {e}")
                logger.error(f"Error fetching houses for org {org_guid}: {e}")

            _set_state(progress=i + 1)

        houses_list = list(all_houses.values())
        count = database.upsert_houses(houses_list)
        _finish_state(f"Upserted {count} houses from {len(org_guids)} orgs")
        logger.info(f"Houses update done: {count}")

    except Exception as e:
        logger.error(f"Houses update failed: {e}")
        _fail_state(e)
        raise


def update_house_info(chunk: int = 1, total_chunks: int = 1, delay: float = 1.5):
    """Fetch and upsert house characteristics + overhaul fund (chunked).

    Each house requires an individual HTTP request to dom.gosuslugi.ru.
    Mandatory delay between requests prevents empty responses from the API.
    """
    _reset_state("house_info", chunk=chunk, total_chunks=total_chunks)
    # rate_limit=0 because we manage delay manually
    api = GosUslugiAPIClient(timeout=15, keep_alive=True, rate_limit=0)

    try:
        all_guids = database.get_all_house_guids()
        chunk_guids = _get_chunk(all_guids, chunk, total_chunks)
        _set_state(total=len(chunk_guids))
        logger.info(f"house_info chunk {chunk}/{total_chunks}: {len(chunk_guids)} houses, delay={delay}s")

        chars_count = 0
        funds_count = 0
        empty_count = 0

        for i, guid in enumerate(chunk_guids):
            try:
                time.sleep(delay)
                info = api.get_house_info(guid)

                # Retry once on empty response
                if _is_empty(info):
                    logger.warning(f"Empty house_info for {guid}, retrying in 3s...")
                    time.sleep(3)
                    info = api.get_house_info(guid)

                if _is_empty(info):
                    empty_count += 1
                    logger.warning(f"Still empty house_info for {guid}, skipping")
                    continue

                # House characteristics
                chars = _extract_characteristics(guid, info)
                if chars:
                    database.upsert_house_characteristics([chars])
                    chars_count += 1

                # Overhaul fund entries
                funds = _extract_overhaul_funds(guid, info)
                if funds:
                    database.upsert_overhaul_fund(funds)
                    funds_count += len(funds)

            except Exception as e:
                _add_error(f"house_info {guid}: {e}")
                logger.error(f"Error for house_info {guid}: {e}")

            _set_state(progress=i + 1)

        result = (f"Chunk {chunk}/{total_chunks}: "
                  f"{chars_count} characteristics, {funds_count} fund entries, {empty_count} empty")
        _finish_state(result)
        logger.info(f"house_info done: {result}")

    except Exception as e:
        logger.error(f"house_info update failed: {e}")
        _fail_state(e)
        raise


def update_management(chunk: int = 1, total_chunks: int = 1, delay: float = 1.5):
    """Fetch and upsert house management + org links (chunked).

    Each house requires an individual HTTP request.
    Also updates municipality_orgs and resource_providers link tables.
    """
    _reset_state("management", chunk=chunk, total_chunks=total_chunks)
    api = GosUslugiAPIClient(timeout=15, keep_alive=True, rate_limit=0)

    try:
        all_guids = database.get_all_house_guids()
        chunk_guids = _get_chunk(all_guids, chunk, total_chunks)
        _set_state(total=len(chunk_guids))
        logger.info(f"management chunk {chunk}/{total_chunks}: {len(chunk_guids)} houses, delay={delay}s")

        mgmt_count = 0
        muni_count = 0
        res_count = 0
        empty_count = 0

        for i, guid in enumerate(chunk_guids):
            try:
                time.sleep(delay)
                data = api.get_home_management(guid)

                # Retry once on empty
                if _is_empty(data):
                    logger.warning(f"Empty management for {guid}, retrying in 3s...")
                    time.sleep(3)
                    data = api.get_home_management(guid)

                if _is_empty(data):
                    empty_count += 1
                    logger.warning(f"Still empty management for {guid}, skipping")
                    continue

                # House management record
                mgmt = _extract_management(guid, data)
                if mgmt:
                    database.upsert_house_management([mgmt])
                    mgmt_count += 1

                # Municipality organizations link table
                muni_orgs = data.get("municipalityOrganizationList") or []
                muni_guids = []
                for mo in muni_orgs:
                    g = mo.get("guid") if isinstance(mo, dict) else None
                    if g:
                        muni_guids.append(g)
                if muni_guids:
                    database.replace_house_org_links(guid, muni_guids, "house_municipality_orgs")
                    muni_count += len(muni_guids)

                # Resource provision organizations link table
                res_orgs = data.get("resourceProvisionOrganizationList") or []
                res_guids = []
                for ro in res_orgs:
                    g = ro.get("guid") if isinstance(ro, dict) else None
                    if g:
                        res_guids.append(g)
                if res_guids:
                    database.replace_house_org_links(guid, res_guids, "house_resource_providers")
                    res_count += len(res_guids)

            except Exception as e:
                _add_error(f"management {guid}: {e}")
                logger.error(f"Error for management {guid}: {e}")

            _set_state(progress=i + 1)

        result = (f"Chunk {chunk}/{total_chunks}: "
                  f"{mgmt_count} management, {muni_count} municipality, "
                  f"{res_count} resource, {empty_count} empty")
        _finish_state(result)
        logger.info(f"management done: {result}")

    except Exception as e:
        logger.error(f"management update failed: {e}")
        _fail_state(e)
        raise
