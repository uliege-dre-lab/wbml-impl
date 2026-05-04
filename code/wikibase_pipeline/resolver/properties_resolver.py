from collections import defaultdict

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

from ..utils.items_utils import clean_text, normalize_text
from ..utils.properties_utils import iri_suffix, search_wikibase_properties
from ..utils.verbose_utils import inform, warn
from ..wikibase_api import WikibaseAPI
from .language_resolver import LanguageResolver

WBML = Namespace("https://example.org/wbml#")
PROPERTY_PREFIX = "urn:wikibase:property:"
PROPERTY_IRI_PREFIX = "urn:wikibase:propertyIRI:"

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
    Input:
    - g: The RDFLib Graph containing the schema.
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


def wb_datatype_from_graph(g: Graph, prop_iri: URIRef) -> str:
    """
    Extract the Wikibase datatype string for the given property IRI from the graph.
    Inputs:
    - g: The RDFLib Graph containing the schema.
    - prop_iri: The URIRef of the property to check.
    Output:
    - The Wikibase datatype string.
    """
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

    return WBML_DATATYPE_MAP[local_name]


def collect_property_metadata(
    g: Graph,
    prop_iri: URIRef,
    language_resolver: LanguageResolver,
    verbose: int,
    require_label: bool = True,
) -> dict:
    """
    Collect labels, aliases, and descriptions for a property from the graph.
    Inputs:
    - g: The RDFLib Graph containing the schema.
    - prop_iri: The URIRef of the property to collect metadata for.
    - language_resolver: An instance of LanguageResolver to resolve languages.
    - verbose: Verbosity level for logging.
    - require_label: If True, will warn and use IRI suffix as fallback.
    Output:
    - A dictionary with keys "labels", "aliases", "descriptions"
    containing the collected metadata.
    """
    labels: dict[str, str] = {}
    aliases: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, str] = {}
    iri_str = str(prop_iri)

    # Labels
    tagged: list[tuple[str, str]] = []
    for lbl in g.objects(prop_iri, RDFS.label):
        raw_value = clean_text(lbl)
        eff_value = normalize_text(raw_value)
        if eff_value is None:
            continue
        raw_lang = getattr(lbl, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"property label {raw_value!r} on <{iri_str}>",
            verbose=verbose,
        )
        tagged.append((eff_lang, eff_value))

    for eff_lang, eff_value in tagged:
        if eff_lang in labels:
            if eff_value == labels[eff_lang]:
                pass
            else:
                raise ValueError(
                    f"Duplicate property label @{eff_lang} on <{iri_str}>: "
                    f"'{labels[eff_lang]}' and '{eff_value}'. "
                    f"At most one label per language is allowed in the mapping."
                )
        else:
            labels[eff_lang] = eff_value

    # Aliases
    for alias in g.objects(prop_iri, SKOS.altLabel):
        raw_value = clean_text(alias)
        eff_value = normalize_text(raw_value)
        if eff_value is None:
            continue
        raw_lang = getattr(alias, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"property alias {str(alias)!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_value not in aliases[eff_lang]:
            aliases[eff_lang].append(eff_value)

    # Fallback if still no labels: IRI suffix
    if not labels and require_label:
        fallback_lang = language_resolver.language
        suffix = iri_suffix(iri_str)
        warn(
            f"  No valid labels for <{iri_str}> — "
            f"using IRI suffix fallback '{suffix}'.",
            verbose,
        )
        labels[fallback_lang] = suffix

    # Descriptions
    for desc in g.objects(prop_iri, RDFS.comment):
        raw_value = clean_text(desc)
        eff_value = normalize_text(raw_value)
        if eff_value is None:
            continue
        raw_lang = getattr(desc, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"property description {str(desc)!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_lang in descriptions:
            if eff_value == descriptions[eff_lang]:
                pass
            else:
                raise ValueError(
                    f"Duplicate property description @{eff_lang} on <{iri_str}>: "
                    f"'{descriptions[eff_lang]}' and '{eff_value}'. "
                    f"At most one description per language is allowed in the mapping."
                )
        else:
            if len(eff_value) > 250:
                warn(
                    f"  Description @{eff_lang} on <{iri_str}> exceeds 250 chars "
                    f"— truncating.",
                    verbose,
                )
                eff_value = eff_value[:250]
            descriptions[eff_lang] = eff_value

    return {
        "labels": labels,
        "aliases": dict(aliases),
        "descriptions": descriptions,
    }


def resolve_one_property(
    prop_iri: URIRef,
    meta: dict,
    schema_graph: Graph,
    wikibase_api: WikibaseAPI,
    default_language: str,
    verbose: int,
) -> tuple[str, str]:
    """
    Find or create a Wikibase property for the given schema property IRI.
    Inputs:
    - prop_iri: The URIRef of the property to resolve.
    - meta: A dictionary containing the property's metadata.
    - schema_graph: The RDFLib Graph containing the schema.
    - wikibase_api: An instance of the WikibaseAPI class.
    - default_language: The default language code to prioritize in label search.
    - verbose: Verbosity level for logging.
    Output:
    - A tuple of (property ID, Wikibase datatype string).
    """
    wb_datatype = wb_datatype_from_graph(schema_graph, prop_iri)
    labels = meta["labels"]

    pid = search_wikibase_properties(
        wikibase_api,
        labels=labels,
        default_language=default_language,
        expected_datatype=wb_datatype,
    )

    if pid is not None:
        inform(
            f"Resolved property <{prop_iri}> by label search -> "
            f"{pid} (datatype='{wb_datatype}')",
            verbose,
        )
        return pid, wb_datatype

    pid = wikibase_api.create_property(
        labels=labels,
        datatype=wb_datatype,
        descriptions=meta["descriptions"],
        aliases=meta["aliases"],
    )
    inform(
        f"Created new property {pid} for <{prop_iri}> (datatype='{wb_datatype}')",
        verbose,
    )
    return pid, wb_datatype


def push_property_metadata(
    pid: str,
    meta: dict,
    wikibase_api: WikibaseAPI,
    verbose: int,
) -> None:
    """
    Push a labels/aliases/descriptions diff to an existing Wikibase property.
    Inputs:
    - pid: The property ID to update.
    - meta: A dictionary containing the property's metadata.
    - wikibase_api: An instance of the WikibaseAPI class.
    - verbose: Verbosity level for logging.
    """
    try:
        entity = wikibase_api.get_entity(pid, props="labels|descriptions|aliases")
    except Exception as exc:
        raise RuntimeError(
            f"Could not fetch entity {pid} to diff metadata: {exc}"
        ) from exc

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
    for lang, value in meta["labels"].items():
        current = existing_labels.get(lang)
        if current is None:
            labels_to_set[lang] = {"language": lang, "value": value}
        elif current == value:
            pass
        else:
            warn(
                f"  [{pid}] Label conflict @{lang}: "
                f"data='{value}', Wikibase='{current}': keeping Wikibase label.",
                verbose,
            )
    if labels_to_set:
        entity_data["labels"] = labels_to_set

    # Descriptions
    descriptions_to_set = {}
    for lang, value in meta["descriptions"].items():
        current = existing_descriptions.get(lang)
        if current is None:
            descriptions_to_set[lang] = {"language": lang, "value": value}
        elif current == value:
            pass
        else:
            warn(
                f"  [{pid}] Description conflict @{lang}: "
                f"schema='{value}', Wikibase='{current}': keeping Wikibase.",
                verbose,
            )
    if descriptions_to_set:
        entity_data["descriptions"] = descriptions_to_set

    # Aliases
    aliases_to_set = {}
    for lang, values in meta["aliases"].items():
        already_aliases = existing_aliases.get(lang, set())
        existing_label = existing_labels.get(lang)
        new_values = [
            v for v in values if v not in already_aliases and v != existing_label
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
    wikibase_api: WikibaseAPI,
    language_resolver: LanguageResolver,
    verbose: int,
) -> None:
    """
    Main entry point for schema property resolution.
    For each rdf:Property in the schema:
    - Validate it has exactly one wbml:propertyType.
    - Check lookup.
    - Search Wikibase by label + datatype filter.
    - If not found, create it.
    - Push metadata diff (labels, descriptions, aliases).
    Inputs:
    - schema_graph: The RDFLib Graph containing the schema.
    - lookup: The lookup cache dictionary to check and update.
    - wikibase_api: An instance of the WikibaseAPI class.
    - language_resolver: An instance of the LanguageResolver class.
    - verbose: Verbosity level for logging.
    """
    validate_schema_properties(schema_graph)
    lookup.setdefault("properties", {})

    for prop_iri in sorted(schema_graph.subjects(RDF.type, RDF.Property)):
        iri_str = str(prop_iri)
        wb_datatype = wb_datatype_from_graph(schema_graph, prop_iri)
        already_resolved = iri_str in lookup["properties"]

        meta = collect_property_metadata(
            schema_graph,
            prop_iri,
            language_resolver,
            verbose=verbose,
            require_label=not already_resolved,
        )
        if (
            already_resolved
            and wb_datatype != lookup["properties"][iri_str]["datatype"]
        ):
            raise ValueError(
                f"Property <{iri_str}> has conflicting datatypes: "
                f"{lookup['properties'][iri_str]['datatype']} in lookup, "
                f"{wb_datatype} in schema. "
            )
        if not already_resolved:
            pid, wb_datatype = resolve_one_property(
                prop_iri,
                meta,
                schema_graph,
                wikibase_api,
                language_resolver.language,
                verbose,
            )
            lookup["properties"][iri_str] = {"id": pid, "datatype": wb_datatype}

        # Skip API call if nothing to push
        if not any([meta["labels"], meta["descriptions"], meta["aliases"]]):
            continue

        push_property_metadata(
            lookup["properties"][iri_str]["id"], meta, wikibase_api, verbose
        )


def collect_property_instance_iris(data_graph: Graph) -> list[URIRef]:
    """
    Collect all urn:wikibase:property: and urn:wikibase:propertyIRI: IRIs
    that appear as subjects or objects in the data graph.
    Input:
    - data_graph: The RDFLib Graph containing the data.
    Output:
    - A sorted list of unique URIRefs.
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
    wikibase_api: WikibaseAPI,
    language_resolver: LanguageResolver,
    verbose: int,
) -> None:
    """
    Main entry point for property instance resolution.
    For every urn:wikibase:property: or urn:wikibase:propertyIRI:
    IRI that appears in the data graph:
    - Already in lookup: push any label/description/alias metadata diff.
    - Not in lookup but wbml:propertyType present in data graph (generated by
      1b_subjectMap_property.rq from wbml:entityMap): resolve or
      create the property in Wikibase, then push metadata.
    - Not in lookup and no wbml:propertyType: raise ValueError.
    Inputs:
    - data_graph: The RDFLib Graph containing the data.
    - lookup: The lookup cache dictionary to check and update.
    - wikibase_api: An instance of the WikibaseAPI class.
    - language_resolver: An instance of the LanguageResolver class.
    - verbose: Verbosity level for logging.
    """
    lookup.setdefault("properties", {})

    for prop_iri in collect_property_instance_iris(data_graph):
        iri_str = str(prop_iri)
        prop_entry = lookup["properties"].get(iri_str)

        # if not in lookup
        if prop_entry is None:
            # if no wbml:propertyType
            if not list(data_graph.objects(prop_iri, WBML.propertyType)):
                raise ValueError(
                    f"Property entity <{iri_str}> found in data graph but not in "
                    f"lookup['properties']. Ensure it is declared in the schema "
                    f"(rdf:Property + wbml:propertyType) or referenced via "
                    f"wbml:propertyEntityMap with wbml:nodeId."
                )
            # wbml:propertyType present → resolve/create and push metadata
            wb_datatype = wb_datatype_from_graph(data_graph, prop_iri)
            meta = collect_property_metadata(
                data_graph,
                prop_iri,
                language_resolver,
                verbose=verbose,
            )
            pid, wb_datatype = resolve_one_property(
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
            if list(data_graph.objects(prop_iri, WBML.propertyType)):
                wb_datatype = wb_datatype_from_graph(data_graph, prop_iri)
                if wb_datatype != prop_entry.get("datatype"):
                    raise ValueError(
                        f"Property <{iri_str}> has conflicting datatypes: "
                        f"{prop_entry['datatype']} in lookup, "
                        f"{wb_datatype} in data graph."
                    )
            meta = collect_property_metadata(
                data_graph,
                prop_iri,
                language_resolver,
                verbose=verbose,
                require_label=False,
            )

        # Skip API call if nothing to push
        if not any([meta["labels"], meta["descriptions"], meta["aliases"]]):
            continue

        push_property_metadata(pid, meta, wikibase_api, verbose)
