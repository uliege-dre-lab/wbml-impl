import json

import pytest

from wikibase_pipeline.wikibase_api import WikibaseAPI


@pytest.fixture
def params():
    return {
        "api_url": "https://example.org/w/api.php",
        "sparql_endpoint": "https://example.org/query/sparql",
        "language": "en",
        "tls_verify": True,
        "verbose": 1,
    }


class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP error {self.status_code}")


class MockSessionAPI:
    def __init__(self):
        self.get_calls = []
        self.post_calls = []

    def get(self, url, params=None, timeout=None, verify=None):
        self.get_calls.append(
            {
                "url": url,
                "params": params,
                "timeout": timeout,
                "verify": verify,
            }
        )

        action = params.get("action")

        if action == "query" and params.get("meta") == "tokens":
            token_type = params["type"]
            return MockResponse(
                {"query": {"tokens": {f"{token_type}token": f"{token_type}_TOKEN"}}}
            )

        if action == "wbsearchentities":
            entity_type = params["type"]
            search = params["search"]

            if entity_type == "item" and search == "Pikachu":
                return MockResponse(
                    {
                        "search": [
                            {"id": "Q25", "label": "Pikachu"},
                            {"id": "Q999", "label": "Pikachu Variant"},
                        ]
                    }
                )

            if entity_type == "property" and search == "instance of":
                return MockResponse(
                    {
                        "search": [
                            {"id": "P31", "label": "instance of"},
                        ]
                    }
                )

            if entity_type == "item" and search == "Missing":
                return MockResponse({"search": []})

            return MockResponse({"search": []})

        if action == "wbgetentities":
            ids = params["ids"]

            if ids == "P31":
                return MockResponse(
                    {
                        "entities": {
                            "P31": {
                                "id": "P31",
                                "datatype": "wikibase-item",
                            }
                        }
                    }
                )

            if ids == "P999":
                return MockResponse(
                    {
                        "entities": {
                            "P999": {
                                "id": "P999",
                                "datatype": "string",
                            }
                        }
                    }
                )

            return MockResponse({"entities": {}})

        return MockResponse({})

    def post(self, url, data=None, timeout=None, verify=None):
        self.post_calls.append(
            {
                "url": url,
                "data": data,
                "timeout": timeout,
                "verify": verify,
            }
        )

        action = data.get("action")

        if action == "login":
            return MockResponse({"login": {"result": "Success"}})

        if action == "wbeditentity" and data.get("new") == "item":
            return MockResponse(
                {
                    "entity": {
                        "id": "Q100",
                    }
                }
            )

        if action == "wbeditentity" and data.get("new") == "property":
            return MockResponse(
                {
                    "entity": {
                        "id": "P100",
                    }
                }
            )

        if action == "wbcreateclaim":
            return MockResponse(
                {
                    "claim": {
                        "id": "Q25$ABC-123",
                    }
                }
            )

        if action == "wbsetqualifier":
            return MockResponse({"success": 1})

        if action == "wbsetreference":
            return MockResponse({"success": 1})

        return MockResponse({})


@pytest.fixture
def api(monkeypatch, params):
    mock_session = MockSessionAPI()

    monkeypatch.setattr("wikibase_pipeline.wikibase_api.load_dotenv", lambda: None)
    monkeypatch.setattr(
        "wikibase_pipeline.wikibase_api.os.getenv",
        lambda key: {"WB_USER": "alice", "WB_PASSWORD": "secret"}.get(key),
    )
    monkeypatch.setattr(
        "wikibase_pipeline.wikibase_api.requests.Session",
        lambda: mock_session,
    )

    api = WikibaseAPI(params)
    return api, mock_session


def test_search_item_by_label_exact_match(api):
    wikibase_api, _ = api

    result = wikibase_api.search_item_by_label("Pikachu")

    assert result == "Q25"


def test_search_item_by_label_missing(api):
    wikibase_api, _ = api

    result = wikibase_api.search_item_by_label("Missing")

    assert result is None


def test_search_property_by_label(api):
    wikibase_api, _ = api

    result = wikibase_api.search_property_by_label("instance of")

    assert result == "P31"


