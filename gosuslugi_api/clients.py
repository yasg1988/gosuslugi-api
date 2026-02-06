import json
import time
import logging
from io import BytesIO
from typing import Union, Optional, List, Dict, Any, Generator
from urllib.parse import urlencode
from uuid import uuid4
from zipfile import ZipFile

import requests
from openpyxl import load_workbook

from gosuslugi_api.utils import Licenses
from gosuslugi_api.consts import REGION_CODES_AND_NAMES
from gosuslugi_api.exceptions import RegionCodeIsAbsentError


logger = logging.getLogger(__name__)


def _get_body_for_logging(body: Union[bytes, str]) -> str:
    try:
        if isinstance(body, bytes):
            return (b' BODY: ' + body).decode('utf-8')
        elif isinstance(body, str):
            return ' BODY: ' + body
        else:
            return ''
    except UnicodeDecodeError:
        return ''


def _get_duration_for_logging(duration: str) -> str:
    if duration is not None:
        return ' {0:.6f}s'.format(duration)
    else:
        return ''


class HTTPClient:

    GET_HTTP_METHOD = 'GET'
    POST_HTTP_METHOD = 'POST'
    PATCH_HTTP_METHOD = 'PATCH'
    PUT_HTTP_METHOD = 'PUT'

    BODY_LESS_METHODS = [GET_HTTP_METHOD]
    LOG_REQUEST_TEMPLATE = '%(method)s %(url)s%(request_body)s%(duration)s'
    LOG_RESPONSE_TEMPLATE = (
        LOG_REQUEST_TEMPLATE
        + ' - HTTP %(status_code)s%(response_body)s%(duration)s')

    def __init__(self, timeout=3, keep_alive=False, default_headers=None):
        self.timeout = timeout
        self.keep_alive = keep_alive
        self.default_headers = default_headers or {}
        self._session = None

    def _log_request(
            self, method, url, body, duration=None, log_method=logger.info):
        message_params = {
            'method': method, 'url': url,
            'request_body': _get_body_for_logging(body),
            'duration': _get_duration_for_logging(duration)}
        log_method(self.LOG_REQUEST_TEMPLATE, message_params)

    def _log_response(self, response, duration, log_method=logger.info):
        message_params = {
            'method': response.request.method,
            'url': response.request.url,
            'request_body': _get_body_for_logging(response.request.body),
            'status_code': response.status_code,
            'response_body': _get_body_for_logging(response.content),
            'duration': _get_duration_for_logging(duration)}
        log_method(self.LOG_RESPONSE_TEMPLATE, message_params)

    def _make_request(self, method, url, **kwargs) -> requests.Response:
        kwargs.setdefault('timeout', self.timeout)
        session = self.session
        timeout = kwargs.pop('timeout', self.timeout)

        headers = self.default_headers.copy()
        headers.update(kwargs.pop('headers', {}))

        request = requests.Request(method, url, headers=headers, **kwargs)
        prepared_request = request.prepare()
        self._log_request(method, url, prepared_request.body)
        start_time = time.time()
        try:
            response = session.send(prepared_request, timeout=timeout)
            duration = time.time() - start_time
            if response.status_code >= 400:
                log_method = logging.error
            else:
                log_method = logging.debug

            self._log_response(
                response, duration=duration, log_method=log_method)
            return response
        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            if e.response:
                self._log_response(
                    e.response, duration=duration, log_method=logging.error)
            else:
                self._log_request(
                    method, url, prepared_request.body,
                    log_method=logging.exception)
            raise
        finally:
            if not self.keep_alive:
                session.close()

    @property
    def session(self) -> requests.Session:
        if self.keep_alive:
            if not self._session:
                self._session = requests.Session()
            return self._session
        else:
            return requests.Session()

    def get(self, url, params=None, **kwargs) -> requests.Response:
        if params:
            url_with_query_params = url + '?' + urlencode(params)
        else:
            url_with_query_params = url

        return self._make_request(
            self.GET_HTTP_METHOD, url_with_query_params, **kwargs)

    def post(self, url, **kwargs) -> requests.Response:
        return self._make_request(self.POST_HTTP_METHOD, url, **kwargs)

    def patch(self, url, **kwargs) -> requests.Response:
        return self._make_request(self.PATCH_HTTP_METHOD, url, **kwargs)

    def put(self, url, **kwargs) -> requests.Response:
        return self._make_request(self.PUT_HTTP_METHOD, url, **kwargs)


