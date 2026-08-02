# Public Health Outbreak Intelligence

**Local, public-source outbreak-intelligence prototype for infection-prevention / healthcare audiences**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

## 🎯 Project Purpose

Public Health Outbreak Intelligence is a **local, deterministic system** that collects, normalizes, deduplicates, scores, and presents public health notices from approved sources. It is designed specifically for **infection-prevention and healthcare audiences** to support decision-making through organized, prioritized information.

### ✅ What This System Does

- **Collects** public notices from an approved source allowlist
- **Normalizes** notices into structured event cards with consistent fields
- **Deduplicates** repeat notices to avoid information overload
- **Scores** relevance with transparent, deterministic rules (no LLM APIs)
- **Produces** cited Markdown daily briefings for human review
- **Runs completely locally** without patient data, Epic access, credentials, cloud databases, email, or automatic notifications

### ❌ What This System Does NOT Do

- ❌ **Diagnose** - Does not interpret symptoms or provide medical diagnoses
- ❌ **Make Clinical Recommendations** - Does not suggest treatments or medical advice
- ❌ **Modify Policy** - Does not create or change healthcare policies
- ❌ **Autonomously Escalate Alerts** - Does not send automatic notifications or take actions
- ❌ **Access Protected Data** - Only uses public, non-PHI sources
- ❌ **Replace Human Judgment** - All output requires qualified human review

### 🎯 Intended Audience

- Infection prevention specialists
- Public health epidemiologists
- Healthcare quality and safety professionals
- Hospital and health system leadership
- Public health department staff

## 🚀 Quick Start

### Prerequisites

- **Python 3.12 or higher** (required)
- **Git** (for version control)
- **Windows, macOS, or Linux** (tested on all platforms)

### Installation

#### 1. Clone the Repository

```powershell
# Clone the repository
git clone https://github.com/Carlosdanger96/public-health-outbreak-intelligence.git
cd public-health-outbreak-intelligence

# Check out the development branch
git checkout agent/initial-outbreak-intelligence
```

#### 2. Set Up Python Environment

**Option A: Using venv (recommended for Windows)**

```powershell
# Create virtual environment
python -m venv .venv

# Activate the environment
.\.venv\Scripts\activate

# Install the package and dependencies
pip install -e ".[dev]"
```

**Option B: Using conda**

```powershell
# Create conda environment
conda create -n outbreak-intel python=3.12
conda activate outbreak-intel

# Install the package and dependencies
pip install -e ".[dev]"
```

#### 3. Initialize the Database

```powershell
# Initialize the SQLite database
python -m outbreak_intel init-db
```

This creates a `data/outbreak_intel.db` file with the required schema.

### 🏃‍♂️ Running the System

#### Demo Mode (Recommended First Run)

```powershell
# Run with fixture data - works immediately, no internet required
python -m outbreak_intel run --demo
```

This will:
- Create demo events from fixture data
- Process them through extraction and scoring
- Save them to the database
- Display collection results

#### Live Collection Mode

```powershell
# Run with live data from approved sources
python -m outbreak_intel run --live
```

⚠️ **CAUTION**: Live collection makes HTTP requests to public health websites. Use responsibly and respect source terms of service.

#### Generate a Briefing

```powershell
# Generate today's briefing
python -m outbreak_intel brief --date 2024-01-15

# Or for today's date (automatic)
python -m outbreak_intel brief

# Save to file
python -m outbreak_intel brief --output briefing_2024-01-15.md
```

#### View Events

```powershell
# List all events
python -m outbreak_intel events list

# List events with filters
python -m outbreak_intel events list --priority urgent_human_review
python -m outbreak_intel events list --source cdc_han
python -m outbreak_intel events list --limit 10

# Show a specific event
python -m outbreak_intel events show EVENT_ID
```

#### Check System Health

```powershell
# Check system status
python -m outbreak_intel health
```

## 📁 Project Structure

