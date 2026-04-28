import json
import os
from typing import Any

import requests
from dotenv import load_dotenv
from urllib3.exceptions import InsecureRequestWarning

from .utils.verbose_utils import inform, warn


class WikibaseAPI:
    """
    A wrapper of the Wikibase API for common operations needed in the pipeline.
    Handles authentication, token management, and provides methods for
    searching, creating, editing, and deleting entities and claims.
    """

    def __init__(self, params: dict) -> None:
        """
        Initialize a WikibaseAPI instance.
        """
        self.api_url = params["api_url"]
        self.session = requests.Session()

        self.language = params["language"]

        self.verify = params["tls_verify"]
        if self.verify is False:
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

        self.verbose = params["verbose"]
        self._property_datatypes_cache: dict[str, str] = {}

        self.user, self.password = self._load_env()
        self.csrf_token: str | None = None
        self._login()

        self._valid_languages_cache: set[str] | None = None

    def _load_env(self) -> tuple[str, str]:
        """
        Load Wikibase credentials from environment variables.
        """
        load_dotenv()
        user = os.getenv("WB_USER")
        password = os.getenv("WB_PASSWORD")
        if not user or not password:
            raise OSError(
                "\nWikibase credentials not found.\n\n"
                "Expected a .env file at the project root with:\n\n"
                "WB_USER=your_username\n"
                "WB_PASSWORD=your_password\n\n"
            )
        return user, password

    def _get_token(self, token_type: str) -> str:
        """
        Get a token of the specified type from the Wikibase API.
        """
        r = self.session.get(
            self.api_url,
            params={
                "action": "query",
                "meta": "tokens",
                "type": token_type,
                "format": "json",
            },
            timeout=30,
            verify=self.verify,
        )
        r.raise_for_status()

        data = r.json()
        try:
            return data["query"]["tokens"][f"{token_type}token"]
        except KeyError as err:
            raise RuntimeError(f"Failed to get {token_type} token: {data}") from err

    def _login(self) -> None:
        """
        Login to the Wikibase API and store the CSRF token for future requests.
        """
        login_token = self._get_token("login")

        r = self.session.post(
            self.api_url,
            data={
                "action": "login",
                "lgname": self.user,
                "lgpassword": self.password,
                "lgtoken": login_token,
                "format": "json",
            },
            timeout=30,
            verify=self.verify,
        )
        r.raise_for_status()
        data = r.json()

        result = data.get("login", {}).get("result")
        if result != "Success":
            raise RuntimeError(f"Login failed: {data}")

        self.csrf_token = None
        self.csrf_token = self._get_token("csrf")

        inform(
            f"Successfully connected to Wikibase API at {self.api_url}.", self.verbose
        )

    def _refresh_csrf_token(self) -> str:
        """
        Refresh and return a new CSRF token.
        """
        self.csrf_token = self._get_token("csrf")
        return self.csrf_token

    def _api_get(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Generic method to perform a GET request
        to the Wikibase API with the given parameters.
        Input:
        - params: The query parameters to send in the GET request.
        Output:
        - The parsed JSON response from the API.
        """
        full_params = {"format": "json", **params}
        r = self.session.get(
            self.api_url,
            params=full_params,
            timeout=30,
            verify=self.verify,
        )
        r.raise_for_status()
        data = r.json()
        self._raise_api_error(data)
        return data

    def _api_post(
        self, data: dict[str, Any], retry_on_badtoken: bool = True
    ) -> dict[str, Any]:
        """
        Generic method to perform a POST request
        to the Wikibase API with the given data.
        If the CSRF token is invalid, refresh it and retry once.
        Input:
        - data: The form data to send in the POST request.
        - retry_on_badtoken: Whether to retry once if a badtoken error is encountered.
        Output:
        - The parsed JSON response from the API.
        """
        if self.csrf_token is None:
            self._refresh_csrf_token()

        full_data = {
            "format": "json",
            "token": self.csrf_token,
            **data,
        }

        r = self.session.post(
            self.api_url,
            data=full_data,
            timeout=30,
            verify=self.verify,
        )
        r.raise_for_status()
        payload = r.json()

        error = payload.get("error")
        if error and error.get("code") == "badtoken":
            if not retry_on_badtoken:
                raise RuntimeError(f"Wikibase API error: {error}")

            inform(
                "CSRF token expired or invalid; refreshing token and retrying once.",
                self.verbose,
            )

            full_data["token"] = self._refresh_csrf_token()

            r = self.session.post(
                self.api_url,
                data=full_data,
                timeout=30,
                verify=self.verify,
            )
            r.raise_for_status()
            payload = r.json()

        self._raise_api_error(payload)
        return payload

    def _raise_api_error(self, data: dict[str, Any]) -> None:
        """
        Raise a RuntimeError if the API response contains an error.
        Input:
        - data: The parsed JSON response from the API.
        """
        if "error" in data:
            raise RuntimeError(f"Wikibase API error: {data['error']}")

    def get_valid_languages(self, refresh: bool = False) -> set[str]:
        """
        Return the set of content languages supported by this Wikibase instance.
        Input:
        - refresh: Whether to refresh the cache.
        """
        if self._valid_languages_cache is not None and not refresh:
            return self._valid_languages_cache

        data = self._api_get(
            {
                "action": "query",
                "meta": "wbcontentlanguages",
                "wbclcontext": "term",
            }
        )

        raw_languages = data.get("query", {}).get("wbcontentlanguages", {})
        if not raw_languages:
            raise RuntimeError(
                "Could not retrieve supported Wikibase content languages "
                f"from API response: {data}"
            )

        valid_langs = set(raw_languages.keys())
        self._valid_languages_cache = valid_langs

        inform(
            f"Loaded {len(valid_langs)} Wikibase content languages: "
            f"{sorted(valid_langs)}",
            self.verbose,
        )
        return valid_langs

    def search_properties_by_label(self, label: str, language: str = "en") -> list[str]:
        """
        Search Wikibase for properties matching the given label.
        Inputs:
        - label: The label to search for.
        - language: The language to search in.
        Returns only PIDs whose label is an exact match.
        """
        data = self._api_get(
            {
                "action": "wbsearchentities",
                "search": label,
                "language": language,
                "type": "property",
                "limit": 50,
            }
        )
        needle = label.strip().lower()
        return [
            result["id"]
            for result in data.get("search", [])
            if result.get("match", {}).get("text", "").strip().lower() == needle
        ]

    def get_property_datatype(self, pid: str) -> str:
        """
        Fetch the datatype of a property from Wikibase.
        Input:
        - pid: The property ID.
        Output:
        - The datatype of the property.
        """
        data = self._api_get(
            {
                "action": "wbgetentities",
                "ids": pid,
                "props": "datatype",
            }
        )
        datatype = data.get("entities", {}).get(pid, {}).get("datatype")
        if not datatype:
            raise RuntimeError(f"Could not retrieve datatype for {pid}: {data}")
        return datatype

    def create_property(
        self,
        labels: dict[str, str],
        datatype: str,
        descriptions: dict[str, str] | None = None,
        aliases: dict[str, list[str]] | None = None,
    ) -> str:
        """
        Create a new property in Wikibase.
        Inputs:
        - labels: A dict of language code to label string.
        - datatype: The Wikibase datatype for this property
        - descriptions: Optional dict of language code to description string.
        - aliases: Optional dict of language code to list of alias strings.
        Metadata are associated with language codes, which must be valid BCP47 codes
        """
        entity_data: dict = {"datatype": datatype}

        if labels:
            entity_data["labels"] = {
                lang: {"language": lang, "value": value}
                for lang, value in labels.items()
                if lang
            }
        if descriptions:
            entity_data["descriptions"] = {
                lang: {"language": lang, "value": value}
                for lang, value in descriptions.items()
                if lang
            }
        if aliases:
            entity_data["aliases"] = {
                lang: [{"language": lang, "value": v} for v in values]
                for lang, values in aliases.items()
                if lang
            }

        data = self._api_post(
            {
                "action": "wbeditentity",
                "new": "property",
                "data": json.dumps(entity_data, ensure_ascii=False),
            }
        )
        pid = data.get("entity", {}).get("id")
        if not pid:
            raise RuntimeError(f"Failed to create property: {data}")
        return pid

    def search_items_by_label(self, label: str, language: str = "en") -> list[str]:
        """
        Search Wikibase for items matching the given label.
        Inputs:
        - label: The label to search for.
        - language: The language to search in.
        Returns only QIDs whose label is an exact match.
        """
        data = self._api_get(
            {
                "action": "wbsearchentities",
                "search": label,
                "language": language,
                "type": "item",
                "limit": 50,
            }
        )
        needle = label.strip().lower()
        return [
            result["id"]
            for result in data.get("search", [])
            if result.get("match", {}).get("text", "").strip().lower() == needle
        ]

    def get_entity_claims(self, qid: str) -> dict:
        """
        Get the claims of an entity by QID.
        Input:
        - qid: The QID of the entity.
        Output:
        - A dict of claims, keyed by property PID.
        """
        entity = self.get_entity(qid, props="claims")
        return entity.get("claims", {})

    def get_entity(
        self,
        qid: str,
        props: str = "labels|descriptions|aliases|claims",
    ) -> dict:
        """
        Fetch entity data from Wikibase.
        Raises RuntimeError if the entity does not exist.
        Inputs:
        - qid: The QID of the entity to fetch.
        - props: The properties to retrieve
        (default: labels, descriptions, aliases, claims).
        Output:
        - A dict containing the entity data for the requested properties.
        """
        data = self._api_get(
            {
                "action": "wbgetentities",
                "ids": qid,
                "props": props,
            }
        )
        entity = data.get("entities", {}).get(qid, {})
        if "missing" in entity:
            raise RuntimeError(f"Entity {qid} not found in Wikibase.")
        return entity

    def create_item(
        self,
        labels: dict[str, str],
        descriptions: dict[str, str] | None = None,
        aliases: dict[str, list[str]] | None = None,
    ) -> str:
        """
        Create a new item in Wikibase.
        Inputs:
        - labels: A dict of language code to label string.
        - descriptions: Optional dict of language code to description string.
        - aliases: Optional dict of language code to list of alias strings.
        Metadata are associated with language codes, which must be valid BCP47 codes.
        Returns the new QID.
        """
        entity_data: dict = {}

        if labels:
            entity_data["labels"] = {
                lang: {"language": lang, "value": value}
                for lang, value in labels.items()
                if lang  # skip RDF literals without a language tag
            }
        if descriptions:
            entity_data["descriptions"] = {
                lang: {"language": lang, "value": value}
                for lang, value in descriptions.items()
                if lang
            }
        if aliases:
            entity_data["aliases"] = {
                lang: [{"language": lang, "value": v} for v in values]
                for lang, values in aliases.items()
                if lang
            }

        data = self._api_post(
            {
                "action": "wbeditentity",
                "new": "item",
                "data": json.dumps(entity_data, ensure_ascii=False),
            }
        )
        qid = data.get("entity", {}).get("id")
        if not qid:
            raise RuntimeError(f"Failed to create item: {data}")
        return qid

    def edit_entity(self, qid: str, entity_data: dict) -> None:
        """
        Push a metadata diff (labels / descriptions / aliases) to an existing entity.
        Inputs:
        - qid: The QID of the entity to edit.
        - entity_data: A dict containing the metadata to update,
        in the same format as the "data" parameter of wbeditentity
        (e.g., {"labels": {"en": {"language": "en", "value": "New label"}}}).
        """
        self._api_post(
            {
                "action": "wbeditentity",
                "id": qid,
                "data": json.dumps(entity_data, ensure_ascii=False),
            }
        )

    def _to_datavalue(self, value, property_datatype: str) -> dict:
        """
        Wrap a simple Wikibase value into the datavalue envelope
        required by wbeditentity.
        Inputs:
        - value: The value to wrap.
        - property_datatype: The datatype of the property for which
        to create the datavalue.
        Output:
        A dict representing the datavalue.
        """
        if property_datatype in ("string", "url"):
            return {"type": "string", "value": value}
        if property_datatype == "wikibase-item":
            return {"type": "wikibase-entityid", "value": value}
        if property_datatype == "monolingualtext":
            return {"type": "monolingualtext", "value": value}
        if property_datatype == "quantity":
            return {"type": "quantity", "value": value}
        if property_datatype == "time":
            return {"type": "time", "value": value}
        raise ValueError(
            f"Cannot build datavalue for unsupported datatype '{property_datatype}'."
        )

    def add_statement(
        self,
        subject_qid: str,
        property_pid: str,
        value,
        property_datatype: str,
        rank: str = "normal",
    ) -> str:
        """
        Create a statement on an entity.
        Inputs:
        - subject_qid: The QID of the entity to which to add the statement.
        - property_pid: The PID of the property for which to add the statement.
        - value: The value of the claim, as a simple Python type (e.g.,
        """
        # Step 1: create the claim (always lands at normal rank)
        data = self._api_post(
            {
                "action": "wbcreateclaim",
                "entity": subject_qid,
                "property": property_pid,
                "snaktype": "value",
                "value": json.dumps(value),
            }
        )
        guid = data.get("claim", {}).get("id")
        if not guid:
            raise RuntimeError(
                f"Failed to create statement on {subject_qid} / {property_pid}: {data}"
            )

        # Step 2: if a non-normal rank is required, update via wbeditentity
        if rank != "normal":
            self._api_post(
                {
                    "action": "wbeditentity",
                    "id": subject_qid,
                    "data": json.dumps(
                        {
                            "claims": [
                                {
                                    "id": guid,
                                    "type": "statement",
                                    "rank": rank,
                                    "mainsnak": {
                                        "snaktype": "value",
                                        "property": property_pid,
                                        "datavalue": self._to_datavalue(
                                            value, property_datatype
                                        ),
                                    },
                                }
                            ]
                        }
                    ),
                }
            )

        return guid

    def add_qualifier(
        self,
        claim_guid: str,
        property_pid: str,
        value,
    ) -> None:
        """
        Add a qualifier snak to an existing claim.
        Inputs:
        - claim_guid: The GUID of the claim to which to add the qualifier.
        - property_pid: The PID of the property for which to add the qualifier.
        - value: The value of the qualifier, as a simple Python type.
        """
        self._api_post(
            {
                "action": "wbsetqualifier",
                "claim": claim_guid,
                "property": property_pid,
                "snaktype": "value",
                "value": json.dumps(value),
            }
        )

    def add_reference(
        self,
        claim_guid: str,
        snaks: list[tuple[str, any, str]],
    ) -> str:
        """
        Create a reference on a claim.
        Inputs:
        - claim_guid: The GUID of the claim to which to add the reference.
        - snaks: A list of snaks to add to the reference,
        where each snak is a tuple of (property_pid, value, property_datatype).
        Output:
        - The hash of the created reference.
        """
        snaks_dict: dict = {}
        for pid, value, datatype in snaks:
            snak = {
                "snaktype": "value",
                "property": pid,
                "datavalue": self._to_datavalue(value, datatype),
            }
            snaks_dict.setdefault(pid, []).append(snak)

        data = self._api_post(
            {
                "action": "wbsetreference",
                "statement": claim_guid,
                "snaks": json.dumps(snaks_dict),
            }
        )
        ref_hash = data.get("reference", {}).get("hash")
        if not ref_hash:
            raise RuntimeError(f"Failed to create reference on {claim_guid}: {data}")
        return ref_hash

    def filter_existing_ids(self, ids: list[str]) -> set[str]:
        """
        Given a list of QIDs / PIDs, return the subset that actually
        exist in Wikibase.
        Input:
        - ids: A list of entity IDs (QIDs or PIDs) to check for existence
        Output:
        - A set of IDs that exist in Wikibase among the input list
        """
        existing: set[str] = set()
        batch_size = 50
        for i in range(0, len(ids), batch_size):
            batch = ids[i : i + batch_size]
            data = self._api_get(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(batch),
                    "props": "info",
                }
            )
            for entity_id, entity_data in data.get("entities", {}).items():
                if "missing" not in entity_data:
                    existing.add(entity_id)
        return existing

    def delete_entity(self, entity_id: str) -> None:
        """
        Delete an entity (item or property) by ID
        Input:
        - entity_id: The ID of the entity to delete.
        """
        if entity_id.startswith("Q"):
            title = f"Item:{entity_id}"
        elif entity_id.startswith("P"):
            title = f"Property:{entity_id}"
        else:
            raise ValueError(f"Unrecognized entity ID format: {entity_id!r}")

        self._api_post(
            {
                "action": "delete",
                "title": title,
                "reason": "Batch deletion via API",
            }
        )
        inform(f"Deleted {entity_id}", self.verbose)

    def delete_items_range(self, start: int, end: int) -> None:
        """
        Delete items from Q{start} to Q{end} (inclusive).
        Works also for a single value if start == end.
        Inputs:
        - start: The starting number for the QID range (e.g., 1 for Q1).
        - end: The ending number for the QID range (e.g., 100 for Q100).
        """
        if start > end:
            raise ValueError("start must be <= end")

        deleted = 0
        skipped = 0

        for i in range(start, end + 1):
            qid = f"Q{i}"
            try:
                self.delete_entity(qid)
                inform(f"Deleted item {qid}", self.verbose)
                deleted += 1
            except Exception as exc:
                warn(f"Skipping {qid}: {exc}", self.verbose)
                skipped += 1

        inform(
            f"Items deletion completed: {deleted} deleted, {skipped} skipped.",
            self.verbose,
        )

    def delete_properties_range(self, start: int, end: int) -> None:
        """
        Delete properties from P{start} to P{end} (inclusive).
        Works also for a single value if start == end.
        Inputs:
        - start: The starting number for the PID range (e.g., 1 for P1).
        - end: The ending number for the PID range (e.g., 100 for P100).
        """
        if start > end:
            raise ValueError("start must be <= end")

        deleted = 0
        skipped = 0

        for i in range(start, end + 1):
            pid = f"P{i}"
            try:
                self.delete_entity(pid)
                inform(f"Deleted property {pid}", self.verbose)
                deleted += 1
            except Exception as exc:
                warn(f"Skipping {pid}: {exc}", self.verbose)
                skipped += 1

        inform(
            f"Properties deletion completed: {deleted} deleted, {skipped} skipped.",
            self.verbose,
        )
