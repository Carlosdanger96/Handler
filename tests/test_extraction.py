"""
Tests for the extraction module.

This module tests the deterministic extraction functionality,
ensuring that structured information is correctly extracted from raw text.
"""

import pytest
from datetime import datetime

from outbreak_intel.extraction import get_extractor, HeuristicExtractor
from outbreak_intel.models import EventCard, Geography, ExplicitFact


@pytest.fixture
def extractor():
    """Create a heuristic extractor for testing."""
    return HeuristicExtractor()


class TestDiseaseExtraction:
    """Test disease and hazard extraction."""

    def test_extract_covid(self, extractor):
        """Test extraction of COVID-19."""
        text = "CDC Health Alert: Increased COVID-19 activity detected"
        disease = extractor.extract_disease(text)
        assert disease is not None
        assert "covid" in disease.lower() or "19" in disease

    def test_extract_influenza(self, extractor):
        """Test extraction of influenza."""
        text = "Seasonal influenza cases are rising across the region"
        disease = extractor.extract_disease(text)
        assert disease is not None
        assert "flu" in disease.lower() or "influenza" in disease.lower()

    def test_extract_measles(self, extractor):
        """Test extraction of measles."""
        text = "Measles outbreak reported in local community"
        disease = extractor.extract_disease(text)
        assert disease is not None
        assert "measles" in disease.lower()

    def test_extract_salmonella(self, extractor):
        """Test extraction of Salmonella."""
        text = "Salmonella outbreak linked to contaminated chicken"
        disease = extractor.extract_disease(text)
        assert disease is not None
        assert "salmonella" in disease.lower()

    def test_extract_no_disease(self, extractor):
        """Test extraction when no disease is present."""
        text = "Public health advisory for the upcoming season"
        disease = extractor.extract_disease(text)
        # May or may not find something, but shouldn't crash
        assert disease is None or isinstance(disease, str)


class TestGeographyExtraction:
    """Test geography extraction."""

    def test_extract_idaho(self, extractor):
        """Test extraction of Idaho geography."""
        text = "Health alert for Idaho residents"
        geographies = extractor.extract_geography(text)
        assert len(geographies) > 0
        idaho_geos = [
            g
            for g in geographies
            if g.get("state") == "Idaho" or g.get("country") == "United States"
        ]
        assert len(idaho_geos) > 0

    def test_extract_united_states(self, extractor):
        """Test extraction of United States."""
        text = "CDC Health Alert for the United States"
        geographies = extractor.extract_geography(text)
        assert len(geographies) > 0
        us_geos = [g for g in geographies if g.get("country") == "United States"]
        assert len(us_geos) > 0

    def test_extract_pacific_northwest(self, extractor):
        """Test extraction of Pacific Northwest region."""
        text = "Public health notice for the Pacific Northwest region"
        geographies = extractor.extract_geography(text)
        assert len(geographies) > 0
        pnw_geos = [g for g in geographies if g.get("region") == "Pacific Northwest"]
        assert len(pnw_geos) > 0

    def test_extract_global(self, extractor):
        """Test extraction of global geography."""
        text = "WHO report on global health trends"
        geographies = extractor.extract_geography(text)
        assert len(geographies) > 0
        global_geos = [g for g in geographies if g.get("region") == "Global"]
        assert len(global_geos) > 0


class TestCountExtraction:
    """Test case and death count extraction."""

    def test_extract_case_count(self, extractor):
        """Test extraction of case count."""
        text = "There have been 125 confirmed cases of the disease"
        counts = extractor.extract_counts(text)
        assert counts["case_count"] == 125

    def test_extract_case_count_with_commas(self, extractor):
        """Test extraction of case count with commas."""
        text = "Over 1,234 cases have been reported"
        counts = extractor.extract_counts(text)
        assert counts["case_count"] == 1234

    def test_extract_death_count(self, extractor):
        """Test extraction of death count."""
        text = "The outbreak has resulted in 23 deaths"
        counts = extractor.extract_counts(text)
        assert counts["death_count"] == 23

    def test_extract_multiple_counts(self, extractor):
        """Test extraction of multiple counts from same text."""
        text = "150 cases and 5 deaths have been reported"
        counts = extractor.extract_counts(text)
        assert counts["case_count"] == 150
        assert counts["death_count"] == 5

    def test_extract_no_counts(self, extractor):
        """Test extraction when no counts are present."""
        text = "Public health advisory issued"
        counts = extractor.extract_counts(text)
        assert counts["case_count"] is None
        assert counts["death_count"] is None


class TestFactExtraction:
    """Test explicit fact extraction."""

    def test_extract_transmission_fact(self, extractor):
        """Test extraction of transmission facts."""
        text = "The disease is transmitted through respiratory droplets"
        facts = extractor.extract_facts(text)
        assert len(facts) > 0
        transmission_facts = [f for f in facts if f["fact_type"] == "transmission"]
        assert len(transmission_facts) > 0

    def test_extract_affected_population(self, extractor):
        """Test extraction of affected population facts."""
        text = "The outbreak primarily affects children under 5 years old"
        facts = extractor.extract_facts(text)
        assert len(facts) > 0
        population_facts = [f for f in facts if f["fact_type"] == "affected_population"]
        assert len(population_facts) > 0


class TestUnknownExtraction:
    """Test unknown and uncertainty extraction."""

    def test_extract_unknown_source(self, extractor):
        """Test extraction of unknown source."""
        text = "The source of the outbreak is currently unknown"
        unknowns = extractor.extract_unknowns(text)
        assert len(unknowns) > 0

    def test_extract_under_investigation(self, extractor):
        """Test extraction of under investigation."""
        text = "The cause is under investigation by health authorities"
        unknowns = extractor.extract_unknowns(text)
        assert len(unknowns) > 0

    def test_extract_no_unknowns(self, extractor):
        """Test extraction when no unknowns are present."""
        text = "The outbreak has been fully investigated and the source identified"
        unknowns = extractor.extract_unknowns(text)
        assert len(unknowns) == 0


class TestFullExtraction:
    """Test complete extraction workflow."""

    def test_full_extraction(self, extractor):
        """Test complete extraction of an event."""
        raw_content = """
        CDC Health Alert: Increased Respiratory Illness in Idaho
        
        The CDC has detected increased respiratory illness activity in Idaho.
        There have been 245 confirmed cases and 3 deaths reported.
        The disease is transmitted through respiratory droplets.
        The source of the outbreak is currently unknown.
        """

        source_url = "https://emergency.cdc.gov/han/2024/han00512.asp"
        source_id = "cdc_han"

        result = extractor.extract(raw_content, source_url, source_id)

        assert result.success is True
        assert result.event is not None
        assert result.confidence == "high"

        event = result.event
        assert event.disease_or_hazard is not None
        assert len(event.geographies) > 0
        assert event.case_count == 245
        assert event.death_count == 3
        assert len(event.explicit_facts) > 0
        assert len(event.unknowns) > 0
        assert event.content_hash is not None

    def test_extraction_with_no_content(self, extractor):
        """Test extraction with empty content."""
        result = extractor.extract("", "https://example.com", "test_source")
        assert result.success is True
        assert result.event is not None


class TestExtractorFactory:
    """Test extractor factory function."""

    def test_get_heuristic_extractor(self):
        """Test getting heuristic extractor."""
        extractor = get_extractor("heuristic")
        assert isinstance(extractor, HeuristicExtractor)

    def test_get_unknown_extractor(self):
        """Test getting unknown extractor type."""
        with pytest.raises(ValueError):
            get_extractor("unknown")
