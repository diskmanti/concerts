import os
import requests
from datetime import date, datetime, time
import json # Added for GitHub API request

# Import the required libraries
from feedgen.feed import FeedGenerator
import pytz

# --- Configuration ---
TICKETMASTER_API_KEY = os.environ.get("TICKETMASTER_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") # Added for creating a new issue
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY") # Added for creating a new issue
OUTPUT_FILE = os.environ.get("GITHUB_OUTPUT")
FEED_BASE_URL = os.environ.get("FEED_BASE_URL", "https://github.com/YOUR_USERNAME/YOUR_REPO")

EUROPEAN_COUNTRY_CODES = {
    "AL", "AD", "AM", "AT", "BY", "BE", "BA", "BG", "CH", "CY", "CZ", "DE",
    "DK", "EE", "ES", "FO", "FI", "FR", "GB", "GE", "GI", "GR", "HR", "HU",
    "IE", "IS", "IT", "LI", "LT", "LU", "LV", "MC", "MD", "ME", "MK", "MT",
    "NL", "NO", "PL", "PT", "RO", "RS", "RU", "SE", "SI", "SK", "SM", "TR",
    "UA", "VA"
}

def get_concert_info(artist_name):
    """Fetches concert data for a single artist from the Ticketmaster API, filtered for Europe."""
    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        'apikey': TICKETMASTER_API_KEY,
        'keyword': artist_name,
        'classificationName': 'Music',
        'sort': 'date,asc',
        'countryCode': ",".join(EUROPEAN_COUNTRY_CODES)
    }
    
    print(f"Checking for {artist_name} in Europe using Ticketmaster API...")
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get('_embedded', {}).get('events', [])
    except requests.exceptions.RequestException as e:
        print(f"  -> Failed to get data for {artist_name}: {e}")
        return None

def get_albania_concerts():
    """Fetches all upcoming music concerts in Albania."""
    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        'apikey': TICKETMASTER_API_KEY,
        'classificationName': 'Music',
        'sort': 'date,asc',
        'countryCode': 'AL' # Country code for Albania
    }
    print("\nFetching all upcoming concerts in Albania...")
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        events = data.get('_embedded', {}).get('events', [])
        print(f" -> Found {len(events)} concert(s) in Albania.")
        return events
    except requests.exceptions.RequestException as e:
        print(f" -> Failed to get concert data for Albania: {e}")
        return None

def format_issue_body(all_concerts):
    """Formats the concert data into a nice Markdown string for the issue body."""
    if not any(all_concerts.values()):
        return "No upcoming European concerts found for your followed artists this week."

    md_body = "Here are the upcoming shows in Europe for your followed bands:\n\n"
    for artist, events in all_concerts.items():
        if events:
            md_body += f"## {artist}\n"
            for event in events:
                event_date = event['dates']['start'].get('localDate', 'N/A')
                venue_info = event.get('_embedded', {}).get('venues', [{}])[0]
                venue_name = venue_info.get('name', 'N/A')
                city = venue_info.get('city', {}).get('name', 'N/A')
                country = venue_info.get('country', {}).get('name', 'N/A')
                ticket_url = event.get('url', '#')
                
                md_body += f"- **{event_date}** - {venue_name} in {city}, {country} ([See Tickets]({ticket_url}))\n"
            md_body += "\n"
            
    return md_body

def format_albania_issue_body(events):
    """Formats the Albania concert data into a Markdown string for the issue body."""
    if not events:
        return "No upcoming concerts found in Albania this week."

    md_body = "Here are all the upcoming concerts in Albania:\n\n"
    for event in events:
        # For general country-wide searches, the artist name is in the 'attractions'
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
        print(" -> GITHUB_TOKEN or GITHUB_REPOSITORY secrets not found. Cannot create issue.")
        return

    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {
        "title": title,
        "body": body,
    }

    print(f"Creating new GitHub issue titled: '{title}'")
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        print(" -> Successfully created GitHub issue.")
    except requests.exceptions.RequestException as e:
        print(f" -> Failed to create GitHub issue: {e}")
        print(f"    Response: {e.response.text}")


