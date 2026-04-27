import re
from collections import defaultdict

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

from ..utils.items_utils import clean_text, iri_suffix, search_item_by_labels
from ..utils.verbose_utils import inform, warn
from .language_resolver import LanguageResolver

WBML = Namespace("https://example.org/wbml#")
CLASS_PREFIX = "urn:wikibase:item:"


def _collect_class_metadata(
    g: Graph,
    class_iri: URIRef,
    language_resolver: LanguageResolver,
    verbose: int,
) -> dict:
    labels: dict[str, str] = {}
    aliases: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, str] = {}
    subclass_of: list[str] = []
    iri_str = str(class_iri)

    # Labels — collect in one pass, then process tagged before untagged
    tagged: list[tuple[str, str]] = []
    untagged: list[str] = []
    for lbl in g.objects(class_iri, RDFS.label):
        raw_value = clean_text(lbl)
        if raw_value is None:
            warn(f"  Skipping invalid class label on <{iri_str}>: {lbl!r}", verbose)
            continue
        raw_lang = getattr(lbl, "language", None)
        if raw_lang is None:
            untagged.append(raw_value)
        else:
            tagged.append((raw_lang, raw_value))

    for raw_lang, raw_value in tagged:
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"label {raw_value!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_lang in labels:
            if " ".join(raw_value.split()) == " ".join(labels[eff_lang].split()):
                pass
            elif raw_value not in aliases[eff_lang]:
                warn(
                    f"  Duplicate class label @{eff_lang} on <{iri_str}>: "
                    f"keeping '{labels[eff_lang]}', "
                    f"adding '{raw_value}' as alias.",
                    verbose,
                )
                aliases[eff_lang].append(raw_value)
        else:
            labels[eff_lang] = raw_value

    for raw_value in untagged:
        eff_lang = language_resolver.resolve_language(
            None,
            context=f"label {raw_value!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_lang in labels:
            if " ".join(raw_value.split()) == " ".join(labels[eff_lang].split()):
                pass  # identical string, silently skip
            elif raw_value not in aliases[eff_lang]:
                warn(
                    f"  Untagged class label on <{iri_str}> resolved to @{eff_lang} "
                    f"which already has a label: adding '{raw_value}' as alias.",
                    verbose,
                )
                aliases[eff_lang].append(raw_value)
        else:
            labels[eff_lang] = raw_value

    # Aliases
    for alias in g.objects(class_iri, SKOS.altLabel):
        raw_value = clean_text(alias)
        if raw_value is None:
            continue
        raw_lang = getattr(alias, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"alias {str(alias)!r} on <{iri_str}>",
            verbose=verbose,
        )
        if raw_value not in aliases[eff_lang]:
            aliases[eff_lang].append(raw_value)

    # Fallback if still no labels: promote an alias (default lang first),
    # else IRI suffix
    if not labels:
        fallback_lang = language_resolver.language or "en"
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
                    f"  No valid class labels for <{iri_str}> — "
                    f"promoting alias '{value}'@{lang} as label.",
                    verbose,
                )
                promoted = True
                break
        if not promoted:
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
        if raw_value is None:
            warn(
                f"  Skipping invalid class description on <{iri_str}>: {desc!r}",
                verbose,
            )
            continue
        raw_lang = getattr(desc, "language", None)
        eff_lang = language_resolver.resolve_language(
            raw_lang,
            context=f"description {str(desc)!r} on <{iri_str}>",
            verbose=verbose,
        )
        if eff_lang in descriptions:
            warn(
                f"  Duplicate class description @{eff_lang} on <{iri_str}>: "
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

    for parent in g.objects(class_iri, RDFS.subClassOf):
        subclass_of.append(str(parent))

    return {
        "labels": labels,
        "aliases": dict(aliases),
        "descriptions": descriptions,
        "subclass_of": subclass_of,
    }


def _resolve_one_class(
    class_iri: URIRef,
    meta: dict,
    wikibase_api,
    default_language: str,
    verbose: int,
    lookup: dict | None = None,  # NEW
) -> str:
    """
    Find or create a Wikibase item for the given class.
    Search order: default-language label to untagged label to other-language labels.
    Handles label-with-description-conflict by extracting the existing QID.
    Returns the QID.
    """
    iri_str = str(class_iri)
    inform(f"Resolving class <{iri_str}> …", verbose)

    qid = search_item_by_labels(
        wikibase_api,
        meta["labels"],
        default_language,
        aliases=meta["aliases"],
        lookup=lookup,
        current_iri=iri_str,
    )
    if qid is not None:
        inform(f"  Found {qid} for <{iri_str}>", verbose)
        return qid

    inform(f"  Not found — creating new item for <{iri_str}>", verbose)
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
                inform(f"  Conflict — using existing {qid} for <{iri_str}>", verbose)
                return qid
            warn(
                f"  label-with-description-conflict but could not parse QID: {err}",
                verbose,
            )
        raise


def _push_class_metadata(
    qid: str,
    meta: dict,
    wikibase_api,
    verbose: int,
    overwrite_on_conflict: bool = False,
) -> None:
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

    # Labels (aliases_to_set initialized here so label-conflict branch can use it)
    labels_to_set = {}
    aliases_to_set = {}
    for lang, value in meta["labels"].items():
        if not lang:
            continue
        value = value.strip()
        current = existing_labels.get(lang)
        if current is None:
            labels_to_set[lang] = {"language": lang, "value": value}
        elif " ".join(current.split()) == " ".join(value.split()):
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
                    f"schema='{value}', Wikibase='{current}': "
                    f"adding '{value}' as alias.",
                    verbose,
                )
                already_alias = existing_aliases.get(lang, set())
                if value not in already_alias and " ".join(value.split()) != " ".join(
                    current.split()
                ):
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
                    f"  [{qid}] Overwriting description@{lang}: "
                    f"'{current}' to '{value}'",
                    verbose,
                )
                descriptions_to_set[lang] = {"language": lang, "value": value}
            else:
                warn(
                    f"  [{qid}] Description conflict @{lang}: "
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
            if " ".join(v.split()) not in already_alias
            and " ".join(v.split()) != " ".join(existing_label.split())
        ]
        if new_values:
            aliases_to_set.setdefault(lang, []).extend(
                {"language": lang, "value": v} for v in new_values
            )
    if aliases_to_set:
        entity_data["aliases"] = aliases_to_set

    if not entity_data:
        return

    inform(f"  [{qid}] Pushing metadata diff: {list(entity_data.keys())} …", verbose)
    wikibase_api.edit_entity(qid, entity_data)


