#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Automation for Amara's Cybersecurity Resource Hub
- Scrapes trusted sources
- Updates markdown files with an 'Auto-collected' section
- De-duplicates URLs across runs via .data/seen.json
"""

import os, re, json, sys, time, datetime
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from dateutil import tz

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / ".data"
DATA_DIR.mkdir(exist_ok=True)
SEEN_FILE = DATA_DIR / "seen.json"

# ---------- helpers ----------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Automation for Education; +https://github.com/)"
}

def load_seen():
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    return {"links": []}

def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen, indent=2), encoding="utf-8")

def dedupe(new_items, seen):
    unique = []
    for it in new_items:
        url = it.get("url")
        if not url: 
            continue
        if url in seen["links"]:
            continue
        seen["links"].append(url)
        unique.append(it)
    return unique

def now_et_iso():
    # Timestamp in US/Eastern for readability in the repo
    et = tz.gettz("America/New_York")
    return datetime.datetime.now(tz=et).strftime("%Y-%m-%d %H:%M %Z")

def fetch_html(url, timeout=25):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text

def md_bullet(title, url, extra=None):
    tail = f" — {extra}" if extra else ""
    return f"- [{title}]({url}){tail}"

def insert_or_replace_section(md_path, section_heading, new_lines):
    """
    Adds or replaces a section that starts with '### {section_heading}'
    and ends before the next '### ' heading or EOF.
    """
    md_path = Path(md_path)
    if not md_path.exists():
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(f"# {md_path.stem}\n\n", encoding="utf-8")

    text = md_path.read_text(encoding="utf-8")

    start_marker = f"### {section_heading}"
    timestamp_line = f"> Last auto-update: {now_et_iso()}"
    content = "\n".join(new_lines) if new_lines else "_No new items found this run._"
    new_section = f"{start_marker}\n{timestamp_line}\n\n{content}\n"

    if start_marker in text:
        # Replace existing section
        pre, rest = text.split(start_marker, 1)
        # find next section
        m = re.search(r"\n###\s", rest)
        if m:
            post = rest[m.start()+1:]  # keep the '### ' for next section
            updated = pre + new_section + post
        else:
            updated = pre + new_section
    else:
        # Append section at end
        if not text.endswith("\n"):
            text += "\n"
        updated = text + "\n" + new_section

    md_path.write_text(updated, encoding="utf-8")


# ---------- scrapers ----------

def scrape_sans_free_events(limit=8):
    """
    Source: SANS 'Free Cybersecurity Events'
    We try to extract upcoming items from sections like webinars/community nights.
    """
    url = "https://www.sans.org/free-cybersecurity-events/"
    items = []
    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        # Look for links inside event cards (titles usually <a> inside <h3>/<h4>)
        for a in soup.select("a"):
            t = (a.get_text() or "").strip()
            href = a.get("href") or ""
            if not t or not href:
                continue
            # Heuristics for event-like links
            if any(word in t.lower() for word in ["webinar", "community", "summit", "forum", "night"]):
                if href.startswith("/"):
                    href = urljoin(url, href)
                items.append({
                    "title": f"SANS: {t}",
                    "url": href,
                    "source": "SANS Free Events",
                    "type": "webinar/summit"
                })
        # keep unique by title/url
        seen_titles = set()
        deduped = []
        for it in items:
            key = (it["title"], it["url"])
            if key not in seen_titles:
                seen_titles.add(key)
                deduped.append(it)
        return deduped[:limit]
    except Exception as ex:
        print("[warn] SANS scrape failed:", ex, file=sys.stderr)
        return []

def scrape_isc2_cc(limit=1):
    """
    Source: ISC2 One Million CC program (free training + exam)
    We only need to confirm/refresh the core link.
    """
    url = "https://www.isc2.org/landing/1mcc"
    return [{
        "title": "ISC2: Certified in Cybersecurity (CC) – Free training & exam",
        "url": url,
        "source": "ISC2",
        "type": "free-cert"
    }][:limit]

def scrape_coursera_free(limit=8):
    """
    Pulls notable free cybersecurity course entries from Coursera listing.
    We filter anchor tags that look like course cards and include 'cyber'.
    """
    url = "https://www.coursera.org/courses?query=free&skills=Cybersecurity"
    items = []
    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("a"):
            title = (a.get_text() or "").strip()
            href = a.get("href") or ""
            if not title or not href:
                continue
            if "cyber" in title.lower() and ("course" in href or "/learn/" in href):
                if href.startswith("/"):
                    href = urljoin(url, href)
                items.append({
                    "title": f"Coursera: {title}",
                    "url": href,
                    "source": "Coursera",
                    "type": "course"
                })
        # de-dup and trim noise
        deduped = []
        seen = set()
        for it in items:
            k = (it["title"], it["url"])
            if k in seen: 
                continue
            seen.add(k)
            deduped.append(it)
        return deduped[:limit]
    except Exception as ex:
        print("[warn] Coursera scrape failed:", ex, file=sys.stderr)
        return []

def scrape_springboard_bootcamps(limit=8):
    """
    Parse Springboard article listing free bootcamps/courses.
    """
    url = "https://www.springboard.com/blog/cybersecurity/free-cybersecurity-bootcamps/"
    items = []
    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        # titles often inside <h2>, <h3>, or <li> with provider names
        for h in soup.select("h2, h3, li a"):
            t = (h.get_text() or "").strip()
            if not t: 
                continue
            if any(k in t.lower() for k in ["bootcamp", "cyber", "security", "google", "per scholas", "flatiron", "cybrary", "fullstack", "evolve"]):
                href = h.get("href") or url
                if href.startswith("/"):
                    href = urljoin(url, href)
                items.append({
                    "title": f"Bootcamp: {t}",
                    "url": href,
                    "source": "Springboard list",
                    "type": "bootcamp"
                })
        # de-dup by title
        seen = set()
        out = []
        for it in items:
            if it["title"] in seen: 
                continue
            seen.add(it["title"])
            out.append(it)
        return out[:limit]
    except Exception as ex:
        print("[warn] Springboard scrape failed:", ex, file=sys.stderr)
        return []

def scrape_cyberskills2work(limit=5):
    """
    Program landing page + training network links.
    """
    url = "https://cyberskills2work.org/"
    items = []
    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        # collect prominent program links
        for a in soup.select("a"):
            t = (a.get_text() or "").strip()
            href = a.get("href") or ""
            if not t or not href:
                continue
            if any(k in t.lower() for k in ["training", "program", "join", "apply"]):
                if href.startswith("/"):
                    href = urljoin(url, href)
                items.append({
                    "title": f"CyberSkills2Work: {t}",
                    "url": href,
                    "source": "CyberSkills2Work",
                    "type": "workforce"
                })
        # Also include root link as anchor
        items.insert(0, {
            "title": "CyberSkills2Work (National Workforce Program)",
            "url": url,
            "source": "CyberSkills2Work",
            "type": "workforce"
        })
        # de-dup by url
        seen = set()
        out = []
        for it in items:
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            out.append(it)
        return out[:limit]
    except Exception as ex:
        print("[warn] CyberSkills2Work scrape failed:", ex, file=sys.stderr)
        return [{"title":"CyberSkills2Work (landing)","url":url,"source":"CyberSkills2Work","type":"workforce"}][:1]


# ---------- writers ----------

def update_events_md(new_events):
    lines = []
    for ev in new_events:
        lines.append(md_bullet(ev["title"], ev["url"], extra=ev.get("type")))
    target = ROOT / "events" / "upcoming-events.md"
    insert_or_replace_section(target, "Auto-collected (SANS & others)", lines)

def update_free_trainings_md(items):
    bullets = []
    for it in items:
        bullets.append(md_bullet(it["title"], it["url"], extra=it.get("type")))
    target = ROOT / "certifications" / "Free-Trainings-&-Certifications.md"
    insert_or_replace_section(target, "Auto-collected (free trainings, courses, bootcamps)", bullets)

def update_internships_md(items):
    bullets = []
    for it in items:
        bullets.append(md_bullet(it["title"], it["url"], extra=it.get("type")))
    target = ROOT / "careers" / "Internships.md"
    insert_or_replace_section(target, "Auto-collected (workforce & programs)", bullets)


# ---------- main ----------

def main():
    print("Starting resource update…")
    seen = load_seen()

    # Scrape sources
    sans = scrape_sans_free_events()
    isc2 = scrape_isc2_cc()
    coursera = scrape_coursera_free()
    springboard = scrape_springboard_bootcamps()
    cs2w = scrape_cyberskills2work()

    # Deduplicate across runs
    new_events = dedupe(sans, seen)
    new_trainings = dedupe(isc2 + coursera + springboard, seen)
    new_intern = dedupe(cs2w, seen)

    # Write sections
    if new_events:
        update_events_md(new_events)
    if new_trainings:
        update_free_trainings_md(new_trainings)
    if new_intern:
        update_internships_md(new_intern)

    save_seen(seen)

    # Exit code indicates whether changes likely occurred (useful in logs)
    made_changes = any([new_events, new_trainings, new_intern])
    print(f"Done. Changes: {made_changes}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
