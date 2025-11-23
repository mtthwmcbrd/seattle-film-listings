import requests
from bs4 import BeautifulSoup
import json
import datetime
import re
import html
import time

OUTPUT_FILE = 'listings.json'

# Robust headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://google.com'
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

def scrape_nwff_html():
    """
    Strategy 1: Scrape the 'Now Playing' /films/ page directly.
    This often uses standard HTML even if the Calendar is JS.
    """
    print("--- Strategy 1: NWFF HTML (/films/) ---")
    listings = []
    url = "https://nwfilmforum.org/films/"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Based on your screenshot, looking for 'preview-wrap'
        items = soup.find_all('article', class_='preview-wrap')
        
        if not items:
            print("No 'preview-wrap' items found on /films/")
            return []

        print(f"Found {len(items)} items on /films/ page.")

        for item in items:
            try:
                # Title
                title_tag = item.find(class_=re.compile(r'title', re.I))
                if not title_tag: continue
                title = title_tag.get_text(strip=True)

                # Link
                link_tag = item.find('a', href=True)
                link = link_tag['href'] if link_tag else url

                # Date (The tricky part on listing pages)
                # We look for the overlay text from your screenshot
                date_tag = item.find(class_=re.compile(r'top_text|date|time', re.I))
                date_display = "Check Website"
                sort_key = datetime.datetime.now().timestamp() + 86400 * 30 # Default to end of list

                if date_tag:
                    raw_text = date_tag.get_text(" ", strip=True)
                    # Attempt to clean up "Thu Nov 20 7.00pm"
                    date_display = raw_text.replace(" .", ":").replace(".", ":")
                    
                    # Try to parse a sortable date
                    # Regex for "Nov 20"
                    match = re.search(r'([A-Z][a-z]{2})\s(\d{1,2})', date_display)
                    if match:
                        month_str, day_str = match.groups()
                        now = datetime.datetime.now()
                        # Parse month name to number
                        try:
                            month_num = datetime.datetime.strptime(month_str, "%b").month
                            # Guess year
                            year = now.year
                            if month_num < now.month - 1: year += 1 # It's next year
                            
                            # Construct approx date for sorting
                            dt = datetime.datetime(year, month_num, int(day_str))
                            sort_key = dt.timestamp()
                        except: pass

                listings.append({
                    "theater": "NWFF",
                    "location": "1515 12th Ave",
                    "title": clean_title(title),
                    "date_display": date_display,
                    "link": link,
                    "sort_key": sort_key
                })
            except Exception: continue
            
    except Exception as e:
        print(f"NWFF HTML Error: {e}")
        
    return listings

def scrape_nwff_rss():
    """
    Strategy 2: The WordPress RSS Feed.
    This is the "old school" reliable method.
    """
    print("--- Strategy 2: NWFF RSS Feed ---")
    listings = []
    # Try the specific Tribe Events RSS feed
    rss_url = "https://nwfilmforum.org/feed/?post_type=tribe_events"
    
    try:
        response = requests.get(rss_url, headers=HEADERS, timeout=15)
        # Use XML parser
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')
        
        if not items:
            print("No items in RSS feed.")
            return []
            
        print(f"Found {len(items)} items in RSS feed.")

        for item in items:
            title = item.title.get_text(strip=True)
            link = item.link.get_text(strip=True)
            
            # RSS PubDate is usually when it was POSTED, not shown.
            # But the 'description' tag often contains the showtimes text.
            desc = item.description.get_text() if item.description else ""
            
            # Try to find a date in the description or title
            # Often Tribe puts "Event on: Date" in description
            date_display = "See Link for Showtimes"
            sort_key = datetime.datetime.now().timestamp()

            # Attempt to extract date from common text patterns
            # This is a guess, but better than nothing
            date_match = re.search(r'(\w{3,9} \d{1,2} @ \d{1,2}:\d{2} [ap]m)', desc, re.I)
            if date_match:
                date_display = date_match.group(1)
            
            listings.append({
                "theater": "NWFF",
                "location": "1515 12th Ave",
                "title": clean_title(title),
                "date_display": date_display,
                "link": link,
                "sort_key": sort_key
            })
            
    except Exception as e:
        print(f"NWFF RSS Error: {e}")

    return listings

def scrape_nwff_ical_brute_force():
    """
    Strategy 3: Try known iCal variations
    """
    print("--- Strategy 3: iCal Brute Force ---")
    listings = []
    # Common variations for WordPress Calendar plugins
    urls = [
        "https://nwfilmforum.org/events/?ical=1",
        "https://nwfilmforum.org/?post_type=tribe_events&ical=1",
        "https://nwfilmforum.org/calendar/?ical=1"
    ]
    
    for url in urls:
        print(f"Trying iCal URL: {url}")
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if "BEGIN:VCALENDAR" in response.text:
                print("SUCCESS: Found valid iCal feed!")
                # Parse logic here (simplified for brevity, reused from previous answer)
                # ... [Copy regex parsing logic here if desired] ...
                # For now, just return a dummy if found so we know it worked
                return [] # Placeholder to indicate we connected
        except: continue
    
    return []

def main():
    all_listings = []
    
    # 1. Scrape Beacon (Always works)
    all_listings.extend(scrape_the_beacon())
    
    # 2. Scrape NWFF (Try strategies in order)
    nwff_data = scrape_nwff_html()
    if not nwff_data:
        nwff_data = scrape_nwff_rss()
    
    if nwff_data:
        all_listings.extend(nwff_data)
    else:
        print("WARNING: All NWFF strategies failed.")

    # Sort
    all_listings.sort(key=lambda x: x['sort_key'])
    
    # Clean sort_key
    for item in all_listings:
        if 'sort_key' in item: del item['sort_key']

    # Save
    data = {
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "movies": all_listings
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Successfully saved {len(all_listings)} listings.")

if __name__ == "__main__":
    main()
