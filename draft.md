# IGOOR GraphRAG Integration Proposal

This document restructures the original draft into an actionable plan for introducing a graph-based retrieval augmentation layer tailored to IGOOR’s patient-support focus. It aligns technical design with the existing plugin ecosystem so implementation tasks can be decomposed and scheduled.

## 1. Objectives & Scope

- **Goal**: enrich IGOOR’s knowledge retrieval with a patient-centric graph that captures entities, relationships, and temporal context across conversations, memories, and documents.
- **Drivers**: better cross-conversation grounding, more relevant patient summaries, and richer follow-up prompts for caregivers.
- **Out of scope (initially)**: UI visualization beyond summary widgets, large-scale model fine-tuning, and external graph databases.

## 2. Architectural Touchpoints

| Component | Required additions | Notes |
|-----------|-------------------|-------|
| `rag` plugin | ingest graph metadata alongside vector chunks; expose graph-aware query methods | keep FAISS workflow intact; GraphRAG logic should be an optional path |
| `memory` plugin | emit structured events (entities + relations) when persisting conversations | reuse existing summarization hooks, add schema-compliant payload |
| `speakerid` plugin | map voice fingerprints to PERSON entities | use canonical identifiers to attach speaker metadata |
| `prompt_manager` | provide prompt templates for ontology-aligned extraction | enforce confidence thresholds before inserting data |
| background jobs (new) | schedule centrality recomputation & consistency audits | run via async task runner or lightweight scheduler within plugin |

Implementation should follow plugin lifecycle hooks: `on_message`, `on_memory_persisted`, `on_query`. Data enrichment happens post-vectorization to avoid blocking latency-critical paths.

## 3. Data Model Enhancements (SQLite)

### 3.1 Core Entities

```sql
CREATE TABLE IF NOT EXISTS rag_entities (
    id INTEGER PRIMARY KEY,
    entity_uuid TEXT UNIQUE NOT NULL,         -- Stable cross-plugin identifier
    canonical_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,                -- PERSON | EVENT | CONDITION | LOCATION
    properties TEXT DEFAULT '{}',             -- JSON for type-specific fields
    confidence REAL DEFAULT 0.8,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rag_entities_type ON rag_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_rag_entities_name ON rag_entities(canonical_name);
```

### 3.2 Alias Normalization

```sql
CREATE TABLE IF NOT EXISTS rag_entity_aliases (
    id INTEGER PRIMARY KEY,
    entity_uuid TEXT NOT NULL,
    alias TEXT NOT NULL,
    alias_type TEXT DEFAULT 'nickname',       -- nickname | cultural | misspelling | system
    confidence REAL DEFAULT 0.7,
    source TEXT,                              -- llm_extraction | user | resolved_conflict
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    UNIQUE(entity_uuid, alias),
    FOREIGN KEY (entity_uuid) REFERENCES rag_entities(entity_uuid)
);

CREATE INDEX IF NOT EXISTS idx_rag_alias_alias ON rag_entity_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_rag_alias_entity ON rag_entity_aliases(entity_uuid);
```

### 3.3 Relationships & Edge Hygiene

```sql
CREATE TABLE IF NOT EXISTS rag_relationships (
    id INTEGER PRIMARY KEY,
    source_uuid TEXT NOT NULL,
    target_uuid TEXT NOT NULL,
    relationship_type TEXT NOT NULL,          -- treated_by | experienced_symptom | lives_with | occurred_before | ...
    context_id INTEGER,                       -- conversation_threads.id or document id
    evidence_snippet TEXT,
    confidence REAL DEFAULT 0.7,
    strength REAL DEFAULT 0.5,                -- derived weighting (0-1)
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_uuid, target_uuid, relationship_type, context_id),
    FOREIGN KEY (source_uuid) REFERENCES rag_entities(entity_uuid),
    FOREIGN KEY (target_uuid) REFERENCES rag_entities(entity_uuid)
);

CREATE INDEX IF NOT EXISTS idx_rag_relationships_type ON rag_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_rag_relationships_source ON rag_relationships(source_uuid);
CREATE INDEX IF NOT EXISTS idx_rag_relationships_target ON rag_relationships(target_uuid);
```

### 3.4 Centrality & Derived Metrics

```sql
CREATE TABLE IF NOT EXISTS rag_entity_metrics (
    entity_uuid TEXT PRIMARY KEY,
    degree_centrality REAL DEFAULT 0,
    betweenness_centrality REAL DEFAULT 0,
    recency_score REAL DEFAULT 0,
    last_calculated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entity_uuid) REFERENCES rag_entities(entity_uuid)
);
```

### 3.5 Data Integrity Safeguards

- Define triggers to bump `last_updated_at` and deduplicate aliases.
- Store ontology mappings in separate lookup tables (`rag_ontology_mappings`) to anchor SNOMED/UMLS codes without bloating core tables.
- Adopt UUID generation helper shared across plugins to avoid collision.

## 4. Ingestion & Graph Construction Pipeline

1. **Chunk ingestion (existing RAG flow):** store vector chunks in FAISS and metadata in `rag_chunks`.
2. **Extraction stage (new):** 
   - Prompt via `prompt_manager` with ontology-specific templates.
   - Validate responses against schema (required fields, confidence thresholds).
