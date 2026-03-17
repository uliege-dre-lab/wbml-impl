from wikibase_pipeline.lookup_io import load_lookup, save_lookup


def test_load_lookup_file_missing(tmp_path):
    path = tmp_path / "lookup.json"

    data = load_lookup(path)

    assert data == {
        "builtins": {},
        "items": {},
        "properties": {},
        "statements": {},
    }


def test_load_lookup_existing(tmp_path):
    path = tmp_path / "lookup.json"

    path.write_text(
        """
        {
          "builtins": {"rdf:type": "P1"},
          "items": {"Pokemon": "Q1"},
          "properties": {},
          "statements": {}
        }
        """,
        encoding="utf-8",
    )

    data = load_lookup(path)

    assert data["builtins"]["rdf:type"] == "P1"
    assert data["items"]["Pokemon"] == "Q1"


def test_load_lookup_adds_missing_sections(tmp_path):
    path = tmp_path / "lookup.json"

    path.write_text(
        """
        {
          "items": {"Pokemon": "Q1"}
        }
        """,
        encoding="utf-8",
    )

    data = load_lookup(path)

    assert "builtins" in data
    assert "properties" in data
    assert "statements" in data
    assert data["items"]["Pokemon"] == "Q1"


def test_save_and_load_lookup(tmp_path):
    path = tmp_path / "lookup.json"

    lookup = {
        "builtins": {"rdf:type": "P1"},
        "items": {"Pikachu": "Q25"},
        "properties": {"height": "P2"},
        "statements": {},
    }

    save_lookup(path, lookup)

    loaded = load_lookup(path)

    assert loaded == lookup
