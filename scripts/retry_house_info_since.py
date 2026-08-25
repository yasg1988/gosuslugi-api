#!/usr/bin/env python3
"""Retry Yoshkar-Ola house-info rows not refreshed since a cutoff time."""

import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gosuslugi_api.clients import GosUslugiAPIClient

import database
import updater


def stale_guids(since: str) -> list[str]:
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT h.gis_guid
                FROM gis_zhkh.houses h
                LEFT JOIN gis_zhkh.house_characteristics c
                  ON c.gis_guid = h.gis_guid
                WHERE h.formatted_address ILIKE %s
                  AND (c.updated_at IS NULL OR c.updated_at < %s::timestamptz)
                ORDER BY h.gis_guid
                """,
                (database.YOSHKAR_OLA_ADDRESS_PATTERN, since),
            )
            return [str(row[0]) for row in cur.fetchall()]
    finally:
        conn.close()


def retry_house(api: GosUslugiAPIClient, guid: str, attempts: int, delay: float) -> bool:
    for attempt in range(1, attempts + 1):
        try:
            time.sleep(delay)
            info = updater._unwrap_house_info(api.get_house_info(guid))
            if updater._is_empty(info):
                raise RuntimeError("empty house-info response")

            characteristics = updater._extract_characteristics(guid, info)
            if characteristics:
                database.upsert_house_characteristics([characteristics])

            funds = updater._extract_overhaul_funds(guid, info)
            if funds:
                database.upsert_overhaul_fund(funds)
            return True
        except Exception as error:
            print(f"attempt {attempt}/{attempts} failed for {guid}: {error}")
            if attempt < attempts:
                time.sleep(delay * attempt)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", required=True, help="ISO timestamp cutoff")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--delay", type=float, default=3.0)
    args = parser.parse_args()

    updater._ensure_portal_available()
    guids = stale_guids(args.since)
    print(f"stale Yoshkar-Ola house-info rows: {len(guids)}")

    api = GosUslugiAPIClient(timeout=30, keep_alive=True, rate_limit=0)
    failed = [
        guid
        for guid in guids
        if not retry_house(api, guid, args.attempts, args.delay)
    ]
    print(f"retried: {len(guids) - len(failed)}, failed: {len(failed)}")
    for guid in failed:
        print(f"failed-guid: {guid}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
