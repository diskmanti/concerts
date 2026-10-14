import os
import json
import time
import requests
from datetime import date, datetime, timedelta, timezone
from feedgen.feed import FeedGenerator

# --- Configuration ---
TICKETMASTER_API_KEY = os.environ.get("TICKETMASTER_API_KEY")
BANDSINTOWN_APP_ID = os.environ.get("BANDSINTOWN_APP_ID")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")
OUTPUT_FILE = os.environ.get("GITHUB_OUTPUT")
FEED_BASE_URL = os.environ.get("FEED_BASE_URL", "https://github.com/diskmanti/concerts")
SEEN_FILE = "seen_events.json"
REQUEST_TIMEOUT = 15
TICKETMASTER_URL = "https://app.ticketmaster.com/discovery/v2"

# Ticketmaster filters by country code; Bandsintown returns country names.
EUROPEAN_COUNTRIES = {
    "AL": "Albania", "AD": "Andorra", "AM": "Armenia", "AT": "Austria", "BY": "Belarus",
    "BE": "Belgium", "BA": "Bosnia and Herzegovina", "BG": "Bulgaria", "CH": "Switzerland",
    "CY": "Cyprus", "CZ": "Czech Republic", "DE": "Germany", "DK": "Denmark", "EE": "Estonia",
    "ES": "Spain", "FO": "Faroe Islands", "FI": "Finland", "FR": "France",
    "GE": "Georgia", "GI": "Gibraltar", "GR": "Greece", "HR": "Croatia", "HU": "Hungary",
    "IE": "Ireland", "IS": "Iceland", "IT": "Italy", "LI": "Liechtenstein", "LT": "Lithuania",
    "LU": "Luxembourg", "LV": "Latvia", "MC": "Monaco", "MD": "Moldova", "ME": "Montenegro",
    "MK": "North Macedonia", "MT": "Malta", "NL": "Netherlands", "NO": "Norway", "PL": "Poland",
    "PT": "Portugal", "RO": "Romania", "RS": "Serbia", "RU": "Russia", "SE": "Sweden",
    "SI": "Slovenia", "SK": "Slovakia", "SM": "San Marino", "TR": "Turkey", "UA": "Ukraine",
    "VA": "Vatican City",
}
EUROPEAN_COUNTRY_NAMES = set(EUROPEAN_COUNTRIES.values()) | {"Czechia", "Türkiye"}


