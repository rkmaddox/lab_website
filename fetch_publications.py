#!/usr/bin/env python3
"""
fetch_publications.py — Auto-populate publications for the Maddox Lab website.

Searches PubMed for published papers and preprints, then checks each preprint
against the bioRxiv/medRxiv API to filter out ones that have been published.

Usage:
    python fetch_publications.py

What it does:
  1. Searches PubMed for all papers + preprints matching the author query
  2. Identifies preprints (journal = bioRxiv/medRxiv)
  3. For each preprint, checks the bioRxiv/medRxiv API to see if it has been
     published — if so, the preprint is excluded (the published version from
     PubMed is used instead)
  4. Writes _data/publications.yml

Manual edits to highlight and pdf fields are preserved across re-runs.
"""

import os
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone

import requests
import yaml

# =============================================================================
# Configuration — edit these to match your lab
# =============================================================================
PUBMED_QUERY = "maddox rk[au]"
OUTPUT_FILE = os.path.join("_data", "publications.yml")

# API endpoints
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
BIORXIV_API = "https://api.biorxiv.org"

# Rate limiting (NCBI allows 3 req/sec without API key)
API_DELAY = 0.35

# Drop preprints older than this many years (likely published under a different
# title or abandoned)
PREPRINT_MAX_AGE_YEARS = 2

# Journal names that indicate a preprint
PREPRINT_JOURNALS = {"biorxiv", "medrxiv"}


# =============================================================================
# PubMed Functions
# =============================================================================

