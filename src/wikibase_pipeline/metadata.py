from collections import defaultdict

from .queries import ALIAS_Q, DESCRIPTION_Q, LABEL_Q
from .utils import inform


def collect_metadata(g, language: str, verbose: int) -> dict:
    metadata = defaultdict(
        lambda: {
            "labels": {},
            "aliases": defaultdict(list),
            "descriptions": {},
        }
    )

    for row in g.query(LABEL_Q):
        iri = str(row.s)
        lang = str(row.lang) if row.lang else language
        metadata[iri]["labels"][lang] = str(row.label)

    for row in g.query(ALIAS_Q):
        iri = str(row.s)
        lang = str(row.lang) if row.lang else language
        metadata[iri]["aliases"][lang].append(str(row.alias))

    for row in g.query(DESCRIPTION_Q):
        iri = str(row.s)
        lang = str(row.lang) if row.lang else language
        metadata[iri]["descriptions"][lang] = str(row.description)

    inform(f"Collected metadata for {len(metadata)} resources.", verbose)
    return metadata


def pick_best_label(
    iri: str, metadata: dict, preferred_langs: tuple[str, ...] = ("en", "fr")
) -> str | None:
    labels = metadata.get(iri, {}).get("labels", {})

    for lang in preferred_langs:
        if lang in labels:
            return labels[lang]

    if labels:
        return next(iter(labels.values()))

    return None


def strip_namespace(iri: str, prefix: str) -> str:
    if not iri.startswith(prefix):
        raise ValueError(f"IRI {iri!r} does not start with prefix {prefix!r}")
    return iri[len(prefix) :]
