from collections import defaultdict

from rdflib import Graph, URIRef
from rdflib.namespace import RDFS, SKOS

from ..utils.items_utils import clean_text, iri_suffix, search_item_by_labels
from ..utils.verbose_utils import inform, warn
from .language_resolver import LanguageResolver

ITEM_PREFIX = "urn:wikibase:item:"


def _is_item_iri(node) -> bool:
    """Return True if the RDF node is a URIRef using the Wikibase item prefix."""
    return isinstance(node, URIRef) and str(node).startswith(ITEM_PREFIX)


def _collect_instance_iris(g: Graph) -> list[URIRef]:
    """
    Collect all instance IRIs from the data graph.
    Considers every subject or object URIRef with the Wikibase item prefix.
    Returns a sorted list of unique URIRefs.
    """
    items: set[URIRef] = set()
    for s, _, o in g:
        if _is_item_iri(s):
            items.add(s)
        if _is_item_iri(o):
            items.add(o)
    return sorted(items)


def _collect_instance_metadata(
    g: Graph,
    item_iri: URIRef,
    language_resolver: LanguageResolver,
    verbose: int,
) -> dict:
    labels: dict[str, str] = {}
    aliases: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, str] = {}
    iri_str = str(item_iri)

    # Labels — collect in one pass, then process tagged before untagged
    tagged: list[tuple[str, str]] = []
    untagged: list[str] = []
    for lbl in g.objects(item_iri, RDFS.label):
        raw_value = clean_text(lbl)
        if raw_value is None:
            warn(f"  Skipping invalid label on <{iri_str}>: {lbl!r}", verbose)
            continue
        raw_lang = getattr(lbl, "language", None)
        if raw_lang is None:
            untagged.append(raw_value)
        else:
            tagged.append((raw_lang, raw_value))

    for raw_lang, raw_value in tagged:
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"instance label {raw_value!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_lang in labels:
            if raw_value not in aliases[eff_lang]:
                warn(
                    f"  Duplicate instance label @{eff_lang} on <{iri_str}>: "
                    f"keeping '{labels[eff_lang]}', adding '{raw_value}' as alias.",
                    verbose,
                )
                aliases[eff_lang].append(raw_value)
        else:
            labels[eff_lang] = raw_value

    for raw_value in untagged:
        eff_lang = language_resolver.resolve_language(
            None,
            context=f"instance label {raw_value!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_lang in labels:
            if raw_value.strip() == labels[eff_lang].strip():
                pass  # identical string, silently skip
            elif raw_value not in aliases[eff_lang]:
                warn(
                    f"  Untagged instance label on <{iri_str}> resolved to @{eff_lang} "
                    f"which already has a label: adding '{raw_value}' as alias.",
                    verbose,
                )
                aliases[eff_lang].append(raw_value)
        else:
            labels[eff_lang] = raw_value

    # Aliases
    for alias in g.objects(item_iri, SKOS.altLabel):
        raw_value = clean_text(alias)
        if raw_value is None:
            continue
        raw_lang = getattr(alias, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"instance alias {str(alias)!r} on <{iri_str}>",
            verbose=verbose,
        )
        if raw_value not in aliases[eff_lang]:
            aliases[eff_lang].append(raw_value)

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
        if raw_value is None:
            warn(f"  Skipping invalid description on <{iri_str}>: {desc!r}", verbose)
            continue
        raw_lang = getattr(desc, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"instance description {str(desc)!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_lang in descriptions:
            warn(
                f"  Duplicate instance description @{eff_lang} on <{iri_str}>: "
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


def _resolve_one_instance(
    item_iri: URIRef, meta: dict, wikibase_api, default_language: str, verbose: int
) -> str:
    """
    Find or create a Wikibase item for the given instance IRI.
    Search order: default-language label to untagged label to other-language labels.
    Returns the QID.
    """
    iri_str = str(item_iri)
    inform(f"Resolving instance <{iri_str}> …", verbose)

    qid = search_item_by_labels(
        wikibase_api, meta["labels"], default_language, aliases=meta["aliases"]
    )
    if qid is not None:
        inform(f"  Found {qid} for <{iri_str}>", verbose)
        return qid

    inform(f"  Not found — creating new item for <{iri_str}>", verbose)
    qid = wikibase_api.create_item(
        labels=meta["labels"],
        descriptions=meta["descriptions"],
        aliases=meta["aliases"],
    )
    inform(f"  Created {qid} for <{iri_str}>", verbose)
    return qid


def _push_instance_metadata(
    qid: str,
    meta: dict,
    wikibase_api,
    verbose: int,
    overwrite_on_conflict: bool = False,
) -> None:
    """
    Push a labels/aliases/descriptions diff to an existing Wikibase item.
    - New values are added.
    - Conflicts: warn + skip (or overwrite if overwrite_on_conflict=True).
    - Aliases: union only, never remove existing ones.
    - Empty language keys (untagged RDF literals) are skipped — invalid for Wikibase.
    """
    try:
        entity = wikibase_api.get_entity(qid, props="labels|descriptions|aliases")
    except Exception as exc:
        warn(f"  Could not fetch entity {qid} to diff metadata: {exc}", verbose)
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
        elif current.strip() == value:
            pass
        else:
            if overwrite_on_conflict:
                inform(
                    f"  [{qid}] Overwriting label@{lang}: '{current}' to '{value}'",
                    verbose,
                )
                labels_to_set[lang] = {"language": lang, "value": value}
            else:
                warn(
                    f"  [{qid}] Label conflict @{lang}: "
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
        value = value.strip()
        current = existing_descriptions.get(lang)
        if current is None:
            descriptions_to_set[lang] = {"language": lang, "value": value}
        elif current.strip() == value:
            pass
        else:
            if overwrite_on_conflict:
                inform(
                    f"  [{qid}] Overwriting description@{lang}:"
                    f" '{current}' to '{value}'",
                    verbose,
                )
                descriptions_to_set[lang] = {"language": lang, "value": value}
            else:
                warn(
                    f"  [{qid}] Description conflict @{lang}: "
                    f"data='{value}', Wikibase='{current}': keeping Wikibase.",
                    verbose,
                )
    if descriptions_to_set:
        entity_data["descriptions"] = descriptions_to_set

    # Aliases — union only
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

    inform(f"  [{qid}] Pushing metadata diff: {list(entity_data.keys())} …", verbose)
    wikibase_api.edit_entity(qid, entity_data)


def resolve_instances(
    data_graph: Graph,
    lookup: dict,
    wikibase_api,
    language_resolver: LanguageResolver,
    verbose: int = 1,
) -> None:
    """
    Main entry point for instance resolution.
      1. Collect all item IRIs from the data graph
      (subjects and objects with item prefix).
      2. For each item not yet in lookup["items"]: find or create it.
      3. Push metadata diff (labels, descriptions, aliases).
    """
    lookup.setdefault("items", {})

    for item_iri in _collect_instance_iris(data_graph):
        iri_str = str(item_iri)
        already_resolved = iri_str in lookup["items"]

        meta = _collect_instance_metadata(
            data_graph,
            item_iri,
            language_resolver,
            verbose=0 if already_resolved else verbose,
        )

        if not already_resolved:
            qid = _resolve_one_instance(
                item_iri, meta, wikibase_api, language_resolver.language, verbose
            )
            lookup["items"][iri_str] = qid

        _push_instance_metadata(lookup["items"][iri_str], meta, wikibase_api, verbose)
