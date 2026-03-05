import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_FILE = os.path.join(BASE_DIR, ".data", "seen.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

CYBER_KEYWORDS = [
    "cyber", "security", "infosec", "soc", "cloud security",
    "penetration", "red team", "blue team", "gRC",
    "risk", "threat", "siem" , "data" , "entry level" , "analyst"
]


# ---------------------------
# Utility
# ---------------------------

def load_seen():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}


def save_seen(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def contains_cyber(text):
    text = text.lower()
    return any(keyword in text for keyword in CYBER_KEYWORDS)


def write_markdown(filepath, title, items):
    content = f"# {title}\n\n"
    if not items:
        content += "_No current listings found._\n"
    else:
        for item in items:
            content += f"- **{item['title']}**  \n"
            content += f"  {item['description']}  \n"
            content += f"  [Link]({item['link']})\n\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------
# Cybersecurity Jobs
# ---------------------------

def scrape_jobs():
    print("Scraping cybersecurity jobs...")
    jobs = []

    # RemoteOK RSS
    feed = feedparser.parse("https://remoteok.com/remote-security-jobs.rss")

    for entry in feed.entries:
        if contains_cyber(entry.title):
            jobs.append({
                "title": entry.title,
                "description": entry.get("summary", "")[:200],
                "link": entry.link
            })

    return jobs[:15]


# ---------------------------
# Cybersecurity Internships
# ---------------------------

def scrape_internships():
    print("Scraping internships...")
    internships = []

    feed = feedparser.parse("https://remoteok.com/remote-internship-jobs.rss")

    for entry in feed.entries:
        if contains_cyber(entry.title):
            internships.append({
                "title": entry.title,
                "description": entry.get("summary", "")[:200],
                "link": entry.link
            })

    return internships[:15]


# ---------------------------
# Certifications
# ---------------------------

def scrape_certifications():
    entry_level = [
        {"title": "CompTIA Security+", "description": "Entry-level cybersecurity certification", "link": "https://www.comptia.org/certifications/security"},
        {"title": "ISC2 CC", "description": "Certified in Cybersecurity (Free exam)", "link": "https://www.isc2.org/Certifications/CC"}
    ]

    mid_level = [
        {"title": "CISSP", "description": "Advanced cybersecurity leadership certification", "link": "https://www.isc2.org/Certifications/CISSP"},
        {"title": "CEH", "description": "Certified Ethical Hacker", "link": "https://www.eccouncil.org/programs/certified-ethical-hacker-ceh/"}
    ]

    free_training = [
        {"title": "Fortinet NSE Training", "description": "Free cybersecurity training courses", "link": "https://training.fortinet.com/"},
        {"title": "Cisco Networking Academy", "description": "Free cybersecurity courses", "link": "https://www.netacad.com/"}
    ]

    return entry_level, mid_level, free_training


# ---------------------------
# Cyber Events (Atlanta + Virtual)
# ---------------------------

def scrape_events():
    print("Scraping cybersecurity events...")
    events = []

    feed = feedparser.parse("https://www.eventbrite.com/d/online/cybersecurity/rss/")

    for entry in feed.entries:
        if contains_cyber(entry.title):
            events.append({
                "title": entry.title,
                "description": entry.get("summary", "")[:200],
                "link": entry.link
            })

    return events[:20]


# ---------------------------
# Technology Clubs (Atlanta)
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
# Main Execution
# ---------------------------

def main():
    seen = load_seen()

    # Jobs
    jobs = scrape_jobs()
    write_markdown(
        os.path.join(BASE_DIR, "careers", "Cybersecurity-roles.md"),
        "Cybersecurity Roles",
        jobs
    )

    # Internships
    internships = scrape_internships()
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
    events = scrape_events()
    write_markdown(
        os.path.join(BASE_DIR, "events", "upcoming-events.md"),
        "Upcoming Cybersecurity Events (Atlanta + Virtual)",
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
