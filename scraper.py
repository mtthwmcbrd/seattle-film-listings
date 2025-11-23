import requests
from bs4 import BeautifulSoup
import json
import datetime
import re
import html

OUTPUT_FILE = 'listings.json'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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

def scrape_nwff_ical():
    print("--- Scraping NWFF (via iCal Feed) ---")
    listings = []
    
    # This URL forces the server to give us a raw text calendar file
    # It bypasses all the JavaScript and HTML layout issues
    ical_url = "https://nwfilmforum.org/calendar/?ical=1"
    
    try:
        response = requests.get(ical_url, headers=HEADERS, timeout=20)
        data = response.text
        
        # Regex to find Event Blocks
        # We look for BEGIN:VEVENT ... END:VEVENT
        events = re.findall(r'BEGIN:VEVENT(.*?)END:VEVENT', data, re.DOTALL)
        
        print(f"iCal feed returned {len(events)} raw events.")

        for event_block in events:
            try:
                # 1. Extract Title (SUMMARY)
                summary_match = re.search(r'SUMMARY:(.*?)\n', event_block)
                if not summary_match: continue
                title = summary_match.group(1).strip()
                
                # Cleanup Title (remove slashed characters sometimes found in ics)
                title = title.replace(r'\,', ',').replace(r'\;', ';')

                # Filter out non-films
                if any(x in title.lower() for x in ['workshop', 'camp', 'registration', 'closed']):
                    continue

                # 2. Extract Date (DTSTART)
                # Format is usually DTSTART;TZID=America/Los_Angeles:20251122T190000
                dt_match = re.search(r'DTSTART(?:;.*?)?:(\d{8}T\d{6})', event_block)
                if not dt_match: continue
                
                dt_str = dt_match.group(1) # e.g., 20251122T190000
                dt = datetime.datetime.strptime(dt_str, "%Y%m%dT%H%M%S")
                
                # Skip past events
                if dt < datetime.datetime.now():
                    continue

                date_display = dt.strftime("%a, %b %d @ %I:%M %p")

                # 3. Extract Link (URL)
                link_match = re.search(r'URL:(.*?)\n', event_block)
                link = link_match.group(1).strip() if link_match else "https://nwfilmforum.org/calendar"

                listings.append({
                    "theater": "NWFF",
                    "location": "1515 12th Ave",
                    "title": clean_title(title),
                    "date_display": date_display,
                    "link": link,
                    "sort_key": dt.timestamp()
                })
            except Exception as e:
                continue

    except Exception as e:
        print(f"NWFF iCal Error: {e}")
        
    return listings

def main():
    all_listings = []
    
    all_listings.extend(scrape_the_beacon())
    all_listings.extend(scrape_nwff_ical())
    
    # Sort by date
    all_listings.sort(key=lambda x: x['sort_key'])
    
    # Deduplicate
    unique_listings = []
    seen = set()
    for item in all_listings:
        uid = f"{item['theater']}{item['title']}{item['date_display']}"
        if uid not in seen:
            unique_listings.append(item)
            seen.add(uid)
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
