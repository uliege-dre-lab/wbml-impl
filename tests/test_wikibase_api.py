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


class MockSession:
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

        token_type = params["type"]
        return MockResponse(
            {"query": {"tokens": {f"{token_type}token": f"{token_type}_TOKEN"}}}
        )

    def post(self, url, data=None, timeout=None, verify=None):
        self.post_calls.append(
            {
                "url": url,
                "data": data,
                "timeout": timeout,
                "verify": verify,
            }
        )

        return MockResponse({"login": {"result": "Success"}})


class MockSessionLoginFail(MockSession):
    def post(self, url, data=None, timeout=None, verify=None):
        self.post_calls.append(
            {
                "url": url,
                "data": data,
                "timeout": timeout,
                "verify": verify,
            }
        )
        return MockResponse({"login": {"result": "Failed"}})


def test_wikibase_api_init_success(monkeypatch, params):
    mock_session = MockSession()

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

    assert api.api_url == params["api_url"]
    assert api.sparql_endpoint == params["sparql_endpoint"]
    assert api.language == "en"
    assert api.verify is True
    assert api.verbose == 1
    assert api.user == "alice"
    assert api.password == "secret"
    assert api.csrf_token == "csrf_TOKEN"

    assert len(mock_session.get_calls) == 2
    assert mock_session.get_calls[0]["params"]["type"] == "login"
    assert mock_session.get_calls[1]["params"]["type"] == "csrf"

    assert len(mock_session.post_calls) == 1
    assert mock_session.post_calls[0]["data"]["action"] == "login"
    assert mock_session.post_calls[0]["data"]["lgname"] == "alice"
    assert mock_session.post_calls[0]["data"]["lgpassword"] == "secret"


def test_wikibase_api_missing_env(monkeypatch, params):
    monkeypatch.setattr("wikibase_pipeline.wikibase_api.load_dotenv", lambda: None)
    monkeypatch.setattr("wikibase_pipeline.wikibase_api.os.getenv", lambda key: None)

    with pytest.raises(OSError, match="Wikibase credentials not found"):
        WikibaseAPI(params)


def test_wikibase_api_login_failure(monkeypatch, params):
    mock_session = MockSessionLoginFail()

    monkeypatch.setattr("wikibase_pipeline.wikibase_api.load_dotenv", lambda: None)
    monkeypatch.setattr(
        "wikibase_pipeline.wikibase_api.os.getenv",
        lambda key: {"WB_USER": "alice", "WB_PASSWORD": "secret"}.get(key),
    )
    monkeypatch.setattr(
        "wikibase_pipeline.wikibase_api.requests.Session",
        lambda: mock_session,
    )

    with pytest.raises(RuntimeError, match="Login failed"):
        WikibaseAPI(params)