def search_pubmed(query, retmax=500):
    """Search PubMed and return a list of PMIDs."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": retmax,
    }
    resp = requests.get(ESEARCH_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    pmids = data["esearchresult"]["idlist"]
    total = int(data["esearchresult"]["count"])
    print(f"  PubMed search returned {total} results")
    return pmids


def fetch_pubmed_records(pmids, batch_size=100):
    """Fetch full PubMed XML records in batches. Returns list of paper dicts."""
    papers = []
    for i in range(0, len(pmids), batch_size):
        batch = pmids[i : i + batch_size]
        params = {
            "db": "pubmed",
            "id": ",".join(batch),
            "retmode": "xml",
        }
        resp = requests.get(EFETCH_URL, params=params, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        for article_elem in root.findall(".//PubmedArticle"):
            paper = _parse_pubmed_article(article_elem)
            if paper:
                papers.append(paper)

        if i + batch_size < len(pmids):
            time.sleep(API_DELAY)

    return papers


def _parse_pubmed_article(article_elem):
    """Parse a single <PubmedArticle> XML element into a dict."""
    citation = article_elem.find("MedlineCitation")
    if citation is None:
        return None
    article = citation.find("Article")
    if article is None:
        return None

    # --- Title ---
    title_elem = article.find("ArticleTitle")
    title = _get_all_text(title_elem) if title_elem is not None else ""
    if title.endswith("."):
        title = title[:-1]

    # --- Authors ---
    authors = []
    author_list = article.find("AuthorList")
    if author_list is not None:
        for author in author_list.findall("Author"):
            last = _xml_text(author, "LastName")
            initials = _xml_text(author, "Initials")
            if last:
                authors.append(f"{last} {initials}" if initials else last)
            else:
                collective = _xml_text(author, "CollectiveName")
                if collective:
                    authors.append(collective)
    authors_str = ", ".join(authors)

    # --- Journal ---
    journal_elem = article.find("Journal")
    journal = ""
    volume = ""
    issue = ""
    year = ""

    if journal_elem is not None:
        journal = _xml_text(journal_elem, "ISOAbbreviation") or _xml_text(
            journal_elem, "Title"
        )
        ji = journal_elem.find("JournalIssue")
        if ji is not None:
            volume = _xml_text(ji, "Volume")
            issue = _xml_text(ji, "Issue")
            year = _extract_year(ji.find("PubDate"))

    # --- Pages ---
    pages = ""
    pagination = article.find("Pagination")
    if pagination is not None:
        pages = _xml_text(pagination, "MedlinePgn")

    # --- DOI ---
    doi = ""
    pubmed_data = article_elem.find("PubmedData")
    if pubmed_data is not None:
        for aid in pubmed_data.findall(".//ArticleId"):
            if aid.get("IdType") == "doi" and aid.text:
                doi = f"https://doi.org/{aid.text}"
                break
    if not doi:
        for eloc in article.findall("ELocationID"):
            if eloc.get("EIdType") == "doi" and eloc.text:
                doi = f"https://doi.org/{eloc.text}"
                break

    # --- Detect preprint ---
    is_preprint = _is_preprint_journal(journal)

    # --- Volume string ---
    vol_str = ""
    if not is_preprint:
        if volume:
            vol_str = volume
            if issue:
                vol_str += f"({issue})"
            if pages:
                vol_str += f", {pages}"
        elif pages:
            vol_str = pages

    if not year:
        return None

    return {
        "title": title,
        "authors": authors_str,
        "journal": _normalize_preprint_journal(journal) if is_preprint else journal,
        "volume": vol_str,
        "doi": doi,
        "year": int(year),
        "is_preprint": is_preprint,
    }


def _is_preprint_journal(journal):
    """Check if a journal name indicates a preprint server."""
    j = journal.lower().replace(" ", "").replace(".", "")
    return j in PREPRINT_JOURNALS or "biorxiv" in j or "medrxiv" in j


def _normalize_preprint_journal(journal):
    """Return a clean display name for preprint servers."""
    j = journal.lower()
    if "medrxiv" in j:
        return "medRxiv"
    return "bioRxiv"


def _xml_text(parent, tag):
    """Get text content of a child element, or empty string."""
    elem = parent.find(tag)
    if elem is not None and elem.text:
        return elem.text.strip()
    return ""


def _get_all_text(elem):
    """Get all text content from an element, including text inside child tags."""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        if child.text:
            parts.append(child.text)
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


def _extract_year(pubdate_elem):
    """Extract year from a PubDate element."""
    if pubdate_elem is None:
        return ""
    year_elem = pubdate_elem.find("Year")
    if year_elem is not None and year_elem.text:
        return year_elem.text
    medline_date = pubdate_elem.find("MedlineDate")
    if medline_date is not None and medline_date.text:
        match = re.search(r"(\d{4})", medline_date.text)
        if match:
            return match.group(1)
    return ""


# =============================================================================
# bioRxiv/medRxiv Publication Check
# =============================================================================

def check_preprint_published(doi_url):
    """
    Query the bioRxiv/medRxiv API to check if a preprint has been published.

    Takes a full DOI URL (https://doi.org/10.1101/...) and returns True if
    published, False otherwise.
    """
    # Extract the raw DOI (e.g., 10.1101/2024.01.15.123456)
    raw_doi = doi_url.replace("https://doi.org/", "").replace("http://doi.org/", "")

    for server in ["biorxiv", "medrxiv"]:
        url = f"{BIORXIV_API}/pubs/{server}/{raw_doi}/na/json"
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                collection = data.get("collection", [])
                if collection:
                    pub_doi = collection[0].get("published_doi", "")
                    if pub_doi:
                        return True
                    return False  # Found on this server, not published
        except (requests.RequestException, ValueError):
            pass
        time.sleep(API_DELAY)

    # Not found on either server — assume not published
    return False


# =============================================================================
# Combine and Output
# =============================================================================

def normalize_title(title):
    """Normalize a title for fuzzy matching."""
    t = title.lower()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _title_similarity(a, b):
    """
    Simple word-overlap similarity between two normalized titles.
    Returns a float 0..1. Catches typos like 'Psuedo' vs 'Pseudo' because
    most other words still match.
    """
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return len(intersection) / max(len(words_a), len(words_b))


def _matches_any_published(preprint_title, published_titles):
    """Check if a preprint title matches any published title (exact or fuzzy)."""
    norm = normalize_title(preprint_title)
    # Exact match
    if norm in published_titles:
        return True
    # Fuzzy match (>85% word overlap catches typo corrections, minor rewording)
    for pub_title in published_titles:
        if _title_similarity(norm, pub_title) > 0.85:
            return True
    return False


def filter_preprints(papers):
    """
    Separate papers into published and preprints, then filter out preprints
    that have been published (checking the bioRxiv/medRxiv API).
    """
    published = [p for p in papers if not p["is_preprint"]]
    preprints = [p for p in papers if p["is_preprint"]]

    if not preprints:
        return published

    print(f"  Found {len(preprints)} preprints — checking publication status...")

    # Build title set of published papers for quick matching
    published_titles = {normalize_title(p["title"]) for p in published}

    kept_preprints = []
    for pp in preprints:
        short_title = pp["title"][:60]

        # Check 1: Does the published version already appear in our results?
        # Uses fuzzy matching to handle title changes between preprint and paper
        if _matches_any_published(pp["title"], published_titles):
            print(f"    skip (published version in results): {short_title}...")
            continue

        # Check 2: Drop preprints older than PREPRINT_MAX_AGE_YEARS
        cutoff_year = datetime.now(timezone.utc).year - PREPRINT_MAX_AGE_YEARS
        if pp["year"] < cutoff_year:
            print(f"    skip (older than {PREPRINT_MAX_AGE_YEARS} years):          {short_title}...")
            continue

        # Check 3: Ask the bioRxiv/medRxiv API
        if pp["doi"]:
            print(f"    checking: {short_title}...")
            if check_preprint_published(pp["doi"]):
                print(f"    skip (published per API):            {short_title}...")
                continue

        print(f"    KEEP preprint:                       {short_title}...")
        kept_preprints.append(pp)

    print(f"  Keeping {len(kept_preprints)} unpublished preprints")
    return published + kept_preprints


def group_by_year(papers):
    """Group papers by year (descending) for YAML output."""
    by_year = defaultdict(list)
    for paper in papers:
        by_year[paper["year"]].append(paper)

    result = []
    for year in sorted(by_year.keys(), reverse=True):
        year_papers = sorted(by_year[year], key=lambda p: p["title"].lower())
        year_entry = {"year": year, "papers": []}
        for p in year_papers:
            entry = {
                "id": "",
                "title": p["title"],
                "authors": p["authors"],
                "journal": p["journal"],
                "volume": p["volume"],
                "doi": p["doi"],
                "pdf": "",
                "highlight": False,
                "preprint": p["is_preprint"],
            }
            year_entry["papers"].append(entry)
        result.append(year_entry)

    return result


def merge_with_existing(new_publications, output_file):
    """
    Preserve manually-set 'highlight' and 'pdf' values from an existing YAML.

    This means you can run the script repeatedly without losing your edits
    to those fields.
    """
    if not os.path.exists(output_file):
        return new_publications

    try:
        with open(output_file, "r", encoding="utf-8") as f:
            existing = yaml.safe_load(f)
    except Exception:
        return new_publications

    if not existing:
        return new_publications

    # Build lookup: normalized title → existing paper entry
    existing_lookup = {}
    for year_group in existing:
        if not isinstance(year_group, dict):
            continue
        for paper in year_group.get("papers", []):
            key = normalize_title(paper.get("title", ""))
            existing_lookup[key] = paper

    # Merge preserved fields
    for year_group in new_publications:
        for paper in year_group["papers"]:
            key = normalize_title(paper["title"])
            if key in existing_lookup:
                old = existing_lookup[key]
                paper["id"] = old.get("id", "")
                paper["highlight"] = old.get("highlight", False)
                paper["pdf"] = old.get("pdf", "")

    return new_publications


def write_yaml(publications, output_file):
    """Write publications list to YAML with a header comment."""
    header = (
        "# =============================================================================\n"
        "# Publications — AUTO-GENERATED by fetch_publications.py\n"
        "# =============================================================================\n"
        "# To regenerate: python fetch_publications.py\n"
        "#\n"
        "# Safe to edit:\n"
        "#   id: short-id         — unique ID for cross-referencing from research.yml\n"
        "#   highlight: true/false — accent border for key papers\n"
        "#   pdf: \"url\"           — link to PDF file\n"
        "# These fields are preserved when you re-run the script.\n"
        "#\n"
        "# preprint: true means the entry will show bold 'Preprint.' on the website.\n"
        "# =============================================================================\n\n"
    )

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.dump(
            publications,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )

    total = sum(len(y["papers"]) for y in publications)
    preprint_count = sum(
        1 for y in publications for p in y["papers"] if p["preprint"]
    )
    print(f"\nWrote {output_file}: {total} entries "
          f"({total - preprint_count} published, {preprint_count} preprints)")


# =============================================================================
# Main
# =============================================================================

def main():
    print("=" * 60)
    print("  Maddox Lab — Publication Fetcher")
    print("=" * 60)

    # Step 1: Search PubMed (returns both published papers and preprints)
    print(f"\n[1/3] Searching PubMed for \"{PUBMED_QUERY}\"...")
    pmids = search_pubmed(PUBMED_QUERY)
    all_papers = fetch_pubmed_records(pmids)
    n_preprints = sum(1 for p in all_papers if p["is_preprint"])
    print(f"  Retrieved {len(all_papers)} records "
          f"({len(all_papers) - n_preprints} published, {n_preprints} preprints)")

    # Step 2: Filter preprints — check bioRxiv/medRxiv API for each one
    print(f"\n[2/3] Filtering preprints...")
    filtered = filter_preprints(all_papers)

    # Step 3: Group by year and write
    publications = group_by_year(filtered)
    publications = merge_with_existing(publications, OUTPUT_FILE)

    print(f"\n[3/3] Writing {OUTPUT_FILE}...")
    write_yaml(publications, OUTPUT_FILE)

    print("\nDone!")


if __name__ == "__main__":
    main()
