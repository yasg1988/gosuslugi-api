"""Database module for GIS ZhKH data (psycopg2, sync)."""

import os
import logging

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")

YOSHKAR_OLA_ADDRESS_PATTERN = "%Йошкар-Ола%"


def get_connection():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )


def get_all_house_guids() -> list[str]:
    """Get Yoshkar-Ola house GIS GUIDs sorted (for chunking)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT gis_guid
                FROM gis_zhkh.houses
                WHERE formatted_address ILIKE %s
                ORDER BY gis_guid
                """,
                (YOSHKAR_OLA_ADDRESS_PATTERN,),
            )
            return [str(row[0]) for row in cur.fetchall()]
    finally:
        conn.close()


def get_all_org_guids() -> list[str]:
    """Get organization GIS GUIDs relevant to Yoshkar-Ola houses."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT h.management_org_guid
                FROM gis_zhkh.houses h
                WHERE h.formatted_address ILIKE %s
                  AND h.management_org_guid IS NOT NULL
                ORDER BY h.management_org_guid
                """,
                (YOSHKAR_OLA_ADDRESS_PATTERN,),
            )
            return [str(row[0]) for row in cur.fetchall()]
    finally:
        conn.close()


def upsert_organizations(orgs: list[dict]) -> int:
    """UPSERT organizations into gis_zhkh.organizations. Returns count."""
    if not orgs:
        return 0
    conn = get_connection()
    count = 0
    try:
        with conn.cursor() as cur:
            for org in orgs:
                cur.execute("""
                    INSERT INTO gis_zhkh.organizations (
                        gis_guid, full_name, short_name, inn, ogrn, kpp,
                        org_type, org_address, postal_address, factual_address,
                        phone, fax, email, url,
                        chief_last_name, chief_first_name, chief_middle_name,
                        okopf_code, okopf_name, state_registration_date,
                        org_roles, ogrn_ip, org_oid, is_branch, updated_at
                    ) VALUES (
                        %(gis_guid)s, %(full_name)s, %(short_name)s, %(inn)s, %(ogrn)s, %(kpp)s,
                        %(org_type)s, %(org_address)s, %(postal_address)s, %(factual_address)s,
                        %(phone)s, %(fax)s, %(email)s, %(url)s,
                        %(chief_last_name)s, %(chief_first_name)s, %(chief_middle_name)s,
                        %(okopf_code)s, %(okopf_name)s, %(state_registration_date)s,
                        %(org_roles)s, %(ogrn_ip)s, %(org_oid)s, %(is_branch)s, NOW()
                    )
                    ON CONFLICT (gis_guid) DO UPDATE SET
                        full_name = EXCLUDED.full_name,
                        short_name = EXCLUDED.short_name,
                        inn = EXCLUDED.inn,
                        ogrn = EXCLUDED.ogrn,
                        kpp = EXCLUDED.kpp,
                        org_type = EXCLUDED.org_type,
                        org_address = EXCLUDED.org_address,
                        postal_address = EXCLUDED.postal_address,
                        factual_address = EXCLUDED.factual_address,
                        phone = EXCLUDED.phone,
                        fax = EXCLUDED.fax,
                        email = EXCLUDED.email,
                        url = EXCLUDED.url,
                        chief_last_name = EXCLUDED.chief_last_name,
                        chief_first_name = EXCLUDED.chief_first_name,
                        chief_middle_name = EXCLUDED.chief_middle_name,
                        okopf_code = EXCLUDED.okopf_code,
                        okopf_name = EXCLUDED.okopf_name,
                        state_registration_date = EXCLUDED.state_registration_date,
                        org_roles = EXCLUDED.org_roles,
                        ogrn_ip = EXCLUDED.ogrn_ip,
                        org_oid = EXCLUDED.org_oid,
                        is_branch = EXCLUDED.is_branch,
                        updated_at = NOW()
                """, org)
                count += 1
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return count