def generate_rss_feed(all_concerts):
    """Generates an RSS feed from the concert data and returns it as a string."""
    fg = FeedGenerator()

    fg.title('European Concerts for Followed Artists')
    fg.link(href=FEED_BASE_URL, rel='alternate')
    fg.description('Upcoming European concerts for artists followed in my list.')
    fg.language('en')

    flat_event_list = []
    for artist, events in all_concerts.items():
        if events:
            for event in events:
                event['artist_name'] = artist
                flat_event_list.append(event)
    
    if not flat_event_list:
        print("  -> No concerts found to add to the RSS feed.")
    
    flat_event_list.sort(key=lambda x: x['dates']['start'].get('localDate', '9999-12-31'))
    
    utc = pytz.UTC

    for event in flat_event_list:
        artist = event['artist_name']
        event_date_str = event['dates']['start'].get('localDate', 'N/A')
        venue_info = event.get('_embedded', {}).get('venues', [{}])[0]
        venue_name = venue_info.get('name', 'N/A')
        city = venue_info.get('city', {}).get('name', 'N/A')
        country = venue_info.get('country', {}).get('name', 'N/A')
        ticket_url = event.get('url', '#')

        item_title = f"{artist} @ {venue_name} in {city}, {country} on {event_date_str}"
        item_description = f"A concert by {artist} is scheduled for {event_date_str} at {venue_name}."

        fe = fg.add_entry()
        fe.id(ticket_url)
        fe.title(item_title)
        fe.link(href=ticket_url)
        fe.description(item_description)

        try:
            parsed_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            naive_datetime = datetime.combine(parsed_date, time(12, 0))
            aware_datetime = utc.localize(naive_datetime)
            fe.pubDate(aware_datetime)
        except (ValueError, TypeError):
            fe.pubDate(datetime.now(utc))

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

    all_upcoming_concerts = {}
    for band in bands_to_track:
        concerts = get_concert_info(band)
        if concerts:
            all_upcoming_concerts[band] = concerts

    # --- GitHub Issue Generation (Followed Artists) ---
    issue_title = f"Weekly Concert Alert (Europe): {date.today().isoformat()}"
    issue_body = format_issue_body(all_upcoming_concerts)
    
    if OUTPUT_FILE:
        with open(OUTPUT_FILE, "a") as f:
            f.write(f"issue_title={issue_title}\n")
            f.write("issue_body<<EOF\n")
            f.write(f"{issue_body}\n")
            f.write("EOF\n")
        print("Output prepared for GitHub Actions.")
    else:
        print("\n--- ISSUE PREVIEW (Local Test) ---")
        print("Title:", issue_title)
        print("Body:\n", issue_body)

    # --- RSS Feed Generation ---
    print("\nGenerating RSS feed...")
    rss_content = generate_rss_feed(all_upcoming_concerts)
    
    if rss_content:
        try:
            with open('concerts.rss', 'w', encoding='utf-8') as f:
                f.write(rss_content.decode('utf-8'))
            print(" -> Successfully generated and saved to concerts.rss")
        except Exception as e:
            print(f" -> Error saving RSS file: {e}")
    else:
        print(" -> RSS content was not generated (likely no events found). File not written.")
    
    # --- NEW FEATURE: Create GitHub Issue for Albanian Concerts ---
    albania_concerts = get_albania_concerts()
    if albania_concerts:
        albania_issue_title = f"Upcoming Concerts in Albania: {date.today().isoformat()}"
        albania_issue_body = format_albania_issue_body(albania_concerts)
        create_github_issue(albania_issue_title, albania_issue_body)
    else:
        print("\nNo upcoming concerts found in Albania. Skipping issue creation.")


    print("\nScript finished.")