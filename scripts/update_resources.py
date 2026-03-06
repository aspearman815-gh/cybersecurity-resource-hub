#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import sys
import time
import traceback
import requests
from urllib.parse import urlencode, quote_plus
from bs4 import BeautifulSoup

# ---------------------------
# Paths & basic config
# ---------------------------

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DATA_DIR = os.path.join(BASE_DIR, ".data")
DATA_FILE = os.path.join(DATA_DIR, "seen.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (ResourceBot; +https://github.com/)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = 20  # seconds

# Environment controls (see workflow env:)
ENABLE_LINKEDIN_SCRAPE = os.getenv("ENABLE_LINKEDIN_SCRAPE", "false").lower() == "true"
LI_LOCATION = os.getenv("LI_LOCATION", "United States")
LI_REMOTE_ONLY = os.getenv("LI_REMOTE_ONLY", "true").lower() == "true"
LI_TIME_RANGE = os.getenv("LI_TIME_RANGE", "").strip()  # e.g., r86400 / r604800 / r2592000

INDEED_ENTRY_QUERY = os.getenv("INDEED_ENTRY_QUERY", '("cybersecurity" OR "security analyst" OR SOC) ("entry level" OR junior OR "analyst I" OR associate)')
INDEED_INTERN_QUERY = os.getenv("INDEED_INTERN_QUERY", '("cybersecurity" OR "information security") (intern OR internship)')
INDEED_LOCATION = os.getenv("INDEED_LOCATION", "Remote")

CYBER_KEYWORDS = [
    "cyber", "security", "infosec", "soc", "cloud security",
    "penetration", "red team", "blue team", "grc", "risk", "threat", "siem"
]

# ---------------------------
# Utils
# ---------------------------

def log(msg: str):
    print(f"[update_resources] {msg}")

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "careers"), exist_ok=True)

def load_seen():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"links": []}
    return {"links": []}

