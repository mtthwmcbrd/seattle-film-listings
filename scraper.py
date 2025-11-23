import requests
from bs4 import BeautifulSoup
import json
import datetime
import re

OUTPUT_FILE = 'listings.json'

def scrape_the_beacon():
    print("Scraping The Beacon...")
    url = "https://thebeacon.film/calendar"
    listings = []
    
    try:
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # STRATEGY: Find the "Select Showtimes" text, then look up for the Title and down for the Times.
        # This is more robust than guessing class names like 'event' or 'calendar-entry'.
        anchors = soup.find_all(string=re.compile("Select Showtimes"))
        
        for anchor in anchors:
            # The 'anchor' is just text. We want the container it sits inside.
            container = anchor.find_parent('div') 
            
            # 1. Find the Title
            # We assume the title is a header (h1-h4) somewhere *before* this section in the same block
            # We traverse up the tree until we find a block that likely holds the whole movie entry
            movie_block = container.find_parent('div', class_=re.compile(r'entry|film|event|item', re.I))
            
            # If we can't find a parent with a nice class, just go up 2-3 levels
            if not movie_block:
                movie_block = container.parent.parent
            
            # Search for the header inside this block
            title_tag = movie_block.find(['h2', 'h3', 'h4'])
            if not title_tag:
                # Fallback: look for strong text or links
                title_tag = movie_block.find('a', class_=re.compile(r'title|header', re.I))
            
            title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"

            # 2. Find the Dates/Times
            # They usually appear in a list or div immediately following the "Select Showtimes" text
            # We grab all text that looks like a date/time (e.g., "Sat, Nov 22 7:00PM")
            times_text = container.get_text(" ", strip=True)
            
            # Regex to find patterns like "7:00 PM" or "Sat, Nov 22"
            # This extracts just the times to make it cleaner
            found_times = re.findall(r'\d{1,2}:\d{2}\s?(?:AM|PM)', times_text)
            date_display = " | ".join(found_times) if found_times else "Check Website"
            
            # Clean up duplicates if any
            unique_times = sorted(list(set(found_times)))
            date_display = ", ".join(unique_times)

            listings.append({
                "theater": "The Beacon",
                "title": title,
                "date": date_display,
                "link": url
            })
            
    except Exception as e:
        print(f"Error scraping Beacon: {e}")

    return listings

def main():
    all_listings = []
    
    # Run the scraper
    beacon_data = scrape_the_beacon()
    all_listings.extend(beacon_data)
    
    # Save to file
    data = {
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "movies": all_listings
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Successfully saved {len(all_listings)} listings to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()