import requests
from bs4 import BeautifulSoup
import json
import datetime
import re
import sys

# Define output file
OUTPUT_FILE = 'listings.json'

# Real browser headers to avoid being blocked
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://google.com'
}

def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text).strip()

def scrape_the_beacon():
    print("--- Scraping The Beacon ---")
    url = "https://thebeacon.film/calendar"
    listings = []
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print("ERROR: Failed to load page.")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')

        # Debug: Print page title to verify we got the right page
        print(f"Page Title: {soup.title.string if soup.title else 'No Title'}")

        # STRATEGY: The Beacon listings usually have a "Select Showtimes" section.
        # We look for the movie title (h2/h3) and then find the times associated with it.
        
        # 1. Find all potential movie containers
        # These are usually divs that contain both a header and the text "Select Showtimes"
        items = soup.find_all('div', class_=re.compile(r'entry|film|item|event', re.I))
        
        print(f"Found {len(items)} potential containers.")
        
        for item in items:
            text_content = item.get_text()
            
            # Check if this container actually has showtimes
            if "Select Showtimes" in text_content or "Purchase Tickets" in text_content:
                
                # Find Title: Look for the first Header tag
                title_tag = item.find(['h1', 'h2', 'h3', 'h4'])
                if not title_tag: continue
                
                title = clean_text(title_tag.get_text())
                
                # Find Times: Look for time patterns like "7:00 PM"
                # We specifically look in the text *after* the title
                times = re.findall(r'\d{1,2}:\d{2}\s?(?:AM|PM)', text_content)
                unique_times = sorted(list(set(times)))
                
                if unique_times:
                    print(f"Found: {title} - {unique_times}")
                    listings.append({
                        "theater": "The Beacon",
                        "title": title,
                        "date": ", ".join(unique_times),
                        "link": url
                    })
        
        # FALLBACK: If the above found nothing, just grab H3s and assume they are movies
        if len(listings) == 0:
            print("Standard parsing failed. Trying fallback...")
            headers = soup.find_all(['h2', 'h3'])
            for h in headers:
                t = clean_text(h.get_text())
                if len(t) > 2 and "Menu" not in t and "Calendar" not in t:
                    listings.append({
                        "theater": "The Beacon",
                        "title": t,
                        "date": "See Website",
                        "link": url
                    })

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        
    return listings

def scrape_grand_illusion():
    print("--- Scraping Grand Illusion ---")
    url = "https://grandillusioncinema.org/"
    listings = []
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Grand Illusion uses 'film-entry' or similar classes
        items = soup.find_all(class_=re.compile(r'film-entry|post|product'))
        
        for item in items:
            title_tag = item.find(['h1', 'h2', 'h3'])
            if title_tag:
                title = clean_text(title_tag.get_text())
                if "Membership" in title or "Newsletter" in title: continue
                
                listings.append({
                    "theater": "Grand Illusion",
                    "title": title,
                    "date": "Check Website", 
                    "link": url
                })
    except Exception as e:
        print(f"Grand Illusion Error: {e}")
        
    return listings

def main():
    all_listings = []
    
    all_listings.extend(scrape_the_beacon())
    all_listings.extend(scrape_grand_illusion())
    
    print(f"Total listings found: {len(all_listings)}")
    
    # ALWAYS save the file, even if empty, so the frontend doesn't crash
    data = {
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "movies": all_listings
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
