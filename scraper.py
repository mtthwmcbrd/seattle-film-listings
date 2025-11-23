import requests
from bs4 import BeautifulSoup
import json
import datetime
import re
import html

OUTPUT_FILE = 'listings.json'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def clean_title(title):
    # Fixes &amp; -> &, and removes extra spaces
    return html.unescape(title).strip()

def scrape_the_beacon():
    print("--- Scraping The Beacon ---")
    url = "https://thebeacon.film/calendar"
    listings = []
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        items = soup.find_all('section', class_='showtime')
        
        for item in items:
            try:
                title_tag = item.find('section', itemprop='name')
                if not title_tag: continue
                title = title_tag.get_text(strip=True)
                
                if "RENT THE BEACON" in title: continue

                time_tag = item.find('section', itemprop='startDate')
                raw_date = None
                date_str = "Check Website"
                
                if time_tag and time_tag.get('content'):
                    iso_date = time_tag['content']
                    dt = datetime.datetime.fromisoformat(iso_date)
                    raw_date = dt
                    date_str = dt.strftime("%a, %b %d @ %I:%M %p")

                link_tag = item.find('a')
                link = link_tag['href'] if link_tag else url
                if not link.startswith('http'): link = "https://thebeacon.film" + link

                listings.append({
                    "theater": "The Beacon",
                    "location": "4405 Rainier Ave S",
                    "title": clean_title(title),
                    "date_display": date_str,
                    "link": link,
                    "sort_key": raw_date.timestamp() if raw_date else 0
                })
            except Exception: continue
    except Exception as e:
        print(f"Beacon Error: {e}")

    return listings

def scrape_nwff_api():
    print("--- Scraping NWFF (via API) ---")
    listings = []
    
    # This URL is the direct data feed for their calendar
    api_url = "https://nwfilmforum.org/wp-json/tribe/events/v1/events"
    
    # We ask for 100 events starting from today
    params = {
        "per_page": 100,
        "start_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        response = requests.get(api_url, params=params, headers=HEADERS, timeout=15)
        data = response.json()
        
        if 'events' not in data:
            print("API returned no events.")
            return []
            
        print(f"API returned {len(data['events'])} raw events.")

        for event in data['events']:
            try:
                title = event.get('title', 'Unknown Title')
                
                # Filter out Workshops/Camps to keep it to "Films"
                if any(x in title.lower() for x in ['workshop', 'camp', 'registration']):
                    continue

                # Get Date
                start_date_str = event.get('start_date') # "2025-11-20 19:00:00"
                dt = datetime.datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S")
                date_display = dt.strftime("%a, %b %d @ %I:%M %p")
                
                # Get Link
                link = event.get('url', 'https://nwfilmforum.org/calendar')

                listings.append({
                    "theater": "NWFF",
                    "location": "1515 12th Ave",
                    "title": clean_title(title),
                    "date_display": date_display,
                    "link": link,
                    "sort_key": dt.timestamp()
                })
            except Exception as e:
                print(f"Skipping NWFF item: {e}")
                
    except Exception as e:
        print(f"NWFF API Error: {e}")
        
    return listings

def main():
    all_listings = []
    
    all_listings.extend(scrape_the_beacon())
    all_listings.extend(scrape_nwff_api())
    
    # Sort everything by date
    all_listings.sort(key=lambda x: x['sort_key'])
    
    # Remove duplicates (sometimes API returns same movie twice if scraped oddly)
    unique_listings = []
    seen = set()
    for item in all_listings:
        # Create a unique signature
        uid = f"{item['theater']}{item['title']}{item['date_display']}"
        if uid not in seen:
            unique_listings.append(item)
            seen.add(uid)
            
        # Clean up the sort key before saving
        if 'sort_key' in item: del item['sort_key']

    data = {
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "movies": unique_listings
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Successfully saved {len(unique_listings)} listings.")

if __name__ == "__main__":
    main()
