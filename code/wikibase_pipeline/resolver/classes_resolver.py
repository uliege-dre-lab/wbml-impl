import re
from collections import defaultdict

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

from ..utils.claims_utils import find_existing_claim_guid
from ..utils.items_utils import (
    clean_text,
    iri_suffix,
    normalize_text,
    search_item_by_labels,
)
from ..utils.verbose_utils import inform, warn
from ..wikibase_api import WikibaseAPI
from .language_resolver import LanguageResolver


def collect_class_metadata(
    g: Graph,
    class_iri: URIRef,
    language_resolver: LanguageResolver,
    verbose: int,
    require_label: bool = True,
) -> dict:
    """
    Collect labels, aliases, descriptions,
    and parent classes for a given rdfs:Class IRI.
    Inputs:
    - g: The RDFLib Graph containing the schema.
    - class_iri: The URIRef of the class to collect metadata for.
    - language_resolver: An instance of LanguageResolver.
    - verbose: Verbosity level for logging.
    - require_label: If True, will use IRI suffix as fallback.
    Output:
    - A dictionary with keys: "labels", "aliases", "descriptions".
    """
    labels: dict[str, str] = {}
    aliases: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, str] = {}
    iri_str = str(class_iri)

    # Labels
    tagged: list[tuple[str, str]] = []
    for lbl in g.objects(class_iri, RDFS.label):
        raw_value = clean_text(lbl)
        eff_value = normalize_text(raw_value)
        if eff_value is None:
            continue
        raw_lang = getattr(lbl, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"class label {raw_value!r} on <{iri_str}>",
            verbose=verbose,
        )
        tagged.append((eff_lang, eff_value))

    for eff_lang, eff_value in tagged:
        if eff_lang in labels:
            if eff_value == labels[eff_lang]:
                pass
            else:
                raise ValueError(
                    f"Duplicate class label @{eff_lang} on <{iri_str}>: "
                    f"'{labels[eff_lang]}' and '{eff_value}'. "
                    f"At most one label per language is allowed in the mapping."
                )
        else:
            labels[eff_lang] = eff_value

    # Aliases
    for alias in g.objects(class_iri, SKOS.altLabel):
        raw_value = clean_text(alias)
        eff_value = normalize_text(raw_value)
        if eff_value is None:
            continue
        raw_lang = getattr(alias, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"alias {str(alias)!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_value not in aliases[eff_lang]:
            aliases[eff_lang].append(eff_value)

    # Fallback if still no labels: IRI suffix
    if not labels and require_label:
        fallback_lang = language_resolver.language
        fallback = iri_suffix(iri_str)
        warn(
            f"  No valid class labels for <{iri_str}> — "
            f"using IRI suffix fallback '{fallback}'.",
            verbose,
        )
        labels[fallback_lang] = fallback

    # Descriptions
    for desc in g.objects(class_iri, RDFS.comment):
        raw_value = clean_text(desc)
        eff_value = normalize_text(raw_value)
        if eff_value is None:
            continue
        raw_lang = getattr(desc, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"description {str(desc)!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_lang in descriptions:
            if eff_value == descriptions[eff_lang]:
                pass
            else:
                raise ValueError(
                    f"Duplicate class description @{eff_lang} on <{iri_str}>: "
                    f"'{descriptions[eff_lang]}' and '{eff_value}'. "
                    f"At most one description per language is allowed in the mapping."
                )
        else:
            descriptions[eff_lang] = eff_value

    return {"labels": labels, "aliases": dict(aliases), "descriptions": descriptions}


def resolve_one_class(
    class_iri: URIRef,
    meta: dict,
    wikibase_api: WikibaseAPI,
    default_language: str,
    verbose: int,
) -> str:
    """
    Find or create a Wikibase item for the given class.
    Inputs:
    - class_iri: The URIRef of the class to resolve.
    - meta: The metadata dictionary for the class.
    - wikibase_api: An instance of WikibaseAPI class.
    - default_language: The default language code to prioritize in the search.
    - verbose: Verbosity level for logging.
    Output:
    - The QID of the resolved or created item.
    """
    iri_str = str(class_iri)

    qid = search_item_by_labels(
        wikibase_api,
        meta["labels"],
        default_language,
        verbose=verbose,
    )

    if qid is not None:
        inform(f"  Found {qid} for <{iri_str}> label by search", verbose)
        return qid

    try:
        qid = wikibase_api.create_item(
            labels=meta["labels"],
            descriptions=meta["descriptions"],
            aliases=meta["aliases"],
        )
        inform(f"  Created {qid} for <{iri_str}>", verbose)
        return qid
    except RuntimeError as exc:
        err = str(exc)
        if "label-with-description-conflict" in err:
            match = re.search(r"\[\[Item:(Q\d+)\|", err)
            if match:
                qid = match.group(1)
                inform(f"  Conflict: using existing {qid} for <{iri_str}>", verbose)
                return qid
            else:
                raise RuntimeError(
                    f"label-with-description-conflict for <{iri_str}> "
                    f"but could not parse QID from error: {err}"
                ) from exc
        raise


def push_class_metadata(
    qid: str,
    meta: dict,
    wikibase_api: WikibaseAPI,
    verbose: int,
) -> None:
    """
    Push metadata (labels, descriptions, aliases) to Wikibase for the given QID.
    Inputs:
    - qid: The QID of the item to update.
    - meta: The metadata dictionary with keys "labels", "descriptions", "aliases".
    - wikibase_api: An instance of WikibaseAPI class.
    - verbose: Verbosity level for logging.
    """
    try:
        entity = wikibase_api.get_entity(qid, props="labels|descriptions|aliases")
    except Exception as exc:
        raise RuntimeError(
            f"Could not fetch entity {qid} to diff metadata: {exc}"
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
                f"  [{qid}] Label conflict @{lang}: "
                f"schema='{value}', Wikibase='{current}': keeping Wikibase label.",
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
                f"  [{qid}] Description conflict @{lang}: "
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

    inform(f"  [{qid}] Pushing metadata diff: {list(entity_data.keys())} …", verbose)
    wikibase_api.edit_entity(qid, entity_data)


def push_subclass_claims(
    g: Graph,
    lookup: dict,
    wikibase_api: WikibaseAPI,
    verbose: int,
) -> None:
    """
    Push rdfs:subClassOf claims to Wikibase.
    Inputs:
    - g: The RDFLib Graph containing the schema.
    - lookup: The lookup cache dictionary.
    - wikibase_api: An instance of the WikibaseAPI class.
    - verbose: Verbosity level for logging.
    """
    subclassof_pid = (
        lookup.get("properties", {}).get(str(RDFS.subClassOf), {}).get("id")
    )
    if subclassof_pid is None:
        raise ValueError(
            "subClassOf property not found in lookup cache. "
            "Make sure to resolve built-in properties before classes."
        )

    claims_cache: dict[str, dict] = {}

    for child_iri, _, parent_iri in g.triples((None, RDFS.subClassOf, None)):
        if (child_iri, RDF.type, RDFS.Class) not in g:
            continue

        child_str = str(child_iri)
        parent_str = str(parent_iri)
        child_qid = lookup["items"].get(child_str)
        parent_qid = lookup["items"].get(parent_str)

        if child_qid is None:
            raise ValueError(f"Child <{child_str}> not in lookup.")
        if parent_qid is None:
            raise ValueError(f"Parent <{parent_str}> not in lookup.")

        if child_qid not in claims_cache:
            try:
                claims_cache[child_qid] = wikibase_api.get_entity_claims(child_qid)
            except Exception as exc:
                warn(f"  Could not fetch claims for {child_qid}: {exc}", verbose)
                claims_cache[child_qid] = {}

        wikibase_value = {"entity-type": "item", "id": parent_qid}
        if find_existing_claim_guid(
            claims_cache[child_qid], subclassof_pid, wikibase_value, "wikibase-item"
        ):
            inform(
                f"  subClassOf {child_qid} -> {parent_qid} already exists, skipping.",
                verbose,
            )
            continue

        wikibase_api.add_statement(
            subject_qid=child_qid,
            property_pid=subclassof_pid,
            value=wikibase_value,
            property_datatype="wikibase-item",
        )


def resolve_schema_classes(
    schema_graph: Graph,
    lookup: dict,
    wikibase_api: WikibaseAPI,
    language_resolver: LanguageResolver,
    verbose: int,
) -> None:
    """
    Main entry point for class resolution.
    - For each rdfs:Class not yet in lookup["items"]: find or create it.
    - Push metadata diff (labels, descriptions, aliases).
    - Add rdfs:subClassOf claims.
    Inputs:
    - schema_graph: The RDFLib Graph containing the schema.
    - lookup: The lookup cache dictionary.
    - wikibase_api: An instance of the WikibaseAPI class.
    - language_resolver: An instance of LanguageResolver class.
    - verbose: Verbosity level for logging.
    """
    lookup.setdefault("items", {})

    for class_iri in sorted(schema_graph.subjects(RDF.type, RDFS.Class)):
        iri_str = str(class_iri)
        already_resolved = iri_str in lookup["items"]

        meta = collect_class_metadata(
            schema_graph,
            class_iri,
            language_resolver,
            verbose=verbose,
            require_label=not already_resolved,
        )

        if not already_resolved:
            qid = resolve_one_class(
                class_iri,
                meta,
                wikibase_api,
                language_resolver.language,
                verbose,
            )
            lookup["items"][iri_str] = qid

        if not any([meta["labels"], meta["descriptions"], meta["aliases"]]):
            continue

        push_class_metadata(lookup["items"][iri_str], meta, wikibase_api, verbose)

    push_subclass_claims(schema_graph, lookup, wikibase_api, verbose)