def upsert_houses(houses: list[dict]) -> int:
    """UPSERT houses into gis_zhkh.houses. Returns count."""
    if not houses:
        return 0
    conn = get_connection()
    count = 0
    try:
        with conn.cursor() as cur:
            for h in houses:
                cur.execute("""
                    INSERT INTO gis_zhkh.houses (
                        gis_guid, fias_guid, status, formatted_address,
                        city, street, house_number, building_number, struct_number,
                        postal_code, cadastre_number, oktmo_code, oktmo_name,
                        building_year, operation_year, reconstruction_year,
                        max_floor_count, deterioration, deterioration_date,
                        total_square, residential_square,
                        residential_premise_count, nonresidential_premise_count,
                        plan_series, house_type_code, house_type_name,
                        house_condition_code, house_condition_name,
                        wall_material, house_uid, management_org_guid,
                        fias_objectguid, updated_at
                    ) VALUES (
                        %(gis_guid)s, %(fias_guid)s, %(status)s, %(formatted_address)s,
                        %(city)s, %(street)s, %(house_number)s, %(building_number)s, %(struct_number)s,
                        %(postal_code)s, %(cadastre_number)s, %(oktmo_code)s, %(oktmo_name)s,
                        %(building_year)s, %(operation_year)s, %(reconstruction_year)s,
                        %(max_floor_count)s, %(deterioration)s, %(deterioration_date)s,
                        %(total_square)s, %(residential_square)s,
                        %(residential_premise_count)s, %(nonresidential_premise_count)s,
                        %(plan_series)s, %(house_type_code)s, %(house_type_name)s,
                        %(house_condition_code)s, %(house_condition_name)s,
                        %(wall_material)s, %(house_uid)s, %(management_org_guid)s,
                        %(fias_objectguid)s, NOW()
                    )
                    ON CONFLICT (gis_guid) DO UPDATE SET
                        fias_guid = EXCLUDED.fias_guid,
                        status = EXCLUDED.status,
                        formatted_address = EXCLUDED.formatted_address,
                        city = EXCLUDED.city,
                        street = EXCLUDED.street,
                        house_number = EXCLUDED.house_number,
                        building_number = EXCLUDED.building_number,
                        struct_number = EXCLUDED.struct_number,
                        postal_code = EXCLUDED.postal_code,
                        cadastre_number = EXCLUDED.cadastre_number,
                        oktmo_code = EXCLUDED.oktmo_code,
                        oktmo_name = EXCLUDED.oktmo_name,
                        building_year = EXCLUDED.building_year,
                        operation_year = EXCLUDED.operation_year,
                        reconstruction_year = EXCLUDED.reconstruction_year,
                        max_floor_count = EXCLUDED.max_floor_count,
                        deterioration = EXCLUDED.deterioration,
                        deterioration_date = EXCLUDED.deterioration_date,
                        total_square = EXCLUDED.total_square,
                        residential_square = EXCLUDED.residential_square,
                        residential_premise_count = EXCLUDED.residential_premise_count,
                        nonresidential_premise_count = EXCLUDED.nonresidential_premise_count,
                        plan_series = EXCLUDED.plan_series,
                        house_type_code = EXCLUDED.house_type_code,
                        house_type_name = EXCLUDED.house_type_name,
                        house_condition_code = EXCLUDED.house_condition_code,
                        house_condition_name = EXCLUDED.house_condition_name,
                        wall_material = EXCLUDED.wall_material,
                        house_uid = EXCLUDED.house_uid,
                        management_org_guid = EXCLUDED.management_org_guid,
                        fias_objectguid = EXCLUDED.fias_objectguid,
                        updated_at = NOW()
                """, h)
                count += 1
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return count


def upsert_house_characteristics(chars: list[dict]) -> int:
    """UPSERT into gis_zhkh.house_characteristics."""
    if not chars:
        return 0
    conn = get_connection()
    count = 0
    try:
        with conn.cursor() as cur:
            for c in chars:
                cur.execute("""
                    INSERT INTO gis_zhkh.house_characteristics (
                        gis_guid, porch_count, lift_count, building_series_type,
                        premise_count, residential_premise_total_square,
                        nonresidential_premise_total_square, total_square,
                        energy_efficiency_code, energy_efficiency_name,
                        overhaul_fund_forming_code, overhaul_fund_forming_name,
                        management_agreement_date, management_agreement_type,
                        last_update_date,
                        common_props_square, house_is_emergency, emergency_reason,
                        emergency_doc_number, emergency_doc_date,
                        land_plot_square, land_plot_cadastre_numbers, operation_year,
                        updated_at
                    ) VALUES (
                        %(gis_guid)s, %(porch_count)s, %(lift_count)s, %(building_series_type)s,
                        %(premise_count)s, %(residential_premise_total_square)s,
                        %(nonresidential_premise_total_square)s, %(total_square)s,
                        %(energy_efficiency_code)s, %(energy_efficiency_name)s,
                        %(overhaul_fund_forming_code)s, %(overhaul_fund_forming_name)s,
                        %(management_agreement_date)s, %(management_agreement_type)s,
                        %(last_update_date)s,
                        %(common_props_square)s, %(house_is_emergency)s, %(emergency_reason)s,
                        %(emergency_doc_number)s, %(emergency_doc_date)s,
                        %(land_plot_square)s, %(land_plot_cadastre_numbers)s, %(operation_year)s,
                        NOW()
                    )
                    ON CONFLICT (gis_guid) DO UPDATE SET
                        porch_count = EXCLUDED.porch_count,
                        lift_count = EXCLUDED.lift_count,
                        building_series_type = EXCLUDED.building_series_type,
                        premise_count = EXCLUDED.premise_count,
                        residential_premise_total_square = EXCLUDED.residential_premise_total_square,
                        nonresidential_premise_total_square = EXCLUDED.nonresidential_premise_total_square,
                        total_square = EXCLUDED.total_square,
                        energy_efficiency_code = EXCLUDED.energy_efficiency_code,
                        energy_efficiency_name = EXCLUDED.energy_efficiency_name,
                        overhaul_fund_forming_code = EXCLUDED.overhaul_fund_forming_code,
                        overhaul_fund_forming_name = EXCLUDED.overhaul_fund_forming_name,
                        management_agreement_date = EXCLUDED.management_agreement_date,
                        management_agreement_type = EXCLUDED.management_agreement_type,
                        last_update_date = EXCLUDED.last_update_date,
                        common_props_square = EXCLUDED.common_props_square,
                        house_is_emergency = EXCLUDED.house_is_emergency,
                        emergency_reason = EXCLUDED.emergency_reason,
                        emergency_doc_number = EXCLUDED.emergency_doc_number,
                        emergency_doc_date = EXCLUDED.emergency_doc_date,
                        land_plot_square = EXCLUDED.land_plot_square,
                        land_plot_cadastre_numbers = EXCLUDED.land_plot_cadastre_numbers,
                        operation_year = EXCLUDED.operation_year,
                        updated_at = NOW()
                """, c)
                count += 1
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return count


