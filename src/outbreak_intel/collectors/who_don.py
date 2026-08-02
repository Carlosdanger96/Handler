"""
WHO Disease Outbreak News Collector.

This module collects disease outbreak news from the World Health Organization's
Disease Outbreak News (DON) page.
"""

from datetime import datetime
from typing import Optional, Any
import feedparser

from .base import BaseCollector, CollectorResult
from ..models import EventCard, EventType, PriorityBand, ReviewStatus, Geography
from ..config import AppConfig


class WHO_DON_Collector(BaseCollector):
    """Collector for WHO Disease Outbreak News."""

    def get_source_id(self) -> str:
        return "who_don"

    def get_source_name(self) -> str:
        return "WHO Disease Outbreak News"

    def get_base_url(self) -> str:
        return "https://www.who.int/emergencies/disease-outbreak-news"

    def collect(self) -> CollectorResult:
        """Collect WHO DON data."""
        retrieved_at = datetime.utcnow()

        try:
            items = []

            # Try to use RSS feed first
            feed_url = self.source_config.feed_url or "https://www.who.int/feeds/entity/134702/rss"

            try:
                feed = feedparser.parse(feed_url)
                items.extend(self._parse_feed(feed))
            except Exception:
                pass

            # Also parse the main page
            html = self._fetch_url(self.get_base_url())
            if html:
                items.extend(self._parse_html_page(html))

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

    def _parse_html_page(self, html: str) -> list[dict[str, Any]]:
        """Parse the WHO DON HTML page."""
        soup = self._parse_html(html)
        items = []

        # Look for outbreak news entries
        news_sections = soup.find_all("div", class_=["outbreak-news", "don-item", "news-item"])

        if not news_sections:
            # Try to find any content that looks like outbreak news
            main_content = soup.find("main") or soup.find("div", class_="content") or soup

            # Look for links that might be outbreak news
            links = main_content.find_all("a", href=True)
            for link in links:
                href = link.get("href", "")
                text = link.get_text(strip=True)

                # Check if this looks like outbreak news
                if (
                    "outbreak" in href.lower()
                    or "disease" in href.lower()
                    or "outbreak" in text.lower()
                    or "disease" in text.lower()
                ):
                    # Try to find more context
                    parent = link.parent
                    summary = ""

                    if parent and parent.name in ["p", "div", "li", "article"]:
                        summary = parent.get_text(strip=True)

                    # Clean up URL
                    if href and not href.startswith("http"):
                        if href.startswith("/"):
                            href = f"https://www.who.int{href}"
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
            for section in news_sections:
                title_elem = section.find(["h2", "h3", "h4", "a"])
                title = title_elem.get_text(strip=True) if title_elem else "Untitled WHO DON"

                link_elem = section.find("a", href=True)
                url = link_elem.get("href", "") if link_elem else ""
                if url and not url.startswith("http"):
                    if url.startswith("/"):
                        url = f"https://www.who.int{url}"
                    else:
                        url = f"{self.get_base_url()}{url}"

                # Try to find date
                date_elem = section.find(
                    ["time", "span", "div"], class_=["date", "published", "timestamp"]
                )
                published = date_elem.get_text(strip=True) if date_elem else ""

                summary = section.get_text(strip=True)

                items.append(
                    {
                        "title": title,
                        "url": url,
                        "published": published,
                        "summary": summary,
                        "content": "",
                    }
                )

        return items

    def parse_item(self, item_data: dict[str, Any]) -> Optional[EventCard]:
        """Parse a WHO DON item into an EventCard."""
        try:
            title = item_data.get("title", "Untitled WHO Disease Outbreak News")
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
                        "%d %b %Y",
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
            event_type = EventType.OUTBREAK
            if "advisory" in title.lower():
                event_type = EventType.ADVISORY
            elif "investigation" in title.lower():
                event_type = EventType.INVESTIGATION
            elif "update" in title.lower():
                event_type = EventType.UPDATE

            # Extract geography from title/summary
            geographies = self._extract_geography(title, summary)

            # Relevance reasons
            relevance_reasons = ["WHO Disease Outbreak News"]

            # Check for US/Idaho/PNW relevance
            us_terms = [
                "united states",
                "usa",
                "america",
                "idaho",
                "pacific northwest",
                "north america",
                "canada",
                "mexico",
            ]
            if any(term in title.lower() or term in summary.lower() for term in us_terms):
                relevance_reasons.append("US travel/importation relevance")
                if "idaho" in title.lower() or "idaho" in summary.lower():
                    relevance_reasons.append("Idaho relevance")

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
                            "source_attribution": "WHO DON",
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
                            "source_attribution": "WHO DON",
                            "confidence": "high",
                        }
                    )

                # Countries affected
                country_match = re.finditer(r"([A-Z][a-z]+(?: [A-Z][a-z]+)*)", content)
                for match in country_match:
                    country_name = match.group(1)
                    # Skip common non-country words
                    if (
                        country_name
                        not in [
                            "Health",
                            "Organization",
                            "World",
                            "Disease",
                            "Outbreak",
                            "News",
                            "Public",
                            "Report",
                        ]
                        and len(country_name) > 2
                    ):
                        explicit_facts.append(
                            {
                                "fact_text": f"Affects {country_name}",
                                "fact_type": "geographic_spread",
                                "source_attribution": "WHO DON",
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
                official_source="World Health Organization",
                explicit_facts=explicit_facts,
                unknowns=[],
                relevance_reasons=relevance_reasons,
                priority_score=0,
                priority_band=PriorityBand.ARCHIVE,
                summary=summary or content[:200] + "..."
                if content
                else "WHO Disease Outbreak News",
                content_hash=content_hash,
                review_status=ReviewStatus.PENDING,
                raw_content=content,
                metadata={
                    "source_type": "web",
                    "feed_url": self.source_config.feed_url,
                    "page_url": self.get_base_url(),
                },
            )

            return event

        except Exception as e:
            print(f"Error parsing WHO DON item: {e}")
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
            r"(?:Yellow fever)",
            r"(?:Cholera|Vibrio cholerae)",
            r"(?:Marburg|Marburg virus)",
            r"(?:Lassa fever)",
            r"(?:Rift Valley fever)",
            r"(?:Crimean\-Congo hemorrhagic fever)",
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
                    "WHO",
                    "Public",
                    "Advisory",
                    "Outbreak",
                    "Investigation",
                    "Update",
                    "World",
                    "Organization",
                    "Disease",
                    "News",
                    "Report",
                    "Global",
                    "International",
                ]
            ):
                return word

        return None

    def _extract_geography(self, title: str, summary: str) -> list[Geography]:
        """Extract geographic information from title and summary."""
        import re

        geographies = []
        text = f"{title} {summary}"

        # Country patterns
        country_patterns = [
            (r"\b(?:United States|USA|US|America)\b", "United States"),
            (r"\b(?:Idaho)\b", "Idaho"),
            (r"\b(?:Canada)\b", "Canada"),
            (r"\b(?:Mexico)\b", "Mexico"),
            (r"\b(?:Pacific Northwest)\b", "Pacific Northwest"),
            (r"\b(?:North America)\b", "North America"),
            (r"\b(?:South America)\b", "South America"),
            (r"\b(?:Europe)\b", "Europe"),
            (r"\b(?:Africa)\b", "Africa"),
            (r"\b(?:Asia)\b", "Asia"),
            (r"\b(?:Australia)\b", "Australia"),
            (r"\b(?:Oceania)\b", "Oceania"),
        ]

        for pattern, region in country_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                if region == "Idaho":
                    geographies.append(Geography(country="United States", state="Idaho"))
                    geographies.append(Geography(region="Pacific Northwest"))
                elif region == "United States":
                    geographies.append(Geography(country="United States"))
                elif region == "Pacific Northwest":
                    geographies.append(Geography(region="Pacific Northwest"))
                else:
                    geographies.append(Geography(country=region))

        # If no specific geography found, add global
        if not geographies:
            geographies.append(Geography(region="Global"))

        return geographies
