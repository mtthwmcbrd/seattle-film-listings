import requests
from bs4 import BeautifulSoup
import json
import datetime
import re
import html
import time

OUTPUT_FILE = 'listings.json'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def clean_text(text):
    if not text: return ""
    return html.unescape(text).strip()

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
                    "title": clean_text(title),
                    "date_display": date_str,
                    "link": link,
                    "sort_key": raw_date.timestamp() if raw_date else 0
                })
            except Exception: continue
    except Exception as e:
        print(f"Beacon Error: {e}")

    return listings

def scrape_nwff_list_view():
    print("--- Scraping NWFF (List View) ---")
    listings = []
    
    # The "List View" is the secret weapon. It renders as a standard HTML list.
    # We scrape the current month list.
    url = "https://nwfilmforum.org/calendar/list/"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Tribe Events List View Structure
        # Usually <div class="type-tribe_events"> or <div class="tribe-events-calendar-list__event-details">
        # But NWFF might use custom classes. We'll search for the common "event" containers.
        
        # Look for standard Tribe List classes
        events = soup.find_all('div', class_=re.compile(r'type-tribe_events|tribe-events-calendar-list__event-details'))
        
        # Fallback: Look for the specific 'preview-wrap' class if they use their grid style on the list page
        if not events:
            events = soup.find_all('article', class_='preview-wrap')
            
        print(f"Found {len(events)} events in List View.")

        for event in events:
            try:
                # 1. Title
                # Tribe standard: <h3 class="tribe-events-calendar-list__event-title">
                # NWFF Custom: <h1 class="preview__slide_bottom_title">
                title_tag = event.find(re.compile(r'h\d'), class_=re.compile(r'title', re.I))
                if not title_tag: continue
                title = clean_text(title_tag.get_text())
                
                # Filter bad titles
                if any(x in title.lower() for x in ['workshop', 'camp', 'registration', 'call for']):
                    continue

                # 2. Link
                link_tag = event.find('a', href=True)
                link = link_tag['href'] if link_tag else url

                # 3. Date
                # Tribe standard: <time> tag
                # NWFF Custom: The 'preview__slide_top_text' div we saw before
                date_display = "Check Website"
                sort_key = datetime.datetime.now().timestamp() + 99999

                # Try finding a <time> tag first (Best case)
                time_tag = event.find('time')
                if time_tag and time_tag.has_attr('datetime'):
                    dt_str = time_tag['datetime']
                    try:
                        dt = datetime.datetime.fromisoformat(dt_str)
                        date_display = dt.strftime("%a, %b %d @ %I:%M %p")
                        sort_key = dt.timestamp()
                    except: pass
                else:
                    # Fallback to text parsing (NWFF Style)
                    date_container = event.find(class_=re.compile(r'time|date|top_text', re.I))
                    if date_container:
                        raw_text = date_container.get_text(" ", strip=True)
                        # Clean: "Thu Nov 20 7.00pm"
                        # Regex to capture "Nov 20 ... 7:00"
                        match = re.search(r'([A-Z][a-z]{2})\s(\d{1,2}).*?(\d{1,2}[:.]\d{2}\s?[ap]m)', raw_text, re.I)
                        if match:
                            m_str = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                            m_str = m_str.replace(".", ":")
                            # Add year
                            year = datetime.datetime.now().year
                            try:
                                dt = datetime.datetime.strptime(f"{m_str} {year}", "%b %d %I:%M%p %Y")
                                # Fix year rollover
                                if dt < datetime.datetime.now() - datetime.timedelta(days=60):
                                    dt = dt.replace(year=year + 1)
                                
                                date_display = dt.strftime("%a, %b %d @ %I:%M %p")
                                sort_key = dt.timestamp()
                            except:
                                date_display = raw_text # Fallback to raw text

                listings.append({
                    "theater": "NWFF",
                    "location": "1515 12th Ave",
                    "title": title,
                    "date_display": date_display,
                    "link": link,
                    "sort_key": sort_key
                })
            except Exception: continue
            
    except Exception as e:
        print(f"NWFF List View Error: {e}")
        
    return listings

def scrape_nwff_rss_tribe():
    """
    Backup Strategy: The Tribe Events RSS Feed (with correct parser)
    """
    print("--- Scraping NWFF (RSS: Tribe Events) ---")
    listings = []
    rss_url = "https://nwfilmforum.org/feed/?post_type=tribe_events"
    
    try:
        response = requests.get(rss_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser') # CORRECT PARSER
        items = soup.find_all('item')
        print(f"RSS returned {len(items)} items.")
        
        for item in items:
            try:
                title = clean_text(item.title.get_text())
                if any(x in title.lower() for x in ['workshop', 'camp']): continue
                
                link = item.link.get_text(strip=True) if item.link else ""
                desc = item.description.get_text(strip=True) if item.description else ""
                
                # Extract date from Description
                date_display = "Check Website"
                sort_key = datetime.datetime.now().timestamp() + 99999
                
                # Look for "November 23 @ 7:00 pm"
                match = re.search(r'([A-Z][a-z]+\s\d{1,2}\s@\s\d{1,2}:\d{2}\s[ap]m)', desc, re.I)
                if match:
                    date_display = match.group(1)
                    # Simple sort key attempt
                    sort_key = datetime.datetime.now().timestamp()

                listings.append({
                    "theater": "NWFF",
                    "location": "1515 12th Ave",
                    "title": title,
                    "date_display": date_display,
                    "link": link,
                    "sort_key": sort_key
                })
            except: continue
    except Exception as e:
        print(f"RSS Error: {e}")
        
    return listings

def main():
    all_listings = []
    
    # 1. Beacon
    all_listings.extend(scrape_the_beacon())
    
    # 2. NWFF (Try List View first, then RSS)
    nwff_data = scrape_nwff_list_view()
    if not nwff_data:
        nwff_data = scrape_nwff_rss_tribe()
        
    all_listings.extend(nwff_data)
    
    # Sort
    all_listings.sort(key=lambda x: x['sort_key'])
    
    # Clean & Dedup
    unique_listings = []
    seen = set()
    for item in all_listings:
        uid = f"{item['theater']}{item['title']}{item['date_display']}"
        if uid not in seen:
            if 'sort_key' in item: del item['sort_key']
            unique_listings.append(item)
            seen.add(uid)

    data = {
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "movies": unique_listings
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Successfully saved {len(unique_listings)} listings.")

if __name__ == "__main__":
    main()