def upsert_overhaul_fund(funds: list[dict]) -> int:
    """UPSERT into gis_zhkh.overhaul_fund."""
    if not funds:
        return 0
    conn = get_connection()
    count = 0
    try:
        with conn.cursor() as cur:
            for f in funds:
                cur.execute("""
                    INSERT INTO gis_zhkh.overhaul_fund (
                        gis_guid, fund_forming_code, fund_forming_name,
                        fund_attribute_code, fund_attribute_name, fund_attribute_tag,
                        status, start_date, end_date,
                        overhaul_fund_forming_method, updated_at
                    ) VALUES (
                        %(gis_guid)s, %(fund_forming_code)s, %(fund_forming_name)s,
                        %(fund_attribute_code)s, %(fund_attribute_name)s, %(fund_attribute_tag)s,
                        %(status)s, %(start_date)s, %(end_date)s,
                        %(overhaul_fund_forming_method)s, NOW()
                    )
                    ON CONFLICT (gis_guid) DO UPDATE SET
                        fund_forming_code = EXCLUDED.fund_forming_code,
                        fund_forming_name = EXCLUDED.fund_forming_name,
                        fund_attribute_code = EXCLUDED.fund_attribute_code,
                        fund_attribute_name = EXCLUDED.fund_attribute_name,
                        fund_attribute_tag = EXCLUDED.fund_attribute_tag,
                        status = EXCLUDED.status,
                        start_date = EXCLUDED.start_date,
                        end_date = EXCLUDED.end_date,
                        overhaul_fund_forming_method = EXCLUDED.overhaul_fund_forming_method,
                        updated_at = NOW()
                """, f)
                count += 1
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return count


