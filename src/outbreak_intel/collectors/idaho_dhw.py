"""
Idaho Department of Health and Welfare Collector.

This module collects communicable disease and infection prevention information
from the Idaho Department of Health and Welfare website.
"""

from datetime import datetime
from typing import Optional, Any
import feedparser

from .base import BaseCollector, CollectorResult
from ..models import EventCard, EventType, PriorityBand, ReviewStatus, Geography
from ..config import AppConfig


class Idaho_DHW_Collector(BaseCollector):
    """Collector for Idaho Department of Health and Welfare."""

    def get_source_id(self) -> str:
        return "idaho_dhw"

    def get_source_name(self) -> str:
        return "Idaho Department of Health and Welfare"

    def get_base_url(self) -> str:
        return "https://healthandwelfare.idaho.gov/services/health/epidemiology-disease-control/communicable-diseases"

    def collect(self) -> CollectorResult:
        """Collect Idaho DHW data."""
        retrieved_at = datetime.utcnow()

        try:
            items = []

            # Try to use RSS feed if available
            if self.source_config.feed_url:
                try:
                    feed = feedparser.parse(self.source_config.feed_url)
                    items.extend(self._parse_feed(feed))
                except Exception:
                    pass

            # Parse the main communicable diseases page
            html = self._fetch_url(self.get_base_url())
            if html:
                items.extend(self._parse_communicable_diseases_page(html))

            # Also try the infection prevention page
            ip_url = "https://healthandwelfare.idaho.gov/services/health/epidemiology-disease-control/infection-prevention"
            try:
                html = self._fetch_url(ip_url)
                if html:
                    items.extend(self._parse_infection_prevention_page(html))
            except Exception:
                pass

            # Remove duplicates by URL
            seen_urls = set()
            unique_items = []
            for item in items:
                url = item.get("url", "")
                if url not in seen_urls:
                    unique_items.append(item)
                    seen_urls.add(url)

            return CollectorResult(
                source_id=self.get_source_id(),
                source_name=self.get_source_name(),
                success=True,
                retrieved_at=retrieved_at,
                items=unique_items,
            )

        except Exception as e:
            return CollectorResult(
                source_id=self.get_source_id(),
                source_name=self.get_source_name(),
                success=False,
                retrieved_at=retrieved_at,
                error_message=str(e),
            )

    def _parse_feed(self, feed: Any) -> list[dict[str, Any]]:
        """Parse RSS feed entries."""
        items = []

        for entry in feed.entries:
            item = {
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", ""),
                "content": entry.get("content", [{}])[0].get("value", "")
                if entry.get("content")
                else "",
            }
            items.append(item)

        return items

    def _parse_communicable_diseases_page(self, html: str) -> list[dict[str, Any]]:
        """Parse the Idaho DHW communicable diseases page."""
        soup = self._parse_html(html)
        items = []

        # Look for disease information sections
        disease_sections = soup.find_all("div", class_=["disease", "communicable", "health-alert"])

        if not disease_sections:
            # Try to find any content that looks like disease info
            main_content = soup.find("main") or soup.find("div", class_="content") or soup

            # Look for headings that might indicate disease sections
            headings = main_content.find_all(["h2", "h3", "h4"])
            for heading in headings:
                title = heading.get_text(strip=True)

                # Check if this looks like a disease or health topic
                if (
                    "disease" in title.lower()
                    or "outbreak" in title.lower()
                    or "infection" in title.lower()
                    or "health" in title.lower()
                ):
                    # Try to find more context
                    next_sibling = heading.find_next_sibling()
                    summary = ""

                    if next_sibling and next_sibling.name in ["p", "div", "ul", "ol"]:
                        summary = next_sibling.get_text(strip=True)

                    # Look for links
                    link = heading.find("a", href=True)
                    url = ""
                    if link:
                        url = link.get("href", "")
                        if url and not url.startswith("http"):
                            if url.startswith("/"):
                                url = f"https://healthandwelfare.idaho.gov{url}"
                            else:
                                url = f"{self.get_base_url()}{url}"

                    items.append(
                        {
                            "title": title,
                            "url": url or self.get_base_url(),
                            "published": "",
                            "summary": summary,
                            "content": "",
                            "page_type": "communicable_diseases",
                        }
                    )
        else:
            for section in disease_sections:
                title_elem = section.find(["h2", "h3", "h4", "a"])
                title = title_elem.get_text(strip=True) if title_elem else "Untitled Disease Info"

                link_elem = section.find("a", href=True)
                url = link_elem.get("href", "") if link_elem else ""
                if url and not url.startswith("http"):
                    if url.startswith("/"):
                        url = f"https://healthandwelfare.idaho.gov{url}"
                    else:
                        url = f"{self.get_base_url()}{url}"

                summary = section.get_text(strip=True)

                items.append(
                    {
                        "title": title,
                        "url": url,
                        "published": "",
                        "summary": summary,
                        "content": "",
                        "page_type": "communicable_diseases",
                    }
                )

        return items

    def _parse_infection_prevention_page(self, html: str) -> list[dict[str, Any]]:
        """Parse the Idaho DHW infection prevention page."""
        soup = self._parse_html(html)
        items = []

        # Look for infection prevention content
        ip_sections = soup.find_all(
            "div", class_=["infection-prevention", "ip-guidance", "guideline"]
        )

        if not ip_sections:
            # Try to find any content that looks like infection prevention info
            main_content = soup.find("main") or soup.find("div", class_="content") or soup

            # Look for headings that might indicate infection prevention sections
            headings = main_content.find_all(["h2", "h3", "h4"])
            for heading in headings:
                title = heading.get_text(strip=True)

                # Check if this looks like infection prevention content
                if (
                    "infection" in title.lower()
                    or "prevention" in title.lower()
                    or "control" in title.lower()
                    or "guidance" in title.lower()
                ):
                    # Try to find more context
                    next_sibling = heading.find_next_sibling()
                    summary = ""

                    if next_sibling and next_sibling.name in ["p", "div", "ul", "ol"]:
                        summary = next_sibling.get_text(strip=True)

                    # Look for links
                    link = heading.find("a", href=True)
                    url = ""
                    if link:
                        url = link.get("href", "")
                        if url and not url.startswith("http"):
                            if url.startswith("/"):
                                url = f"https://healthandwelfare.idaho.gov{url}"
                            else:
                                url = f"https://healthandwelfare.idaho.gov/services/health/epidemiology-disease-control/{url}"

                    items.append(
                        {
                            "title": title,
                            "url": url
                            or "https://healthandwelfare.idaho.gov/services/health/epidemiology-disease-control/infection-prevention",
                            "published": "",
                            "summary": summary,
                            "content": "",
                            "page_type": "infection_prevention",
                        }
                    )
        else:
            for section in ip_sections:
                title_elem = section.find(["h2", "h3", "h4", "a"])
                title = title_elem.get_text(strip=True) if title_elem else "Untitled IP Guidance"

                link_elem = section.find("a", href=True)
                url = link_elem.get("href", "") if link_elem else ""
                if url and not url.startswith("http"):
                    if url.startswith("/"):
                        url = f"https://healthandwelfare.idaho.gov{url}"
                    else:
                        url = f"https://healthandwelfare.idaho.gov/services/health/epidemiology-disease-control/{url}"

                summary = section.get_text(strip=True)

                items.append(
                    {
                        "title": title,
                        "url": url,
                        "published": "",
                        "summary": summary,
                        "content": "",
                        "page_type": "infection_prevention",
                    }
                )

        return items

    def parse_item(self, item_data: dict[str, Any]) -> Optional[EventCard]:
        """Parse an Idaho DHW item into an EventCard."""
        try:
            title = item_data.get("title", "Untitled Idaho DHW Notice")
            url = item_data.get("url", self.get_base_url())
            published_str = item_data.get("published", "")
            summary = item_data.get("summary", "")
            content = item_data.get("content", "")
            page_type = item_data.get("page_type", "unknown")

            # Parse published date
            published_at = None
            if published_str:
                try:
                    for fmt in [
                        "%a, %d %b %Y %H:%M:%S %z",
                        "%a, %d %b %Y %H:%M:%S",
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%d",
                    ]:
                        try:
                            published_at = datetime.strptime(published_str, fmt)
                            break
                        except ValueError:
                            continue
                except:
                    pass

            # Generate deterministic IDs
            event_id = EventCard.generate_event_id(
                source_id=self.get_source_id(), source_url=url, published_at=published_at
            )

            content_hash = EventCard.generate_content_hash(content, url)

            # Extract disease/hazard from title
            disease_or_hazard = self._extract_disease_from_title(title)

            # Determine event type
            event_type = EventType.UPDATE
            if "outbreak" in title.lower():
                event_type = EventType.OUTBREAK
            elif "advisory" in title.lower() or "alert" in title.lower():
                event_type = EventType.HEALTH_ALERT
            elif "guidance" in title.lower() or "recommendation" in title.lower():
                event_type = EventType.ADVISORY

            # Idaho-specific geography
            geographies = [
                Geography(country="United States", state="Idaho"),
                Geography(region="Pacific Northwest"),
            ]

            # Relevance reasons - Idaho DHW is always highly relevant for Idaho
            relevance_reasons = [
                "Idaho Department of Health and Welfare",
                "Idaho relevance",
                "Pacific Northwest relevance",
            ]

            # Check for healthcare relevance
            if any(
                term in title.lower() or term in summary.lower()
                for term in ["healthcare", "hospital", "clinical", "medical", "infection"]
            ):
                relevance_reasons.append("Healthcare relevance")

            # Create explicit facts
            explicit_facts = []
            if content:
                import re

                # Case counts
                case_match = re.search(
                    r"(\d+)\s*(?:cases?|infections?|illnesses?)", content, re.IGNORECASE
                )
                if case_match:
                    explicit_facts.append(
                        {
                            "fact_text": f"{case_match.group(1)} cases reported in Idaho",
                            "fact_type": "case_count",
                            "source_attribution": "Idaho DHW",
                            "confidence": "high",
                        }
                    )

                # Death counts
                death_match = re.search(
                    r"(\d+)\s*(?:deaths?|fatalities?|died)", content, re.IGNORECASE
                )
                if death_match:
                    explicit_facts.append(
                        {
                            "fact_text": f"{death_match.group(1)} deaths reported in Idaho",
                            "fact_type": "death_count",
                            "source_attribution": "Idaho DHW",
                            "confidence": "high",
                        }
                    )

                # County-specific information
                county_match = re.finditer(r"(?:[A-Z][a-z]+ )?County", content)
                for match in county_match:
                    # Try to get the county name
                    text_before = content[: match.start()]
                    county_name_match = re.search(
                        r"([A-Z][a-z]+(?: [A-Z][a-z]+)*) County", text_before + match.group(0)
                    )
                    if county_name_match:
                        county_name = county_name_match.group(1)
                        explicit_facts.append(
                            {
                                "fact_text": f"Affects {county_name} County, Idaho",
                                "fact_type": "geographic_spread",
                                "source_attribution": "Idaho DHW",
                                "confidence": "medium",
                            }
                        )

            # Create the event card
            event = EventCard(
                event_id=event_id,
                source_id=self.get_source_id(),
                source_name=self.get_source_name(),
                source_url=url,
                source_published_at=published_at,
                retrieved_at=datetime.utcnow(),
                title=title,
                disease_or_hazard=disease_or_hazard,
                event_type=event_type,
                geographies=geographies,
                case_count=None,
                death_count=None,
                affected_settings=["public_health", "healthcare"]
                if "Healthcare relevance" in relevance_reasons
                else ["public_health"],
                official_source="Idaho Department of Health and Welfare",
                explicit_facts=explicit_facts,
                unknowns=[],
                relevance_reasons=relevance_reasons,
                priority_score=0,
                priority_band=PriorityBand.ARCHIVE,
                summary=summary or content[:200] + "..." if content else "Idaho DHW Notice",
                content_hash=content_hash,
                review_status=ReviewStatus.PENDING,
                raw_content=content,
                metadata={
                    "source_type": "web",
                    "page_type": page_type,
                    "page_url": self.get_base_url(),
                },
            )

            return event

        except Exception as e:
            print(f"Error parsing Idaho DHW item: {e}")
            return None

    def _extract_disease_from_title(self, title: str) -> Optional[str]:
        """Extract disease or hazard from title."""
        import re

        # Common disease patterns
        disease_patterns = [
            r"(?:COVID\-19|SARS\-CoV\-2|Coronavirus)",
            r"(?:Influenza|Flu)",
            r"(?:Measles|Rubeola)",
            r"(?:Mpox|Monkeypox)",
            r"(?:Dengue|Chikungunya|Zika)",
            r"(?:Salmonella|E\. coli|Listeria|Shigella)",
            r"(?:Tuberculosis|TB)",
            r"(?:Hepatitis [ABC])",
            r"(?:HIV|AIDS)",
            r"(?:Rabies)",
            r"(?:Anthrax|Bacillus anthracis)",
            r"(?:Botulism|Clostridium botulinum)",
            r"(?:Plague|Yersinia pestis)",
            r"(?:Smallpox|Variola)",
            r"(?:Polio|Poliomyelitis)",
            r"(?:Legionnaires\' disease|Legionella)",
            r"(?:Meningitis|Meningococcal)",
            r"(?:Pertussis|Whooping cough)",
            r"(?:Varicella|Chickenpox)",
        ]

        for pattern in disease_patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return match.group(0)

        # Look for capitalized words that might be disease names
        words = title.split()
        for word in words:
            if (
                word[0].isupper()
                and len(word) > 3
                and word
                not in [
                    "Health",
                    "Alert",
                    "Network",
                    "CDC",
                    "Public",
                    "Advisory",
                    "Outbreak",
                    "Investigation",
                    "Update",
                    "United",
                    "States",
                    "Idaho",
                    "Department",
                    "Welfare",
                    "Disease",
                    "Control",
                    "Epidemiology",
                    "Services",
                    "Infection",
                    "Prevention",
                ]
            ):
                return word

        return None
