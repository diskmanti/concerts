import os
import requests
from datetime import date

# --- Configuration ---
# This will be loaded from the GitHub Secret you create
TICKETMASTER_API_KEY = os.environ.get("TICKETMASTER_API_KEY")
# The file path provided by the GitHub Actions runner
OUTPUT_FILE = os.environ.get("GITHUB_OUTPUT")

def get_concert_info(artist_name):
    """Fetches concert data for a single artist from the Ticketmaster API."""
    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        'apikey': TICKETMASTER_API_KEY,
        'keyword': artist_name,
        'classificationName': 'Music', # IMPORTANT: Filters results to only music events
        'sort': 'date,asc'             # Gets the soonest events first
    }
    
    print(f"Checking for {artist_name} using Ticketmaster API...")
    try:
        response = requests.get(url, params=params)
        response.raise_for_status() # Raise an error for bad responses (4xx or 5xx)
        data = response.json()
        # Events are nested inside the '_embedded' key. If it doesn't exist, return an empty list.
        return data.get('_embedded', {}).get('events', [])
    except requests.exceptions.RequestException as e:
        print(f"  -> Failed to get data for {artist_name}: {e}")
        return None

def format_issue_body(all_concerts):
    """Formats the concert data into a nice Markdown string for the issue body."""
    if not any(all_concerts.values()):
        return "No upcoming concerts found for your followed artists this week."

    md_body = "Here are the upcoming shows for your followed bands:\n\n"
    for artist, events in all_concerts.items():
        if events:
            md_body += f"## {artist}\n"
            for event in events:
                # The data structure is different, so we parse it accordingly
                event_date = event['dates']['start'].get('localDate', 'N/A')
                venue_info = event.get('_embedded', {}).get('venues', [{}])[0]
                venue_name = venue_info.get('name', 'N/A')
                city = venue_info.get('city', {}).get('name', 'N/A')
                country = venue_info.get('country', {}).get('countryCode', 'N/A')
                ticket_url = event.get('url', '#')
                
                md_body += f"- **{event_date}** - {venue_name} in {city}, {country} ([See Tickets]({ticket_url}))\n"
            md_body += "\n"
            
    return md_body

# --- Main Execution (No changes needed below this line) ---
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
        if concerts is not None:
            all_upcoming_concerts[band] = concerts

    issue_title = f"Weekly Concert Alert: {date.today().isoformat()}"
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

    print("Script finished.")