def upsert_house_management(mgmt_list: list[dict]) -> int:
    """UPSERT into gis_zhkh.house_management."""
    if not mgmt_list:
        return 0
    conn = get_connection()
    count = 0
    try:
        with conn.cursor() as cur:
            for m in mgmt_list:
                cur.execute("""
                    INSERT INTO gis_zhkh.house_management (
                        gis_guid, management_type_code, management_type_name,
                        life_cycle_stage_code, life_cycle_stage_name,
                        management_contract_date, end_contract_date,
                        management_org_role,
                        house_management_type_code, house_management_type_name,
                        int_wall_material, energy_efficiency, energy_inspection_date,
                        cultural_heritage, land_plot_cadastre_number,
                        emergency_doc_number, emergency_doc_date,
                        overhaul_fund_contribution, underground_floor_count,
                        building_square, updated_at
                    ) VALUES (
                        %(gis_guid)s, %(management_type_code)s, %(management_type_name)s,
                        %(life_cycle_stage_code)s, %(life_cycle_stage_name)s,
                        %(management_contract_date)s, %(end_contract_date)s,
                        %(management_org_role)s,
                        %(house_management_type_code)s, %(house_management_type_name)s,
                        %(int_wall_material)s, %(energy_efficiency)s, %(energy_inspection_date)s,
                        %(cultural_heritage)s, %(land_plot_cadastre_number)s,
                        %(emergency_doc_number)s, %(emergency_doc_date)s,
                        %(overhaul_fund_contribution)s, %(underground_floor_count)s,
                        %(building_square)s, NOW()
                    )
                    ON CONFLICT (gis_guid) DO UPDATE SET
                        management_type_code = EXCLUDED.management_type_code,
                        management_type_name = EXCLUDED.management_type_name,
                        life_cycle_stage_code = EXCLUDED.life_cycle_stage_code,
                        life_cycle_stage_name = EXCLUDED.life_cycle_stage_name,
                        management_contract_date = EXCLUDED.management_contract_date,
                        end_contract_date = EXCLUDED.end_contract_date,
                        management_org_role = EXCLUDED.management_org_role,
                        house_management_type_code = EXCLUDED.house_management_type_code,
                        house_management_type_name = EXCLUDED.house_management_type_name,
                        int_wall_material = EXCLUDED.int_wall_material,
                        energy_efficiency = EXCLUDED.energy_efficiency,
                        energy_inspection_date = EXCLUDED.energy_inspection_date,
                        cultural_heritage = EXCLUDED.cultural_heritage,
                        land_plot_cadastre_number = EXCLUDED.land_plot_cadastre_number,
                        emergency_doc_number = EXCLUDED.emergency_doc_number,
                        emergency_doc_date = EXCLUDED.emergency_doc_date,
                        overhaul_fund_contribution = EXCLUDED.overhaul_fund_contribution,
                        underground_floor_count = EXCLUDED.underground_floor_count,
                        building_square = EXCLUDED.building_square,
                        updated_at = NOW()
                """, m)
                count += 1
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return count


def get_data_freshness() -> list[dict]:
    """Get data freshness stats from v_data_freshness view."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name, total_rows, with_updated_at,
                       oldest_update, newest_update, hours_since_update
                FROM gis_zhkh.v_data_freshness
            """)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def get_field_fill_rates() -> list[dict]:
    """Get fill rates for key fields across tables."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 'organizations' AS table_name,
                       COUNT(*) AS total,
                       COUNT(inn) AS inn,
                       COUNT(ogrn) AS ogrn,
                       COUNT(email) AS email,
                       COUNT(phone) AS phone,
                       COUNT(org_roles) AS org_roles,
                       COUNT(org_oid) AS org_oid
                FROM gis_zhkh.organizations
            """)
            org_cols = [d[0] for d in cur.description]
            org_row = dict(zip(org_cols, cur.fetchone()))

            cur.execute("""
                SELECT 'houses' AS table_name,
                       COUNT(*) AS total,
                       COUNT(fias_guid) AS fias_guid,
                       COUNT(cadastre_number) AS cadastre_number,
                       COUNT(building_year) AS building_year,
                       COUNT(total_square) AS total_square,
                       COUNT(wall_material) AS wall_material
                FROM gis_zhkh.houses
            """)
            house_cols = [d[0] for d in cur.description]
            house_row = dict(zip(house_cols, cur.fetchone()))

            cur.execute("""
                SELECT 'house_management' AS table_name,
                       COUNT(*) AS total,
                       COUNT(house_management_type_name) AS mgmt_type,
                       COUNT(int_wall_material) AS wall_material,
                       COUNT(emergency_doc_number) AS emergency_doc,
                       COUNT(energy_efficiency) AS energy_eff
                FROM gis_zhkh.house_management
            """)
            mgmt_cols = [d[0] for d in cur.description]
            mgmt_row = dict(zip(mgmt_cols, cur.fetchone()))

            return [org_row, house_row, mgmt_row]
    finally:
        conn.close()


def replace_house_org_links(house_guid: str, org_guids: list[str], table: str) -> int:
    """Replace org links for a house (DELETE + INSERT). table is 'house_municipality_orgs' or 'house_resource_providers'."""
    if table not in ("house_municipality_orgs", "house_resource_providers"):
        raise ValueError(f"Invalid table: {table}")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                    INSERT INTO gis_zhkh.organizations (gis_guid, full_name, updated_at)
                    SELECT guid::uuid, 'GIS linked organization ' || guid, NOW()
                    FROM unnest(%s::text[]) AS guid
                    ON CONFLICT (gis_guid) DO NOTHING
                """,
                (org_guids,),
            )
            cur.execute(f"DELETE FROM gis_zhkh.{table} WHERE house_gis_guid = %s", (house_guid,))
            for org_guid in org_guids:
                cur.execute(
                    f"INSERT INTO gis_zhkh.{table} (house_gis_guid, org_gis_guid) VALUES (%s, %s)",
                    (house_guid, org_guid),
                )
            conn.commit()
        return len(org_guids)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
