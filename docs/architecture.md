# Public Health Outbreak Intelligence - Architecture

## Overview

The Public Health Outbreak Intelligence system is designed as a local, deterministic pipeline for collecting, processing, and presenting public health notices from approved sources. The architecture follows a modular, layered approach to ensure maintainability, testability, and transparency.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Public Health Outbreak Intelligence              │
├─────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │   CLI       │    │   Config    │    │   Database  │          │
│  │   Module    │    │   Module    │    │   Module    │          │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘          │
│         │                  │                  │                 │
│         └──────────────────┼──────────────────┘                 │
│                            │                                      │
│                            ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Services Layer                          │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │                 Pipeline Service                     │    │   │
│  │  │  - run_pipeline()                                   │    │   │
│  │  │  - run_demo_pipeline()                              │    │   │
│  │  │  - process_event()                                 │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                      │
│         ┌──────────────────┼──────────────────┐                 │
│         │                  │                  │                 │
│         ▼                  ▼                  ▼                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │  Collectors  │    │  Extraction  │    │    Triage   │          │
│  │   Module    │    │   Module    │    │   Module    │          │
│  │             │    │             │    │             │          │
│  │  - CDC HAN  │    │  - Heuristic│    │  - Scoring  │          │
│  │  - CDC Out. │    │   Extractor │    │  - Dedup    │          │
│  │  - Idaho DHW│    │             │    │             │          │
│  │  - WHO DON  │    │             │    │             │          │
│  └─────────────┘    └─────────────┘    └─────────────┘          │
│         │                  │                  │                 │
│         └──────────────────┼──────────────────┘                 │
│                            │                                      │
│                            ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Models Layer                           │   │
│  │  - EventCard (Pydantic model)                            │   │
│  │  - SourceConfig                                         │   │
│  │  - Geography, ExplicitFact, etc.                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Module Structure

### 1. CLI Module (`cli.py`)
- **Purpose**: Command-line interface for the system
- **Commands**:
  - `init-db`: Initialize the database
  - `run --demo`: Run pipeline with fixture data
  - `run --live`: Run live collection from approved sources
  - `brief --date`: Generate Markdown briefing
  - `events list/show`: Manage and view events
  - `sources list/stats`: Manage and view sources
  - `health`: System health check

### 2. Config Module (`config.py`)
- **Purpose**: Configuration management
- **Features**:
  - Load configuration from YAML files
  - Environment variable overrides
  - Source configuration management
  - Scoring policy configuration

### 3. Database Module (`db.py`)
- **Purpose**: SQLite database operations
- **Features**:
  - Event storage and retrieval
  - Source metadata tracking
  - Collection run history
  - Pipeline run history
  - Indexed queries for performance

### 4. Models Module (`models.py`)
- **Purpose**: Data models and validation
- **Key Models**:
  - `EventCard`: Core event data structure
  - `SourceConfig`: Source configuration
  - `Geography`: Geographic information
  - `ExplicitFact`: Extracted factual information
  - `PriorityBand`: Priority classification
  - `ReviewStatus`: Review workflow status

### 5. Collectors Module
- **Purpose**: Data collection from approved sources
- **Base Class**: `BaseCollector` (abstract)
- **Implementations**:
  - `CDC_HAN_Collector`: CDC Health Alert Network
  - `CDC_Outbreaks_Collector`: CDC Outbreak Investigations
  - `Idaho_DHW_Collector`: Idaho Department of Health and Welfare
  - `WHO_DON_Collector`: WHO Disease Outbreak News

### 6. Extraction Module
- **Purpose**: Extract structured information from raw content
- **Base Class**: `BaseExtractor` (abstract)
- **Implementations**:
  - `HeuristicExtractor`: Deterministic rule-based extraction
- **Features**:
  - Disease/hazard extraction
  - Geography extraction
  - Count extraction (cases, deaths)
  - Fact extraction
  - Unknown extraction

### 7. Triage Module
- **Purpose**: Event prioritization and deduplication
- **Submodules**:
  - `scoring.py`: Deterministic scoring with transparent rules
  - `dedup.py`: Deduplication based on content hashing

### 8. Briefing Module
- **Purpose**: Generate Markdown briefings
- **Features**:
  - Organize events by priority band
  - Include source health information
  - Provide summary statistics
  - Add disclaimers and metadata

### 9. Services Module
- **Purpose**: Pipeline orchestration
- **Key Functions**:
  - `run_pipeline()`: Complete pipeline execution
  - `run_demo_pipeline()`: Demo mode with fixtures
  - `process_event()`: Individual event processing

## Data Flow

