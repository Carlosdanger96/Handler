# Public Health Outbreak Intelligence - Safety Boundaries

## Overview

This document explicitly defines the safety boundaries and constraints of the Public Health Outbreak Intelligence system. These boundaries ensure that the system operates safely, ethically, and within its intended scope.

## Core Safety Principles

### 1. No Protected Health Information (PHI)

**STRICT PROHIBITION**: The system must **never** collect, process, store, or transmit any Protected Health Information (PHI) as defined by HIPAA.

**Included in PHI prohibition:**
- Patient names, identifiers, or any personal identifiers
- Medical record numbers
- Health plan beneficiary numbers
- Account numbers
- Certificate/license numbers
- Vehicle identifiers and serial numbers
- Device identifiers and serial numbers
- Web URLs
- IP addresses
- Biometric identifiers (fingerprints, voice prints, etc.)
- Full-face photographic images and comparable images
- Any other unique identifying number, characteristic, or code

**Verification:**
- All data sources must be public and explicitly non-PHI
- All collected data must be reviewed to ensure no PHI is present
- Any data containing PHI must be immediately deleted and reported

### 2. No Patient Data

**STRICT PROHIBITION**: The system must **never** access, collect, or process any patient-specific data.

**Prohibited patient data includes:**
- Individual patient medical records
- Patient diagnoses or treatment information
- Patient test results or laboratory data
- Patient demographic information
- Patient contact information
- Any data that can be linked to individual patients

**Allowed data:**
- Aggregated, de-identified public health statistics
- Population-level health data
- Public health alerts and advisories
- Epidemiological reports without patient identifiers

### 3. No Epic Access or Integration

**STRICT PROHIBITION**: The system must **never** access, integrate with, or attempt to connect to any Epic Systems Corporation products or services.

**This includes:**
- Epic Electronic Health Record (EHR) systems
- Epic MyChart patient portals
- Epic data APIs or interfaces
- Any system that contains Epic data
- Any credentials or tokens for Epic access

**Verification:**
- No Epic-related dependencies in the codebase
- No Epic API endpoints in configuration
- No Epic credentials or tokens in any files

### 4. No Laboratory Data

**STRICT PROHIBITION**: The system must **never** access or process laboratory data.

**Prohibited laboratory data includes:**
- Individual laboratory test results
- Laboratory information systems (LIS) data
- Lab specimen information
- Laboratory quality control data
- Any data from clinical laboratories

**Allowed data:**
- Public health laboratory reports (aggregated, de-identified)
- Public health surveillance data
- Epidemiological reports from health departments

### 5. No Employee Data

**STRICT PROHIBITION**: The system must **never** collect or process employee-specific data.

**Prohibited employee data includes:**
- Employee names or identifiers
- Employee contact information
- Employee health information
- Employee performance data
- Any data that can be linked to individual employees

## Clinical and Decision-Making Boundaries

### 6. No Diagnosis

**STRICT PROHIBITION**: The system must **never** diagnose, suggest diagnoses, or provide diagnostic information.

**Prohibited activities:**
- Interpreting symptoms or test results
- Providing differential diagnoses
- Suggesting medical conditions or diseases
- Any activity that could be construed as medical diagnosis

**Allowed activities:**
- Reporting publicly available health alerts
- Presenting aggregated epidemiological data
- Providing links to official health information
- Routing information for human review

### 7. No Clinical Recommendations

**STRICT PROHIBITION**: The system must **never** make clinical recommendations or provide medical advice.

**Prohibited activities:**
- Recommending treatments or medications
- Suggesting clinical interventions
- Providing medical management guidance
- Any activity that could influence clinical decision-making

**Allowed activities:**
- Reporting official public health recommendations
- Providing links to clinical guidelines from authoritative sources
- Presenting information for educational purposes

### 8. No Policy Modification

**STRICT PROHIBITION**: The system must **never** modify, create, or influence healthcare policy.

**Prohibited activities:**
- Creating or modifying healthcare policies
- Influencing organizational policies
- Making policy recommendations
- Any activity that could change healthcare practices or procedures

**Allowed activities:**
- Reporting on existing policies from official sources
- Providing information about policy changes from authoritative sources
- Presenting policy information for review

### 9. Human Review Required

**MANDATORY REQUIREMENT**: Every item surfaced by the system **must** undergo qualified human review before any action is taken.

**Implementation:**
- All events are marked with `review_status: PENDING` initially
- Briefings explicitly state that human review is required
- No automatic actions are taken based on system output
- All surfaced items include clear disclaimers

**Human review must:**
- Be performed by qualified public health professionals
- Verify the accuracy of information
- Assess the relevance and importance of each item
- Determine appropriate actions (if any)

## Technical Boundaries

### 10. No Automatic Notifications

**STRICT PROHIBITION**: The system must **never** send automatic notifications.

**Prohibited notification methods:**
- Email notifications
- SMS/text message notifications
- Slack or other messaging platform notifications
- Webhook notifications
- Desktop notifications
- Push notifications
- Any form of automatic alerting

**Allowed activities:**
- Generating reports for manual review
- Storing data for later retrieval
- Providing CLI output during execution

### 11. No Scheduled Execution

**STRICT PROHIBITION**: The system must **never** execute automatically on a schedule.

**Prohibited activities:**
- Cron jobs or scheduled tasks
- Windows Task Scheduler tasks
- Systemd timers
- Any form of automatic, recurring execution

**Allowed activities:**
- Manual execution via CLI commands
- Interactive use during development
- Batch processing initiated by users

### 12. No Credentials or API Keys

