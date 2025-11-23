import requests
from bs4 import BeautifulSoup
import json
import datetime

OUTPUT_FILE = 'listings.json'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def scrape_the_beacon():
    print("--- Scraping The Beacon (Precision Mode) ---")
    url = "https://thebeacon.film/calendar"
    listings = []
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # TARGET: <section class="showtime transformer">
        # This matches the HTML screenshot you provided exactly.
        items = soup.find_all('section', class_='showtime')
        
        print(f"Found {len(items)} showtime elements.")
        
        for item in items:
            try:
                # 1. Get Title (<section itemprop="name">)
                title_tag = item.find('section', itemprop='name')
                if not title_tag: continue
                title = title_tag.get_text(strip=True)
                
                # Filter out private rentals if you want
                if "RENT THE BEACON" in title: continue

                # 2. Get Date/Time (<section itemprop="startDate" content="...">)
                # The 'content' attribute (e.g., "2025-11-26T16:00") gives us the exact timestamp.
                time_tag = item.find('section', itemprop='startDate')
                date_str = "Check Website"
                raw_date = None
                
                if time_tag and time_tag.get('content'):
                    iso_date = time_tag['content'] # "2025-11-26T16:00"
                    
                    # Convert ISO format to a nice readable string
                    dt = datetime.datetime.fromisoformat(iso_date)
                    raw_date = dt # Keep raw object for sorting
                    # Format: "Wed, Nov 26 @ 4:00 PM"
                    date_str = dt.strftime("%a, %b %d @ %I:%M %p")

                # 3. Get Link (The parent <a> tag)
                link_tag = item.find('a')
                link = link_tag['href'] if link_tag else url
                if not link.startswith('http'):
                    link = "https://thebeacon.film" + link

                listings.append({
                    "theater": "The Beacon",
                    "title": title,
                    "date": date_str,
                    "link": link,
                    "sort_key": raw_date.timestamp() if raw_date else 0
                })

            except Exception as e:
                print(f"Skipped an item due to error: {e}")
                continue

        # Sort the movies by date (oldest to newest)
        listings.sort(key=lambda x: x['sort_key'])
        
        # Remove the sort_key before saving to JSON (cleaner data)
        for item in listings:
            del item['sort_key']

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

    return listings

def main():
    all_listings = scrape_the_beacon()
    
    # Save to file
    data = {
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "movies": all_listings
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Successfully saved {len(all_listings)} listings.")

if __name__ == "__main__":
    main()
