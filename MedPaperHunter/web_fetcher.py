"""Web fetcher module for MedPaperHunter.

Provides CARSI-based session management for accessing Web of Science (WoS)
and Embase through university authentication. Handles the SAML login flow
and fetches articles from both databases.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

# WoS API endpoint
WOS_SEARCH_URL = "https://www.webofscience.com/api/wos/search"

# Embase search endpoint
EMBASE_SEARCH_URL = "https://www.embase.com/search"


class CARSIAuthError(Exception):
    """Raised when CARSI authentication fails."""

    pass


class CARSISession:
    """CARSI-based session manager for university-authenticated database access.

    Handles the SAML SSO login flow through a CARSI identity provider,
    then provides methods to search WoS and Embase using the authenticated
    session cookies.

    Args:
        carsi_url: The CARSI login URL for the target institution.
        username: Institutional username (student/staff ID).
        password: Institutional password.
    """

    def __init__(self, carsi_url: str, username: str, password: str) -> None:
        self.carsi_url = carsi_url
        self.username = username
        self.password = password
        self._client: Optional[httpx.AsyncClient] = None
        self._authenticated: bool = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx async client.

        Returns:
            The httpx.AsyncClient instance.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=False,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )
        return self._client

    async def login(self) -> bool:
        """Perform CARSI authentication via SAML SSO flow.

        The login flow typically involves:
        1. GET the CARSI login page to obtain the SAML request
        2. POST credentials to the identity provider
        3. Handle SAML response and redirects
        4. Extract session cookies

        Returns:
            True if authentication was successful, False otherwise.

        Raises:
            CARSIAuthError: If authentication fails at any step.
        """
        client = await self._get_client()
        logger.info("Starting CARSI login flow via: %s", self.carsi_url)

        try:
            # Step 1: GET the CARSI login page to obtain SAML request
            resp = await client.get(self.carsi_url)
            if resp.status_code in (301, 302, 303, 307):
                redirect_url = resp.headers.get("location", "")
                if redirect_url:
                    resp = await client.get(redirect_url)

            # Step 2: Extract SAML request and form action from the login page
            saml_data, form_action = self._extract_saml_request(resp.text)

            if not form_action:
                logger.error("Could not find login form action in CARSI page")
                raise CARSIAuthError(
                    "Failed to locate login form. The CARSI URL may be incorrect "
                    "or the institution's IdP page structure has changed."
                )

            # Step 3: POST credentials to the identity provider
            login_data = {
                **saml_data,
                "username": self.username,
                "password": self.password,
            }

            # TODO: Institution-specific adjustments may be required here.
            # Different universities may use different field names for
            # username/password (e.g., "user", "passwd", "j_username", etc.)
            # and may require additional fields (e.g., captcha, OTP).
            # Adjust the field names below to match your institution's IdP.
            resp = await client.post(form_action, data=login_data)

            # Step 4: Follow redirects and handle SAML response
            redirect_chain = 0
            max_redirects = 10
            while resp.status_code in (301, 302, 303, 307) and redirect_chain < max_redirects:
                redirect_url = resp.headers.get("location", "")
                if not redirect_url:
                    break

                # Handle SAML POST binding if present
                if resp.status_code == 200 and "SAMLResponse" in resp.text:
                    saml_action, saml_response = self._extract_saml_response(resp.text)
                    if saml_action and saml_response:
                        resp = await client.post(
                            saml_action,
                            data={"SAMLResponse": saml_response},
                        )
                        continue

                resp = await client.get(redirect_url)
                redirect_chain += 1

            # Step 5: Verify authentication success
            self._authenticated = self._verify_auth_success(resp)
            if self._authenticated:
                logger.info("CARSI authentication successful")
            else:
                logger.warning(
                    "CARSI authentication may have failed. "
                    "Session cookies: %s",
                    list(client.cookies.keys()),
                )

            return self._authenticated

        except httpx.HTTPError as exc:
            logger.error("HTTP error during CARSI login: %s", exc)
            raise CARSIAuthError(f"HTTP error during CARSI login: {exc}") from exc

    def _extract_saml_request(self, html: str) -> tuple[dict[str, str], str]:
        """Extract SAML request parameters and form action from HTML.

        Args:
            html: The HTML content of the login page.

        Returns:
            Tuple of (form_data_dict, form_action_url).
        """
        # Look for hidden form inputs
        form_data: dict[str, str] = {}
        form_action = ""

        # Match form action
        action_match = re.search(r'<form[^>]*action=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if action_match:
            form_action = action_match.group(1)

        # Match hidden inputs (SAMLRequest, RelayState, etc.)
        input_pattern = re.compile(
            r'<input[^>]*type=["\']hidden["\'][^>]*name=["\']([^"\']*)["\'][^>]*value=["\']([^"\']*)["\']',
            re.IGNORECASE,
        )
        for match in input_pattern.finditer(html):
            form_data[match.group(1)] = match.group(2)

        # Also try reversed attribute order (value before name)
        input_pattern_rev = re.compile(
            r'<input[^>]*type=["\']hidden["\'][^>]*value=["\']([^"\']*)["\'][^>]*name=["\']([^"\']*)["\']',
            re.IGNORECASE,
        )
        for match in input_pattern_rev.finditer(html):
            form_data[match.group(2)] = match.group(1)

        return form_data, form_action

    def _extract_saml_response(self, html: str) -> tuple[str, str]:
        """Extract SAML response and action URL from an auto-submit form.

        Args:
            html: The HTML content containing the SAML response form.

        Returns:
            Tuple of (form_action_url, saml_response_value).
        """
        action_match = re.search(r'<form[^>]*action=["\']([^"\']*)["\']', html, re.IGNORECASE)
        action_url = action_match.group(1) if action_match else ""

        saml_match = re.search(
            r'<input[^>]*name=["\']SAMLResponse["\'][^>]*value=["\']([^"\']*)["\']',
            html,
            re.IGNORECASE,
        )
        if not saml_match:
            saml_match = re.search(
                r'<input[^>]*value=["\']([^"\']*)["\'][^>]*name=["\']SAMLResponse["\']',
                html,
                re.IGNORECASE,
            )

        saml_response = saml_match.group(1) if saml_match else ""

        return action_url, saml_response

    def _verify_auth_success(self, resp: httpx.Response) -> bool:
        """Verify whether authentication was successful.

        Args:
            resp: The final HTTP response after the login flow.

        Returns:
            True if authentication appears successful.
        """
        # Check for common success indicators
        success_indicators = [
            "webofscience.com" in str(resp.url),
            "embase.com" in str(resp.url),
            resp.status_code == 200,
        ]

        # Check for common failure indicators
        failure_indicators = [
            "login failed" in resp.text.lower(),
            "invalid credentials" in resp.text.lower(),
            "authentication error" in resp.text.lower(),
        ]

        # TODO: Institution-specific success/failure checks can be added here.
        # For example, checking for a specific welcome message or dashboard URL.

        return any(success_indicators) and not any(failure_indicators)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> CARSISession:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

    # ------------------------------------------------------------------
    # WoS search
    # ------------------------------------------------------------------

    async def fetch_wos(
        self,
        query: str,
        max_results: int = 500,
        date_range: str = "",
    ) -> list[dict[str, Any]]:
        """Search Web of Science using the authenticated session.

        Args:
            query: WoS search query string (e.g. "TS=(cancer immunotherapy)").
            max_results: Maximum number of results to retrieve.
            date_range: Optional date range filter (e.g. "2020-2024").

        Returns:
            List of article dicts with source="wos".

        Raises:
            CARSIAuthError: If not authenticated.
            httpx.HTTPStatusError: If the WoS API returns an error.
        """
        if not self._authenticated:
            raise CARSIAuthError("Not authenticated. Call login() first.")

        client = await self._get_client()
        articles: list[dict[str, Any]] = []

        logger.info("Searching WoS with query: %s", query)

        try:
            # Build request parameters
            params: dict[str, Any] = {
                "q": query,
                "count": min(max_results, 100),
                "first": 1,
            }

            if date_range:
                params["timeSpan"] = date_range

            # TODO: WoS API may require specific headers and authentication tokens
            # beyond session cookies. The exact API contract varies by subscription.
            # Adjust the request format as needed for your WoS subscription tier.

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }

            resp = await client.get(
                WOS_SEARCH_URL,
                params=params,
                headers=headers,
            )
            resp.raise_for_status()

            data = resp.json()
            wos_records = data.get("Data", {}).get("Records", {}).get("records", [])

            for record in wos_records[:max_results]:
                article = self._parse_wos_record(record)
                articles.append(article)

            # Handle pagination if needed
            page = 1
            while len(articles) < max_results and wos_records:
                page += 1
                params["first"] = (page - 1) * 100 + 1
                resp = await client.get(
                    WOS_SEARCH_URL,
                    params=params,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                wos_records = data.get("Data", {}).get("Records", {}).get("records", [])
                for record in wos_records:
                    if len(articles) >= max_results:
                        break
                    article = self._parse_wos_record(record)
                    articles.append(article)

        except httpx.HTTPError as exc:
            logger.error("WoS search failed: %s", exc)
            raise

        logger.info("WoS search returned %d articles", len(articles))
        return articles

    def _parse_wos_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Parse a single WoS record into a standardized article dict.

        Args:
            record: A single record dict from the WoS API response.

        Returns:
            Standardized article dict with source="wos".
        """
        article: dict[str, Any] = {
            "source": "wos",
            "pmid": None,
            "title": "",
            "authors": [],
            "journal": "",
            "pub_date": "",
            "abstract": "",
            "doi": None,
        }

        # Title
        title_data = record.get("title", {})
        if isinstance(title_data, dict):
            article["title"] = title_data.get("full", "").strip()
        elif isinstance(title_data, str):
            article["title"] = title_data.strip()

        # Authors
        author_data = record.get("authors", {})
        if isinstance(author_data, dict):
            for author in author_data.get("authors", []):
                name = author.get("fullName", "").strip()
                if name:
                    article["authors"].append(name)
        elif isinstance(author_data, list):
            for author in author_data:
                if isinstance(author, dict):
                    name = author.get("fullName", "").strip()
                    if name:
                        article["authors"].append(name)
                elif isinstance(author, str):
                    article["authors"].append(author.strip())

        # Journal / Source
        source_data = record.get("source", {})
        if isinstance(source_data, dict):
            article["journal"] = source_data.get("title", "").strip()
        elif isinstance(source_data, str):
            article["journal"] = source_data.strip()

        # Publication date
        pub_date_data = record.get("pubDate", {})
        if isinstance(pub_date_data, dict):
            parts = [
                pub_date_data.get("year", ""),
                pub_date_data.get("month", ""),
                pub_date_data.get("day", ""),
            ]
            article["pub_date"] = " ".join(p for p in parts if p)
        elif isinstance(pub_date_data, str):
            article["pub_date"] = pub_date_data.strip()

        # Abstract
        abstract_data = record.get("abstract", {})
        if isinstance(abstract_data, dict):
            article["abstract"] = abstract_data.get("text", "").strip()
        elif isinstance(abstract_data, str):
            article["abstract"] = abstract_data.strip()

        # DOI
        identifiers = record.get("identifiers", {})
        if isinstance(identifiers, dict):
            for idm in identifiers.get("identifier", []):
                if isinstance(idm, dict) and idm.get("type") == "doi":
                    article["doi"] = idm.get("value", "").strip()
                    break

        # PMID (may not be present in WoS)
        if isinstance(identifiers, dict):
            for idm in identifiers.get("identifier", []):
                if isinstance(idm, dict) and idm.get("type") == "pmid":
                    article["pmid"] = idm.get("value", "").strip()
                    break

        return article

    # ------------------------------------------------------------------
    # Embase search
    # ------------------------------------------------------------------

    async def fetch_embase(
        self,
        query: str,
        max_results: int = 500,
        date_range: str = "",
    ) -> list[dict[str, Any]]:
        """Search Embase using the authenticated session.

        Args:
            query: Embase search query string (e.g. "(cancer AND immunotherapy):ab,ti").
            max_results: Maximum number of results to retrieve.
            date_range: Optional date range filter (e.g. "2020-2024").

        Returns:
            List of article dicts with source="embase".

        Raises:
            CARSIAuthError: If not authenticated.
            httpx.HTTPStatusError: If the Embase API returns an error.
        """
        if not self._authenticated:
            raise CARSIAuthError("Not authenticated. Call login() first.")

        client = await self._get_client()
        articles: list[dict[str, Any]] = []

        logger.info("Searching Embase with query: %s", query)

        try:
            # TODO: Embase search API specifics may vary.
            # The endpoint and request format below are a skeleton.
            # Adjust based on the actual Embase API documentation
            # available through your institutional subscription.

            params: dict[str, Any] = {
                "query": query,
                "size": min(max_results, 100),
                "from": 0,
            }

            if date_range:
                params["dateRange"] = date_range

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }

            resp = await client.get(
                EMBASE_SEARCH_URL,
                params=params,
                headers=headers,
            )
            resp.raise_for_status()

            data = resp.json()
            embase_results = data.get("results", [])

            for result in embase_results[:max_results]:
                article = self._parse_embase_record(result)
                articles.append(article)

            # Handle pagination
            offset = 100
            while len(articles) < max_results and embase_results:
                params["from"] = offset
                resp = await client.get(
                    EMBASE_SEARCH_URL,
                    params=params,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                embase_results = data.get("results", [])
                for result in embase_results:
                    if len(articles) >= max_results:
                        break
                    article = self._parse_embase_record(result)
                    articles.append(article)
                offset += 100

        except httpx.HTTPError as exc:
            logger.error("Embase search failed: %s", exc)
            raise

        logger.info("Embase search returned %d articles", len(articles))
        return articles

    def _parse_embase_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Parse a single Embase record into a standardized article dict.

        Args:
            record: A single record dict from the Embase API response.

        Returns:
            Standardized article dict with source="embase".
        """
        article: dict[str, Any] = {
            "source": "embase",
            "pmid": None,
            "title": "",
            "authors": [],
            "journal": "",
            "pub_date": "",
            "abstract": "",
            "doi": None,
        }

        # Title
        article["title"] = record.get("title", "").strip()

        # Authors
        author_list = record.get("authors", [])
        if isinstance(author_list, list):
            for author in author_list:
                if isinstance(author, str):
                    article["authors"].append(author.strip())
                elif isinstance(author, dict):
                    name = author.get("name", "").strip()
                    if name:
                        article["authors"].append(name)

        # Journal
        citation = record.get("citation", "")
        if citation:
            article["journal"] = citation.strip()

        # Publication date
        article["pub_date"] = record.get("publicationDate", "").strip()

        # Abstract
        abstract_text = record.get("abstract", "")
        if isinstance(abstract_text, str):
            article["abstract"] = abstract_text.strip()
        elif isinstance(abstract_text, list):
            article["abstract"] = " ".join(abstract_text)

        # DOI
        article["doi"] = record.get("doi", None)

        # PMID
        article["pmid"] = record.get("pmid", None)

        return article
