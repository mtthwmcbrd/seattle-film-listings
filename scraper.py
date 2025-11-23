import requests
from bs4 import BeautifulSoup
import json
import datetime
import re

# Define the output file
OUTPUT_FILE = 'listings.json'

def scrape_the_beacon():
    print("Scraping The Beacon...")
    url = "https://thebeacon.film/calendar"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.content, 'html.parser')
        listings = []
        
        # The Beacon uses a calendar grid. We look for specific day entries.
        # Note: This selector is hypothetical based on common structures; 
        # you would inspect the actual page source to find the exact class names.
        # For The Beacon, they often use 'entry' or 'calendar-day' classes.
        
        # Simplified logic: Look for movie titles in the calendar text
        # A robust scraper would parse the specific DOM structure.
        events = soup.find_all('div', class_='event') # Example selector
        
        for event in events:
            title_tag = event.find('h3') or event.find('a')
            if title_tag:
                title = title_tag.get_text(strip=True)
                # Extract time/date from sibling elements
                date_str = "See Website" # Placeholder for complex date parsing
                
                listings.append({
                    "theater": "The Beacon",
                    "title": title,
                    "date": date_str,
                    "link": url
                })
        return listings
    except Exception as e:
        print(f"Error scraping Beacon: {e}")
        return []

def scrape_grand_illusion():
    print("Scraping Grand Illusion...")
    url = "https://grandillusioncinema.org/"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.content, 'html.parser')
        listings = []
        
        # Grand Illusion usually lists "Now Playing" or "Coming Soon" on the home page
        items = soup.select('.film-entry') # Hypothetical class
        
        if not items:
            # Fallback: look for general headers if specific class fails
            items = soup.find_all('h2')

        for item in items:
            title = item.get_text(strip=True)
            # rudimentary filtering to avoid scraping navigation headers
            if len(title) > 3 and "Menu" not in title:
                listings.append({
                    "theater": "Grand Illusion",
                    "title": title,
                    "date": "Check Website", 
                    "link": url
                })
        return listings
    except Exception as e:
        print(f"Error scraping Grand Illusion: {e}")
        return []

def main():
    all_listings = []
    
    # Add scrapers here
    all_listings.extend(scrape_the_beacon())
    all_listings.extend(scrape_grand_illusion())
    
    # Add a timestamp
    data = {
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "movies": all_listings
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Successfully saved {len(all_listings)} listings to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()