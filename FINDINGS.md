# GIS ZhKH API Findings (2026-02-06)

Research results for dom.gosuslugi.ru public API endpoints.

## Two Types of GUIDs

| Type | Source | Example | Used In |
|------|--------|---------|---------|
| **FIAS objectguid** | FIAS database (`as_houses.objectguid`) | `080439f6-256d-433d-9c2b-0363c5a8a686` | `/nsi/.../fias/v4/houses?houseCodes=` |
| **GIS GKH GUID** | homemanagement API | `700f05da-b213-41dc-b530-c8a48a214509` | `/homemanagement/.../public/1/`, `/information-disclosure/.../house-info` |

Using the wrong GUID type causes HTTP 500 or empty results.

## Working Public Endpoints (No Auth)

### 1. Organization Search
```
POST /ppa/api/rest/services/ppa/organizations/chooser/search;page=1;itemsPerPage=10
Content-Type: application/json

{
  "commonSearchString": "INN or name",
  "regionNames": ["Республика Марий Эл"],
  "organizationStatuses": {"coll": ["REGISTERED"], "operand": "OR"},
  "organizationTypes": {"coll": ["B","L","A"], "operand": "OR"},
  ...
}
```
Returns: org_guid, name, INN, OGRN, chief name, roles

### 2. Houses by Organization
```
POST /homemanagement/api/rest/services/houses/public/searchByOrg?pageIndex=1&elementsPerPage=100
Content-Type: application/json

{"organizationGuid": "...", "calcCount": true}
```
Returns: total count, list of houses with GIS GKH GUID, FIAS GUID, address

### 3. House Management Details
```
GET /homemanagement/api/rest/services/houses/public/1/{gisGkhGuid}/
```
Returns: 14KB+ JSON — full management info, address hierarchy

### 4. House Characteristics (information-disclosure)
```
GET /information-disclosure/api/rest/services/disclosures/mkd/house-info?houseGuid={gisGkhGuid}
Headers: Session-GUID, Request-GUID (random UUIDs)
```
Returns: built year, floor count, apartment count, total area, energy efficiency, overhaul fund

### 5. FIAS House Lookup
```
GET /nsi/api/rest/services/nsi/fias/v4/houses?houseCodes={fiasObjectguid}&includeDuplicates=false&actual=true
```
Returns: FIAS address data, postal code. **houseCodes must be UUID, NOT integer objectid!**

### 6. Organization Details
```
GET /ppa/api/rest/services/ppa/public/organizations/orgByGuid?organizationGuid={guid}
```
Returns: detailed organization information

## Non-Working Endpoints

| Endpoint | Status | Note |
|----------|--------|------|
| `/licenses/.../region-license-xls/{region}` | 403 | License download blocked |
| `/homemanagement/.../houses/search?regionCode=12` | 403 | Requires auth |
| `/homemanagement/.../public/searchByAddress` | WAF | Bot detection triggered |
| `/nsi/.../fias/v4/addrobj` | 500 | Endpoint removed |
| `/nsi/.../fias/v4/search` | 500 | Endpoint removed |

## Data Collection Workflow

```
1. Search all management companies in region (search_organizations)
2. For each org → get list of houses (get_houses_by_org)
3. For each house → get GIS GKH GUID
4. By GIS GKH GUID → house characteristics (get_house_info)
5. By FIAS GUID (from step 2) → link to FIAS database
```

## Available House Characteristics

From `information-disclosure` endpoint:
- Construction year
- Number of floors
- Number of apartments
- Total building area (sq.m)
- Energy efficiency class
- Overhaul fund size
- Building deterioration percentage
- Management organization info