def test_get_property_datatype(api):
    wikibase_api, _ = api

    datatype = wikibase_api.get_property_datatype("P31")

    assert datatype == "wikibase-item"


def test_get_property_datatype_uses_cache(api):
    wikibase_api, mock_session = api

    datatype1 = wikibase_api.get_property_datatype("P31")
    datatype2 = wikibase_api.get_property_datatype("P31")

    assert datatype1 == "wikibase-item"
    assert datatype2 == "wikibase-item"

    wbgetentities_calls = [
        call
        for call in mock_session.get_calls
        if call["params"].get("action") == "wbgetentities"
    ]
    assert len(wbgetentities_calls) == 1


def test_create_item(api):
    wikibase_api, mock_session = api

    qid = wikibase_api.create_item(
        label="Pikachu",
        description="Mouse Pokémon",
    )

    assert qid == "Q100"

    last_post = mock_session.post_calls[-1]
    assert last_post["data"]["action"] == "wbeditentity"
    assert last_post["data"]["new"] == "item"

    entity_data = json.loads(last_post["data"]["data"])
    assert entity_data["labels"]["en"]["value"] == "Pikachu"
    assert entity_data["descriptions"]["en"]["value"] == "Mouse Pokémon"


def test_create_property(api):
    wikibase_api, mock_session = api

    pid = wikibase_api.create_property(
        label="Pokédex entry",
        datatype="string",
        description="Pokémon encyclopedia description",
    )

    assert pid == "P100"
    assert wikibase_api._property_datatypes_cache["P100"] == "string"

    last_post = mock_session.post_calls[-1]
    assert last_post["data"]["action"] == "wbeditentity"
    assert last_post["data"]["new"] == "property"
    assert last_post["data"]["datatype"] == "string"

    entity_data = json.loads(last_post["data"]["data"])
    assert entity_data["labels"]["en"]["value"] == "Pokédex entry"
    assert (
        entity_data["descriptions"]["en"]["value"] == "Pokémon encyclopedia description"
    )


def test_add_claim(api):
    wikibase_api, mock_session = api
    wikibase_api._property_datatypes_cache["P31"] = "wikibase-item"

    claim_id = wikibase_api.add_claim(
        subject_qid="Q25",
        property_pid="P31",
        value="Q5",
    )

    assert claim_id == "Q25$ABC-123"

    last_post = mock_session.post_calls[-1]
    assert last_post["data"]["action"] == "wbcreateclaim"
    assert last_post["data"]["entity"] == "Q25"
    assert last_post["data"]["property"] == "P31"

    value = json.loads(last_post["data"]["value"])
    assert value["entity-type"] == "item"
    assert value["id"] == "Q5"
    assert value["numeric-id"] == 5


def test_add_qualifier(api):
    wikibase_api, mock_session = api
    wikibase_api._property_datatypes_cache["P999"] = "string"

    wikibase_api.add_qualifier(
        statement_guid="Q25$ABC-123",
        property_pid="P999",
        value="special condition",
    )

    last_post = mock_session.post_calls[-1]
    assert last_post["data"]["action"] == "wbsetqualifier"
    assert last_post["data"]["claim"] == "Q25$ABC-123"
    assert last_post["data"]["property"] == "P999"

    value = json.loads(last_post["data"]["value"])
    assert value == "special condition"


def test_add_reference(api):
    wikibase_api, mock_session = api
    wikibase_api._property_datatypes_cache["P999"] = "string"

    wikibase_api.add_reference(
        statement_guid="Q25$ABC-123",
        reference_snaks=[("P999", "Bulbapedia")],
    )

    last_post = mock_session.post_calls[-1]
    assert last_post["data"]["action"] == "wbsetreference"
    assert last_post["data"]["statement"] == "Q25$ABC-123"

    snaks = json.loads(last_post["data"]["snaks"])
    assert "P999" in snaks
    assert snaks["P999"][0]["property"] == "P999"
    assert snaks["P999"][0]["datatype"] == "string"
    assert snaks["P999"][0]["datavalue"] == "Bulbapedia"