3. **Entity resolution:**
   - Attempt canonical lookup by UUID, alias, fuzzy match (within plugin scope).
   - Score matches using weighted sum (aliases 40%, context 40%, name similarity 20%).
   - Auto-merge when score ≥ 0.85, queue for review (Phase 2) when in [0.6, 0.85).
4. **Relationship creation:** enforce `source_uuid != target_uuid` and prevent duplicates via UNIQUE constraint.
5. **Metric update:** enqueue background job to recompute centrality nightly or when edge count delta passes threshold.
6. **Audit logging:** append ingestion events to `rag_graph_audit` (table to be created) for observability and rollback.

The ingestion pipeline should run asynchronously to avoid blocking live user sessions; leverage existing task execution framework or add a lightweight worker in the plugin.

## 5. Query & Retrieval Flow

1. Resolve user query intent (existing semantic classification).
2. **Graph-first lookup:**
   - Identify candidate entities (top-k by centrality + recency) using graph search.
   - Expand via relationship hops constrained by ontology (e.g., PERSON→CONDITION, EVENT→LOCATION) and time filters.
3. **Hybrid retrieval:** combine graph-derived candidate chunks with FAISS vector results (e.g., 50/50 blend) using RRF or weighted sum.
4. **Answer synthesis:**
   - Provide canonical names, list relevant aliases in tooltips (UI phase).
   - Surface relationship context to LLM prompt to reduce hallucinations.
5. **Follow-up suggestions:** generate next-step prompts based on high-strength edges not covered in answer (Phase 3).

## 6. Ontology Strategy

### 6.1 MVP Taxonomy

- **PERSON**: patient, family_member, clinician, caregiver.
- **CONDITION**: chronic_condition, acute_condition, symptom.
- **EVENT**: diagnosis, treatment, hospitalization, life_event.
- **RELATIONSHIPS**: treated_by, experienced_symptom, lives_with, occurred_before.

Store ontology definitions in JSON fixtures consumed by plugins to keep extraction prompts consistent.

### 6.2 External Code Integration

- Map CONDITIONS to SNOMED CT where coverage exists; fallback to ICD-10 if missing.
- For medications, populate RxNorm codes. Keep a `rag_external_codes` table with fields `(entity_uuid, system, code, display_name)`.

### 6.3 Evolution Plan (Phase 3+)

- Expand PERSON subtypes (support_worker, pharmacist) as data volume grows.
- Introduce emotional_state nodes only once UI can surface them responsibly.

## 7. Coherence & Maintenance

### 7.1 Entity Resolution Service

- Reuse alias indexes and maintain `rag_resolution_queue` for borderline matches requiring human input.
- Track resolution history in `rag_entity_history` (entity_uuid, field, old_value, new_value, source, timestamp).

### 7.2 Temporal Consistency Checks

- Scheduled job scans for conflicting ages or timelines (e.g., EVENT dates out of sequence) and flags via `status_manager` notifications.

### 7.3 Background Jobs

| Job | Frequency | Purpose |
|-----|-----------|---------|
| `graph_recompute_centrality` | nightly | refresh `rag_entity_metrics` |
| `graph_resolution_audit` | every 6h | process resolution queue & update alias confidence |
| `graph_data_retention` | weekly | prune low-confidence orphan entities |

### 7.4 Human-in-the-Loop Hooks

- Provide plugin API `request_entity_review(entity_uuid, reason)` to surface tasks inside operator dashboard.
- Log user corrections and feed them back into alias confidence adjustments.

## 8. Implementation Roadmap

| Phase | Duration (est.) | Deliverables |
|-------|-----------------|--------------|
| **P0 – Foundations** | 2 sprints | Schema migration, UUID helper, alias table, ingestion scaffolding, background job stubs |
| **P1 – MVP GraphRAG** | 2–3 sprints | Entity/relationship extraction integrated into RAG plugin, basic hybrid retrieval, nightly centrality computation |
| **P2 – Patient Enrichment** | 2 sprints | Confidence scoring, resolution queue, ontology mapping to SNOMED/ICD/RxNorm, temporal filters |
| **P3 – Operationalization** | 2 sprints | Dashboards for audits, follow-up suggestion generation, speaker linking, basic UI widgets |
| **P4 – Visualization (optional)** | tbd | Graph UI, timeline views, interactive exploration |

Each phase requires regression testing across `tests/` modules; add new unit/integration tests for ingestion and retrieval steps.

## 9. Metrics & Monitoring

- **Accuracy**: % of answers referencing correct canonical entities (sampled weekly).
- **Coverage**: number of entities/relationships per patient session.
- **Freshness**: median time from new conversation fact to graph availability.
- **Conflict Rate**: count of items in resolution queue over trailing 7 days.
- **Latency**: additional milliseconds added by graph-enhanced query flow (target < 150 ms).

Instrument metrics using existing logging plus lightweight SQLite summary tables (`rag_metrics_daily`). Export aggregated stats to the monitoring pipeline already used by `status_manager`.

## 10. Next Steps Checklist

1. Sign off on schema migrations and data retention policy.
2. Implement UUID generation utility in shared utils.
3. Add extraction prompts aligned with MVP ontology.
4. Prototype ingestion worker with mocked LLM output.
5. Draft tests to validate alias resolution and relationship deduplication.

This structured plan should enable incremental delivery while preserving coherence across IGOOR’s existing plugins and operational workflows.