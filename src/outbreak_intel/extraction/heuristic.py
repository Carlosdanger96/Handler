"""
Heuristic Extractor for Public Health Outbreak Intelligence.

This module implements a deterministic, rule-based extractor that uses
heuristics and patterns to extract structured information from raw text.
No LLM APIs are used - all extraction is based on predefined rules.
"""

import re
from datetime import datetime
from typing import Optional, Any

from .base import BaseExtractor, ExtractionResult
from ..models import EventCard, Geography, ExplicitFact, EventType, PriorityBand, ReviewStatus


class HeuristicExtractor(BaseExtractor):
    """
    Deterministic heuristic-based extractor.

    This extractor uses regular expressions and pattern matching to extract
    structured information from public health notices. It's designed to be
    transparent, deterministic, and reproducible.
    """

    def __init__(self):
        """Initialize the heuristic extractor."""
        # Compile common patterns for efficiency
        self.disease_patterns = self._compile_disease_patterns()
        self.geography_patterns = self._compile_geography_patterns()
        self.count_patterns = self._compile_count_patterns()
        self.fact_patterns = self._compile_fact_patterns()
        self.unknown_patterns = self._compile_unknown_patterns()

    def _compile_disease_patterns(self) -> list[re.Pattern]:
        """Compile disease detection patterns."""
        patterns = [
            # Viral diseases
            r"\b(?:COVID\-19|SARS\-CoV\-2|Coronavirus|2019\-nCoV)\b",
            r"\b(?:Influenza|Flu|Seasonal flu)\b",
            r"\b(?:Measles|Rubeola)\b",
            r"\b(?:Mumps)\b",
            r"\b(?:Rubella|German measles)\b",
            r"\b(?:Ebola|EVD|Ebola virus disease)\b",
            r"\b(?:Mpox|Monkeypox)\b",
            r"\b(?:Dengue|Dengue fever)\b",
            r"\b(?:Chikungunya)\b",
            r"\b(?:Zika|Zika virus)\b",
            r"\b(?:Yellow fever)\b",
            r"\b(?:West Nile virus|West Nile)\b",
            r"\b(?:Hepatitis [ABC]|Hep [ABC])\b",
            r"\b(?:HIV|AIDS|Human immunodeficiency virus)\b",
            r"\b(?:Rabies)\b",
            r"\b(?:Polio|Poliomyelitis)\b",
            r"\b(?:Smallpox|Variola)\b",
            r"\b(?:Measles|Mumps|Rubella)\b",
            # Bacterial diseases
            r"\b(?:Tuberculosis|TB|Mycobacterium tuberculosis)\b",
            r"\b(?:Salmonella|Salmonellosis)\b",
            r"\b(?:E\. coli|Escherichia coli)\b",
            r"\b(?:Listeria|Listeriosis)\b",
            r"\b(?:Shigella|Shigellosis)\b",
            r"\b(?:Campylobacter|Campylobacteriosis)\b",
            r"\b(?:Legionnaires\' disease|Legionella)\b",
            r"\b(?:Pertussis|Whooping cough|Bordetella pertussis)\b",
            r"\b(?:Diphtheria|Corynebacterium diphtheriae)\b",
            r"\b(?:Tetanus|Clostridium tetani)\b",
            r"\b(?:Anthrax|Bacillus anthracis)\b",
            r"\b(?:Botulism|Clostridium botulinum)\b",
            r"\b(?:Plague|Yersinia pestis)\b",
            r"\b(?:Cholera|Vibrio cholerae)\b",
            r"\b(?:Syphilis|Treponema pallidum)\b",
            r"\b(?:Gonorrhea|Neisseria gonorrhoeae)\b",
            r"\b(?:Meningitis|Meningococcal disease)\b",
            r"\b(?:Sepsis|Septicemia)\b",
            # Parasitic diseases
            r"\b(?:Malaria|Plasmodium)\b",
            r"\b(?:Toxoplasmosis|Toxoplasma gondii)\b",
            r"\b(?:Giardiasis|Giardia)\b",
            r"\b(?:Cryptosporidiosis|Cryptosporidium)\b",
            # Fungal diseases
            r"\b(?:Candidiasis|Candida)\b",
            r"\b(?:Aspergillosis|Aspergillus)\b",
            r"\b(?:Histoplasmosis|Histoplasma)\b",
            # Other
            r"\b(?:Prion disease|Creutzfeldt\-Jakob disease)\b",
            r"\b(?:Novel pathogen|Emerging pathogen|Unknown pathogen)\b",
        ]

        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

    def _compile_geography_patterns(self) -> list[tuple[re.Pattern, dict[str, Any]]]:
        """Compile geography detection patterns."""
        patterns = [
            # Countries
            (
                r"\b(?:United States|USA|US|America|United States of America)\b",
                {"country": "United States"},
            ),
            (r"\b(?:Canada)\b", {"country": "Canada"}),
            (r"\b(?:Mexico)\b", {"country": "Mexico"}),
            (r"\b(?:United Kingdom|UK|Britain)\b", {"country": "United Kingdom"}),
            (r"\b(?:England)\b", {"country": "United Kingdom", "region": "England"}),
            (r"\b(?:Scotland)\b", {"country": "United Kingdom", "region": "Scotland"}),
            (r"\b(?:Wales)\b", {"country": "United Kingdom", "region": "Wales"}),
            (
                r"\b(?:Northern Ireland)\b",
                {"country": "United Kingdom", "region": "Northern Ireland"},
            ),
            # US States
            (r"\b(?:Alabama|AL)\b", {"country": "United States", "state": "Alabama"}),
            (r"\b(?:Alaska|AK)\b", {"country": "United States", "state": "Alaska"}),
            (r"\b(?:Arizona|AZ)\b", {"country": "United States", "state": "Arizona"}),
            (r"\b(?:Arkansas|AR)\b", {"country": "United States", "state": "Arkansas"}),
            (r"\b(?:California|CA)\b", {"country": "United States", "state": "California"}),
            (r"\b(?:Colorado|CO)\b", {"country": "United States", "state": "Colorado"}),
            (r"\b(?:Connecticut|CT)\b", {"country": "United States", "state": "Connecticut"}),
            (r"\b(?:Delaware|DE)\b", {"country": "United States", "state": "Delaware"}),
            (r"\b(?:Florida|FL)\b", {"country": "United States", "state": "Florida"}),
            (r"\b(?:Georgia|GA)\b", {"country": "United States", "state": "Georgia"}),
            (r"\b(?:Hawaii|HI)\b", {"country": "United States", "state": "Hawaii"}),
            (r"\b(?:Idaho|ID)\b", {"country": "United States", "state": "Idaho"}),
            (r"\b(?:Illinois|IL)\b", {"country": "United States", "state": "Illinois"}),
            (r"\b(?:Indiana|IN)\b", {"country": "United States", "state": "Indiana"}),
            (r"\b(?:Iowa|IA)\b", {"country": "United States", "state": "Iowa"}),
            (r"\b(?:Kansas|KS)\b", {"country": "United States", "state": "Kansas"}),
            (r"\b(?:Kentucky|KY)\b", {"country": "United States", "state": "Kentucky"}),
            (r"\b(?:Louisiana|LA)\b", {"country": "United States", "state": "Louisiana"}),
            (r"\b(?:Maine|ME)\b", {"country": "United States", "state": "Maine"}),
            (r"\b(?:Maryland|MD)\b", {"country": "United States", "state": "Maryland"}),
            (r"\b(?:Massachusetts|MA)\b", {"country": "United States", "state": "Massachusetts"}),
            (r"\b(?:Michigan|MI)\b", {"country": "United States", "state": "Michigan"}),
            (r"\b(?:Minnesota|MN)\b", {"country": "United States", "state": "Minnesota"}),
            (r"\b(?:Mississippi|MS)\b", {"country": "United States", "state": "Mississippi"}),
            (r"\b(?:Missouri|MO)\b", {"country": "United States", "state": "Missouri"}),
            (r"\b(?:Montana|MT)\b", {"country": "United States", "state": "Montana"}),
            (r"\b(?:Nebraska|NE)\b", {"country": "United States", "state": "Nebraska"}),
            (r"\b(?:Nevada|NV)\b", {"country": "United States", "state": "Nevada"}),
            (r"\b(?:New Hampshire|NH)\b", {"country": "United States", "state": "New Hampshire"}),
            (r"\b(?:New Jersey|NJ)\b", {"country": "United States", "state": "New Jersey"}),
            (r"\b(?:New Mexico|NM)\b", {"country": "United States", "state": "New Mexico"}),
            (r"\b(?:New York|NY)\b", {"country": "United States", "state": "New York"}),
            (r"\b(?:North Carolina|NC)\b", {"country": "United States", "state": "North Carolina"}),
            (r"\b(?:North Dakota|ND)\b", {"country": "United States", "state": "North Dakota"}),
            (r"\b(?:Ohio|OH)\b", {"country": "United States", "state": "Ohio"}),
            (r"\b(?:Oklahoma|OK)\b", {"country": "United States", "state": "Oklahoma"}),
            (r"\b(?:Oregon|OR)\b", {"country": "United States", "state": "Oregon"}),
            (r"\b(?:Pennsylvania|PA)\b", {"country": "United States", "state": "Pennsylvania"}),
            (r"\b(?:Rhode Island|RI)\b", {"country": "United States", "state": "Rhode Island"}),
            (r"\b(?:South Carolina|SC)\b", {"country": "United States", "state": "South Carolina"}),
            (r"\b(?:South Dakota|SD)\b", {"country": "United States", "state": "South Dakota"}),
            (r"\b(?:Tennessee|TN)\b", {"country": "United States", "state": "Tennessee"}),
            (r"\b(?:Texas|TX)\b", {"country": "United States", "state": "Texas"}),
            (r"\b(?:Utah|UT)\b", {"country": "United States", "state": "Utah"}),
            (r"\b(?:Vermont|VT)\b", {"country": "United States", "state": "Vermont"}),
            (r"\b(?:Virginia|VA)\b", {"country": "United States", "state": "Virginia"}),
            (r"\b(?:Washington|WA)\b", {"country": "United States", "state": "Washington"}),
            (r"\b(?:West Virginia|WV)\b", {"country": "United States", "state": "West Virginia"}),
            (r"\b(?:Wisconsin|WI)\b", {"country": "United States", "state": "Wisconsin"}),
            (r"\b(?:Wyoming|WY)\b", {"country": "United States", "state": "Wyoming"}),
            # Regions
            (r"\b(?:Pacific Northwest|PNW)\b", {"region": "Pacific Northwest"}),
            (r"\b(?:Northeast|Northeastern)\b", {"region": "Northeast"}),
            (r"\b(?:Southeast|Southeastern)\b", {"region": "Southeast"}),
            (r"\b(?:Midwest|Midwestern)\b", {"region": "Midwest"}),
            (r"\b(?:Southwest|Southwestern)\b", {"region": "Southwest"}),
            (r"\b(?:West|Western)\b", {"region": "West"}),
            # Continents
            (r"\b(?:Africa)\b", {"country": "Africa"}),
            (r"\b(?:Asia)\b", {"country": "Asia"}),
            (r"\b(?:Europe)\b", {"country": "Europe"}),
            (r"\b(?:North America)\b", {"country": "North America"}),
            (r"\b(?:South America)\b", {"country": "South America"}),
            (r"\b(?:Oceania)\b", {"country": "Oceania"}),
            (r"\b(?:Antarctica)\b", {"country": "Antarctica"}),
            # Global
            (r"\b(?:Global|Worldwide|Internationally|World)\b", {"region": "Global"}),
        ]

        return [(re.compile(pattern, re.IGNORECASE), geo_data) for pattern, geo_data in patterns]

    def _compile_count_patterns(self) -> list[re.Pattern]:
        """Compile patterns for extracting counts."""
        patterns = [
            # Case counts
            r"(\d{1,4}(?:,\d{3})*)\s*(?:cases?|infections?|illnesses?|patients?|individuals?)\b",
            r"(\d{1,4}(?:,\d{3})*)\s*(?:confirmed|probable|suspected|presumptive)\s*(?:cases?|infections?)\b",
            r"(\d{1,4}(?:,\d{3})*)\s*(?:new|additional)\s*(?:cases?|infections?)\b",
            r"(\d{1,4}(?:,\d{3})*)\s*(?:total|overall|cumulative)\s*(?:cases?|infections?)\b",
            # Death counts
            r"(\d{1,4}(?:,\d{3})*)\s*(?:deaths?|fatalities?|fatal|died|mortality)\b",
            r"(\d{1,4}(?:,\d{3})*)\s*(?:confirmed|reported)\s*(?:deaths?|fatalities?)\b",
            # Hospitalization counts
            r"(\d{1,4}(?:,\d{3})*)\s*(?:hospitalizations?|hospitalized)\b",
            # Other counts
            r"(\d{1,4}(?:,\d{3})*)\s*(?:exposures?|exposed)\b",
            r"(\d{1,4}(?:,\d{3})*)\s*(?:contacts?|contact tracing)\b",
        ]

        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

    def _compile_fact_patterns(self) -> list[tuple[re.Pattern, str]]:
        """Compile patterns for extracting explicit facts."""
        patterns = [
            # Transmission patterns
            (
                r"(?:transmission|spread|transmitted|is transmitted|was transmitted|has been transmitted)\s*([^.?,]+)(?:\.|,|$)",
                "transmission",
            ),
            (
                r"(?:mode of transmission|transmission mode)\s*:?\s*([^.?,]+)(?:\.|,|$)",
                "transmission",
            ),
            # Severity patterns
            (
                r"(?:severity|severe|mild|moderate|critical)\s*(?:cases?|illness|disease)\s*([^.?,]+)(?:\.|,|$)",
                "severity",
            ),
            # Age group patterns
            (
                r"(?:affects?|affecting|in)\s*(children|adults|elderly|infants|adolescents|all ages)\b",
                "affected_population",
            ),
            # Setting patterns
            (
                r"(?:in|at|among)\s*(healthcare settings?|hospitals?|nursing homes?|schools?|daycare|prisons?|jails?|shelters?)\b",
                "affected_settings",
            ),
            # Time patterns
            (
                r"(?:since|from|starting)\s*(\d{1,2}\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*\d{4})",
                "timeline",
            ),
            (
                r"(?:over the past|in the last|during the last)\s*(\d+\s*(?:days?|weeks?|months?|years?))",
                "timeline",
            ),
        ]

        return [(re.compile(pattern, re.IGNORECASE), fact_type) for pattern, fact_type in patterns]

    def _compile_unknown_patterns(self) -> list[re.Pattern]:
        """Compile patterns for extracting unknowns."""
        patterns = [
            r"([^.?,]*\bunknown\b[^.?,]*)",
            r"([^.?,]*\bunclear\b[^.?,]*)",
            r"([^.?,]*\bnot known\b[^.?,]*)",
            r"([^.?,]*\bnot yet determined\b[^.?,]*)",
            r"([^.?,]*\bunder investigation\b[^.?,]*)",
            r"(?:it is unknown|we do not know|not sure)\s*([^.?,]+)",
            r"(?:the cause is|etiology is|source is)\s*(?:unknown|unclear|not known|under investigation)",
            r"(?:further investigation|additional testing|more information)\s*(?:is needed|required|necessary)",
            r"(?:pending|awaiting)\s*(?:results|confirmation|testing)",
            r"(?:to be determined|TBD)",
        ]

        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

    def extract(self, raw_content: str, source_url: str, source_id: str) -> ExtractionResult:
        """Extract structured information from raw content."""
        try:
            # Extract disease/hazard
            disease = self.extract_disease(raw_content)

            # Extract geography
            geography_data = self.extract_geography(raw_content)
            geographies = [Geography(**geo) for geo in geography_data]

            # Extract counts
            counts = self.extract_counts(raw_content)

            # Extract facts
            facts_data = self.extract_facts(raw_content)
            explicit_facts = [ExplicitFact(**fact) for fact in facts_data]

            # Extract unknowns
            unknowns = self.extract_unknowns(raw_content)

            # Generate content hash
            content_hash = EventCard.generate_content_hash(raw_content, source_url)

            # Create a basic event card with extracted data
            event = EventCard(
                event_id=EventCard.generate_event_id(source_id, source_url),
                source_id=source_id,
                source_name="",  # Will be set by collector
                source_url=source_url,
                source_published_at=None,  # Will be set by collector
                retrieved_at=datetime.utcnow(),
                title="",  # Will be set by collector
                disease_or_hazard=disease,
                event_type=EventType.UNKNOWN,
                geographies=geographies,
                case_count=counts.get("case_count"),
                death_count=counts.get("death_count"),
                affected_settings=[],  # Will be set by collector
                official_source="",  # Will be set by collector
                explicit_facts=explicit_facts,
                unknowns=unknowns,
                relevance_reasons=[],  # Will be set by collector
                priority_score=0,
                priority_band=PriorityBand.ARCHIVE,
                summary="",  # Will be set by collector
                content_hash=content_hash,
                review_status=ReviewStatus.PENDING,
                raw_content=raw_content,
                metadata={
                    "extractor": "heuristic",
                    "extraction_timestamp": datetime.utcnow().isoformat(),
                },
            )

            extracted_data = {
                "disease": disease,
                "geographies": geography_data,
                "counts": counts,
                "facts": facts_data,
                "unknowns": unknowns,
            }

            return ExtractionResult(
                success=True, event=event, extracted_data=extracted_data, confidence="high"
            )

        except Exception as e:
            return ExtractionResult(success=False, error_message=str(e), confidence="low")

    def extract_disease(self, text: str) -> Optional[str]:
        """Extract disease or hazard information from text."""
        for pattern in self.disease_patterns:
            match = pattern.search(text)
            if match:
                return match.group(0)

        # Try to find capitalized words that might be disease names
        words = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        for word in words:
            if len(word) > 3 and word not in [
                "Health",
                "Alert",
                "Network",
                "Public",
                "Advisory",
                "Outbreak",
                "Investigation",
                "Update",
                "Disease",
                "Control",
                "Prevention",
                "Department",
                "Welfare",
                "Services",
                "United",
                "States",
                "World",
                "Organization",
                "Report",
                "Information",
            ]:
                return word

        return None

    def extract_geography(self, text: str) -> list[dict[str, Any]]:
        """Extract geographic information from text."""
        geographies = []
        seen = set()

        for pattern, geo_data in self.geography_patterns:
            if pattern.search(text):
                # Create a unique key for this geography
                geo_key = tuple(sorted(geo_data.items()))
                if geo_key not in seen:
                    geographies.append(geo_data)
                    seen.add(geo_key)

        # If no specific geography found, add global
        if not geographies:
            geographies.append({"region": "Global"})

        return geographies

    def extract_counts(self, text: str) -> dict[str, Optional[int]]:
        """Extract case and death counts from text."""
        counts = {
            "case_count": None,
            "death_count": None,
            "hospitalization_count": None,
            "exposure_count": None,
        }

        for pattern in self.count_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                number_str = match.group(1).replace(",", "")
                try:
                    number = int(number_str)

                    # Determine count type from context
                    context = match.group(0).lower()

                    if any(term in context for term in ["death", "fatal", "died", "mortality"]):
                        if counts["death_count"] is None or number > counts["death_count"]:
                            counts["death_count"] = number
                    elif any(term in context for term in ["hospital", "hospitalized"]):
                        if (
                            counts["hospitalization_count"] is None
                            or number > counts["hospitalization_count"]
                        ):
                            counts["hospitalization_count"] = number
                    elif any(term in context for term in ["expos", "contact"]):
                        if counts["exposure_count"] is None or number > counts["exposure_count"]:
                            counts["exposure_count"] = number
                    else:
                        # Default to case count
                        if counts["case_count"] is None or number > counts["case_count"]:
                            counts["case_count"] = number

                except ValueError:
                    continue

        return counts

    def extract_facts(self, text: str) -> list[dict[str, Any]]:
        """Extract explicit facts from text."""
        facts = []

        for pattern, fact_type in self.fact_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                # Handle patterns with and without capture groups
                if match.groups():
                    fact_text = match.group(1).strip()
                else:
                    fact_text = match.group(0).strip()

                if fact_text:
                    facts.append(
                        {
                            "fact_text": fact_text,
                            "fact_type": fact_type,
                            "source_attribution": "extracted",
                            "confidence": "medium",
                        }
                    )

        # Remove duplicates
        seen = set()
        unique_facts = []
        for fact in facts:
            fact_key = (fact["fact_text"], fact["fact_type"])
            if fact_key not in seen:
                unique_facts.append(fact)
                seen.add(fact_key)

        return unique_facts

    def extract_unknowns(self, text: str) -> list[str]:
        """Extract unknowns and uncertainties from text."""
        unknowns = []

        for pattern in self.unknown_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                unknown_text = match.group(1).strip() if match.groups() else match.group(0).strip()
                if unknown_text and unknown_text not in unknowns:
                    unknowns.append(unknown_text)

        return unknowns
