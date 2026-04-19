from collections import defaultdict

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

from ..utils.properties_utils import lookup_get, search_wikibase_properties
from ..utils.verbose_utils import inform, warn
from .language_resolver import LanguageResolver

WBML = Namespace("https://example.org/wbml#")
PROPERTY_PREFIX = "urn:wikibase:property:"

# Maps wbml: local names (used in .ttl files) → Wikibase API datatype strings
WBML_DATATYPE_MAP: dict[str, str] = {
    "item": "wikibase-item",
    "string": "string",
    "url": "url",
    "externalId": "external-id",
    "quantity": "quantity",
    "time": "time",
    "monolingualText": "monolingualtext",
}


def validate_schema_properties(g: Graph) -> None:
    """
    Validate that every rdf:Property has exactly one wbml:propertyType.
    """
    errors: list[str] = []

    for prop_iri in sorted(g.subjects(RDF.type, RDF.Property)):
        iri_str = str(prop_iri)
        types = list(g.objects(prop_iri, WBML.propertyType))

        if not types:
            errors.append(
                f"  <{iri_str}>: missing wbml:propertyType. "
                f"Add e.g. `wbml:propertyType wbml:string`. "
                f"Supported types: {sorted(WBML_DATATYPE_MAP)}"
            )
        elif len(types) > 1:
            type_strs = sorted(str(t) for t in types)
            errors.append(
                f"  <{iri_str}>: conflicting wbml:propertyType values: {type_strs}."
            )

    if errors:
        raise ValueError("Schema property validation failed:\n" + "\n".join(errors))


def _wb_datatype_from_graph(g: Graph, prop_iri: URIRef) -> str:
    prop_type_uri = str(next(g.objects(prop_iri, WBML.propertyType)))
    wbml_ns = str(WBML)

    if not prop_type_uri.startswith(wbml_ns):
        raise ValueError(
            f"Invalid wbml:propertyType <{prop_type_uri}> for <{prop_iri}>. "
            f"Types must use the wbml: namespace. "
            f"Supported: {sorted(WBML_DATATYPE_MAP)}"
        )

    local_name = prop_type_uri[len(wbml_ns) :]
    if local_name not in WBML_DATATYPE_MAP:
        raise ValueError(
            f"Unsupported wbml:propertyType wbml:{local_name} for <{prop_iri}>. "
            f"Supported: {sorted(WBML_DATATYPE_MAP)}"
        )

    return WBML_DATATYPE_MAP[local_name]  # returns the Wikibase API string