def save_seen(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def contains_cyber(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in CYBER_KEYWORDS)

def safe_get(d: dict, k: str, default: str = "") -> str:
    v = d.get(k, default) or default
    return v.strip()

def write_markdown(filepath, title, items):
    lines = [f"# {title}", ""]
    if not items:
        lines.append("_No current listings found._")
    else:
        for it in items:
            t = safe_get(it, "title", "Untitled")
            desc = safe_get(it, "description", "")
            link = safe_get(it, "link", "")
            if desc:
                lines.append(f"- **{t}**  \n  {desc}  \n  {link}")
            else:
                lines.append(f"- **{t}**  \n  {link}")
            lines.append("")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# ---------------------------
# RSS/Atom fetch
# ---------------------------

def parse_rss(url: str):
    """Return list of {title, link, description, published}."""
    log(f"Fetching RSS: {url}")
    out = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as ex:
        log(f"ERROR fetching {url}: {ex}")
        return out

    soup = None
    for parser_name in ("lxml-xml", "xml", "html.parser"):
        try:
            soup = BeautifulSoup(r.content, parser_name)
            if soup:
                break
        except Exception:
            soup = None
    if soup is None:
        return out

    for n in soup.find_all(["item", "entry"]):
        title = (n.find("title").text if n.find("title") else "").strip()
        link_tag = n.find("link")
        link = (link_tag.get("href") or link_tag.text or "").strip() if link_tag else ""
        desc = ""
        for tag in ("summary", "description", "content"):
            t = n.find(tag)
            if t and t.text:
                desc = t.text
                break
        pub = ""
        for tag in ("pubDate", "published", "updated"):
            t = n.find(tag)
            if t and t.text:
                pub = t.text
                break

        desc = " ".join((desc or "").split())
        if len(desc) > 240:
            desc = desc[:237] + "..."

        out.append({"title": title, "link": link, "description": desc, "published": pub})
    log(f"Parsed {len(out)} items from RSS")
    return out

def dedupe_and_filter(items, seen, limit=None):
    out = []
    for it in items:
        title = safe_get(it, "title")
        text = f"{title} {safe_get(it, 'description', '')}"
        if not contains_cyber(text):
            continue
        link = safe_get(it, "link")
        if link and link in seen["links"]:
            continue
        if link:
            seen["links"].append(link)
        out.append({"title": title, "link": link, "description": safe_get(it, "description")})
        if limit and len(out) >= limit:
            break
    return out

# ---------------------------
# LinkedIn (links by default; optional guest collector)
# ---------------------------

def linkedin_job_search_url(keywords: str, location: str, experience: str, remote_only: bool, time_range: str):
    """
    Build a LinkedIn jobs search URL.
    NOTE: LinkedIn prohibits automated scraping/automation; links are the safe default.  (Help Center policy)
    """
    params = {
        "keywords": keywords,
        "location": location,
        "sortBy": "DD",
    }
    if experience:
        params["f_E"] = experience      # 1=Internship, 2=Entry level (undocumented; may change)
    if remote_only:
        params["f_WT"] = "2"            # Remote (undocumented)
    if time_range:
        params["f_TPR"] = time_range    # freshness (e.g., r604800=7d)
    return f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"

def li_make_link_lists(location: str, remote_only: bool, time_range: str):
    entry_titles = [
        "cybersecurity analyst",
        "information security analyst",
        "soc analyst",
        "security operations analyst",
    ]
    intern_titles = [
        "cybersecurity intern",
        "information security intern",
        "soc intern",
        "security analyst intern",
    ]
    entry = [{
        "title": f"LinkedIn: {t.title()} — Entry Level",
        "link": linkedin_job_search_url(t, location, experience="2", remote_only=remote_only, time_range=time_range),
        "description": "LinkedIn job search (entry-level filter)."
    } for t in entry_titles]
    interns = [{
        "title": f"LinkedIn: {t.title()} — Internships",
        "link": linkedin_job_search_url(t, location, experience="1", remote_only=remote_only, time_range=time_range),
        "description": "LinkedIn job search (internship filter)."
    } for t in intern_titles]
    return entry, interns

def li_guest_collect(keywords: str, location: str, exp_level: str, remote_only: bool, time_range: str, limit=20, sleep_s=1.0):
    """
    Optional, UNDOCUMENTED. Use at your own risk.
    """
    items = []
    base = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    params = {"keywords": keywords, "location": location, "f_E": exp_level, "sortBy": "DD", "start": 0}
    if remote_only:
        params["f_WT"] = "2"
    if time_range:
        params["f_TPR"] = time_range

    while len(items) < limit and params["start"] <= 100:
        try:
            r = requests.get(base, params=params, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code != 200:
                log(f"LinkedIn guest endpoint status={r.status_code} for {keywords}")
                break
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("li div.base-card, div.base-search-card")
            if not cards:
                break
            for c in cards:
                a = c.select_one("a[href*='/jobs/view/']")
                title_el = c.select_one("[class*='title']")
                company_el = c.select_one("[class*='subtitle']")
                loc_el = c.select_one("[class*='location']")
                link = (a.get("href") or "").split("?")[0] if a else ""
                title = (title_el.get_text(strip=True) if title_el else "").strip()
                comp = (company_el.get_text(strip=True) if company_el else "").strip()
                loc  = (loc_el.get_text(strip=True) if loc_el else "").strip()
                if not link or not title:
                    continue
                desc = " • ".join([p for p in [comp, loc] if p])
                items.append({"title": title, "link": link, "description": desc})
                if len(items) >= limit: break
            params["start"] += 25
            time.sleep(sleep_s)
        except Exception as ex:
            log(f"LinkedIn guest fetch error '{keywords}': {ex}")
            break
    return items

def scrape_linkedin_lists():
    # Default: links-only (compliant)
    entry_links, intern_links = li_make_link_lists(LI_LOCATION, LI_REMOTE_ONLY, LI_TIME_RANGE)
    if not ENABLE_LINKEDIN_SCRAPE:
        return entry_links, intern_links

    log("LinkedIn guest-collector ENABLED (undocumented; may break).")
    entry_terms = ["cybersecurity analyst", "information security analyst", "soc analyst"]
    intern_terms = ["cybersecurity intern", "security analyst intern", "soc intern"]
    entry_items, intern_items = [], []
    for t in entry_terms:
        entry_items.extend(li_guest_collect(t, LI_LOCATION, exp_level="2", remote_only=LI_REMOTE_ONLY, time_range=LI_TIME_RANGE, limit=10))
    for t in intern_terms:
        intern_items.extend(li_guest_collect(t, LI_LOCATION, exp_level="1", remote_only=LI_REMOTE_ONLY, time_range=LI_TIME_RANGE, limit=10))
    # Fallback to links if empty
    return (entry_items or entry_links), (intern_items or intern_links)

# ---------------------------
# Indeed via RSS (no HTML scraping)
# ---------------------------

def indeed_rss_url(query: str, location: str | None):
    """
    Community-documented pattern: replace 'www' with 'rss' and use q / l params.
    Example: https://rss.indeed.com/rss?q=WordPress&l=San+Dimas%2C+CA
    """
    params = {"q": query}
    if location:
        params["l"] = location
    return f"https://rss.indeed.com/rss?{urlencode(params, quote_via=quote_plus)}"

def scrape_indeed(query: str, location: str, seen, limit=30):
    url = indeed_rss_url(query, location)
    items = parse_rss(url)
    return dedupe_and_filter(items, seen, limit=limit)

# ---------------------------
# Main
# ---------------------------

def main():
    try:
        log(f"BASE_DIR={BASE_DIR}")
        ensure_dirs()
        seen = load_seen()

        # LinkedIn (links by default; optional guest collection)
        li_entry, li_intern = scrape_linkedin_lists()
        write_markdown(
            os.path.join(BASE_DIR, "careers", "LinkedIn-Entry-Level.md"),
            f"LinkedIn Entry-Level Cybersecurity — {LI_LOCATION}{' (Remote only)' if LI_REMOTE_ONLY else ''}",
            li_entry
        )
        write_markdown(
            os.path.join(BASE_DIR, "careers", "LinkedIn-Internships.md"),
            f"LinkedIn Cybersecurity Internships — {LI_LOCATION}{' (Remote only)' if LI_REMOTE_ONLY else ''}",
            li_intern
        )

        # Indeed RSS (Entry‑level + Internships)
        indeed_entry = scrape_indeed(INDEED_ENTRY_QUERY, INDEED_LOCATION, seen, limit=35)
        indeed_intern = scrape_indeed(INDEED_INTERN_QUERY, INDEED_LOCATION, seen, limit=35)

        # If feed empty (or changed), write search links instead so the page is never blank
        if not indeed_entry:
            indeed_entry = [{
                "title": "Indeed Search — Entry‑Level Cybersecurity",
                "link": f"https://www.indeed.com/jobs?q={quote_plus(INDEED_ENTRY_QUERY)}&l={quote_plus(INDEED_LOCATION)}",
                "description": "Fallback search link (RSS returned no items)."
            }]
        if not indeed_intern:
            indeed_intern = [{
                "title": "Indeed Search — Cybersecurity Internships",
                "link": f"https://www.indeed.com/jobs?q={quote_plus(INDEED_INTERN_QUERY)}&l={quote_plus(INDEED_LOCATION)}",
                "description": "Fallback search link (RSS returned no items)."
            }]

        write_markdown(
            os.path.join(BASE_DIR, "careers", "Indeed-Entry-Level.md"),
            f"Indeed Entry‑Level Cybersecurity — {INDEED_LOCATION}",
            indeed_entry
        )
        write_markdown(
            os.path.join(BASE_DIR, "careers", "Indeed-Internships.md"),
            f"Indeed Cybersecurity Internships — {INDEED_LOCATION}",
            indeed_intern
        )

        save_seen(seen)
        log("Update complete.")
    except Exception:
        log("FATAL ERROR:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
