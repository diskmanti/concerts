import os
import requests
from datetime import date

# --- Configuration ---
# Loaded from GitHub Secrets
BANDSINTOWN_APP_ID = os.environ.get("BANDSINTOWN_APP_ID")
# The file path provided by the GitHub Actions runner
OUTPUT_FILE = os.environ.get("GITHUB_OUTPUT")

def get_concert_info(artist_name):
    """Fetches concert data for a single artist from the Bandsintown API."""
    encoded_artist = requests.utils.quote(artist_name)
    url = f"https://rest.bandsintown.com/artists/{encoded_artist}/events?app_id={BANDSINTOWN_APP_ID}"
    
    print(f"Checking for {artist_name}...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
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
                venue = event.get('venue', {})
                event_date = event.get('datetime', 'N/A').split('T')[0]
                venue_name = venue.get('name', 'N/A')
                city = venue.get('city', 'N/A')
                country = venue.get('country', 'N/A')
                ticket_url = event.get('url', '#')
                
                md_body += f"- **{event_date}** - {venue_name} in {city}, {country} ([See Tickets]({ticket_url}))\n"
            md_body += "\n"
            
    return md_body

# --- Main Execution ---
if __name__ == "__main__":
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
    
    # Write the output to the GITHUB_OUTPUT file for the workflow to use
    if OUTPUT_FILE:
        with open(OUTPUT_FILE, "a") as f:
            # Use a multiline string format for the body
            f.write(f"issue_title={issue_title}\n")
            f.write("issue_body<<EOF\n")
            f.write(f"{issue_body}\n")
            f.write("EOF\n")
        print("Output prepared for GitHub Actions.")
    else:
        # Fallback for local testing
        print("\n--- ISSUE PREVIEW ---")
        print("Title:", issue_title)
        print("Body:\n", issue_body)

    print("Script finished.")