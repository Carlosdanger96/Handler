"""
CDC Outbreak Investigations Collector.

This module collects information about ongoing outbreak investigations
from the CDC's outbreak investigations page.
"""

from datetime import datetime
from typing import Optional, Any
import feedparser

from .base import BaseCollector, CollectorResult
from ..models import EventCard, EventType, PriorityBand, ReviewStatus, Geography
from ..config import AppConfig


class CDC_Outbreaks_Collector(BaseCollector):
    """Collector for CDC Outbreak Investigations."""

    def get_source_id(self) -> str:
        return "cdc_outbreaks"

    def get_source_name(self) -> str:
        return "CDC Outbreak Investigations"

    def get_base_url(self) -> str:
        return "https://www.cdc.gov/outbreaks/index.html"

    def collect(self) -> CollectorResult:
        """Collect CDC outbreak investigation data."""
        retrieved_at = datetime.utcnow()

        try:
            # Try to use RSS feed if available
            if self.source_config.feed_url:
                try:
                    feed = feedparser.parse(self.source_config.feed_url)
                    items = self._parse_feed(feed)
                except Exception:
                    items = []

            # Always try to parse the main page
            html = self._fetch_url(self.get_base_url())
            if html:
                page_items = self._parse_html_page(html)
                # Combine items, avoiding duplicates
                urls = set(item.get("url") for item in items)
                for item in page_items:
                    if item.get("url") not in urls:
                        items.append(item)
                        urls.add(item.get("url"))

            return CollectorResult(
                source_id=self.get_source_id(),
                source_name=self.get_source_name(),
                success=True,
                retrieved_at=retrieved_at,
                items=items,
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

    def _parse_html_page(self, html: str) -> list[dict[str, Any]]:
        """Parse the CDC Outbreaks HTML page."""
        soup = self._parse_html(html)
        items = []

        # Look for outbreak entries - CDC typically uses specific classes
        outbreak_sections = soup.find_all(
            "div", class_=["outbreak-item", "outbreak", "investigation"]
        )

        if not outbreak_sections:
            # Try to find any content that looks like outbreak info
            main_content = soup.find("main") or soup.find("div", class_="content") or soup

            # Look for links that might be outbreak investigations
            links = main_content.find_all("a", href=True)
            for link in links:
                href = link.get("href", "")
                text = link.get_text(strip=True)

                # Check if this looks like an outbreak investigation
                if (
                    "outbreak" in href.lower()
                    or "investigation" in href.lower()
                    or "outbreak" in text.lower()
                    or "investigation" in text.lower()
                ):
                    # Try to find more context
                    parent = link.parent
                    summary = ""

                    if parent and parent.name in ["p", "div", "li"]:
                        summary = parent.get_text(strip=True)

                    # Clean up URL
                    if href and not href.startswith("http"):
                        if href.startswith("/"):
                            href = f"https://www.cdc.gov{href}"
                        else:
                            href = f"{self.get_base_url()}{href}"

                    items.append(
                        {
                            "title": text,
                            "url": href,
                            "published": "",
                            "summary": summary,
                            "content": "",
                        }
                    )
        else:
            for section in outbreak_sections:
                title_elem = section.find(["h2", "h3", "h4", "a"])
                title = title_elem.get_text(strip=True) if title_elem else "Untitled Outbreak"

                link_elem = section.find("a", href=True)
                url = link_elem.get("href", "") if link_elem else ""
                if url and not url.startswith("http"):
                    if url.startswith("/"):
                        url = f"https://www.cdc.gov{url}"
                    else:
                        url = f"{self.get_base_url()}{url}"

                summary = section.get_text(strip=True)

                items.append(
                    {"title": title, "url": url, "published": "", "summary": summary, "content": ""}
                )

        return items

    def parse_item(self, item_data: dict[str, Any]) -> Optional[EventCard]:
        """Parse a CDC Outbreak item into an EventCard."""
        try:
            title = item_data.get("title", "Untitled CDC Outbreak Investigation")
            url = item_data.get("url", self.get_base_url())
            published_str = item_data.get("published", "")
            summary = item_data.get("summary", "")
            content = item_data.get("content", "")

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

            # Determine event type - CDC outbreaks are typically investigations
            event_type = EventType.INVESTIGATION
            if "outbreak" in title.lower():
                event_type = EventType.OUTBREAK
            elif "update" in title.lower():
                event_type = EventType.UPDATE

            # Create geography - CDC is US-focused
            geographies = [Geography(country="United States")]

            # Check for specific locations
            if "idaho" in title.lower() or "idaho" in summary.lower():
                relevance_reasons = ["CDC Outbreak Investigation", "Idaho relevance"]
                geographies.append(Geography(country="United States", state="Idaho"))
            else:
                relevance_reasons = ["CDC Outbreak Investigation"]

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
                            "fact_text": f"{case_match.group(1)} cases reported",
                            "fact_type": "case_count",
                            "source_attribution": "CDC Outbreak Investigation",
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
                            "fact_text": f"{death_match.group(1)} deaths reported",
                            "fact_type": "death_count",
                            "source_attribution": "CDC Outbreak Investigation",
                            "confidence": "high",
                        }
                    )

                # States affected
                state_match = re.finditer(r"([A-Z][a-z]+(?: [A-Z][a-z]+)*)", content)
                for match in state_match:
                    state_name = match.group(1)
                    # Check if it's a US state
                    us_states = [
                        "Alabama",
                        "Alaska",
                        "Arizona",
                        "Arkansas",
                        "California",
                        "Colorado",
                        "Connecticut",
                        "Delaware",
                        "Florida",
                        "Georgia",
                        "Hawaii",
                        "Idaho",
                        "Illinois",
                        "Indiana",
                        "Iowa",
                        "Kansas",
                        "Kentucky",
                        "Louisiana",
                        "Maine",
                        "Maryland",
                        "Massachusetts",
                        "Michigan",
                        "Minnesota",
                        "Mississippi",
                        "Missouri",
                        "Montana",
                        "Nebraska",
                        "Nevada",
                        "New Hampshire",
                        "New Jersey",
                        "New Mexico",
                        "New York",
                        "North Carolina",
                        "North Dakota",
                        "Ohio",
                        "Oklahoma",
                        "Oregon",
                        "Pennsylvania",
                        "Rhode Island",
                        "South Carolina",
                        "South Dakota",
                        "Tennessee",
                        "Texas",
                        "Utah",
                        "Vermont",
                        "Virginia",
                        "Washington",
                        "West Virginia",
                        "Wisconsin",
                        "Wyoming",
                    ]

                    if state_name in us_states:
                        explicit_facts.append(
                            {
                                "fact_text": f"Affects {state_name}",
                                "fact_type": "geographic_spread",
                                "source_attribution": "CDC Outbreak Investigation",
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
                official_source="CDC Outbreak Investigations",
                explicit_facts=explicit_facts,
                unknowns=[],
                relevance_reasons=relevance_reasons,
                priority_score=0,
                priority_band=PriorityBand.ARCHIVE,
                summary=summary or content[:200] + "..."
                if content
                else "CDC Outbreak Investigation",
                content_hash=content_hash,
                review_status=ReviewStatus.PENDING,
                raw_content=content,
                metadata={"source_type": "web", "page_url": self.get_base_url()},
            )

            return event

        except Exception as e:
            print(f"Error parsing CDC Outbreak item: {e}")
            return None

    def _extract_disease_from_title(self, title: str) -> Optional[str]:
        """Extract disease or hazard from title."""
        import re

        # Common disease patterns
        disease_patterns = [
            r"(?:COVID\-19|SARS\-CoV\-2|Coronavirus)",
            r"(?:Influenza|Flu)",
            r"(?:Measles|Rubeola)",
            r"(?:Ebola|EVD)",
            r"(?:Mpox|Monkeypox)",
            r"(?:Dengue|Chikungunya|Zika)",
            r"(?:Salmonella|E\. coli|Listeria|Shigella)",
            r"(?:Tuberculosis|TB)",
            r"(?:Hepatitis [ABC])",
            r"(?:HIV|AIDS)",
            r"(?:Malaria|Plasmodium)",
            r"(?:Rabies)",
            r"(?:Anthrax|Bacillus anthracis)",
            r"(?:Botulism|Clostridium botulinum)",
            r"(?:Plague|Yersinia pestis)",
            r"(?:Smallpox|Variola)",
            r"(?:Polio|Poliomyelitis)",
            r"(?:Legionnaires\' disease|Legionella)",
            r"(?:Meningitis|Meningococcal)",
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
                ]
            ):
                return word

        return None