### Live Collection Flow
```
1. CLI Command: python -m outbreak_intel run --live
2. Pipeline Service: run_pipeline()
3. For each enabled source:
   a. Get collector for source
   b. Collector.collect() -> CollectorResult
   c. For each item in CollectorResult.items:
      i. Collector.parse_item() -> EventCard
      ii. Pipeline.process_event():
          - Extraction (if raw_content available)
          - Scoring
      iii. Check for duplicates (Database)
      iv. Save to database (if not duplicate)
   d. Save collection result
4. Return PipelineResult
```

### Demo Flow
```
1. CLI Command: python -m outbreak_intel run --demo
2. Pipeline Service: run_demo_pipeline()
3. Create demo events from fixtures
4. For each demo event:
   a. Pipeline.process_event():
      - Extraction (if raw_content available)
      - Scoring
   b. Check for duplicates (Database)
   c. Save to database (if not duplicate)
5. Return PipelineResult
```

### Briefing Generation Flow
```
1. CLI Command: python -m outbreak_intel brief --date YYYY-MM-DD
2. Briefing Service: generate_briefing()
3. Database: get_events_by_date()
4. Organize events by priority band
5. Format events as Markdown
6. Add source health information
7. Add summary statistics
8. Return Markdown string
```

## Scoring Algorithm

The scoring system uses deterministic, transparent rules with the following factors:

1. **Idaho / Pacific Northwest Relevance (0-35 points)**
   - Explicit Idaho mentions: 35 points
   - Pacific Northwest mentions: 17 points
   - Idaho DHW source: 35 points

2. **Healthcare / Infection-Prevention Relevance (0-25 points)**
   - Multiple healthcare terms: 25 points
   - Single healthcare term: 12-18 points
   - Healthcare settings affected: 25 points
   - CDC HAN/Outbreaks source: 18 points

3. **Official Urgency / Severity Signal (0-20 points)**
   - Health Alert event type: 20 points
   - Outbreak event type: 15 points
   - Investigation event type: 10 points
   - Urgency keywords: 15 points
   - High case counts (>1000): 20 points
   - Death counts (>0): 15 points

4. **US Travel / Importation Relevance (0-10 points)**
   - US geography: 10 points
   - US travel terms: 10 points
   - WHO DON source: 5 points

5. **Novelty (0-10 points)**
   - Multiple novelty terms: 10 points
   - Single novelty term: 5 points
   - Novel/emerging diseases: 10 points

### Priority Bands
- **75-100**: `urgent_human_review`
- **45-74**: `review_today`
- **20-44**: `monitor`
- **0-19**: `archive`

## Deduplication Strategy

1. **Content Hash**: SHA-256 hash of `source_url:content` for exact matching
2. **Time Window**: Check for duplicates within 24-hour window
3. **Similarity Matching**: 
   - Same source + similar title (Jaccard similarity > 0.9)
   - Same source + similar content hash
   - Same disease + similar geography

## Storage Schema

### SQLite Tables

1. **events**: Main event storage
   - event_id (PRIMARY KEY)
   - source_id, source_name, source_url
   - source_published_at, retrieved_at
   - title, disease_or_hazard, event_type
   - geographies_json, case_count, death_count
   - affected_settings_json, official_source
   - explicit_facts_json, unknowns_json, relevance_reasons_json
   - priority_score, priority_band, summary
   - content_hash, review_status
   - raw_content, metadata_json
   - created_at, updated_at

2. **sources**: Source metadata
   - source_id (PRIMARY KEY)
   - source_name, source_url, feed_url
   - enabled, priority
   - last_retrieved_at, last_success, last_error
   - created_at

3. **collection_runs**: Collection history
   - run_id (PRIMARY KEY)
   - started_at, completed_at, source_id
   - success, item_count, new_events, duplicate_events
   - error_message

4. **pipeline_runs**: Pipeline history
   - run_id (PRIMARY KEY)
   - started_at, completed_at
   - total_new_events, total_duplicate_events
   - errors_json

## Security and Safety Boundaries

- **No PHI**: Only public-source data is collected and stored
- **No Patient Data**: No patient identifiers, medical records, or personal information
- **No Credentials**: No API keys, passwords, or authentication tokens in source
- **No Automatic Notifications**: No email, Slack, webhooks, or desktop notifications
- **No Clinical Decision-Making**: System only routes items for human review
- **No Autonomous Actions**: No policy changes, no automatic escalations
- **Human Review Required**: Every surfaced item requires qualified human review

## Performance Considerations

- **SQLite**: Suitable for local, single-user operation
- **Indexing**: Appropriate indexes on frequently queried fields
- **Memory**: Events processed in memory, only stored after processing
- **Timeouts**: HTTP requests have configurable timeouts
- **Retries**: Failed requests are retried with exponential backoff

## Scalability

The current architecture is designed for:
- Local, single-user operation
- Small to medium-scale data collection
- Batch processing of events

For larger-scale deployment, consider:
- Migration to PostgreSQL or other database
- Distributed task queue (Celery, RQ)
- Horizontal scaling of collectors
- Caching layer for frequent queries