**STRICT PROHIBITION**: The system must **never** require or use credentials, API keys, or authentication tokens.

**Prohibited items:**
- API keys for any service
- Authentication tokens
- Passwords or credentials
- OAuth tokens
- Any form of secret or sensitive access information

**Verification:**
- No credentials in source code
- No credentials in configuration files
- No credentials in environment variable examples
- No API key dependencies

### 13. No Cloud Databases

**STRICT PROHIBITION**: The system must **never** use cloud-based databases or storage.

**Prohibited services:**
- AWS RDS, DynamoDB, S3, etc.
- Google Cloud SQL, Firestore, Cloud Storage, etc.
- Azure SQL Database, Cosmos DB, Blob Storage, etc.
- Any cloud-based database or storage service

**Allowed storage:**
- Local SQLite database files
- Local file system storage
- Local memory (during processing)

### 14. No External Dependencies on LLM APIs

**STRICT PROHIBITION**: The system must **never** require or use Large Language Model (LLM) APIs in version 1.

**Prohibited activities:**
- Calling OpenAI, Anthropic, or other LLM APIs
- Using LLM-based extraction or processing
- Any dependency on external AI services

**Allowed activities:**
- Optional LLM interface for future implementation
- Local, deterministic processing
- Rule-based extraction and analysis

## Data Handling Boundaries

### 15. Data Source Restrictions

**MANDATORY REQUIREMENT**: Only data from the approved source allowlist may be collected.

**Approved sources:**
- CDC Health Alert Network (HAN)
- CDC Outbreak Investigations
- Idaho Department of Health and Welfare
- WHO Disease Outbreak News

**Prohibited sources:**
- Any source not on the approved allowlist
- Social media platforms
- Generic news aggregators
- Unverified dashboards
- Any source requiring authentication

### 16. Data Retention

**MANDATORY REQUIREMENT**: All data must be from public sources and properly attributed.

**Requirements:**
- All collected data must include source attribution
- All briefings must include source links
- All data must be traceable to its original source
- No data may be presented without proper attribution

### 17. Data Modification

**STRICT PROHIBITION**: The system must **never** modify the content of collected data.

**Prohibited activities:**
- Altering source content
- Paraphrasing or summarizing in a way that changes meaning
- Removing or adding information to source content

**Allowed activities:**
- Extracting structured information from source content
- Normalizing data formats
- Adding metadata and annotations
- Creating summaries that preserve original meaning

## Operational Boundaries

### 18. Scope of Use

**MANDATORY REQUIREMENT**: The system is for **decision-support and research only**.

**Intended use:**
- Supporting public health professionals in their work
- Providing organized access to public health information
- Aiding in the identification of relevant public health events
- Facilitating human review of public health notices

**Prohibited use:**
- Clinical decision-making
- Patient care
- Emergency response coordination
- Policy creation or modification
- Any use that could affect patient outcomes

### 19. User Responsibilities

**MANDATORY REQUIREMENT**: Users of the system must understand and accept the following responsibilities:

- All system output requires human verification
- The system does not replace professional judgment
- Users are responsible for appropriate use of system output
- Users must comply with all applicable laws and regulations
- Users must report any safety concerns or violations

### 20. System Limitations

**EXPLICIT ACKNOWLEDGMENT**: The system has the following limitations:

- Only processes public-source data
- Only covers approved sources
- May miss relevant information
- May include false positives
- Requires human interpretation
- Not a substitute for professional expertise

## Verification and Compliance

### Compliance Checking

Before any code is committed or deployed, the following must be verified:

1. **No PHI**: Code review must confirm no PHI handling
2. **No Credentials**: Code review must confirm no credentials or secrets
3. **No Prohibited Sources**: Code review must confirm only approved sources
4. **No Automatic Actions**: Code review must confirm no automatic notifications or scheduling
5. **Proper Attribution**: Code review must confirm all data is properly attributed

### Audit Trail

The system maintains the following audit information:

- Collection timestamps and sources
- Processing timestamps and methods
- Scoring calculations and reasons
- User actions (via CLI commands)
- Error logs and system messages

### Incident Response

If any safety boundary is violated:

1. **Immediate Action**: Stop the violating process or operation
2. **Containment**: Isolate any affected data or systems
3. **Investigation**: Determine the cause and scope of the violation
4. **Remediation**: Fix the underlying issue
5. **Reporting**: Report the incident to appropriate authorities
6. **Prevention**: Implement measures to prevent recurrence

## Summary

The Public Health Outbreak Intelligence system operates within strict safety boundaries to ensure:

✅ **No PHI** - Only public, non-identifiable data
✅ **No Patient Data** - No individual patient information
✅ **No Epic Access** - No integration with Epic systems
✅ **No Laboratory Data** - No lab results or specimen data
✅ **No Employee Data** - No individual employee information
✅ **No Diagnosis** - No medical diagnosis or interpretation
✅ **No Clinical Recommendations** - No medical advice or guidance
✅ **No Policy Modification** - No policy creation or changes
✅ **Human Review Required** - All items require human verification
✅ **No Automatic Notifications** - No email, SMS, webhooks, etc.
✅ **No Scheduled Execution** - No cron jobs or automatic runs
✅ **No Credentials** - No API keys, passwords, or tokens
✅ **No Cloud Databases** - Only local SQLite storage
✅ **No LLM APIs** - No external AI service dependencies
✅ **Approved Sources Only** - Only allowlisted public health sources
✅ **Proper Attribution** - All data must be sourced and linked

These boundaries ensure that the system operates safely, ethically, and within its intended scope as a decision-support and research tool for public health professionals.
