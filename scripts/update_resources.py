#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import sys
import traceback
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser as dtparser

# ---------------------------
# Paths & Config
# ---------------------------

# Repo root = parent of /scripts
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DATA_DIR = os.path.join(BASE_DIR, ".data")
DATA_FILE = os.path.join(DATA_DIR, "seen.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (ResourceBot; +https://github.com/)"
}

CYBER_KEYWORDS = [
    "cyber", "security", "infosec", "soc", "cloud security",
    "penetration", "red team", "blue team", "grc",
    "risk", "threat", "siem"
]

TIMEOUT = 20  # seconds


# ---------------------------
# Utility
# ---------------------------

def log(msg):
    print(f"[update_resources] {msg}")

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    for folder in ["careers", "certifications", "events", "resources"]:
        os.makedirs(os.path.join(BASE_DIR, folder), exist_ok=True)

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
        json.dump(data, f, indent=2)

def contains_cyber(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in CYBER_KEYWORDS)

def safe_get(d: dict, key: str, default: str = "") -> str:
    val = d.get(key, default) or default
    return val.strip()

def write_markdown(filepath, title, items):
    """
    Overwrites the file with a clean list.
    Change to section-based updates if you later prefer partial updates.
    """
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
            lines.append("")  # blank line
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------
# RSS/Atom fetch
# ---------------------------

def parse_rss(url: str):
    """
    Lightweight RSS/Atom fetch -> list of {title, link, description, published}
    """
    log(f"Fetching RSS: {url}")
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as ex:
        log(f"ERROR fetching {url}: {ex}")
        return items

    # Try XML-capable parsers; fallback to html if needed
    soup = None
    for parser_name in ("lxml-xml", "xml", "html.parser"):
        try:
            soup = BeautifulSoup(r.content, parser_name)
            break
        except Exception:
            soup = None
    if soup is None:
        log(f"ERROR: Could not initialize BeautifulSoup for {url}")
        return items

    nodes = soup.find_all(["item", "entry"])
    for n in nodes:
        title = (n.title.text if n and n.find("title") else "").strip()

        link = ""
        link_tag = n.find("link") if n else None
        if link_tag:
            link = (link_tag.get("href") or link_tag.text or "").strip()

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

        # Normalize desc
        desc = " ".join((desc or "").split())
        if len(desc) > 240:
            desc = desc[:237] + "..."

        items.append({
            "title": title,
            "link": link,
            "description": desc,
            "published": pub,
        })

    log(f"Parsed {len(items)} items from {url}")
    return items

def dedupe_and_filter(items, seen, keyword_filter=True, limit=None):
    out = []
    for it in items:
        link = safe_get(it, "link")
        title = safe_get(it, "title")
        text = f"{title} {safe_get(it, 'description', '')}"
        if keyword_filter and not contains_cyber(text):
            continue
        if link and link in seen["links"]:
            continue
        if link:
            seen["links"].append(link)
        out.append(it)
        if limit and len(out) >= limit:
            break
    return out


# ---------------------------
# Scrapers
# ---------------------------

def scrape_jobs(seen):
    log("Scraping jobs…")
    items = parse_rss("https://remoteok.com/remote-security-jobs.rss")
    return dedupe_and_filter(items, seen, keyword_filter=True, limit=15)

def scrape_internships(seen):
    log("Scraping internships…")
    items = parse_rss("https://remoteok.com/remote-internship-jobs.rss")
    return dedupe_and_filter(items, seen, keyword_filter=True, limit=15)

def scrape_certifications():
    entry = [
        {
            "title": "CompTIA Security+",
            "description": "Broad entry-level cybersecurity certification covering core security domains.",
            "link": "https://www.comptia.org/certifications/security"
        },
        {
            "title": "ISC2 Certified in Cybersecurity (CC)",
            "description": "Entry credential with fundamentals; widely recognized.",
            "link": "https://www.isc2.org/Certifications/CC"
        }
    ]
    mid = [
        {
            "title": "CISSP",
            "description": "Advanced security leadership certification.",
            "link": "https://www.isc2.org/Certifications/CISSP"
        },
        {
            "title": "CEH",
            "description": "Practical ethical hacking fundamentals and techniques.",
            "link": "https://www.eccouncil.org/programs/certified-ethical-hacker-ceh/"
        }
    ]
    free = [
        {
            "title": "Fortinet Training Institute (NSE)",
            "description": "Free self-paced security training courses.",
            "link": "https://training.fortinet.com/"
        },
        {
            "title": "Cisco Skills for All / NetAcad",
            "description": "Free networking & security courses.",
            "link": "https://www.netacad.com/"
        }
    ]
    return entry, mid, free

def scrape_events(seen):
    log("Scraping events…")
    items = parse_rss("https://www.eventbrite.com/d/online/cybersecurity/rss/")
    return dedupe_and_filter(items, seen, keyword_filter=True, limit=20)

def scrape_clubs():
    return [
        {
            "title": "ISSA Atlanta",
            "description": "Information Systems Security Association - Atlanta Chapter",
            "link": "https://www.issa-atlanta.org/"
        },
        {
            "title": "ISACA Atlanta",
            "description": "ISACA Atlanta Chapter",
            "link": "https://engage.isaca.org/atlantachapter/home"
        },
        {
            "title": "OWASP Atlanta",
            "description": "Open Web Application Security Project - Atlanta",
            "link": "https://owasp.org/www-chapter-atlanta/"
        }
    ]


# ---------------------------
# Main
# ---------------------------

def main():
    try:
        log(f"BASE_DIR={BASE_DIR}")
        ensure_dirs()
        seen = load_seen()

        # Jobs
        jobs = scrape_jobs(seen)
        write_markdown(
            os.path.join(BASE_DIR, "careers", "Cybersecurity-roles.md"),
            "Cybersecurity Roles",
            jobs
        )

        # Internships
        internships = scrape_internships(seen)
        write_markdown(
            os.path.join(BASE_DIR, "careers", "Internships.md"),
            "Cybersecurity Internships",
            internships
        )

        # Certifications
        entry, mid, free = scrape_certifications()
        write_markdown(
            os.path.join(BASE_DIR, "certifications", "Entry-Level-Certifications.md"),
            "Entry-Level Cybersecurity Certifications",
            entry
        )
        write_markdown(
            os.path.join(BASE_DIR, "certifications", "Mid-Level-Certifications.md"),
            "Mid-Level Cybersecurity Certifications",
            mid
        )
        write_markdown(
            os.path.join(BASE_DIR, "certifications", "Free-Trainings-&-Certifications.md"),
            "Free Cybersecurity Training & Certifications",
            free
        )

        # Events
        events = scrape_events(seen)
        write_markdown(
            os.path.join(BASE_DIR, "events", "upcoming-events.md"),
            "Upcoming Cybersecurity Events (Online + Regional)",
            events
        )

        # Clubs (static)
        clubs = scrape_clubs()
        write_markdown(
            os.path.join(BASE_DIR, "resources", "Technology-Clubs.md"),
            "Cybersecurity & Technology Clubs (Atlanta)",
            clubs
        )

        save_seen(seen)
        log("Update complete.")
    except Exception:
        log("FATAL ERROR:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
``
