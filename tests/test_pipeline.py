# tests/test_update.py

from pathlib import Path

from wikibase_pipeline.pipeline import update


class FakeGraph:
    def __init__(self):
        self.parse_calls = []

    def parse(self, path, format=None):
        self.parse_calls.append((Path(path), format))


class FakeWikibaseAPI:
    def __init__(self, config):
        self.config = config


def test_update_orchestrates_pipeline(monkeypatch, tmp_path):
    pipeline_ini = tmp_path / "pipeline.ini"
    config_ini = tmp_path / "config.ini"
    output_nt = tmp_path / "output.nt"
    lookup_file = tmp_path / "lookup.json"

    pipeline = {
        "wikibase": {
            "verbose": 2,
            "language": "en",
            "lookup_file": str(lookup_file),
        },
        "urn": {
            "item": "urn:wikibase:Q:",
            "property": "urn:wikibase:P:",
            "qualifier": "urn:wikibase:QP:",
            "reference": "urn:wikibase:RP:",
            "statement": "urn:wikibase:S:",
        },
    }

    lookup = {"items": {}, "properties": {}, "builtins": {}}
    metadata = {"urn:wikibase:Q:1": {"labels": {"en": "Item 1"}}}
    structures = {
        "direct_claims": [],
        "statement_links": [],
        "statement_values": [],
        "qualifiers": [],
        "references": [],
    }

    calls = []
    fake_graph = FakeGraph()

    def fake_load_pipeline_ini(path):
        calls.append(("load_pipeline_ini", Path(path)))
        return pipeline

    def fake_load_config_ini(path, verbose):
        calls.append(("load_config_ini", Path(path), verbose))
        return str(output_nt)

    def fake_rml_execute(config_path, output_value, verbose):
        calls.append(("rml_execute", Path(config_path), output_value, verbose))

    def fake_load_lookup(path, verbose):
        calls.append(("load_lookup", path, verbose))
        return lookup

    def fake_collect_metadata(g, language, verbose):
        calls.append(("collect_metadata", g, language, verbose))
        return metadata

    def fake_search_builtins_properties(g, lookup_arg, wb_api, verbose):
        calls.append(("search_builtins_properties", g, lookup_arg, wb_api, verbose))

    def fake_resolve_properties(g, lookup_arg, wb_api, prefixes, verbose):
        calls.append(("resolve_properties", g, lookup_arg, wb_api, prefixes, verbose))

    def fake_resolve_items(g, lookup_arg, metadata_arg, wb_api, prefixes, verbose):
        calls.append(
            ("resolve_items", g, lookup_arg, metadata_arg, wb_api, prefixes, verbose)
        )

    def fake_extract_structures(g, prefixes, verbose):
        calls.append(("extract_structures", g, prefixes, verbose))
        return structures

    def fake_validate_structures(structures_arg, lookup_arg, wb_api, prefixes, verbose):
        calls.append(
            (
                "validate_structures",
                structures_arg,
                lookup_arg,
                wb_api,
                prefixes,
                verbose,
            )
        )

    def fake_write_structures(structures_arg, lookup_arg, wb_api, verbose):
        calls.append(("write_structures", structures_arg, lookup_arg, wb_api, verbose))

    def fake_save_lookup(path, lookup_arg, verbose):
        calls.append(("save_lookup", path, lookup_arg, verbose))

    monkeypatch.setattr(
        "wikibase_pipeline.pipeline.load_pipeline_ini", fake_load_pipeline_ini
    )
    monkeypatch.setattr(
        "wikibase_pipeline.pipeline.load_config_ini", fake_load_config_ini
    )
    monkeypatch.setattr("wikibase_pipeline.pipeline.rml_execute", fake_rml_execute)
    monkeypatch.setattr("wikibase_pipeline.pipeline.WikibaseAPI", FakeWikibaseAPI)
    monkeypatch.setattr("wikibase_pipeline.pipeline.load_lookup", fake_load_lookup)
    monkeypatch.setattr("wikibase_pipeline.pipeline.Graph", lambda: fake_graph)
    monkeypatch.setattr(
        "wikibase_pipeline.pipeline.collect_metadata", fake_collect_metadata
    )
    monkeypatch.setattr(
        "wikibase_pipeline.pipeline.search_builtins_properties",
        fake_search_builtins_properties,
    )
    monkeypatch.setattr(
        "wikibase_pipeline.pipeline.resolve_properties", fake_resolve_properties
    )
    monkeypatch.setattr("wikibase_pipeline.pipeline.resolve_items", fake_resolve_items)
    monkeypatch.setattr(
        "wikibase_pipeline.pipeline.extract_structures", fake_extract_structures
    )
    monkeypatch.setattr(
        "wikibase_pipeline.pipeline.validate_structures", fake_validate_structures
    )
    monkeypatch.setattr(
        "wikibase_pipeline.pipeline.write_structures", fake_write_structures
    )
    monkeypatch.setattr("wikibase_pipeline.pipeline.save_lookup", fake_save_lookup)

    update(pipeline_ini, config_ini)

    assert ("load_pipeline_ini", pipeline_ini) in calls
    assert ("load_config_ini", config_ini, 2) in calls
    assert ("rml_execute", config_ini, str(output_nt), 2) in calls
    assert ("load_lookup", str(lookup_file), 2) in calls

    assert fake_graph.parse_calls == [(output_nt, "nt")]

    collect_call = next(call for call in calls if call[0] == "collect_metadata")
    assert collect_call[2] == "en"
    assert collect_call[3] == 2

    search_builtins_call = next(
        call for call in calls if call[0] == "search_builtins_properties"
    )
    assert search_builtins_call[1] is fake_graph
    assert search_builtins_call[2] is lookup
    assert isinstance(search_builtins_call[3], FakeWikibaseAPI)
    assert search_builtins_call[4] == 2

    resolve_properties_call = next(
        call for call in calls if call[0] == "resolve_properties"
    )
    assert resolve_properties_call[1] is fake_graph
    assert resolve_properties_call[2] is lookup
    assert isinstance(resolve_properties_call[3], FakeWikibaseAPI)
    assert resolve_properties_call[4] == pipeline["urn"]
    assert resolve_properties_call[5] == 2

    resolve_items_call = next(call for call in calls if call[0] == "resolve_items")
    assert resolve_items_call[1] is fake_graph
    assert resolve_items_call[2] is lookup
    assert resolve_items_call[3] is metadata
    assert isinstance(resolve_items_call[4], FakeWikibaseAPI)
    assert resolve_items_call[5] == pipeline["urn"]
    assert resolve_items_call[6] == 2

    extract_call = next(call for call in calls if call[0] == "extract_structures")
    assert extract_call[1] is fake_graph
    assert extract_call[2] == pipeline["urn"]
    assert extract_call[3] == 2

    validate_call = next(call for call in calls if call[0] == "validate_structures")
    assert validate_call[1] is structures
    assert validate_call[2] is lookup
    assert isinstance(validate_call[3], FakeWikibaseAPI)
    assert validate_call[4] == pipeline["urn"]
    assert validate_call[5] == 2

    write_call = next(call for call in calls if call[0] == "write_structures")
    assert write_call[1] is structures
    assert write_call[2] is lookup
    assert isinstance(write_call[3], FakeWikibaseAPI)
    assert write_call[4] == 2

    save_call = next(call for call in calls if call[0] == "save_lookup")
    assert save_call == ("save_lookup", str(lookup_file), lookup, 2)
