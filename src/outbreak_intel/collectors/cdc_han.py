"""
CDC Health Alert Network (HAN) Collector.

This module collects health alerts from the CDC's Health Alert Network,
which provides urgent health information to public health officials.
"""

from datetime import datetime
from typing import Optional, Any
import feedparser

from .base import BaseCollector, CollectorResult
from ..models import EventCard, EventType, PriorityBand, ReviewStatus, Geography
from ..config import AppConfig


class CDC_HAN_Collector(BaseCollector):
    """Collector for CDC Health Alert Network."""

    def get_source_id(self) -> str:
        return "cdc_han"

    def get_source_name(self) -> str:
        return "CDC Health Alert Network"

    def get_base_url(self) -> str:
        return "https://emergency.cdc.gov/han/"

    def collect(self) -> CollectorResult:
        """Collect CDC HAN alerts."""
        retrieved_at = datetime.utcnow()

        try:
            # Try to use RSS feed first
            feed_url = self.source_config.feed_url or "https://emergency.cdc.gov/han/han-rss.asp"

            try:
                feed = feedparser.parse(feed_url)
                items = self._parse_feed(feed)
            except Exception as e:
                # Fall back to HTML parsing
                html = self._fetch_url(self.get_base_url())
                if html:
                    items = self._parse_html_page(html)
                else:
                    raise Exception(f"Failed to fetch CDC HAN data: {e}")

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
        """Parse the CDC HAN HTML page."""
        soup = self._parse_html(html)
        items = []

        # Look for alert entries - this is a simplified parser
        # CDC HAN pages typically have alert entries in specific divs
        alert_sections = soup.find_all("div", class_=["han-alert", "alert", "han-item"])

        if not alert_sections:
            # Try to find any links that might be alerts
            main_content = soup.find("main") or soup.find("div", class_="content") or soup
            links = main_content.find_all("a", href=True)

            for link in links:
                href = link.get("href", "")
                if href and ("han" in href.lower() or "alert" in href.lower()):
                    # Try to extract more info
                    title = link.get_text(strip=True)
                    parent = link.parent
                    summary = ""

                    # Look for nearby text that might be a summary
                    if parent and parent.name == "p":
                        summary = parent.get_text(strip=True)
                    elif link.find_next_sibling():
                        summary = link.find_next_sibling().get_text(strip=True)

                    items.append(
                        {
                            "title": title,
                            "url": href
                            if href.startswith("http")
                            else f"{self.get_base_url()}{href}",
                            "published": "",
                            "summary": summary,
                            "content": "",
                        }
                    )
        else:
            for section in alert_sections:
                title_elem = section.find(["h2", "h3", "h4"])
                title = title_elem.get_text(strip=True) if title_elem else "Untitled Alert"

                link_elem = section.find("a", href=True)
                url = link_elem.get("href", "") if link_elem else ""
                if url and not url.startswith("http"):
                    url = f"{self.get_base_url()}{url}"

                summary = section.get_text(strip=True)

                items.append(
                    {"title": title, "url": url, "published": "", "summary": summary, "content": ""}
                )

        return items

    def parse_item(self, item_data: dict[str, Any]) -> Optional[EventCard]:
        """Parse a CDC HAN item into an EventCard."""
        try:
            title = item_data.get("title", "Untitled CDC HAN Alert")
            url = item_data.get("url", self.get_base_url())
            published_str = item_data.get("published", "")
            summary = item_data.get("summary", "")
            content = item_data.get("content", "")

            # Parse published date
            published_at = None
            if published_str:
                try:
                    # Try various date formats
                    for fmt in [
                        "%a, %d %b %Y %H:%M:%S %z",
                        "%a, %d %b %Y %H:%M:%S",
                        "%Y-%m-%d %H:%M:%S",
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

            # Extract disease/hazard from title (simple heuristic)
            disease_or_hazard = self._extract_disease_from_title(title)

            # Determine event type
            event_type = EventType.HEALTH_ALERT
            if "outbreak" in title.lower():
                event_type = EventType.OUTBREAK
            elif "investigation" in title.lower():
                event_type = EventType.INVESTIGATION
            elif "advisory" in title.lower():
                event_type = EventType.ADVISORY

            # Create geography - CDC HAN is US-focused
            geographies = [Geography(country="United States")]

            # Check for Idaho/PNW relevance
            relevance_reasons = ["CDC Health Alert Network"]
            if "idaho" in title.lower() or "idaho" in summary.lower():
                relevance_reasons.append("Idaho relevance")
                geographies.append(Geography(country="United States", state="Idaho"))

            # Check for healthcare relevance
            if any(
                term in title.lower() or term in summary.lower()
                for term in ["healthcare", "hospital", "clinical", "medical", "infection"]
            ):
                relevance_reasons.append("Healthcare relevance")

            # Create explicit facts
            explicit_facts = []
            if content:
                # Simple fact extraction - look for specific patterns
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
                            "source_attribution": "CDC HAN",
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
                            "source_attribution": "CDC HAN",
                            "confidence": "high",
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
                case_count=None,  # Will be extracted later
                death_count=None,  # Will be extracted later
                affected_settings=["public_health", "healthcare"]
                if "healthcare" in relevance_reasons
                else ["public_health"],
                official_source="CDC Health Alert Network",
                explicit_facts=explicit_facts,
                unknowns=[],  # Will be populated by extraction
                relevance_reasons=relevance_reasons,
                priority_score=0,  # Will be calculated by scoring
                priority_band=PriorityBand.ARCHIVE,  # Will be calculated by scoring
                summary=summary or content[:200] + "..." if content else "CDC Health Alert",
                content_hash=content_hash,
                review_status=ReviewStatus.PENDING,
                raw_content=content,
                metadata={"source_type": "rss", "feed_url": self.source_config.feed_url},
            )

            return event

        except Exception as e:
            print(f"Error parsing CDC HAN item: {e}")
            return None

    def _extract_disease_from_title(self, title: str) -> Optional[str]:
        """Extract disease or hazard from title using simple patterns."""
        import re

        # Common disease patterns
        disease_patterns = [
            r"(?:COVID\-19|SARS\-CoV\-2|Coronavirus)",
            r"(?:Influenza|Flu)",
            r"(?:Measles|Rubeola)",
            r"(?:Ebola|EVD)",
            r"(?:Mpox|Monkeypox)",
            r"(?:Dengue|Chikungunya|Zika)",
            r"(?:Salmonella|E\. coli|Listeria)",
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
                and word not in ["Health", "Alert", "Network", "CDC", "Public", "Advisory"]
            ):
                return word

        return None
