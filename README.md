## gosuslugi-api

#### `gosuslugi-api` is an MIT licensed library written in Python.<br>It was developed to obtain data from `https://dom.gosuslugi.ru/` (GIS GKH)

> Fork of [GregEremeev/gosuslugi-api](https://github.com/GregEremeev/gosuslugi-api) with updated methods, rate limiting, and documentation.

### What data is available (no auth required)

| Data | Method | Status |
|------|--------|--------|
| Organization search (by INN, name) | `search_organizations()` | Working |
| Organization details | `get_organization()` | Working |
| Houses by organization | `get_houses_by_org()` | Working |
| All houses (auto-pagination) | `get_all_houses_by_org()` | Working |
| House management details | `get_home_management()` | Working |
| House characteristics (year, floors, area) | `get_house_info()` | Working |
| FIAS house lookup | `get_actual_houses()` | Working |
| License info | `get_licenses()` | Blocked (HTTP 403) |

### Important: Two types of GUIDs

The API uses two different GUID systems. **Do not mix them!**

| GUID type | Source | Used in |
|-----------|--------|---------|
| **FIAS objectguid** | FIAS database | `get_actual_houses()` |
| **GIS GKH GUID** | `get_houses_by_org()` → item `guid` | `get_home_management()`, `get_house_info()` |

### Quick start

1. Install the library:
```bash
pip install gosuslugi-api
```

2. Search organizations and get house data:

```python
from gosuslugi_api.clients import GosUslugiAPIClient

client = GosUslugiAPIClient()

# Search for management companies in a region
orgs = client.search_organizations(
    query='управляющая компания',
    region_names=['Республика Марий Эл'],
)
print(f'Found {len(orgs)} organizations')

# Get houses managed by an organization
org_guid = orgs[0]['guid']
houses = client.get_houses_by_org(org_guid, per_page=10)
print(f'Total houses: {houses["total"]}')

for house in houses['items']:
    print(f'  {house.get("address", "N/A")}')

    # Get house characteristics (year, floors, area, apartments)
    gis_guid = house['guid']
    try:
        info = client.get_house_info(gis_guid)
        print(f'    Built: {info}')
    except Exception as e:
        print(f'    Info unavailable: {e}')
```

3. Iterate through ALL houses of an organization:

```python
# Auto-pagination - yields individual house dicts
for house in client.get_all_houses_by_org(org_guid, per_page=100):
    print(house.get('address', 'N/A'))
```

4. FIAS house lookup:

```python
# Look up by FIAS objectguid (UUID format, NOT integer!)
fias_data = client.get_actual_houses('080439f6-256d-433d-9c2b-0363c5a8a686')
print(fias_data)
```

### Rate limiting

The client includes built-in rate limiting (0.5 sec between requests by default) to avoid being blocked:

```python
# Custom rate limit
client = GosUslugiAPIClient(rate_limit=1.0)  # 1 sec between requests

# Disable rate limiting (not recommended)
client = GosUslugiAPIClient(rate_limit=0)
```

### Changes from upstream

- Added `search_organizations()` with region filtering support
- Added `get_houses_by_org()` and `get_all_houses_by_org()` for house listings
- Fixed methods that bypassed the HTTP client (now all go through `_http_client`)
- Added rate limiting to prevent IP bans
- Increased default timeout from 3s to 10s
- Added docstrings and type hints
- Updated for Python 3.8+
