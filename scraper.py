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

def scrape_nwff_rss():
    print("--- Scraping NWFF (RSS Feed) ---")
    listings = []
    
    # Try the main events feed
    # We use 'html.parser' which is built-in, avoiding the XML error
    rss_url = "https://nwfilmforum.org/feed/?post_type=tribe_events"
    
    try:
        response = requests.get(rss_url, headers=HEADERS, timeout=15)
        # FIX: Use 'html.parser' instead of 'xml'
        soup = BeautifulSoup(response.content, 'html.parser')
        
        items = soup.find_all('item')
        print(f"RSS Feed returned {len(items)} items.")

        for item in items:
            try:
                title = item.title.get_text(strip=True)
                link = item.link.get_text(strip=True) if item.link else "https://nwfilmforum.org"
                
                # RSS descriptions often contain the date like "November 23 @ 7:00 pm"
                desc = item.description.get_text(strip=True) if item.description else ""
                
                # 1. Clean Title
                # Sometimes title is "Movie Name - November 22". We want just "Movie Name"
                clean_title_str = title.split(" &#8211; ")[0] # Remove dash and date if present
                clean_title_str = clean_title(clean_title_str)

                # Filter out Workshops
                if any(x in clean_title_str.lower() for x in ['workshop', 'camp', 'class', 'registration']):
                    continue

                # 2. Extract Date
                # Look for patterns like "Nov 23 @ 7:00 pm" or "November 23 @ 7:00 pm"
                date_display = "Check Website"
                sort_key = datetime.datetime.now().timestamp() + 86400 * 60 # Default to far future
                
                # Regex to find date in description
                # Matches: Month Name DD @ HH:MM am/pm
                date_match = re.search(r'([A-Z][a-z]+ \d{1,2} @ \d{1,2}:\d{2} [ap]m)', desc)
                
                if date_match:
                    date_str = date_match.group(1) # e.g. "November 23 @ 7:00 pm"
                    date_display = date_str
                    
                    # Try to parse into a real date object for sorting
                    try:
                        # We need to guess the year (RSS doesn't always have it)
                        current_year = datetime.datetime.now().year
                        dt = datetime.datetime.strptime(f"{date_str} {current_year}", "%B %d @ %I:%M %p %Y")
                        
                        # If date is way in the past (e.g. scraped a Jan movie in Dec), add a year
                        if dt < datetime.datetime.now() - datetime.timedelta(days=30):
                            dt = dt.replace(year=current_year + 1)
                            
                        sort_key = dt.timestamp()
                        # Reformat nicely: "Sat, Nov 23 @ 7:00 PM"
                        date_display = dt.strftime("%a, %b %d @ %I:%M %p")
                    except:
                        pass # Keep raw string if parsing fails
                
                listings.append({
                    "theater": "NWFF",
                    "location": "1515 12th Ave",
                    "title": clean_title_str,
                    "date_display": date_display,
                    "link": link,
                    "sort_key": sort_key
                })
                
            except Exception as e:
                print(f"Skipping RSS item: {e}")
                continue

    except Exception as e:
        print(f"NWFF RSS Error: {e}")

    return listings

def main():
    all_listings = []
    
    # 1. Beacon
    all_listings.extend(scrape_the_beacon())
    
    # 2. NWFF
    nwff_data = scrape_nwff_rss()
    all_listings.extend(nwff_data)
    
    # Sort by date
    all_listings.sort(key=lambda x: x['sort_key'])
    
    # Deduplicate
    unique_listings = []
    seen = set()
    for item in all_listings:
        # Create a unique signature
        uid = f"{item['theater']}{item['title']}{item['date_display']}"
        if uid not in seen:
            unique_listings.append(item)
            seen.add(uid)
        
        # Cleanup
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