```text
public-health-outbreak-intelligence/
├── README.md                    # This file
├── pyproject.toml               # Project configuration and dependencies
├── .gitignore                   # Git ignore patterns
├── .env.example                 # Environment variable template
├── LICENSE                      # MIT License
│
├── src/
│   └── outbreak_intel/          # Main package
│       ├── __init__.py          # Package initialization
│       ├── cli.py               # Command-line interface
│       ├── config.py            # Configuration management
│       ├── db.py                # Database operations
│       ├── models.py            # Data models (Pydantic)
│       │
│       ├── collectors/          # Data collection modules
│       │   ├── __init__.py       # Collector exports
│       │   ├── base.py           # Base collector class
│       │   ├── cdc_han.py        # CDC Health Alert Network collector
│       │   ├── cdc_outbreaks.py   # CDC Outbreak Investigations collector
│       │   ├── idaho_dhw.py      # Idaho DHW collector
│       │   └── who_don.py        # WHO Disease Outbreak News collector
│       │
│       ├── extraction/          # Data extraction modules
│       │   ├── __init__.py       # Extractor exports
│       │   ├── base.py           # Base extractor class
│       │   └── heuristic.py      # Deterministic heuristic extractor
│       │
│       ├── triage/              # Event triage modules
│       │   ├── __init__.py       # Triage exports
│       │   ├── scoring.py        # Deterministic scoring algorithm
│       │   └── dedup.py          # Deduplication logic
│       │
│       ├── briefing/            # Briefing generation modules
│       │   ├── __init__.py       # Briefing exports
│       │   └── markdown.py       # Markdown briefing generator
│       │
│       └── services/            # Service modules
│           ├── __init__.py       # Service exports
│           └── pipeline.py       # Main processing pipeline
│
├── config/                      # Configuration files
│   ├── sources.yaml             # Approved source configurations
│   └── scoring_policy.yaml      # Scoring policy configuration
│
├── data/                        # Data directory
│   ├── fixtures/                # Sample data for testing
│   │   ├── cdc_han_sample.html  # CDC HAN sample page
│   │   ├── idaho_dhw_sample.html # Idaho DHW sample page
│   │   └── who_don_sample.html  # WHO DON sample page
│   └── outbreak_intel.db        # SQLite database (gitignored)
│
├── docs/                        # Documentation
│   ├── architecture.md          # System architecture
│   ├── source-governance.md     # Source management policy
│   ├── safety-boundaries.md     # Safety constraints and boundaries
│   └── evaluation-plan.md       # Evaluation methodology
│
└── tests/                       # Test files
    ├── __init__.py
    ├── test_extraction.py        # Extraction tests
    ├── test_dedup.py            # Deduplication tests
    ├── test_scoring.py          # Scoring tests
    └── test_briefing.py         # Briefing tests
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file (copied from `.env.example`) to customize the system:

```bash
# Database path
DATABASE_PATH=data/outbreak_intel.db