class GosUslugiAPIClient:
    """Client for dom.gosuslugi.ru public API (no auth required).

    Provides access to:
    - Organization search (management companies, HOAs)
    - House listings by organization
    - House management details
    - House characteristics (year, floors, area, apartments)
    - FIAS house lookup
    - License information (may be blocked - HTTP 403)
    """

    REGION_CODES_AND_NAMES = REGION_CODES_AND_NAMES

    BASE_URL = 'https://dom.gosuslugi.ru/'

    # License endpoints (may return 403)
    LICENSE_UID_URL = (
        f'{BASE_URL}licenses/api/rest/services/public/'
        'licenses/region-license-xls/{}')
    DOWNLOAD_LICENSES_INFO_URL = (
        f'{BASE_URL}filestore/publicDownloadAllFilesServlet?'
        'context=licenses&uids={uid}&zipFileName={file_name}.zip')

    # Organization endpoints
    ORGANIZATIONS_URL = (
        f'{BASE_URL}ppa/api/rest/services/ppa/'
        'organizations/chooser/search;page={{page}};itemsPerPage={{per_page}}')
    ORGANIZATION_URL = (
        f'{BASE_URL}ppa/api/rest/services/ppa/public/organizations'
        '/orgByGuid?organizationGuid={}')

    # FIAS endpoints
    HOUSE_CODE_URL = (
        f'{BASE_URL}nsi/api/rest/services/nsi/fias/v4/houses?'
        'houseCodes={}&includeDuplicates=false&actual={}')

    # Home management endpoints
    HOME_MANAGEMENTS_URL = (
        f'{BASE_URL}homemanagement/api/rest/services/houses/public/'
        'searchByOrg?pageIndex={{page_number}}&elementsPerPage={{elems_per_page}}')
    HOME_MANAGEMENT_URL = (
        f'{BASE_URL}homemanagement/api/rest/services/'
        'houses/public/1/{}/')

    # House info / characteristics endpoint
    HOUSE_INFO_URL = (
        f'{BASE_URL}information-disclosure/api/rest/services/'
        'disclosures/mkd/house-info?houseGuid={}')

    # Default rate limit delay (seconds between requests)
    DEFAULT_RATE_LIMIT = 0.5

    def __init__(self, timeout=10, keep_alive=True, rate_limit=None):
        """Initialize the client.

        Args:
            timeout: HTTP request timeout in seconds (default: 10).
            keep_alive: Reuse HTTP connections (default: True).
            rate_limit: Delay between requests in seconds (default: 0.5).
                Set to 0 to disable rate limiting.
        """
        self._region_codes = set(self.REGION_CODES_AND_NAMES)
        self._http_client = HTTPClient(timeout=timeout, keep_alive=keep_alive)
        self._rate_limit = rate_limit if rate_limit is not None else self.DEFAULT_RATE_LIMIT
        self._last_request_time = 0

    def _wait_rate_limit(self):
        """Wait to respect rate limiting."""
        if self._rate_limit > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._rate_limit:
                time.sleep(self._rate_limit - elapsed)
        self._last_request_time = time.time()

    def _get_response_body(self, response: requests.Response):
        status_code = response.status_code
        if status_code >= 400:
            response.raise_for_status()
        elif not response.content:
            return ''
        else:
            return response.json()

    def _get(self, url, **kwargs) -> requests.Response:
        self._wait_rate_limit()
        return self._http_client.get(url, **kwargs)

    def _post(self, url, **kwargs) -> requests.Response:
        self._wait_rate_limit()
        return self._http_client.post(url, **kwargs)

    # ========== Organization methods ==========

    def search_organizations(
        self,
        query: str,
        page: int = 1,
        per_page: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search organizations (management companies, HOAs) by name, INN, or OGRN.

        This is the main method for finding organizations. It searches
        the GIS GKH registry of registered organizations.

        Tip: include city name in query to filter by location,
        e.g. "управляющая Йошкар-Ола".

        Args:
            query: Search string - INN, OGRN, or part of organization name.
            page: Page number (1-based).
            per_page: Results per page (max ~50).

        Returns:
            List of organization dicts with keys:
            - guid: Organization GUID (use in get_houses_by_org)
            - shortName / fullName: Organization name
            - inn, ogrn, kpp: Tax identifiers
            - chiefName: Director name
            - organizationRoles: List of roles in GIS GKH
        """
        payload = {
            'sortCriteriaList': [
                {'sortedBy': 'organizationType', 'ascending': False},
                {'sortedBy': 'shortName', 'ascending': True},
                {'sortedBy': 'fullName', 'ascending': True},
                {'sortedBy': 'parentKpp', 'ascending': True},
                {'sortedBy': 'kpp', 'ascending': True},
            ],
            'organizationStatuses': {
                'coll': ['REGISTERED'],
                'operand': 'OR',
            },
            'organizationTypes': {
                'coll': ['B', 'L', 'A'],
                'operand': 'OR',
            },
            'subordinationOrgTypeList': {
                'coll': ['HEAD', 'BRANCH'],
                'operand': 'OR',
            },
            'commonSearchString': query,
            'roleConstraints': {
                'coll': [
                    {'roleCode': '1', 'roleStatuses': ['APPROVED']},
                    {'roleCode': '19', 'roleStatuses': ['APPROVED']},
                    {'roleCode': '20', 'roleStatuses': ['APPROVED']},
                    {'roleCode': '22', 'roleStatuses': ['APPROVED']},
                    {'roleCode': '21', 'roleStatuses': ['APPROVED']},
                ],
                'operand': 'OR',
            },
        }

        url = (
            f'{self.BASE_URL}ppa/api/rest/services/ppa/'
            f'organizations/chooser/search;page={page};itemsPerPage={per_page}'
        )
        headers = {'Content-Type': 'application/json'}
        response = self._post(url, data=json.dumps(payload), headers=headers)
        return self._get_response_body(response)

    def get_organizations(self, inn: str) -> Any:
        """Search organizations by INN (legacy method).

        Wrapper around search_organizations for backward compatibility.

        Args:
            inn: Organization INN.

        Returns:
            List of organization dicts.
        """
        return self.search_organizations(query=str(inn))

    def get_organization(self, guid: str) -> Any:
        """Get detailed organization info by GUID.

        Args:
            guid: Organization GUID from search_organizations.

        Returns:
            Organization details dict.
        """
        url = self.ORGANIZATION_URL.format(guid)
        return self._get_response_body(self._get(url))

    # ========== House listing methods ==========

    def get_houses_by_org(
        self,
        org_guid: str,
        page: int = 1,
        per_page: int = 100,
    ) -> Dict[str, Any]:
        """Get houses managed by an organization.

        This returns a single page of houses. Use get_all_houses_by_org
        to iterate through all pages automatically.

        Args:
            org_guid: Organization GUID from search_organizations.
            page: Page number (1-based).
            per_page: Results per page.

        Returns:
            Dict with:
            - total: Total number of houses
            - items: List of house dicts with keys:
                - guid: GIS GKH house GUID (use in get_house_info)
                - houseGuid: FIAS house GUID
                - address: Full address string
                - managementOrganization: Managing org info
        """
        url = (
            f'{self.BASE_URL}homemanagement/api/rest/services/houses/public/'
            f'searchByOrg?pageIndex={page}&elementsPerPage={per_page}'
        )
        payload = json.dumps({
            'organizationGuid': org_guid,
            'calcCount': True,
        })
        headers = {'Content-Type': 'application/json'}
        response = self._post(url, data=payload, headers=headers)
        return self._get_response_body(response)

    def get_all_houses_by_org(
        self,
        org_guid: str,
        per_page: int = 100,
    ) -> Generator[Dict[str, Any], None, None]:
        """Iterate through ALL houses managed by an organization.

        Automatically handles pagination.

        Args:
            org_guid: Organization GUID.
            per_page: Results per page.

        Yields:
            Individual house dicts from each page.
        """
        first_page = self.get_houses_by_org(org_guid, page=1, per_page=per_page)
        total = first_page.get('total', 0) or 0
        items = first_page.get('items', [])
        for item in items:
            yield item

        if total <= per_page:
            return

        total_pages = (total + per_page - 1) // per_page
        for page_num in range(2, total_pages + 1):
            page_data = self.get_houses_by_org(org_guid, page=page_num, per_page=per_page)
            for item in page_data.get('items', []):
                yield item

    # ========== House detail methods ==========

    def get_home_management(self, home_management_guid: str) -> Any:
        """Get house management details by GIS GKH GUID.

        IMPORTANT: This requires a GIS GKH GUID (from get_houses_by_org
        items' 'guid' field), NOT a FIAS GUID.

        Args:
            home_management_guid: GIS GKH house management GUID.

        Returns:
            Detailed house management info (address hierarchy, org info).
        """
        url = self.HOME_MANAGEMENT_URL.format(home_management_guid)
        return self._get_response_body(self._get(url))

    def get_house_info(self, house_guid: str) -> Any:
        """Get house characteristics from information-disclosure.

        IMPORTANT: This requires a GIS GKH GUID, NOT a FIAS GUID.

        Args:
            house_guid: GIS GKH house GUID.

        Returns:
            House characteristics dict with building info:
            - built year, floor count, apartment count
            - total area, energy efficiency class
            - overhaul fund info, deterioration percentage
        """
        headers = {
            'Session-GUID': str(uuid4()),
            'Request-GUID': str(uuid4()),
        }
        url = self.HOUSE_INFO_URL.format(house_guid)
        return self._get_response_body(self._get(url, headers=headers))

    # ========== FIAS methods ==========

    def get_actual_houses(self, house_code: str) -> Any:
        """Look up actual FIAS house data by FIAS objectguid.

        IMPORTANT: house_code must be a FIAS objectguid (UUID format),
        NOT an integer objectid.

        Args:
            house_code: FIAS house objectguid (UUID).

        Returns:
            List of FIAS house records with address, postal code.
        """
        url = self.HOUSE_CODE_URL.format(house_code, 'true')
        return self._get_response_body(self._get(url))

    def get_not_actual_houses(self, house_code: str) -> Any:
        """Look up non-actual (historical) FIAS house data.

        Args:
            house_code: FIAS house objectguid (UUID).

        Returns:
            List of historical FIAS house records.
        """
        url = self.HOUSE_CODE_URL.format(house_code, 'false')
        return self._get_response_body(self._get(url))

    # ========== Legacy pagination method ==========

    def get_home_managements(self, org_guid: str, start_page: int = 1, per_page: int = 1):
        """Get home managements by organization (legacy paginated generator).

        Prefer get_houses_by_org / get_all_houses_by_org for new code.
        """
        url = (
            f'{self.BASE_URL}homemanagement/api/rest/services/houses/public/'
            f'searchByOrg?pageIndex={start_page}&elementsPerPage={per_page}'
        )
        payload = json.dumps({'organizationGuid': org_guid, 'calcCount': True})
        headers = {'Content-Type': 'application/json'}
        self._wait_rate_limit()
        response = requests.post(url, data=payload, headers=headers)
        json_body = self._get_response_body(response)
        yield json_body
        objects_number = json_body.get('total') or 0
        for page_num in range(2, objects_number + 1):
            url = (
                f'{self.BASE_URL}homemanagement/api/rest/services/houses/public/'
                f'searchByOrg?pageIndex={page_num}&elementsPerPage={per_page}'
            )
            self._wait_rate_limit()
            response = requests.post(url, data=payload, headers=headers)
            yield self._get_response_body(response)

    # ========== License methods (may be blocked) ==========

    def _get_license_uids(self, region_codes):
        license_uids = {}
        for region_code in region_codes:
            if region_code < 10:
                url_region_code = f'0{region_code}'
            else:
                url_region_code = region_code
            response = self._get(
                self.LICENSE_UID_URL.format(url_region_code))
            if response.status_code != 200:
                logger.error(f'uid for {region_code} was not obtained')
            else:
                license_uids[
                    self.REGION_CODES_AND_NAMES[region_code]] = response.text

        return license_uids

    def _get_licenses_info(self, license_uids):
        licenses_info = {}
        for region_name, license_uid in license_uids.items():
            self._wait_rate_limit()
            response = requests.get(
                self.DOWNLOAD_LICENSES_INFO_URL.format(
                    uid=license_uid, file_name=region_name))
            if response.status_code != 200:
                logger.error(
                    f'License info for {region_name} was not obtained')
            else:
                licenses_info[region_name] = response.content

        return licenses_info

    def _get_workbooks_from_licenses_info(self, licenses_info):
        for region_name, zip_content in licenses_info.items():
            zip_file = ZipFile(BytesIO(zip_content))
            for name in zip_file.namelist():
                if name.endswith('.xlsx'):
                    xlsx_content = BytesIO(zip_file.open(name).read())
                    workbook = load_workbook(xlsx_content, read_only=True)
                    yield Licenses(region_name=region_name, workbook=workbook)

    def get_licenses(self, region_codes: List[int]):
        """Get license information for regions.

        WARNING: This endpoint currently returns HTTP 403 (blocked).

        Args:
            region_codes: List of region codes (e.g. [12] for Mari El).
        """
        for region_code in region_codes:
            if region_code not in REGION_CODES_AND_NAMES:
                raise RegionCodeIsAbsentError(
                    f'Region code {region_code} is absent in reference')

        license_uids = self._get_license_uids(region_codes)
        licenses_info = self._get_licenses_info(license_uids)
        return self._get_workbooks_from_licenses_info(licenses_info)
