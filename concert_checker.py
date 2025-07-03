import os
import requests
from datetime import date, datetime, time

# --- NEW: Import the feed generator library ---
from feedgen.feed import FeedGenerator

# --- Configuration ---
TICKETMASTER_API_KEY = os.environ.get("TICKETMASTER_API_KEY")
OUTPUT_FILE = os.environ.get("GITHUB_OUTPUT")

# --- NEW: Set a base URL for your feed. Important for links. ---
# Replace with your actual GitHub Pages URL or where you'll host the feed.
# For example: "https://your-username.github.io/your-repo-name/"
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

# --- NEW: Function to generate the RSS feed ---
def generate_rss_feed(all_concerts):
    """Generates an RSS feed from the concert data and returns it as a string."""
    fg = FeedGenerator()

    # Set up the feed's channel information
    fg.title('European Concerts for Followed Artists')
    fg.link(href=FEED_BASE_URL, rel='alternate')
    fg.description('Upcoming European concerts for artists followed in my list.')
    fg.language('en')

    # Flatten the list of all events and add the artist name to each event
    flat_event_list = []
    for artist, events in all_concerts.items():
        if events:
            for event in events:
                event['artist_name'] = artist # Add artist context to the event
                flat_event_list.append(event)
    
    # Sort all events by date, regardless of artist
    # This makes for a much better, chronologically-ordered feed
    flat_event_list.sort(key=lambda x: x['dates']['start'].get('localDate', '9999-12-31'))
    
    # Add each event as an item to the feed
    for event in flat_event_list:
        artist = event['artist_name']
        event_date_str = event['dates']['start'].get('localDate', 'N/A')
        venue_info = event.get('_embedded', {}).get('venues', [{}])[0]
        venue_name = venue_info.get('name', 'N/A')
        city = venue_info.get('city', {}).get('name', 'N/A')
        country = venue_info.get('country', {}).get('name', 'N/A')
        ticket_url = event.get('url', '#')

        # Create a nice title and description for the feed item
        item_title = f"{artist} @ {venue_name} in {city}, {country} on {event_date_str}"
        item_description = f"A concert by {artist} is scheduled for {event_date_str} at {venue_name}."

        fe = fg.add_entry()
        fe.id(ticket_url)  # The ticket URL is a perfect unique identifier
        fe.title(item_title)
        fe.link(href=ticket_url)
        fe.description(item_description)

        # Handle the publication date. RSS requires a full datetime.
        # We parse the date and combine it with a default time (e.g., noon)
        # as the API's time field can be inconsistent.
        try:
            parsed_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            # We use a fixed time like noon. This is a reasonable default.
            event_datetime = datetime.combine(parsed_date, time(12, 0))
            fe.pubDate(event_datetime)
        except (ValueError, TypeError):
            # If date parsing fails, use the current time as a fallback
            fe.pubDate(datetime.now())

    # Return the feed as an XML string
    # We set encoding to UTF-8 to handle special characters in band/venue names
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
        if concerts is not None:
            all_upcoming_concerts[band] = concerts

    # --- GitHub Issue Generation (Unchanged) ---
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

    # --- NEW: RSS Feed Generation ---
    print("\nGenerating RSS feed...")
    rss_content = generate_rss_feed(all_upcoming_concerts)
    
    # Save the RSS feed to a file
    try:
        with open('concerts.rss', 'w', encoding='utf-8') as f:
            f.write(rss_content)
        print(" -> Successfully generated and saved to concerts.rss")
    except Exception as e:
        print(f" -> Error saving RSS file: {e}")

    print("\nScript finished.")