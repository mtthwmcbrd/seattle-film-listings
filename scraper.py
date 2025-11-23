import requests
from bs4 import BeautifulSoup
import json
import datetime
import re

OUTPUT_FILE = 'listings.json'

# Headers to look like a real browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def scrape_the_beacon():
    print("--- Scraping The Beacon (Calendar Grid) ---")
    url = "https://thebeacon.film/calendar"
    listings = []
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        print(f"Status Code: {response.status_code}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Strategy: The calendar is usually a bunch of day blocks.
        # We look for ANY element that contains a time format like "7:00 PM"
        # and then assume the text immediately before/around it is the title.
        
        # 1. Find all elements that might be an 'event'
        # Beacon often uses classes like 'event', 'calendar-event', 'chip'
        potential_events = soup.find_all('div', class_=re.compile(r'event|content|chip|inner', re.I))
        
        print(f"Scanning {len(potential_events)} layout elements...")
        
        for event in potential_events:
            text = event.get_text(" ", strip=True)
            
            # Check if this text block has a time in it (e.g. 7:00 PM or 7:00PM)
            time_match = re.search(r'(\d{1,2}:\d{2}\s?(?:AM|PM))', text, re.I)
            
            if time_match:
                time_str = time_match.group(1)
                
                # The Title is usually the text in this block minus the time
                # Example: "The Matrix 7:00 PM" -> Title: "The Matrix"
                title_candidate = text.replace(time_str, "").strip()
                
                # Cleanup: Remove "Sold Out", "Q&A", etc if they stick to the title
                title_candidate = re.sub(r'(Sold Out|Buy Tickets|Pt\s\d)', '', title_candidate, flags=re.I).strip()
                
                # Filter out garbage (too short, or just a date)
                if len(title_candidate) > 2 and not re.match(r'^\w{3}, \w{3} \d{1,2}$', title_candidate):
                    
                    # Avoid duplicates (The Beacon lists the same movie multiple times per month)
                    # We will create a unique key based on Title + Time to avoid adding the exact same showtime twice
                    entry = {
                        "theater": "The Beacon",
                        "title": title_candidate,
                        "date": time_str, # In a real app, we'd parse the full date from the column header
                        "link": url
                    }
                    
                    # Simple deduplication check
                    if entry not in listings:
                        listings.append(entry)
                        print(f"Found: {title_candidate} @ {time_str}")

    except Exception as e:
        print(f"Error: {e}")

    return listings

def main():
    all_listings = scrape_the_beacon()
    
    # Debugging: If empty, add a fake movie so you KNOW the site is loading the file
    if not all_listings:
        print("No listings found. Adding debug entry.")
        all_listings.append({
            "theater": "The Beacon",
            "title": "No listings found (Check Logs)",
            "date": "Error",
            "link": "#"
        })

    data = {
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "movies": all_listings
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved {len(all_listings)} items.")

if __name__ == "__main__":
    main()
