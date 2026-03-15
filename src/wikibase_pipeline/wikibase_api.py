import os

import requests
from dotenv import load_dotenv
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