def _push_subclass_claims(
    g: Graph,
    lookup: dict,
    wikibase_api,
    verbose: int,
) -> None:
    """
    Add rdfs:subClassOf claims for every rdfs:Class that declares a parent.
    Skips silently if the PID is missing from lookup.
    """
    subclassof_pid = (
        lookup.get("properties", {}).get(str(RDFS.subClassOf), {}).get("id")
    )
    if subclassof_pid is None:
        warn(
            "  rdfs:subClassOf PID not found in lookup. Skipping subclass claims.",
            verbose,
        )
        return

    for child_iri, _, parent_iri in g.triples((None, RDFS.subClassOf, None)):
        if (child_iri, RDF.type, RDFS.Class) not in g:
            continue

        child_str = str(child_iri)
        parent_str = str(parent_iri)
        child_qid = lookup["items"].get(child_str)
        parent_qid = lookup["items"].get(parent_str)

        if child_qid is None:
            warn(f"  Child <{child_str}> not in lookup, skipping subClassOf.", verbose)
            continue
        if parent_qid is None:
            warn(
                f"  Parent <{parent_str}> not in lookup, skipping subClassOf.", verbose
            )
            continue

        try:
            wikibase_api.add_item_claim(
                subject_qid=child_qid,
                property_pid=subclassof_pid,
                value=parent_qid,
            )
        except Exception as exc:
            warn(f"  Could not add subClassOf claim on {child_qid}: {exc}", verbose)


def resolve_schema_classes(
    schema_graph: Graph,
    lookup: dict,
    wikibase_api,
    language_resolver: LanguageResolver,
    verbose: int = 1,
) -> None:
    """
    Main entry point for class resolution.
      1. For each rdfs:Class not yet in lookup["items"]: find or create it.
      2. Push metadata diff (labels, descriptions, aliases).
      3. Add rdfs:subClassOf claims (builtins must already be resolved).
    """
    lookup.setdefault("items", {})

    for class_iri in sorted(schema_graph.subjects(RDF.type, RDFS.Class)):
        iri_str = str(class_iri)
        meta = _collect_class_metadata(
            schema_graph, class_iri, language_resolver, verbose=verbose
        )

        if iri_str not in lookup["items"]:
            qid = _resolve_one_class(
                class_iri,
                meta,
                wikibase_api,
                language_resolver.language,
                verbose,
                lookup=lookup,
            )
            lookup["items"][iri_str] = qid

        _push_class_metadata(lookup["items"][iri_str], meta, wikibase_api, verbose)

    _push_subclass_claims(schema_graph, lookup, wikibase_api, verbose)
