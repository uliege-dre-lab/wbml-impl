LABEL_Q = """
SELECT ?s ?label ?lang WHERE {
    ?s <http://www.w3.org/2000/01/rdf-schema#label> ?label .
    BIND(LANG(?label) AS ?lang)
}
"""

ALIAS_Q = """
SELECT ?s ?alias ?lang
WHERE {
  ?s ?p ?alias .
  FILTER (
    ?p = <http://www.w3.org/2004/02/skos/core#altLabel> ||
    ?p = <http://schema.org/alternateName> ||
    ?p = <https://schema.org/alternateName>
  )
  BIND(LANG(?alias) AS ?lang)
}
"""

DESCRIPTION_Q = """
SELECT ?s ?description ?lang
WHERE {
  ?s ?p ?description .
  FILTER (
    ?p = <http://schema.org/description> ||
    ?p = <https://schema.org/description> ||
    ?p = <http://www.w3.org/2000/01/rdf-schema#comment>
  )
}
"""

BUILTINS_Q = """
SELECT DISTINCT ?p
WHERE {
  ?s ?p ?o .
  FILTER (
    ?p = <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ||
    ?p = <http://www.w3.org/2000/01/rdf-schema#subClassOf> ||
    ?p = <http://www.w3.org/2002/07/owl#sameAs>
  )
}
"""


def build_main_properties_query(property_prefix: str) -> str:
    return f"""
    SELECT DISTINCT ?p
    WHERE {{
      ?s ?p ?o .
      FILTER(STRSTARTS(STR(?p), "{property_prefix}"))
    }}
    """


def build_qualifier_properties_query(qualifier_prefix: str) -> str:
    return f"""
    SELECT DISTINCT ?p
    WHERE {{
      ?s ?p ?o .
      FILTER(STRSTARTS(STR(?p), "{qualifier_prefix}"))
    }}
    """


def build_reference_properties_query(reference_prefix: str) -> str:
    return f"""
    SELECT DISTINCT ?p
    WHERE {{
      ?s ?p ?o .
      FILTER(STRSTARTS(STR(?p), "{reference_prefix}"))
    }}
    """


def build_items_query(item_prefix: str) -> str:
    return f"""
    SELECT DISTINCT ?x
    WHERE {{
      {{
        ?x ?p ?o .
        FILTER(isIRI(?x))
        FILTER(STRSTARTS(STR(?x), "{item_prefix}"))
      }}
      UNION
      {{
        ?s ?p ?x .
        FILTER(isIRI(?x))
        FILTER(STRSTARTS(STR(?x), "{item_prefix}"))
      }}
    }}
    """


def build_direct_claims_query(item_prefix: str, property_prefix: str) -> str:
    return f"""
    SELECT ?s ?p ?o
    WHERE {{
      ?s ?p ?o .
      FILTER(STRSTARTS(STR(?s), "{item_prefix}"))
      FILTER(STRSTARTS(STR(?p), "{property_prefix}"))
      FILTER(
        isLiteral(?o) ||
        (isIRI(?o) && STRSTARTS(STR(?o), "{item_prefix}"))
      )
    }}
    """


def build_statement_links_query(
    item_prefix: str, property_prefix: str, statement_prefix: str
) -> str:
    return f"""
    SELECT ?item ?prop ?stmt
    WHERE {{
      ?item ?prop ?stmt .
      FILTER(STRSTARTS(STR(?item), "{item_prefix}"))
      FILTER(STRSTARTS(STR(?prop), "{property_prefix}"))
      FILTER(STRSTARTS(STR(?stmt), "{statement_prefix}"))
    }}
    """


def build_statement_values_query(
    statement_prefix: str, property_prefix: str, item_prefix: str
) -> str:
    return f"""
    SELECT ?stmt ?prop ?value
    WHERE {{
      ?stmt ?prop ?value .
      FILTER(STRSTARTS(STR(?stmt), "{statement_prefix}"))
      FILTER(STRSTARTS(STR(?prop), "{property_prefix}"))
      FILTER(
        isLiteral(?value) ||
        (isIRI(?value) && STRSTARTS(STR(?value), "{item_prefix}"))
      )
    }}
    """


def build_qualifiers_query(
    statement_prefix: str, qualifier_prefix: str, item_prefix: str
) -> str:
    return f"""
    SELECT ?stmt ?qp ?value
    WHERE {{
      ?stmt ?qp ?value .
      FILTER(STRSTARTS(STR(?stmt), "{statement_prefix}"))
      FILTER(STRSTARTS(STR(?qp), "{qualifier_prefix}"))
      FILTER(
        isLiteral(?value) ||
        (isIRI(?value) && STRSTARTS(STR(?value), "{item_prefix}"))
      )
    }}
    """


def build_references_query(
    statement_prefix: str, reference_prefix: str, item_prefix: str
) -> str:
    return f"""
    SELECT ?stmt ?rp ?value
    WHERE {{
      ?stmt ?rp ?value .
      FILTER(STRSTARTS(STR(?stmt), "{statement_prefix}"))
      FILTER(STRSTARTS(STR(?rp), "{reference_prefix}"))
      FILTER(
        isLiteral(?value) ||
        (isIRI(?value) && STRSTARTS(STR(?value), "{item_prefix}"))
      )
    }}
    """
