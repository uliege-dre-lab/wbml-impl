import re
from collections import defaultdict

from rdflib import Graph, URIRef
from rdflib.namespace import RDFS, SKOS

from ..utils.items_utils import (
    clean_text,
    iri_suffix,
    normalize_text,
    search_item_by_labels,
)
from ..utils.verbose_utils import inform, warn
from ..wikibase_api import WikibaseAPI
from .language_resolver import LanguageResolver

ITEM_PREFIX = "urn:wikibase:item:"


def _is_item_iri(node) -> bool:
    """Return True if the RDF node is a URIRef using the Wikibase item prefix."""
    return isinstance(node, URIRef) and str(node).startswith(ITEM_PREFIX)


def collect_instance_iris(g: Graph) -> list[URIRef]:
    """
    Collect all instance IRIs from the data graph.
    Input:
    - g: The RDFLib Graph containing the data to be processed.
    Output:
    - Sorted list of URIRefs that are subjects or objects with the item prefix.
    """
    items: set[URIRef] = set()
    for s, _, o in g:
        if _is_item_iri(s):
            items.add(s)
        if _is_item_iri(o):
            items.add(o)
    return sorted(items)


def collect_instance_metadata(
    g: Graph,
    item_iri: URIRef,
    language_resolver: LanguageResolver,
    verbose: int,
    require_label: bool = True,
) -> dict:
    """
    Collect labels, aliases, and descriptions for an instance IRI.
    Input:
    - g: The RDFLib Graph containing the data to be processed.
    - item_iri: The URIRef of the instance to collect metadata for.
    - language_resolver: An instance of the LanguageResolver class.
    - verbose: Verbosity level for logging.
    - require_label: Flag indicating if a label is required for the item.
    Output:
    - A dictionary with keys "labels", "aliases", and "descriptions"
    containing the collected metadata.
    """
    labels: dict[str, str] = {}
    aliases: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, str] = {}
    iri_str = str(item_iri)

    # Labels
    tagged: list[tuple[str, str]] = []
    for lbl in g.objects(item_iri, RDFS.label):
        raw_value = clean_text(lbl)
        eff_value = normalize_text(raw_value)
        if eff_value is None:
            continue
        raw_lang = getattr(lbl, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"instance label {raw_value!r} on <{iri_str}>",
            verbose=verbose,
        )
        tagged.append((eff_lang, eff_value))

    for eff_lang, eff_value in tagged:
        if eff_lang in labels:
            if eff_value == labels[eff_lang]:
                pass
            else:
                raise ValueError(
                    f"Duplicate instance label @{eff_lang} on <{iri_str}>: "
                    f"'{labels[eff_lang]}' and '{eff_value}'. "
                    f"At most one label per language is allowed in the mapping."
                )
        else:
            labels[eff_lang] = eff_value

    # Aliases
    for alias in g.objects(item_iri, SKOS.altLabel):
        raw_value = clean_text(alias)
        eff_value = normalize_text(raw_value)
        if eff_value is None:
            continue
        raw_lang = getattr(alias, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"instance alias {str(alias)!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_value not in aliases[eff_lang]:
            aliases[eff_lang].append(eff_value)

    # Fallback if still no labels: IRI suffix
    if not labels and require_label:
        fallback_lang = language_resolver.language
        fallback = iri_suffix(iri_str)
        warn(
            f"  No valid labels for <{iri_str}> — "
            f"using IRI suffix fallback '{fallback}'.",
            verbose,
        )
        labels[fallback_lang] = fallback

    # Descriptions
    for desc in g.objects(item_iri, RDFS.comment):
        raw_value = clean_text(desc)
        eff_value = normalize_text(raw_value)
        if eff_value is None:
            continue
        raw_lang = getattr(desc, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"instance description {str(desc)!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_lang in descriptions:
            if eff_value == descriptions[eff_lang]:
                pass
            else:
                raise ValueError(
                    f"Duplicate instance description @{eff_lang} on <{iri_str}>: "
                    f"'{descriptions[eff_lang]}' and '{eff_value}'. "
                    f"At most one description per language is allowed in the mapping."
                )
        else:
            descriptions[eff_lang] = eff_value

    return {
        "labels": labels,
        "aliases": dict(aliases),
        "descriptions": descriptions,
    }


def resolve_one_instance(
    item_iri: URIRef,
    meta: dict,
    wikibase_api: WikibaseAPI,
    default_language: str,
    verbose: int,
) -> str:
    """
    Find or create a Wikibase item for the given instance IRI.
    Input:
    - item_iri: The URIRef of the instance to resolve.
    - meta: A dictionary containing the instance metadata.
    - wikibase_api: An instance of the WikibaseAPI class.
    - default_language: The default language.
    - verbose: Verbosity level for logging.
    Output:
    - The QID of the resolved or created Wikibase item.
    """
    iri_str = str(item_iri)

    qid = search_item_by_labels(
        wikibase_api, meta["labels"], default_language, verbose=verbose
    )
    if qid is not None:
        inform(f"  Found {qid} for <{iri_str}> by label search", verbose)
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


def push_instance_metadata(
    qid: str,
    meta: dict,
    wikibase_api: WikibaseAPI,
    verbose: int,
) -> None:
    """
    Push a labels/aliases/descriptions diff to an existing Wikibase item.
    Inputs:
    - qid: The QID of the existing Wikibase item.
    - meta: A dictionary containing the metadata changes to push.
    - wikibase_api: An instance of the WikibaseAPI class.
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
                f"  [{qid}] Description conflict @{lang}: "
                f"data='{value}', Wikibase='{current}': keeping Wikibase.",
                verbose,
            )
    if descriptions_to_set:
        entity_data["descriptions"] = descriptions_to_set

    # Aliases
    aliases_to_set = {}
    for lang, values in meta["aliases"].items():
        already_aliases = existing_aliases.get(lang, set())
        already_label = existing_labels.get(lang)
        new_values = [
            v for v in values if v not in already_aliases and v != already_label
        ]
        if new_values:
            aliases_to_set[lang] = [{"language": lang, "value": v} for v in new_values]
    if aliases_to_set:
        entity_data["aliases"] = aliases_to_set

    if not entity_data:
        return

    inform(f"  [{qid}] Pushing metadata diff: {list(entity_data.keys())} …", verbose)
    wikibase_api.edit_entity(qid, entity_data)


def resolve_instances(
    data_graph: Graph,
    lookup: dict,
    wikibase_api: WikibaseAPI,
    language_resolver: LanguageResolver,
    verbose: int,
) -> None:
    """
    Main entry point for instance resolution.
    - Collect all item IRIs from the data graph
    (subjects and objects with item prefix).
    - For each item not yet in lookup["items"]: find or create it.
    - Push metadata diff (labels, descriptions, aliases).
    Inputs:
    - data_graph: The RDFLib Graph containing the data to be processed.
    - lookup: The lookup cache dictionary to update with resolved IDs.
    - wikibase_api: An instance of the WikibaseAPI class.
    - language_resolver: An instance of the LanguageResolver class.
    - verbose: Verbosity level for logging.
    """
    lookup.setdefault("items", {})

    for item_iri in collect_instance_iris(data_graph):
        iri_str = str(item_iri)
        already_resolved = iri_str in lookup["items"]

        meta = collect_instance_metadata(
            data_graph,
            item_iri,
            language_resolver,
            verbose=verbose,
            require_label=not already_resolved,
        )

        if not already_resolved:
            qid = resolve_one_instance(
                item_iri, meta, wikibase_api, language_resolver.language, verbose
            )
            lookup["items"][iri_str] = qid

        if not any([meta["labels"], meta["descriptions"], meta["aliases"]]):
            continue

        push_instance_metadata(lookup["items"][iri_str], meta, wikibase_api, verbose)
