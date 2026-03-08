# ATFE9009 – Wikibase RDF Pipeline

Declarative generation of Wikibase statements.

## Project Overview

This project is developed as part of the Master’s thesis in Engineering in Data Science.

The goal of this project is to design a **declarative pipeline** that generates Wikibase statements from structured data and inserts them into a Wikibase instance.

The pipeline handles:

- RDF generation from source data
- reconciliation of entities and properties with existing Wikibase entities
- creation of missing entities when necessary
- management of opaque IRIs through a lookup mechanism

The objective is to simplify and automate the process of integrating external data into Wikibase while preserving consistency with the existing knowledge graph.
