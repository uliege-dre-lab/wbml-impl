import json
import os
from typing import Any

import requests
from dotenv import load_dotenv
from rdflib import Literal, URIRef
from urllib3.exceptions import InsecureRequestWarning

from .utils import inform


class WikibaseAPI:
    def __init__(self, params: dict) -> None:
        self.api_url = params["api_url"]
        self.session = requests.Session()

        self.sparql_endpoint = params["sparql_endpoint"]

        self.language = params["language"]

        self.verify = params["tls_verify"]
        if self.verify is False:
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

        self.verbose = params["verbose"]
        self._property_datatypes_cache: dict[str, str] = {}

        self.user, self.password = self._load_env()
        self._login()

    def _load_env(self) -> tuple[str, str]:
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

        self.csrf_token = self._get_token("csrf")

        inform(
            f"Successfully connected to Wikibase API at {self.api_url}.", self.verbose
        )

    def _api_get(self, params: dict[str, Any]) -> dict[str, Any]:
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

    def _api_post(self, data: dict[str, Any]) -> dict[str, Any]:
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
        self._raise_api_error(payload)
        return payload

    def _raise_api_error(self, data: dict[str, Any]) -> None:
        if "error" in data:
            raise RuntimeError(f"Wikibase API error: {data['error']}")

    def _search_entities(self, search: str, entity_type: str) -> list[dict[str, Any]]:
        data = self._api_get(
            {
                "action": "wbsearchentities",
                "search": search,
                "language": self.language,
                "type": entity_type,
                "limit": 10,
            }
        )
        return data.get("search", [])

    def _get_entity(self, entity_id: str) -> dict[str, Any]:
        data = self._api_get(
            {
                "action": "wbgetentities",
                "ids": entity_id,
                "props": "info|labels|descriptions|claims|datatype",
                "languages": self.language,
            }
        )
        entities = data.get("entities", {})
        if entity_id not in entities:
            raise RuntimeError(
                f"Entity {entity_id} not found in wbgetentities response."
            )
        return entities[entity_id]

    def _qid_numeric_id(self, qid: str) -> int:
        if not qid.startswith("Q"):
            raise ValueError(f"Expected QID, got {qid!r}")
        return int(qid[1:])

    def _pid_numeric_id(self, pid: str) -> int:
        if not pid.startswith("P"):
            raise ValueError(f"Expected PID, got {pid!r}")
        return int(pid[1:])

    def search_property_by_label(self, label: str) -> str | None:
        results = self._search_entities(label, "property")
        for result in results:
            if result.get("label", "").strip().casefold() == label.strip().casefold():
                return result["id"]
        if results:
            return results[0]["id"]
        return None

    def search_item_by_label(self, label: str) -> str | None:
        data = self._api_get(
            {
                "action": "wbsearchentities",
                "search": label,
                "language": self.language,
                "type": "item",
                "limit": 10,
            }
        )

        exact = []
        for row in data.get("search", []):
            returned_label = row.get("label")
            if returned_label == label:
                exact.append(row["id"])

        if len(exact) == 1:
            return exact[0]

        if len(exact) > 1:
            raise ValueError(
                f"Multiple exact item matches for label {label!r}: {exact}"
            )

        return None

    def find_property_by_external_iri(self, iri: str) -> str | None:
        return None

    def find_item_by_external_iri(self, iri: str) -> str | None:
        return None

    def create_property(
        self,
        label: str,
        datatype: str,
        description: str | None = None,
    ) -> str:
        inform(
            f"Creating property: label={label!r}, datatype={datatype!r}",
            self.verbose,
        )

        entity_data: dict[str, Any] = {
            "labels": {
                self.language: {
                    "language": self.language,
                    "value": label,
                }
            },
            "datatype": datatype,
        }

        if description:
            entity_data["descriptions"] = {
                self.language: {
                    "language": self.language,
                    "value": description,
                }
            }

        data = self._api_post(
            {
                "action": "wbeditentity",
                "new": "property",
                "data": json.dumps(entity_data, ensure_ascii=False),
            }
        )

        entity = data.get("entity", {})
        pid = entity.get("id")
        if not pid:
            raise RuntimeError(f"Property creation failed: {data}")

        self._property_datatypes_cache[pid] = datatype
        inform(f"Created property {pid} ({label})", self.verbose)
        return pid

    def create_item(
        self,
        label: str,
        description: str | None = None,
    ) -> str:
        entity_data: dict[str, Any] = {
            "labels": {
                self.language: {
                    "language": self.language,
                    "value": label,
                }
            }
        }

        if description:
            entity_data["descriptions"] = {
                self.language: {
                    "language": self.language,
                    "value": description,
                }
            }

        data = self._api_post(
            {
                "action": "wbeditentity",
                "new": "item",
                "data": json.dumps(entity_data, ensure_ascii=False),
            }
        )

        entity = data.get("entity", {})
        qid = entity.get("id")
        if not qid:
            raise RuntimeError(f"Item creation failed: {data}")

        inform(f"Created item {qid} ({label})", self.verbose)
        return qid

    def get_property_datatype(self, property_pid: str) -> str:
        if property_pid in self._property_datatypes_cache:
            return self._property_datatypes_cache[property_pid]

        entity = self._get_entity(property_pid)
        datatype = entity.get("datatype")
        if not datatype:
            raise RuntimeError(
                f"Could not read datatype for property {property_pid}: {entity}"
            )

        self._property_datatypes_cache[property_pid] = datatype
        return datatype

    def add_claim(self, subject_qid: str, property_pid: str, value) -> str:
        claim_data = self._build_claim_value(property_pid, value)

        data = self._api_post(
            {
                "action": "wbcreateclaim",
                "entity": subject_qid,
                "property": property_pid,
                "snaktype": "value",
                "value": json.dumps(claim_data, ensure_ascii=False),
            }
        )

        claim = data.get("claim", {})
        claim_id = claim.get("id")
        if not claim_id:
            raise RuntimeError(f"Claim creation failed: {data}")

        inform(
            f"Added claim on {subject_qid} with {property_pid} -> {value!r}",
            self.verbose,
        )
        return claim_id

    def add_qualifier(self, statement_guid: str, property_pid: str, value) -> None:
        qualifier_value = self._build_claim_value(property_pid, value)

        data = self._api_post(
            {
                "action": "wbsetqualifier",
                "claim": statement_guid,
                "property": property_pid,
                "snaktype": "value",
                "value": json.dumps(qualifier_value, ensure_ascii=False),
            }
        )

        if "pageinfo" not in data and "claim" not in data and "success" not in data:
            raise RuntimeError(f"Qualifier insertion may have failed: {data}")

        inform(
            f"Added qualifier {property_pid} -> {value!r} on {statement_guid}",
            self.verbose,
        )

    def add_reference(
        self, statement_guid: str, reference_snaks: list[tuple[str, object]]
    ) -> None:
        snaks: dict[str, list[dict[str, Any]]] = {}

        for property_pid, value in reference_snaks:
            datavalue = self._build_claim_value(property_pid, value)
            datatype = self.get_property_datatype(property_pid)

            snak = {
                "snaktype": "value",
                "property": property_pid,
                "datatype": datatype,
                "datavalue": datavalue,
            }
            snaks.setdefault(property_pid, []).append(snak)

        data = self._api_post(
            {
                "action": "wbsetreference",
                "statement": statement_guid,
                "snaks": json.dumps(snaks, ensure_ascii=False),
            }
        )

        if "pageinfo" not in data and "reference" not in data and "success" not in data:
            raise RuntimeError(f"Reference insertion may have failed: {data}")

        inform(
            f"Added reference on {statement_guid}",
            self.verbose,
        )

    def _build_claim_value(self, property_pid: str, value) -> dict[str, Any]:
        datatype = self.get_property_datatype(property_pid)

        if datatype == "wikibase-item":
            return self._build_wikibase_item_value(value)

        if datatype in {"string", "external-id", "url"}:
            return self._build_string_like_value(value)

        if datatype == "monolingualtext":
            return self._build_monolingualtext_value(value)

        if datatype == "quantity":
            return self._build_quantity_value(value)

        if datatype == "time":
            return self._build_time_value(value)

        raise NotImplementedError(
            f"Datatype {datatype!r} is not implemented yet for property {property_pid}."
        )

    def _build_wikibase_item_value(self, value) -> dict[str, Any]:
        if isinstance(value, URIRef):
            value = str(value)

        if not isinstance(value, str) or not value.startswith("Q"):
            raise ValueError(f"Expected a QID for wikibase-item value, got {value!r}")

        return {
            "entity-type": "item",
            "numeric-id": self._qid_numeric_id(value),
            "id": value,
        }

    def _build_string_like_value(self, value) -> str:
        if isinstance(value, Literal):
            return str(value)
        if isinstance(value, URIRef):
            return str(value)
        return str(value)

    def _build_monolingualtext_value(self, value) -> dict[str, Any]:
        if not isinstance(value, Literal):
            raise ValueError(
                "Expected rdflib Literal for monolingualtext, "
                f"got {type(value).__name__}: {value!r}"
            )

        language = value.language or self.language
        return {
            "text": str(value),
            "language": language,
        }

    def _build_quantity_value(self, value) -> dict[str, Any]:
        if isinstance(value, Literal):
            lexical = str(value)
        else:
            lexical = str(value)

        if lexical.startswith(("+", "-")):
            amount = lexical
        else:
            amount = f"+{lexical}"

        return {
            "amount": amount,
            "unit": "1",
        }

    def _build_time_value(self, value) -> dict[str, Any]:
        if isinstance(value, Literal):
            lexical = str(value)
        else:
            lexical = str(value)

        time_string, precision = self._normalize_time_lexical(lexical)

        return {
            "time": time_string,
            "timezone": 0,
            "before": 0,
            "after": 0,
            "precision": precision,
            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
        }

    def _normalize_time_lexical(self, lexical: str) -> tuple[str, int]:
        text = lexical.strip()

        if len(text) == 4 and text.isdigit():
            return f"+{text}-01-01T00:00:00Z", 9

        if len(text) == 7 and text[4] == "-":
            return f"+{text}-01T00:00:00Z", 10

        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            return f"+{text}T00:00:00Z", 11

        if "T" in text:
            normalized = text
            if normalized.endswith("Z"):
                pass
            elif normalized.endswith("+00:00"):
                normalized = normalized[:-6] + "Z"
            else:
                # keep simple first version
                if not normalized.endswith("Z"):
                    normalized = normalized + "Z"

            if not normalized.startswith(("+", "-")):
                normalized = "+" + normalized

            return normalized, 14

        raise ValueError(f"Unsupported time literal lexical form: {lexical!r}")

    def delete(self, entity_id: str) -> dict:
        if entity_id.startswith("Q"):
            title = f"Item:{entity_id}"
        elif entity_id.startswith("P"):
            title = f"Property:{entity_id}"
        else:
            raise ValueError("entity_id must start with 'Q' or 'P' (e.g., Q42, P17).")

        r = self.session.post(
            self.api_url,
            data={
                "action": "delete",
                "title": title,
                "token": self.csrf_token,
                "format": "json",
            },
            timeout=30,
            verify=self.verify,
        )
        r.raise_for_status()
        return r.json()

    def delete_items_range(
        self,
        start: int,
        end: int,
    ) -> tuple[list[str], dict[str, str]]:
        deleted: list[str] = []
        failed: dict[str, str] = {}

        for i in range(start, end + 1):
            qid = f"Q{i}"
            try:
                self.delete(qid)
                deleted.append(qid)
                inform(f"Deleted {qid}", self.verbose)
            except Exception as err:
                failed[qid] = str(err)
                inform(f"Failed to delete {qid}: {err}", self.verbose)

        inform(
            f"Deletion finished: {len(deleted)} deleted, {len(failed)} failed.",
            self.verbose,
        )
        return deleted, failed