# HTTP settings
USER_AGENT=PublicHealthOutbreakIntelligence/0.1.0 (+https://github.com/Carlosdanger96/public-health-outbreak-intelligence)
HTTP_TIMEOUT=30
MAX_RETRIES=3

# Demo mode (default: false)
DEMO_MODE=false

# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO
```

### Source Configuration

Approved sources are configured in `config/sources.yaml`:

```yaml
sources:
  - source_id: cdc_han
    source_name: CDC Health Alert Network
    source_url: https://emergency.cdc.gov/han/
    feed_url: https://emergency.cdc.gov/han/han-rss.asp
    enabled: true
    priority: 10
    timeout: 30

  - source_id: cdc_outbreaks
    source_name: CDC Outbreak Investigations
    source_url: https://www.cdc.gov/outbreaks/index.html
    enabled: true
    priority: 9
    timeout: 30

  - source_id: idaho_dhw
    source_name: Idaho Department of Health and Welfare
    source_url: https://healthandwelfare.idaho.gov/services/health/epidemiology-disease-control/communicable-diseases
    enabled: true
    priority: 8
    timeout: 30

  - source_id: who_don
    source_name: WHO Disease Outbreak News
    source_url: https://www.who.int/emergencies/disease-outbreak-news
    feed_url: https://www.who.int/feeds/entity/134702/rss
    enabled: true
    priority: 7
    timeout: 30
```

### Scoring Policy

Scoring weights and thresholds are configured in `config/scoring_policy.yaml`:

```yaml
scoring:
  # Weight factors (0-100 total)
  idaho_pnw_weight: 35        # Idaho/Pacific Northwest relevance
  healthcare_ip_weight: 25    # Healthcare/infection-prevention relevance
  official_urgency_weight: 20 # Official urgency/severity signal
  travel_weight: 10          # US travel/importation relevance
  novelty_weight: 10         # Novelty

  # Priority band thresholds
  urgent_threshold: 75       # Score >= 75: urgent_human_review
  review_threshold: 45       # Score >= 45: review_today
  monitor_threshold: 20      # Score >= 20: monitor
  # Score < 20: archive
```

## 📊 Data Model

The core data model is the `EventCard`, which captures all essential information about a public health event:

```python
# Key EventCard fields:
event_id: str  # Unique identifier
source_id: str  # Source identifier (cdc_han, idaho_dhw, etc.)
source_name: str  # Human-readable source name
source_url: str  # URL of the original notice
source_published_at: datetime  # When the source published
disease_or_hazard: Optional[str]  # Primary disease or hazard
event_type: EventType  # outbreak, health_alert, investigation, advisory, update
geographies: list[Geography]  # Affected geographic areas
case_count: Optional[int]  # Number of cases (if explicitly stated)
death_count: Optional[int]  # Number of deaths (if explicitly stated)
affected_settings: list[str]  # Settings affected (healthcare, schools, etc.)
official_source: str  # Official source organization
explicit_facts: list[ExplicitFact]  # Extracted factual statements
unknowns: list[str]  # Explicitly stated unknowns or uncertainties
relevance_reasons: list[str]  # Reasons this event is relevant
priority_score: int  # Calculated priority score (0-100)
priority_band: PriorityBand  # urgent_human_review, review_today, monitor, archive
summary: str  # Brief summary
content_hash: str  # Hash for deduplication
review_status: ReviewStatus  # pending, reviewed, dismissed, archived
```

**Important**: If an item does not state a case count, it stores `None` - we **never infer** missing data.

## 🎯 Deterministic Scoring

Events are scored using transparent, deterministic rules with the following factors:

| Factor | Weight | Description |
|--------|--------|-------------|
| Idaho/PNW Relevance | 0-35 | Explicit Idaho mentions, PNW geography, Idaho DHW source |
| Healthcare/IP Relevance | 0-25 | Healthcare terms, settings, CDC HAN/Outbreaks sources |
| Official Urgency | 0-20 | Event type, urgency keywords, high case/death counts |
| US Travel Relevance | 0-10 | US geography, travel terms, WHO DON source |
| Novelty | 0-10 | Novelty keywords, emerging diseases |

### Priority Bands

| Score Range | Priority Band | Action |
|-------------|---------------|--------|
| 75-100 | `urgent_human_review` | Immediate human review required |
| 45-74 | `review_today` | Review within 24 hours |
| 20-44 | `monitor` | Monitor for developments |
| 0-19 | `archive` | Archive for reference |

**Every score includes**:
- A list of score contributions (how many points from each factor)
- Plain-English reasons for the score
- The system **routes items only** - it never generates action directives

## 📄 Briefing Format

The system generates Markdown briefings with the following structure:

```markdown
# Public Health Outbreak Intelligence Brief — YYYY-MM-DD

> **DISCLAIMER**: This report contains public-source information only and is provided for 
> decision-support and research purposes. Every item requires qualified human review. 
> This system does not diagnose, make clinical recommendations, modify policy, or autonomously 
> escalate alerts. No patient data, Epic access, credentials, or automatic notifications are involved.

## 🔴 Urgent Human Review
- [Title](source-url)
  - **Why surfaced**: Idaho relevance; CDC Health Alert
  - **Disease/Hazard**: Respiratory Syncytial Virus
  - **Type**: health_alert | **Source**: CDC Health Alert Network
  - **Geography**: United States (Idaho)
  - **Explicit facts**: 15% increase in RSV hospitalizations; Pediatric cases rising
  - **Counts**: 245 cases, 3 deaths
  - **Score**: 82/100

## 🟡 Review Today

## 🟢 Monitor

## ⚪ Archive

## Source Health
- **CDC Health Alert Network**: success, last retrieved at 2024-01-15T10:30:00
- **Idaho Department of Health and Welfare**: success, last retrieved at 2024-01-15T10:35:00
- **WHO Disease Outbreak News**: success, last retrieved at 2024-01-15T10:40:00

## Summary
- **Total events**: 3
- **Urgent review**: 1
- **Review today**: 1
- **Monitor**: 1
- **Archive**: 0

---

*This briefing was generated automatically from public sources. All information 
requires verification by qualified public health professionals.*
```

## 🔒 Safety Boundaries

The system operates within strict safety boundaries. See [docs/safety-boundaries.md](docs/safety-boundaries.md) for complete details.

### Key Safety Principles

✅ **No PHI**: Only public, non-identifiable data
✅ **No Patient Data**: No individual patient information
✅ **No Epic Access**: No integration with Epic systems
✅ **No Laboratory Data**: No lab results or specimen data
✅ **No Employee Data**: No individual employee information
✅ **No Diagnosis**: No medical diagnosis or interpretation
✅ **No Clinical Recommendations**: No medical advice or guidance
✅ **No Policy Modification**: No policy creation or changes
✅ **Human Review Required**: Every item requires qualified human review
✅ **No Automatic Notifications**: No email, SMS, webhooks, etc.
✅ **No Scheduled Execution**: No cron jobs or automatic runs
✅ **No Credentials**: No API keys, passwords, or tokens
✅ **No Cloud Databases**: Only local SQLite storage
✅ **Approved Sources Only**: Only allowlisted public health sources
✅ **Proper Attribution**: All data must be sourced and linked

## 🧪 Quality Assurance

### Running Tests

```powershell
# Install development dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run specific test files
pytest tests/test_extraction.py
pytest tests/test_dedup.py
pytest tests/test_scoring.py
pytest tests/test_briefing.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src/outbreak_intel --cov-report=term-missing
```

### Code Quality Checks

```powershell
# Run linting
ruff check .

# Run type checking
mypy src

# Format code
ruff format .
```

### Pre-commit Quality Gate

Before committing any changes, run:

```powershell
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .

# Run type checking
mypy src

# Initialize database and test demo
python -m outbreak_intel init-db
python -m outbreak_intel run --demo
python -m outbreak_intel brief --date <today>
```

**Fix all failures** - do not commit code that doesn't pass these checks.

## 📚 Documentation

- **[Architecture](docs/architecture.md)**: System design and data flow
- **[Source Governance](docs/source-governance.md)**: Source approval and management policy
- **[Safety Boundaries](docs/safety-boundaries.md)**: Complete safety constraints and requirements
- **[Evaluation Plan](docs/evaluation-plan.md)**: Testing and validation methodology

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Commit your changes** (`git commit -m 'Add amazing feature'`)
4. **Run quality checks** (see above)
5. **Push to the branch** (`git push origin feature/amazing-feature`)
6. **Open a Pull Request**

### Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guide
- Use type hints for all functions and methods
- Include docstrings for all public functions and classes
- Keep lines under 100 characters
- Use descriptive variable and function names

### Commit Messages

- Use concise, descriptive commit messages
- Reference issue numbers when applicable
- Follow conventional commit style

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with Python 3.12+
- Uses [Typer](https://typer.tiangolo.com/) for CLI
- Uses [Pydantic](https://pydantic.dev/) for data validation
- Uses [HTTPX](https://www.python-httpx.org/) for HTTP requests
- Uses [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) for HTML parsing
- Uses [Feedparser](https://feedparser.readthedocs.io/) for RSS/Atom parsing
- Uses [SQLite3](https://docs.python.org/3/library/sqlite3.html) for local storage

## 📞 Support

For questions, issues, or feedback:

- **GitHub Issues**: [Open an issue](https://github.com/Carlosdanger96/public-health-outbreak-intelligence/issues)
- **Documentation**: Check the [docs/](docs/) directory
- **Email**: carlosdanger96@gmail.com

## 🚨 Current Limitations

This is a **version 1 prototype** with the following limitations:

1. **Demo Mode Only**: Live collection is implemented but requires explicit opt-in
2. **Limited Sources**: Only 4 approved sources currently supported
3. **Basic Parsing**: HTML parsing is based on current page structures
4. **No Persistence**: Database is local SQLite (not suitable for multi-user)
5. **No Scheduling**: Must be run manually
6. **No Authentication**: All sources must be public and unauthenticated
7. **Basic Deduplication**: Uses content hashing and simple similarity
8. **Static Scoring**: Scoring weights are configurable but fixed

### Planned Future Improvements

1. **Enhanced Parsing**: More robust HTML parsing with fallbacks
2. **Additional Sources**: Expand the allowlist with more public health sources
3. **Improved Deduplication**: More sophisticated similarity detection
4. **Performance Optimization**: Optimize for larger data volumes
5. **Monitoring Dashboard**: Web interface for viewing and managing events
6. **Export Functionality**: Export briefings in multiple formats (PDF, etc.)
7. **Advanced Filtering**: More sophisticated filtering and search capabilities
8. **Historical Analysis**: Trend analysis and historical reporting

---

**Built with ❤️ for public health professionals**

*This system is for decision-support and research only. All output requires qualified human review.*
