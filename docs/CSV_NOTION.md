# Use case: Notion ontology export (CSV)

This document describes the use of the pipeline over CSV files exported from a Notion workspace.

---

## 1. Dataset Overview

The dataset comes from a Notion workspace that describes an ontology for a university research platform (RISE). The ontology covers the publicly accessible information about the platform: its classes, data properties, and object properties.

The `csv_notion/` folder contains the following source files used by the mapping:

| File | Description |
|---|---|---|
| `classes_with_english_translations.csv` | All ontology classes, with French and English labels, aliases, descriptions, and parent class hierarchy |
| `data_properties_with_english_translations.csv` | Data properties (attributes with literal values), with their scope (`Portée`), domain, cardinality, and good practices |
| `object_properties_with_english_translations.csv` | Object properties (relationships between classes), with their domain, range class, inverse, and good practices |

> The `_all` variants of the original Notion exports are unfiltered raw dumps. The `_with_english_translations` files are the cleaned and enriched versions that the pipeline actually uses (from https://github.com/chrdebru/wikibase-release-pipeline/tree/main)

---

## 2. CSV File Structure

### `classes_with_english_translations.csv`

| Column | Description |
|---|---|
| `Nom de la classe` | French name of the class — used as the node key and French label |
| `Autres labels` | Alternative French labels (aliases) |
| `Description` | French description |
| `Hiérarchie (classe parent)` | Parent class name, used to generate `rdfs:subClassOf` statements |
| `English name` | English label |
| `Alternative labels (EN)` | English aliases |
| `Description (EN)` | English description |

### `data_properties_with_english_translations.csv`

| Column | Description |
|---|---|
| `Nom` | French name of the property — used as the node key and French label |
| `Portée` | Value scope: `String`, `URL`, `URI`, or `DateTime` — used to split the mapping by Wikibase datatype |
| `Description` | French description |
| `Domaine` | Domain class (informational, not mapped as a statement) |
| `Bonnes pratiques` | Free-text good practice notes — mapped as a string statement |
| `Cardinalité` | Cardinality annotation — mapped as a string statement |
| `English name` | English label |
| `Description (EN)` | English description |

### `object_properties_with_english_translations.csv`

| Column | Description |
|---|---|
| `Nom` | French name of the property — used as the node key and French label |
| `Description` | French description |
| `Domaine` | Domain class (informational, not mapped as a statement) |
| `Portée` | Range class name — mapped as a `wbml:item` statement via `wbml:nodeTemplate "Class_{range_class}"` |
| `Inverse` | Inverse property name — mapped as a string statement |
| `Bonnes pratiques` | Free-text good practice notes — mapped as a string statement |
| `Cardinalité` | Cardinality annotation — mapped as a string statement |
| `English name` | English label |
| `Description (EN)` | English description |

---

## 3. Mapping Design

The mapping is defined in `data/mappings/wbml_notion.ttl`.

### Multiple TriplesMaps for the same kind of data

In WBML, the `wbml:propertyType` of a `wbml:propertyEntityMap` is a static value written directly in the mapping file. It cannot be dynamically derived from a data column at runtime. This means it is not possible to write a single TriplesMap that reads the `Portée` column and automatically assigns `wbml:string`, `wbml:url`, or `wbml:time` based on its value.

Therefore, the mapping splits the same CSV into multiple TriplesMap, each covering a different subset of rows filtered by the `Portée` column. Each TriplesMap declares its own fixed `wbml:propertyType`. The filtering is done at the SQL level inside `rml:logicalSource`.

---

### TriplesMap breakdown

#### `<#ClassMapping>` — class labels and descriptions

- **Source:** `classes_with_english_translations.csv`
- **Filter:** rows where `Nom de la classe` is not null or empty
- **Subject:** `wbml:itemMap` with `wbml:nodeTemplate "Class_{name}"`
- **Purpose:** creates one Wikibase item per class and pushes French and English labels, aliases, and descriptions.

#### `<#ClassesHierarchyMapping>` — subclass relationships

- **Source:** `classes_with_english_translations.csv`
- **Filter:** rows where both `Nom de la classe` and `Hiérarchie (classe parent)` are not null or empty
- **Subject:** same `wbml:itemMap` as above — same class items
- **Purpose:** adds a single `rdfs:subClassOf` statement per class that has a declared parent. This is separated from the first mapping because most rows do not have a parent.

#### `<#StringDataPropertyMapping>` — data properties with string scope

- **Source:** `data_properties_with_english_translations.csv`
- **Filter:** rows where `Portée` is not `URL`, `URI`, or `DateTime` (catches `String` and any unspecified scope)
- **Subject:** `wbml:propertyEntityMap` with `wbml:nodeTemplate "Property_{name}"` and `wbml:propertyType wbml:string`
- **Statements added:** `goodPractice` (string) and `cardinality` (string)

#### `<#URLDataPropertyMapping>` — data properties with URL scope

- **Source:** `data_properties_with_english_translations.csv`
- **Filter:** rows where `Portée` is `URL` or `URI`
- **Subject:** `wbml:propertyEntityMap` with `wbml:nodeTemplate "Property_{name}"` and `wbml:propertyType wbml:url`

#### `<#TimeDataPropertyMapping>` — data properties with date/time scope

- **Source:** `data_properties_with_english_translations.csv`
- **Filter:** rows where `Portée` is exactly `DateTime`
- **Subject:** `wbml:propertyEntityMap` with `wbml:nodeTemplate "Property_{name}"` and `wbml:propertyType wbml:time`

#### `<#ObjectPropertyMapping>` — object properties

- **Source:** `object_properties_with_english_translations.csv`
- **Filter:** rows where `Nom` is not null or empty
- **Subject:** `wbml:propertyEntityMap` with `wbml:nodeTemplate "Property_{name}"` and `wbml:propertyType wbml:item`
- **Statements added:**
  - `goodPractice` (string) — free-text recommendations
  - `cardinality` (string) — cardinality annotation
  - `inverse` (string) — name of the inverse property
  - `rangeClass` (item) — points to the range class via `wbml:nodeTemplate "Class_{range_class}"`, which resolves to the corresponding Wikibase item

---

### The auxiliary properties

The statements added to each property entity (good practice, cardinality, inverse, range class) are themselves Wikibase properties. They are declared as inline `rdf:Property` blank nodes inside the `wbml:statementMap`, rather than as top-level named nodes.

```turtle
wbml:statementMap [
  wbml:propertyMap [
    a rdf:Property ;
    wbml:nodeTemplate "goodPractice" ;
    rdfs:label "Good practice"@en ;
    rdfs:label "Bonnes pratiques"@fr ;
    wbml:propertyType wbml:string
  ] ;
  wbml:valueMap [
    wbml:reference "good_practices"
  ]
] ;
```

The `rangeClass` property is declared as `wbml:propertyType wbml:item` because its value is a node template pointing to a class item — not a plain string.

---

## 4. Limitations

### Static property types require manual split

If a new scope type is added to the Notion workspace (for example `quantity` or `external-id`), a new TriplesMap block must be added to `wbml_notion.ttl` manually with the appropriate `wbml:propertyType` and SQL filter. There is no way to make this automatic with the current WBML design.

### Domain column is informational only

The `Domaine` column in both property CSV files is not mapped to any Wikibase statement. It contains references to Notion pages rather than clean class names, making it unsuitable for direct use as an item link.
