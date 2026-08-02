# Public Health Outbreak Intelligence - Source Governance

## Overview

This document defines the governance policy for data sources in the Public Health Outbreak Intelligence system. It establishes the criteria for source inclusion, maintenance requirements, and the approval process for adding or modifying sources.

## Source Allowlist Policy

### Approved Source Criteria

A data source must meet **all** of the following criteria to be included in the allowlist:

1. **Official Public Health Authority**
   - Must be a government health agency or recognized international health organization
   - Must have a mandate for public health surveillance and reporting
   - Must have established credibility and authority in public health

2. **Publicly Accessible Data**
   - Data must be publicly available without authentication
   - Must have a stable, accessible URL or feed endpoint
   - Must not require API keys, tokens, or credentials

3. **Regular Updates**
   - Source must be updated at least weekly
   - Must have a history of consistent updates
   - Must provide timestamps for published content

4. **Structured or Parseable Content**
   - Must provide content in a parseable format (HTML, RSS, JSON, etc.)
   - Must have consistent structure that can be reliably parsed
   - Must include essential metadata (title, date, content)

5. **Relevance to Scope**
   - Must provide information relevant to infectious diseases or public health threats
   - Must cover geographic areas of interest (US, Idaho, Pacific Northwest, or global)
   - Must provide actionable information for public health professionals

### Currently Approved Sources

| Source ID | Source Name | URL | Feed URL | Priority | Status |
|-----------|-------------|-----|----------|----------|--------|
| `cdc_han` | CDC Health Alert Network | https://emergency.cdc.gov/han/ | https://emergency.cdc.gov/han/han-rss.asp | 10 | Active |
| `cdc_outbreaks` | CDC Outbreak Investigations | https://www.cdc.gov/outbreaks/index.html | None | 9 | Active |
| `idaho_dhw` | Idaho Department of Health and Welfare | https://healthandwelfare.idaho.gov/services/health/epidemiology-disease-control/communicable-diseases | None | 8 | Active |
| `who_don` | WHO Disease Outbreak News | https://www.who.int/emergencies/disease-outbreak-news | https://www.who.int/feeds/entity/134702/rss | 7 | Active |

### Prohibited Source Types

The following types of sources are **explicitly prohibited** and must not be added:

1. **Social Media Platforms**
   - Twitter/X
   - Facebook
   - Instagram
   - TikTok
   - Reddit
   - Any user-generated content platforms

2. **Generic News Aggregators**
   - Google News
   - Apple News
   - Microsoft News
   - Generic news websites without public health focus

3. **Unverified Dashboards**
   - Dashboards without clear data sources
   - Dashboards maintained by non-official entities
   - Dashboards with unclear update frequency

4. **Academic Preprint Servers**
   - medRxiv
   - bioRxiv
   - Other preprint servers (without peer review)

5. **Commercial Data Providers**
   - Any source requiring payment or subscription
   - Any source with proprietary data
   - Any source with usage restrictions

6. **Individual Blogs or Personal Websites**
   - Personal blogs
   - Individual researcher websites
   - Non-institutional websites

## Source Addition Process

### Step 1: Source Identification
- Identify a potential source that meets the approved criteria
- Document the source URL, content type, and update frequency
- Verify that the source provides relevant public health information

### Step 2: Technical Feasibility Assessment
- Verify that the source content can be parsed reliably
- Test the source URL for accessibility and stability
- Confirm that the source provides necessary metadata (title, date, etc.)

### Step 3: Governance Review
- Submit a request to add the source with justification
- Include documentation of how the source meets all approval criteria
- Provide examples of the type of content the source provides

### Step 4: Implementation
- Create a new collector class for the source
- Implement parsing logic for the source's content format
- Add appropriate error handling and validation

### Step 5: Testing
- Test the collector with live data from the source
- Verify that extracted events have correct metadata
- Confirm that the source integrates properly with the pipeline

### Step 6: Approval and Deployment
- Obtain approval from system maintainers
- Add the source to the allowlist configuration
- Enable the source in production (if appropriate)

## Source Maintenance Requirements

### Monitoring
- All sources must be monitored for availability and content quality
- Collection failures must be logged and investigated
- Sources with repeated failures may be temporarily disabled

### Content Quality
- Sources must continue to provide relevant, timely information
- Sources with degraded content quality may be reviewed for removal
- Sources that change their format or structure may require collector updates

### Regular Review
- All sources must be reviewed at least quarterly
- Review must verify that sources still meet approval criteria
- Review must confirm that collectors are functioning correctly

## Source Removal Process

A source may be removed from the allowlist if:

1. **Source No Longer Meets Criteria**
   - Source stops providing public health information
   - Source becomes inaccessible or unstable
   - Source changes to require authentication or payment

2. **Content Quality Issues**
   - Source provides consistently low-quality or irrelevant content
   - Source has frequent or prolonged outages
   - Source structure changes in a way that cannot be reliably parsed

3. **Governance Violations**
   - Source begins providing non-public data
   - Source violates any of the prohibited source types
   - Source poses security or privacy risks

### Removal Process
1. Document the reason for removal
2. Disable the source in configuration
3. Notify stakeholders of the removal
4. Archive historical data from the source
5. Remove the source from the allowlist

## Source Configuration

Each source in the allowlist must have a configuration entry in `config/sources.yaml` with the following fields:

```yaml
- source_id: unique_identifier
  source_name: "Human-readable name"
  source_url: "Base URL for the source"
  feed_url: "RSS/Atom feed URL (if available)"
  enabled: true/false
  priority: 1-10
  timeout: HTTP timeout in seconds
  user_agent: Custom user agent (optional)
```

### Priority Levels
- **10**: Highest priority (e.g., CDC HAN)
- **9**: High priority (e.g., CDC Outbreaks)
- **8**: Medium-high priority (e.g., Idaho DHW)
- **7**: Medium priority (e.g., WHO DON)
- **6-1**: Lower priority sources

## User Agent Policy

All HTTP requests must include a clear, identifiable user agent string:

```
PublicHealthOutbreakIntelligence/0.1.0 (+https://github.com/Carlosdanger96/public-health-outbreak-intelligence)
```

This user agent:
- Identifies the system making the request
- Provides a URL for more information
- Allows source administrators to contact us if needed
- Complies with best practices for web crawling

## Rate Limiting and Caching

- All HTTP requests must have configurable timeouts
- Failed requests must be retried with exponential backoff
- Sources must not be polled more frequently than necessary
- Consider caching responses to reduce load on sources

## Error Handling

- Collection failures must be logged with details
- Individual source failures must not crash the entire pipeline
- Errors must be reported in a way that allows debugging
- Sources with persistent errors may be temporarily disabled

## Data Retention

- Raw content from sources may be stored for archival purposes
- All stored data must be from public sources only
- No personal or sensitive data must be stored
- Database backups must follow the same data retention policies
