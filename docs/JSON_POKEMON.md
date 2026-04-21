# Use case: JSON Pokemon dataset

This document describes the use of the pipeline over a json dataset: Pokemon. It explains how the mapping was done.

---

## 1. Dataset Overview

The dataset comes from this repo: `https://github.com/Purukitto/pokemon-data.json.git`

The `json_pokemon/` folder contains four source files:

| File | Description | Notes |
|---|---|---|
| `pokedex_small.json` | Individual Pokémon entries (stats, abilities, evolutions, images, …) | Contains only the 50 first Pokémon due to the size of it |
| `types.json` | Elemental types and their effectiveness relationships | |
| `moves_small.json` | Learnable moves (power, accuracy, PP, category, …) | Contains only the 100 first moves due to the size of it |
| `items_small.json` | In-game items and their categories | Contains only the 100 first items due to the size of it |

The mapping was done over a subset of the full dataset since this is a small demonstration of the use case. The full dataset can also be added.

---

## 2. Classes in the Dataset

The mapping defines the following entity classes (`rdfs:Class`). Each becomes a Wikibase item that acts as a class node.

| Class | Source file | Entities | WBML declaration pattern |
|---|---|---|---|
| **Pokemon** | `pokedex_small.json` | Individual Pokémon (Bulbasaur, Pikachu, …) | Known Qid (`wbml:classId`) |
| **Ability** | `pokedex_small.json` | Skills a Pokémon can have (Overgrow, Blaze, …) | Named node (`wbml:class wbml:AbilityClass`) |
| **Species** | `pokedex_small.json` | Species classifications (Seed Pokémon, …) | Named node (`wbml:class wbml:SpeciesClass`) |
| **EggGroup** | `pokedex_small.json` | Breeding groups (Monster, Dragon, …) | Named node (`wbml:class wbml:EggGroupClass`) |
| **Type** | `types.json` | Elemental types (Fire, Water, Grass, …) | Named node (`wbml:class wbml:TypeClass`) |
| **Move** | `moves_small.json` | Learnable moves (Tackle, Flamethrower, …) | Named node (`wbml:class wbml:MoveClass`) |
| **Item** | `items_small.json` | In-game items (Potion, Ultra Ball, …) | Named node (`wbml:class wbml:ItemClass`) |
| **ItemCategory** | `items_small.json` | Category of an item (Medicine, Ball, …) | Inline blank node (embedded in `wbml:subjectMap`) |

---

## 3. Properties in the Dataset

Properties are declared as `rdf:Property` nodes with a `wbml:propertyType` that indicates the Wikibase datatype (`item`, `quantity`, `string`, `url`, `time`).

| Property | Label | Type | Pattern |
|---|---|---|---|
| `wbml:PokedexNumber` | Pokédex number | quantity | Named node |
| `wbml:HP` | HP | quantity | Named node |
| `wbml:Attack` | Attack | quantity | Named node |
| `wbml:Defense` | Defense | quantity | Named node |
| `wbml:SpecialAttack` | Special Attack | quantity | Named node |
| `wbml:SpecialDefense` | Special Defense | quantity | Named node |
| `wbml:Weight` | Weight | string | Named node |
| `wbml:Gender` | Gender | string | Named node |
| `wbml:HasSpecies` | has species | item | Named node |
| `wbml:HasAbility` | has ability | item | Named node |
| `wbml:IsHiddenAbility` | is hidden ability | string | Named node |
| `wbml:HasEggGroup` | has egg group | item | Named node |
| `wbml:PokemonHasType` | has type (Pokémon) | item | Named node |
| `wbml:MoveHasType` | has type (Move) | item | Named node |
| `wbml:EvolvesFrom` | evolves from | item | Named node |
| `wbml:EvolvesTo` | evolves to | item | Named node |
| `wbml:EvolutionCondition` | evolution condition | string | Named node |
| `wbml:EffectiveAgainst` | effective against | item | Named node |
| `wbml:IneffectiveAgainst` | ineffective against | item | Named node |
| `wbml:NoEffectAgainst` | no effect against | item | Named node |
| `wbml:HasImage` | has image | url | Named node |
| `wbml:ImageType` | Image Type | string | Named node |
| `wbml:ItemNumber` | Item Number | quantity | Named node |
| `wbml:HasItemCategory` | has item category | item | Named node |
| `wbml:Accuracy` | Accuracy | quantity | Named node |
| `wbml:Power` | Power | quantity | Named node |
| `wbml:PP` | PP | quantity | Named node |
| `wbml:MoveCategory` | Move Category | string | Named node |
| `wbml:TMNumber` | TM Number | quantity | Named node |
| `wbml:StatedIn` | stated in | string | Named node |
| `wbml:StatedOn` | stated on | time | Named node |
| *(Speed)* | Speed | quantity | Inline blank node (embedded in `wbml:predicateObjectMap`) |
| *(height)* | height | string | Known Pid (`wbml:predicateId "P56"`) |

---

## 4. Mapping design

The mapping is executed in two steps: schema creation (classes and properties) and data insertion (statements).
The mapping of the Pokemon dataset is defined in `data/mappings/wbml_pokemon.ttl`.

### Class and property definition

To test the different functionalities of the WBML language, the 3 ways to define a class and a property have been used.

**For classes:**