def ticketmaster_get(endpoint, params):
    """Calls a Ticketmaster Discovery endpoint, staying under the 5 requests/second limit."""
    time.sleep(0.25)
    response = requests.get(f"{TICKETMASTER_URL}/{endpoint}.json",
                            params={'apikey': TICKETMASTER_API_KEY, **params},
                            timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json().get('_embedded', {})


def get_attraction_id(artist_name):
    """Finds the Ticketmaster attraction whose name exactly matches the artist (case-insensitive)."""
    attractions = ticketmaster_get('attractions', {
        'keyword': artist_name,
        'classificationName': 'Music',
        'size': 50,
    }).get('attractions', [])
    for attraction in attractions:
        if attraction.get('name', '').casefold() == artist_name.casefold():
            return attraction['id']
    return None


def normalize_ticketmaster_event(event, artist_name):
    venue_info = event.get('_embedded', {}).get('venues', [{}])[0]
    return {
        'id': f"tm:{event['id']}",
        'artist': artist_name,
        'date': event['dates']['start'].get('localDate', 'N/A'),
        'venue': venue_info.get('name', 'N/A'),
        'city': venue_info.get('city', {}).get('name', 'N/A'),
        'country': venue_info.get('country', {}).get('name', 'N/A'),
        'url': event.get('url', '#'),
    }


def get_ticketmaster_concerts(artist_name):
    """Fetches European concerts for a single artist from the Ticketmaster API."""
    print(f"Checking for {artist_name} on Ticketmaster...")
    try:
        attraction_id = get_attraction_id(artist_name)
        if not attraction_id:
            print(f"  -> No Ticketmaster artist named exactly '{artist_name}'. Check the spelling in bands.txt.")
            return []
        events = ticketmaster_get('events', {
            'attractionId': attraction_id,
            'sort': 'date,asc',
            'size': 200,
            'countryCode': ",".join(EUROPEAN_COUNTRIES),
        }).get('events', [])
        return [normalize_ticketmaster_event(e, artist_name) for e in events]
    except requests.exceptions.RequestException as e:
        print(f"  -> Failed to get Ticketmaster data for {artist_name}: {e}")
        return []


def get_bandsintown_concerts(artist_name):
    """Fetches European concerts for a single artist from the Bandsintown API."""
    if not BANDSINTOWN_APP_ID:
        return []
    print(f"Checking for {artist_name} on Bandsintown...")
    try:
        response = requests.get(f"https://rest.bandsintown.com/artists/{requests.utils.quote(artist_name)}/events",
                                params={'app_id': BANDSINTOWN_APP_ID, 'date': 'upcoming'},
                                timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        events = response.json()
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"  -> Failed to get Bandsintown data for {artist_name}: {e}")
        return []
    # Unknown artists come back as an error object instead of a list.
    if not isinstance(events, list):
        return []

    concerts = []
    for event in events:
        venue = event.get('venue', {})
        if venue.get('country') not in EUROPEAN_COUNTRY_NAMES:
            continue
        concerts.append({
            'id': f"bit:{event['id']}",
            'artist': artist_name,
            'date': event.get('datetime', 'N/A')[:10],
            'venue': venue.get('name', 'N/A'),
            'city': venue.get('city', 'N/A'),
            'country': venue.get('country', 'N/A'),
            'url': event.get('url', '#'),
        })
    return concerts


def get_concerts(artist_name):
    """Combines both sources, dropping Bandsintown shows that Ticketmaster already lists."""
    concerts = get_ticketmaster_concerts(artist_name)
    known = {(c['date'], c['city'].casefold()) for c in concerts}
    for concert in get_bandsintown_concerts(artist_name):
        if (concert['date'], concert['city'].casefold()) not in known:
            concerts.append(concert)
    return concerts


def get_albania_concerts():
    """Fetches all upcoming music concerts in Albania within the next 12 months."""
    start_datetime = datetime.now(timezone.utc)
    end_datetime = start_datetime + timedelta(days=365)

    print(f"\nFetching all upcoming concerts in Albania for the next 12 months (until {end_datetime.date()})...")
    try:
        events = ticketmaster_get('events', {
            'classificationName': 'Music',
            'sort': 'date,asc',
            'size': 200,
            'countryCode': 'AL',
            'startDateTime': start_datetime.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'endDateTime': end_datetime.strftime('%Y-%m-%dT%H:%M:%SZ'),
        }).get('events', [])
        print(f" -> Found {len(events)} concert(s) in Albania.")
        return events
    except requests.exceptions.RequestException as e:
        print(f" -> Failed to get concert data for Albania: {e}")
        return None


def load_seen_events():
    try:
        with open(SEEN_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_seen_events(concerts, seen):
    """Stores the first-seen date of every current concert. Past or cancelled ones drop out."""
    today = date.today().isoformat()
    updated = {c['id']: seen.get(c['id'], today) for c in concerts}
    with open(SEEN_FILE, 'w', encoding='utf-8') as f:
        json.dump(updated, f, indent=2, sort_keys=True)
        f.write("\n")
    return updated


def format_concert_line(concert):
    return (f"- **{concert['date']}** - {concert['venue']} in {concert['city']}, "
            f"{concert['country']} ([See Tickets]({concert['url']}))\n")


def format_issue_body(new_concerts):
    """Formats newly announced concerts into a Markdown string for the issue body."""
    md_body = "New shows in Europe announced for your followed bands since the last check:\n\n"
    for artist in sorted({c['artist'] for c in new_concerts}):
        md_body += f"## {artist}\n"
        for concert in new_concerts:
            if concert['artist'] == artist:
                md_body += format_concert_line(concert)
        md_body += "\n"
    md_body += f"All upcoming shows are in the [RSS feed]({FEED_BASE_URL}/blob/main/concerts.rss).\n"
    return md_body


def format_albania_issue_body(events):
    """Formats the Albania concert data into a Markdown string for the issue body."""
    md_body = "Here are all the upcoming concerts in Albania for the next 12 months:\n\n"
    for event in events:
        artist_name = event.get('_embedded', {}).get('attractions', [{}])[0].get('name', 'N/A')
        event_date = event['dates']['start'].get('localDate', 'N/A')
        venue_info = event.get('_embedded', {}).get('venues', [{}])[0]
        venue_name = venue_info.get('name', 'N/A')
        city = venue_info.get('city', {}).get('name', 'N/A')
        ticket_url = event.get('url', '#')

        md_body += f"- **{artist_name}** - {event_date} at {venue_name} in {city} ([See Tickets]({ticket_url}))\n"
    md_body += "\n"

    return md_body


def create_github_issue(title, body):
    """Creates a new GitHub issue."""
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        print(" -> GITHUB_TOKEN or GITHUB_REPOSITORY not set. Cannot create issue.")
        return

    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    print(f"Creating new GitHub issue titled: '{title}'")
    try:
        response = requests.post(url, headers=headers, json={"title": title, "body": body},
                                 timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        print(" -> Successfully created GitHub issue.")
    except requests.exceptions.RequestException as e:
        print(f" -> Failed to create GitHub issue: {e}")
        if e.response is not None:
            print(f"    Response: {e.response.text}")


def generate_rss_feed(concerts, seen):
    """Generates an RSS feed from the concert data and returns it as bytes."""
    fg = FeedGenerator()

    fg.title('European Concerts for Followed Artists')
    fg.link(href=FEED_BASE_URL, rel='alternate')
    fg.description('Upcoming European concerts for artists followed in my list.')
    fg.language('en')

    if not concerts:
        print("  -> No concerts found to add to the RSS feed.")

    # feedgen emits entries in reverse insertion order, so add oldest first to show newest first.
    for concert in sorted(concerts, key=lambda c: (seen[c['id']], c['date'])):
        fe = fg.add_entry()
        fe.id(concert['id'])
        fe.title(f"{concert['artist']} @ {concert['venue']} in {concert['city']}, "
                 f"{concert['country']} on {concert['date']}")
        fe.link(href=concert['url'])
        fe.description(f"A concert by {concert['artist']} is scheduled for {concert['date']} at {concert['venue']}.")
        # pubDate is when the show was first spotted, so readers surface new announcements.
        first_seen = datetime.strptime(seen[concert['id']], '%Y-%m-%d')
        fe.pubDate(first_seen.replace(hour=12, tzinfo=timezone.utc))

    return fg.rss_str(pretty=True)


# --- Main Execution ---
if __name__ == "__main__":
    if not TICKETMASTER_API_KEY:
        print("Error: TICKETMASTER_API_KEY secret not found.")
        exit(1)

    try:
        with open('bands.txt', 'r') as f:
            bands_to_track = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Error: `bands.txt` not found. Please create it and add your favorite bands.")
        exit(1)

    all_concerts = []
    for band in bands_to_track:
        all_concerts.extend(get_concerts(band))

    previously_seen = load_seen_events()
    new_concerts = sorted((c for c in all_concerts if c['id'] not in previously_seen),
                          key=lambda c: c['date'])
    seen = save_seen_events(all_concerts, previously_seen)
    print(f"\nFound {len(all_concerts)} concert(s), {len(new_concerts)} new.")

    # --- GitHub Issue Generation (Followed Artists) ---
    issue_title = f"Weekly Concert Alert (Europe): {date.today().isoformat()}"
    issue_body = format_issue_body(new_concerts) if new_concerts else ""

    if OUTPUT_FILE:
        with open(OUTPUT_FILE, "a") as f:
            f.write(f"has_new={'true' if new_concerts else 'false'}\n")
            f.write(f"issue_title={issue_title}\n")
            f.write("issue_body<<EOF\n")
            f.write(f"{issue_body}\n")
            f.write("EOF\n")
        print("Output prepared for GitHub Actions.")
    else:
        print("\n--- ISSUE PREVIEW (Local Test) ---")
        print("Title:", issue_title)
        print("Body:\n", issue_body or "(no new concerts, no issue would be created)")

    # --- RSS Feed Generation ---
    print("\nGenerating RSS feed...")
    rss_content = generate_rss_feed(all_concerts, seen)
    with open('concerts.rss', 'w', encoding='utf-8') as f:
        f.write(rss_content.decode('utf-8'))
    print(" -> Successfully generated and saved to concerts.rss")

    # --- Create GitHub Issue for Albanian Concerts ---
    albania_concerts = get_albania_concerts()
    if albania_concerts:
        albania_issue_title = f"Concerts in Albania (Next 12 months): {date.today().isoformat()}"
        albania_issue_body = format_albania_issue_body(albania_concerts)
        create_github_issue(albania_issue_title, albania_issue_body)
    else:
        print("\nSkipping issue creation for Albania as no concerts were found in the next 12 months.")

    print("\nScript finished.")