def _collect_property_metadata(
    g: Graph,
    prop_iri: URIRef,
    language_resolver: LanguageResolver,
    verbose: int,
) -> dict:
    labels: dict[str, str] = {}
    aliases: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, str] = {}
    iri_str = str(prop_iri)

    # Labels — collect in one pass, then process tagged before untagged
    tagged: list[tuple[str, str]] = []
    untagged: list[str] = []
    for lbl in g.objects(prop_iri, RDFS.label):
        raw_value = str(lbl).strip()
        if not raw_value:
            continue
        raw_lang = getattr(lbl, "language", None)
        if raw_lang is None:
            untagged.append(raw_value)
        else:
            tagged.append((raw_lang, raw_value))

    for raw_lang, raw_value in tagged:
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"property label {raw_value!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_lang in labels:
            if raw_value not in aliases[eff_lang]:
                warn(
                    f"  Duplicate property label @{eff_lang} on <{iri_str}>: "
                    f"keeping '{labels[eff_lang]}', adding '{raw_value}' as alias.",
                    verbose,
                )
                aliases[eff_lang].append(raw_value)
        else:
            labels[eff_lang] = raw_value

    for raw_value in untagged:
        eff_lang = language_resolver.resolve_language(
            None,
            context=f"property label {raw_value!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_lang in labels:
            if raw_value.strip() == labels[eff_lang].strip():
                pass  # identical string, silently skip
            elif raw_value not in aliases[eff_lang]:
                warn(
                    f"  Untagged property label on <{iri_str}> resolved to @{eff_lang} "
                    f"which already has a label: adding '{raw_value}' as alias.",
                    verbose,
                )
                aliases[eff_lang].append(raw_value)
        else:
            labels[eff_lang] = raw_value

    # Fallback if still no labels: promote an alias (default lang first),
    # else IRI suffix
    if not labels:
        fallback_lang = language_resolver.language
        promoted = False
        for lang in [fallback_lang] + [
            alias for alias in aliases if alias != fallback_lang
        ]:
            if aliases.get(lang):
                value = aliases[lang].pop(0)
                if not aliases[lang]:
                    del aliases[lang]
                labels[lang] = value
                warn(
                    f"  No valid labels for <{iri_str}> — "
                    f"promoting alias '{value}'@{lang} as label.",
                    verbose,
                )
                promoted = True
                break
        if not promoted:
            suffix = (
                iri_str[len(PROPERTY_PREFIX) :]
                if iri_str.startswith(PROPERTY_PREFIX)
                else iri_str
            )
            warn(
                f"  No valid labels for <{iri_str}> — "
                f"using IRI suffix fallback '{suffix}'.",
                verbose,
            )
            labels[fallback_lang] = suffix

    # Aliases
    for alias in g.objects(prop_iri, SKOS.altLabel):
        raw_value = str(alias).strip()
        if not raw_value:
            continue
        raw_lang = getattr(alias, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"property alias {str(alias)!r} on <{iri_str}>",
            verbose=verbose,
        )
        if raw_value not in aliases[eff_lang]:
            aliases[eff_lang].append(raw_value)

    # Descriptions
    for desc in g.objects(prop_iri, RDFS.comment):
        raw_value = str(desc).strip()
        if not raw_value:
            continue
        raw_lang = getattr(desc, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"property description {str(desc)!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_lang in descriptions:
            warn(
                f"  Duplicate property description @{eff_lang} on <{iri_str}>: "
                f"keeping existing, ignoring '{raw_value}'.",
                verbose,
            )
        else:
            descriptions[eff_lang] = raw_value

    return {
        "labels": labels,
        "aliases": dict(aliases),
        "descriptions": descriptions,
    }


def _resolve_one_property(
    prop_iri: URIRef,
    meta: dict,
    schema_graph: Graph,
    wikibase_api,
    default_language: str,
    verbose: int,
) -> tuple[str, str]:
    """
    Find or create a Wikibase property for the given schema property IRI.
    Search is ordered by label priority and filtered by datatype.
    Falls back to the IRI suffix as label if no labels are defined.
    Returns (pid, datatype).
    """
    iri_str = str(prop_iri)
    wb_datatype = _wb_datatype_from_graph(schema_graph, prop_iri)
    labels = meta["labels"]

    inform(
        f"Resolving property <{iri_str}> (datatype='{wb_datatype}') …",
        verbose,
    )

    pid = search_wikibase_properties(
        wikibase_api,
        labels=labels,
        default_language=default_language,
        expected_datatype=wb_datatype,
        aliases=meta["aliases"],
    )

    if pid is not None:
        inform(f"  Found {pid} for <{iri_str}>", verbose)
        return pid, wb_datatype

    inform(f"  Not found — creating new property for <{iri_str}>", verbose)
    pid = wikibase_api.create_property(
        labels=labels,
        datatype=wb_datatype,
        descriptions=meta["descriptions"],
        aliases=meta["aliases"],
    )
    inform(f"  Created {pid} for <{iri_str}>", verbose)
    return pid, wb_datatype


def _push_property_metadata(
    pid: str,
    meta: dict,
    wikibase_api,
    verbose: int,
    overwrite_on_conflict: bool = False,
) -> None:
    """
    Push a labels/aliases/descriptions diff to an existing Wikibase property.
    - New values are added.
    - Conflicts: warn + skip (or overwrite if overwrite_on_conflict=True).
    - Aliases: union only, never remove existing ones.
    - Empty language keys (untagged RDF literals) are skipped.
    """
    try:
        entity = wikibase_api.get_entity(pid, props="labels|descriptions|aliases")
    except Exception as exc:
        warn(f"  Could not fetch entity {pid} to diff metadata: {exc}", verbose)
        return

    existing_labels: dict[str, str] = {
        lang: info["value"] for lang, info in entity.get("labels", {}).items()
    }
    existing_descriptions: dict[str, str] = {
        lang: info["value"] for lang, info in entity.get("descriptions", {}).items()
    }
    existing_aliases: dict[str, set[str]] = {
        lang: {entry["value"] for entry in entries}
        for lang, entries in entity.get("aliases", {}).items()
    }

    entity_data: dict = {}

    # Labels
    labels_to_set = {}
    aliases_to_set = {}
    for lang, value in meta["labels"].items():
        if not lang:
            continue
        value = value.strip()  # ← add this
        current = existing_labels.get(lang)
        if current is None:
            labels_to_set[lang] = {"language": lang, "value": value}
        elif current.strip() == value:  # ← strip both sides
            pass
        else:
            if overwrite_on_conflict:
                inform(
                    f"  [{pid}] Overwriting label@{lang}: '{current}' to '{value}'",
                    verbose,
                )
                labels_to_set[lang] = {"language": lang, "value": value}
            else:
                warn(
                    f"  [{pid}] Label conflict @{lang}: "
                    f"data='{value}', Wikibase='{current}': adding '{value}' as alias.",
                    verbose,
                )
                already_there = existing_aliases.get(lang, set())
                if value not in already_there:
                    aliases_to_set.setdefault(lang, []).append(
                        {"language": lang, "value": value}
                    )
    if labels_to_set:
        entity_data["labels"] = labels_to_set

    # Descriptions
    descriptions_to_set = {}
    for lang, value in meta["descriptions"].items():
        if not lang:
            continue
        value = value.strip()  # ← add this
        current = existing_descriptions.get(lang)
        if current is None:
            descriptions_to_set[lang] = {"language": lang, "value": value}
        elif current.strip() == value:  # ← strip both sides
            pass
        else:
            if overwrite_on_conflict:
                inform(
                    f"  [{pid}] Overwriting description@{lang}:"
                    f" '{current}' to '{value}'",
                    verbose,
                )
                descriptions_to_set[lang] = {"language": lang, "value": value}
            else:
                warn(
                    f"  [{pid}] Description conflict @{lang}: "
                    f"schema='{value}', Wikibase='{current}': keeping Wikibase.",
                    verbose,
                )
    if descriptions_to_set:
        entity_data["descriptions"] = descriptions_to_set

    # Aliases — union only, skip values already present as alias or as label
    for lang, values in meta["aliases"].items():
        if not lang:
            continue
        already_as_alias = existing_aliases.get(lang, set())
        existing_label = existing_labels.get(lang, "")
        new_values = [
            v
            for v in values
            if v not in already_as_alias and v.strip() != existing_label.strip()
        ]
        if new_values:
            aliases_to_set[lang] = [{"language": lang, "value": v} for v in new_values]
    if aliases_to_set:
        entity_data["aliases"] = aliases_to_set

    if not entity_data:
        return

    inform(f"  [{pid}] Pushing metadata diff: {list(entity_data.keys())} …", verbose)
    wikibase_api.edit_entity(pid, entity_data)


def resolve_schema_properties(
    schema_graph: Graph,
    lookup: dict,
    wikibase_api,
    language_resolver: LanguageResolver,
    verbose: int = 1,
) -> None:
    """
    Main entry point for property resolution.

    For each rdf:Property in the schema:
    1. Validate it has exactly one wbml:propertyType.
    2. Check lookup — correct datatype to use it; wrong datatype to raise.
    3. Search Wikibase by label (ordered) + datatype filter.
    4. If not found, create it.
    5. Push metadata diff (labels, descriptions, aliases).
    """
    validate_schema_properties(schema_graph)
    lookup.setdefault("properties", {})

    for prop_iri in sorted(schema_graph.subjects(RDF.type, RDF.Property)):
        iri_str = str(prop_iri)
        wb_datatype = _wb_datatype_from_graph(schema_graph, prop_iri)

        meta = _collect_property_metadata(
            schema_graph, prop_iri, language_resolver, verbose=verbose
        )

        pid = lookup_get(lookup, iri_str, wb_datatype, wikibase_api)

        if pid is not None:
            inform(
                f"Resolved property <{iri_str}> from lookup ->"
                f" {pid} (datatype='{wb_datatype}')",
                verbose,
            )
        else:
            pid, wb_datatype = _resolve_one_property(
                prop_iri,
                meta,
                schema_graph,
                wikibase_api,
                language_resolver.language,
                verbose,
            )
            lookup["properties"][iri_str] = {"id": pid, "datatype": wb_datatype}

        _push_property_metadata(pid, meta, wikibase_api, verbose)