- **Inline blank node** — `ItemCategory` is embedded directly inside a `wbml:subjectMap` as an anonymous blank node. The class definition exists only once, local to the `<#ItemCategoryMapping>` triples map, and is not reused elsewhere. This pattern suits classes whose identity is derived from the data values themselves (here, the distinct `type` strings in `items_small.json`) and that do not need a stable top-level name in the mapping graph.

```turtle
wbml:subjectMap [
  wbml:nodeTemplate "ItemCategory_{type}" ;
  wbml:class [
    a rdfs:Class ;
    wbml:nodeTemplate "ItemCategory" ;
    rdfs:label "Item Category"@en
  ]
]
```

- **Known Qid from Wikibase** — `Pokemon` was created in advance in Wikibase. Using `wbml:classId "Q6999"` lets the pipeline directly point to that existing item instead of creating or resolving a new one. No schema query is run for this class.

```turtle
wbml:subjectMap [
  wbml:nodeTemplate "Pokemon_{id}" ;
  wbml:classId "Q6999"
]
```

- **Named node at the top of the mapping** — all other classes (`Ability`, `Type`, `EggGroup`, `Move`, `Item`, `Species`) are declared as named `rdfs:Class` resources at the top of the file and referenced by name in their respective `wbml:subjectMap`. This makes them reusable across multiple TriplesMap and allows the Schema CONSTRUCT query to collect them in a single pass.

```turtle
wbml:AbilityClass a rdfs:Class ;
  rdfs:label "Ability"@en ;
  rdfs:comment "A special power or skill that a Pokémon can have."@en .

<#AbilityMapping>
  ...
  wbml:subjectMap [
    wbml:nodeTemplate "Ability_{ability_name}" ;
    wbml:class wbml:AbilityClass
  ] .
```

**For properties:**

- **Inline blank node** — the `Speed` property is defined anonymously inside the `wbml:predicateObjectMap` that uses it, rather than being declared at the top of the file. The `Property_schema.rq` CONSTRUCT still picks it up because it has `a rdf:Property`.

```turtle
wbml:predicateObjectMap [
  wbml:predicate [
    a rdf:Property ;
    wbml:nodeTemplate "Speed" ;
    rdfs:label "Speed"@en ;
    wbml:propertyType wbml:quantity ;
    skos:altLabel "Base Speed"@en
  ] ;
  wbml:objectMap [ wbml:reference "base.Speed" ; wbml:datatype xsd:integer ]
] ;
```

- **Known Pid from Wikibase** — the `height` property was already created in Wikibase as `P56`. Using `wbml:predicateId "P56"` bypasses schema creation and resolves the property directly from the lookup.

```turtle
wbml:predicateObjectMap [
  wbml:predicateId "P56" ;
  wbml:objectMap [ wbml:reference "profile.height" ; wbml:datatype xsd:string ]
] ;
```

- **Named node at the top of the mapping** — all other properties (`wbml:Attack`, `wbml:HasAbility`, `wbml:EvolvesFrom`, etc.) are declared as named `rdf:Property` resources at the top of the file, referenced by name wherever they are used.

```turtle
wbml:Attack a rdf:Property ;
  rdfs:label "Attack"@en ;
  wbml:propertyType wbml:quantity .
```

---

### Ranks

The default rank is `Normal`. One statement in `wbml_pokedex.ttl` has been set to an explicit `PreferredRank` to exercise that feature:

**HasSpecies** on a Pokémon entry — the statement linking a Pokémon to its species classification is marked as preferred. This reflects that this is the primary and most specific description of the entity.

```turtle
wbml:predicateObjectMap [
  wbml:predicate [
    a rdf:Property ;
    wbml:nodeTemplate "HasSpecies" ;
    ...
  ] ;
  wbml:objectMap [ wbml:nodeTemplate "Species_{species}" ] ;
  wbml:rank wbml:PreferredRank
] ;
```

---

### Limitations

#### 1. Consequence of reducing the dataset

Since the dataset has been reduced to only 50 Pokémon, the dataset is a bit inconsistent. At the evolution of some Pokémon, their Pokédex numbers are higher than 50 so they are not found and have no mapping for them. Therefore the pipeline just take their `nodeTemplate` as the label and created them as items.

The affected evolutions are:

| Pokémon in dataset | Direction | Missing Pokémon (ID > 50) |
|---|---|---|
| Pikachu (#25) | evolves from | Pichu (#172) |
| Clefairy (#35) | evolves from | Cleffa (#173) |
| Jigglypuff (#39) | evolves from | Igglybuff (#174) |
| Golbat (#42) | evolves to | Crobat (#169) |
| Gloom (#44) | evolves to | Bellossom (#182) |
| Diglett (#50) | evolves to | Dugtrio (#51) |

This problem can be solved by taking the complete dataset.

#### 2. Identical labels for different items

The pipeline implemented aims to be used for small enterprises where the ontology and data should not have many items with the same or similar labels. Therefore label search only checks if an item has the same label or alias, and takes the item with the highest compatibility score when multiple items match.

However, in this dataset, the **Psychic Type** and the **Psychic Move** share the same English label. This results in the pipeline reusing the same Wikibase item for both instead of creating a distinct one for the Move. This is unfortunately unresolved in this work. Two workarounds exist: manually pre-creating both items in Wikibase with their respective labels and aliases so the score match selects the most compatible one, or adding them directly to the lookup file to bypass label search entirely.
