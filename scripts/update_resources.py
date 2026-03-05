#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser as dtparser

# ---------------------------
# Paths & Config
# ---------------------------

# Repo root = parent of this script's parent (repo/scripts/update_resources.py)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DATA_DIR = os.path.join(BASE_DIR, ".data")
DATA_FILE = os.path.join(DATA_DIR, "seen.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (ResourceBot; +https://github.com/)"
}

# Lowercase only (we'll .lower() on checks)
CYBER_KEYWORDS = [
    "cyber", "security", "infosec", "soc", "cloud security",
    "penetration", "red team", "blue team", "grc",
    "risk", "threat", "siem"
]

TIMEOUT = 20  # seconds


# ---------------------------
# Utility
# ---------------------------

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    # Ensure target content folders exist too
    for folder in ["careers", "certifications", "events", "resources"]:
        os.makedirs(os.path.join(BASE_DIR, folder), exist_ok=True)


def load_seen():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
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
    Overwrites the file with a simple, clean list.
    You can change this to 'append/replace a section' if you prefer.
    """
    lines = [f"# {title}", ""]
    if not items:
        lines.append("_No current listings found._")
    else:
        for it in items:
            title = safe_get(it, "title", "Untitled")
            desc = safe_get(it, "description", "")
            link = safe_get(it, "link", "")
            if desc:
                lines.append(f"- **{title}**  \n  {desc}  \n  [Link]({link})")
            else:
                lines.append(f"- **{title}**  \n  [Link]({link})")
            lines.append("")  # blank line after each entry

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def parse_rss(url: str):
    """
    Lightweight RSS/Atom parser using requests + BeautifulSoup.
    Returns a list of entries with title, link, summary/description, published.
    """
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "xml")

        # Atom feeds use <entry>, RSS uses <item>
        nodes = soup.find_all(["item", "entry"])
        for n in nodes:
            title = (n.title.text if n.title else "").strip()
            link_tag = n.find("link")
            link = ""
            if link_tag:
                # Atom: <link href="...">, RSS: <link>url</link>
                link = link_tag.get("href") or link_tag.text or ""
            desc = ""
            # prefer 'summary' then 'description' then 'content'
            if n.find("summary"):
                desc = n.find("summary").text or ""
            elif n.find("description"):
                desc = n.find("description").text or ""
            elif n.find("content"):
                desc = n.find("content").text or ""

            # published date (optional)
            pub = ""
            for tag in ["pubDate", "published", "updated"]:
                if n.find(tag):
                    pub = n.find(tag).text or ""
                    break

            # Trim overly long descriptions
            desc = " ".join(desc.split())
            if len(desc) > 240:
                desc = desc[:237] + "..."

            items.append({
                "title": title,
                "link": link.strip(),
                "description": desc.strip(),
                "published": pub.strip(),
            })
    except Exception as ex:
        print(f"[warn] Failed to parse RSS: {url} -> {ex}")

    return items


def dedupe_and_filter(items, seen, keyword_filter=True, limit=None):
    """
    - Removes duplicates by link
    - Optionally filters by cybersecurity keywords
    - Adds new links to seen['links']
    """
    out = []
    for it in items:
        link = safe_get(it, "link")
        title = safe_get(it, "title")
        if not link and not title:
            continue

        if keyword_filter and not (contains_cyber(title) or contains_cyber(it.get("description", ""))):
            continue

        if link in seen["links"]:
            continue

        seen["links"].append(link)
        out.append(it)

        if limit and len(out) >= limit:
            break
    return out


# ---------------------------
# Cybersecurity Jobs
# ---------------------------

def scrape_jobs(seen):
    print("Scraping cybersecurity jobs...")
    jobs = []

    # RemoteOK security RSS
    jobs += parse_rss("https://remoteok.com/remote-security-jobs.rss")

    # (Optional) Add more feeds if desired:
    # jobs += parse_rss("https://weworkremotely.com/categories/remote-security-jobs.rss")

    jobs = dedupe_and_filter(jobs, seen, keyword_filter=True, limit=15)
    return jobs


# ---------------------------
# Cybersecurity Internships
# ---------------------------

def scrape_internships(seen):
    print("Scraping internships...")
    internships = []

    # RemoteOK internship RSS
    internships += parse_rss("https://remoteok.com/remote-internship-jobs.rss")

    internships = dedupe_and_filter(internships, seen, keyword_filter=True, limit=15)
    return internships


# ---------------------------
# Certifications
# ---------------------------

def scrape_certifications():
    entry_level = [
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

    mid_level = [
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

    free_training = [
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

    return entry_level, mid_level, free_training


# ---------------------------
# Cyber Events (Online + General)
# ---------------------------

def scrape_events(seen):
    print("Scraping cybersecurity events...")
    events = []

    # Eventbrite online cyber events RSS (broad)
    events += parse_rss("https://www.eventbrite.com/d/online/cybersecurity/rss/")

    events = dedupe_and_filter(events, seen, keyword_filter=True, limit=20)
    return events


# ---------------------------
# Technology Clubs (Static examples)
# ---------------------------

def scrape_clubs():
    clubs = [
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
    return clubs


# ---------------------------
# Main
# ---------------------------

def main():
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
    # IMPORTANT: file name should match your repo exactly ("Free-Trainings-&-Certifications.md")
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

    # Tech Clubs
    clubs = scrape_clubs()
    write_markdown(
        os.path.join(BASE_DIR, "resources", "Technology-Clubs.md"),
        "Cybersecurity & Technology Clubs (Atlanta)",
        clubs
    )

    save_seen(seen)
    print("Update complete.")


if __name__ == "__main__":
    main()
