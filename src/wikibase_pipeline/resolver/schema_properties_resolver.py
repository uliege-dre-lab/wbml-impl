from collections import defaultdict

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

from ..utils.items_utils import clean_text
from ..utils.properties_utils import lookup_get, search_wikibase_properties
from ..utils.verbose_utils import inform, warn
from .language_resolver import LanguageResolver

WBML = Namespace("https://example.org/wbml#")
PROPERTY_PREFIX = "urn:wikibase:property:"
PROPERTY_IRI_PREFIX = "urn:wikibase:propertyIRI:"

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
    require_label: bool = True,
) -> dict:
    labels: dict[str, str] = {}
    aliases: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, str] = {}
    iri_str = str(prop_iri)

    # Labels — collect in one pass, then process tagged before untagged
    tagged: list[tuple[str, str]] = []
    untagged: list[str] = []
    for lbl in g.objects(prop_iri, RDFS.label):
        raw_value = clean_text(lbl)
        if raw_value is None:
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
            if (
                " ".join(labels[eff_lang].split()).lower()
                == " ".join(raw_value.split()).lower()
            ):
                pass
            elif raw_value not in [a.lower() for a in aliases[eff_lang]]:
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
            if (
                " ".join(raw_value.split()).lower()
                == " ".join(labels[eff_lang].split()).lower()
            ):
                pass
            elif raw_value not in [a.lower() for a in aliases[eff_lang]]:
                warn(
                    f"  Untagged property label on <{iri_str}> resolved to @{eff_lang} "
                    f"which already has a label: adding '{raw_value}' as alias.",
                    verbose,
                )
                aliases[eff_lang].append(raw_value)
        else:
            labels[eff_lang] = raw_value

    # Aliases
    for alias in g.objects(prop_iri, SKOS.altLabel):
        raw_value = clean_text(alias)
        if raw_value is None:
            continue
        raw_lang = getattr(alias, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"property alias {str(alias)!r} on <{iri_str}>",
            verbose=verbose,
        )
        if raw_value not in [a.lower() for a in aliases[eff_lang]]:
            aliases[eff_lang].append(raw_value)

    # Fallback if still no labels: promote an alias (default lang first),
    # else IRI suffix
    if not labels and require_label:
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

    # Descriptions
    for desc in g.objects(prop_iri, RDFS.comment):
        raw_value = clean_text(desc)
        if raw_value is None:
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
            if len(raw_value) > 250:
                warn(
                    f"  Description @{eff_lang} on <{iri_str}> exceeds 250 chars "
                    f"— truncating.",
                    verbose,
                )
                raw_value = raw_value[:250]
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
        value = value.strip()
        current = existing_labels.get(lang)
        if current is None:
            labels_to_set[lang] = {"language": lang, "value": value}
        elif " ".join(current.split()).lower() == " ".join(value.split()).lower():
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
                if " ".join(value.split()).lower() not in [
                    a.lower() for a in already_there
                ]:
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
        value = value.strip()
        current = existing_descriptions.get(lang)
        if current is None:
            descriptions_to_set[lang] = {"language": lang, "value": value}
        elif " ".join(current.split()) == " ".join(value.split()):
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
        already_alias = existing_aliases.get(lang, set())
        existing_label = existing_labels.get(lang, "")
        new_values = [
            v
            for v in values
            if v not in already_alias
            and " ".join(v.split()).lower() != " ".join(existing_label.split()).lower()
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


def _collect_property_instance_iris(data_graph: Graph) -> list[URIRef]:
    """
    Collect all urn:wikibase:property: and urn:wikibase:propertyIRI: IRIs
    that appear as subjects or objects in the data graph.
    Returns a sorted list of unique URIRefs.
    """
    props: set[URIRef] = set()
    for s, _, o in data_graph:
        for node in (s, o):
            if not isinstance(node, URIRef):
                continue
            node_str = str(node)
            if node_str.startswith(PROPERTY_PREFIX) or node_str.startswith(
                PROPERTY_IRI_PREFIX
            ):
                props.add(node)
    return sorted(props)


def resolve_property_instances(
    data_graph: Graph,
    lookup: dict,
    wikibase_api,
    language_resolver: LanguageResolver,
    verbose: int = 1,
) -> None:
    """
    For every urn:wikibase:property: or urn:wikibase:propertyIRI: IRI that
    appears in the data graph:
    - Already in lookup: push any label/description/alias metadata diff.
    - Not in lookup but wbml:propertyType present in data graph (generated by
      1b_subjectMap_property.rq from wbml:propertyEntityMap): resolve or
      create the property in Wikibase, then push metadata.
    - Not in lookup and no wbml:propertyType: raise ValueError — it must be
      declared in the schema (rdf:Property) or via wbml:nodeId.
    """
    lookup.setdefault("properties", {})

    for prop_iri in _collect_property_instance_iris(data_graph):
        iri_str = str(prop_iri)
        prop_entry = lookup["properties"].get(iri_str)

        if prop_entry is None:
            # Not in lookup: valid only if 1b generated wbml:propertyType
            # on this IRI (i.e. it comes from wbml:propertyEntityMap)
            if not list(data_graph.objects(prop_iri, WBML.propertyType)):
                raise ValueError(
                    f"Property entity <{iri_str}> found in data graph but not in "
                    f"lookup['properties']. Ensure it is declared in the schema "
                    f"(rdf:Property + wbml:propertyType) or referenced via "
                    f"wbml:propertyEntityMap with wbml:nodeId."
                )
            # propertyEntityMap-generated property: resolve or create it
            wb_datatype = _wb_datatype_from_graph(data_graph, prop_iri)
            meta = _collect_property_metadata(
                data_graph,
                prop_iri,
                language_resolver,
                verbose=verbose,
            )
            pid = lookup_get(lookup, iri_str, wb_datatype, wikibase_api)
            if pid is None:
                pid, wb_datatype = _resolve_one_property(
                    prop_iri,
                    meta,
                    data_graph,
                    wikibase_api,
                    language_resolver.language,
                    verbose,
                )
                lookup["properties"][iri_str] = {"id": pid, "datatype": wb_datatype}
        else:
            pid = prop_entry["id"]
            meta = _collect_property_metadata(
                data_graph,
                prop_iri,
                language_resolver,
                verbose=verbose,
                require_label=False,
            )

        # Skip API call if nothing to push
        # (property used only as a predicate with no metadata in data graph)
        if not any([meta["labels"], meta["descriptions"], meta["aliases"]]):
            continue

        _push_property_metadata(pid, meta, wikibase_api, verbose)
