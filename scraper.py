import requests
from bs4 import BeautifulSoup
import json
import datetime
import re
import time

OUTPUT_FILE = 'listings.json'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def get_ordinal_date(n):
    return n + ("th" if 11 <= n <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))

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
                    "title": title,
                    "date_display": date_str,
                    "link": link,
                    "sort_key": raw_date.timestamp() if raw_date else 0
                })
            except Exception: continue
    except Exception as e:
        print(f"Beacon Error: {e}")

    return listings

def scrape_nwff():
    print("--- Scraping Northwest Film Forum ---")
    listings = []
    
    # We will scrape the current month AND the next month to ensure we get future listings
    # NWFF URL structure handles dates like: https://nwfilmforum.org/calendar/?tribe-bar-date=2025-11
    today = datetime.datetime.now()
    dates_to_scrape = [today, today + datetime.timedelta(days=32)]
    
    scraped_urls = []

    for d in dates_to_scrape:
        month_str = d.strftime("%Y-%m")
        url = f"https://nwfilmforum.org/calendar/?tribe-bar-date={month_str}"
        
        if url in scraped_urls: continue
        scraped_urls.append(url)
        
        print(f"Checking NWFF month: {month_str}...")
        
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Based on your screenshot: <article class="preview-wrap">
            items = soup.find_all('article', class_='preview-wrap')
            
            for item in items:
                try:
                    # 1. Title: <h1 class="preview__slide_bottom_title">
                    title_tag = item.find('h1', class_='preview__slide_bottom_title')
                    if not title_tag: continue
                    title = title_tag.get_text(strip=True)

                    # 2. Date/Time: <div class="preview__slide_top_text"> -> " Thu Nov 20 <br> 7.00pm "
                    date_container = item.find('div', class_='preview__slide_top_text')
                    if not date_container: continue
                    
                    # Get text, replace <br> with space, clean up
                    raw_text = date_container.get_text(" ", strip=True) # "Thu Nov 20 7.00pm"
                    
                    # Normalize formatting (remove extra spaces)
                    raw_text = re.sub(r'\s+', ' ', raw_text)
                    
                    # Parse Date
                    # Format usually: "Thu Nov 20 7.00pm" or "7.00pm"
                    # We need to add the Year to make it a real datetime object
                    current_year = d.year 
                    
                    # Handle "Nov 20" vs "Jan 05" (year rollover)
                    # Simple heuristic: if month is Jan and we are in Dec, add 1 to year.
                    
                    # Try to parse: "Thu Nov 20 7.00pm"
                    # Create a datetime object for sorting
                    clean_date_str = raw_text.replace(".", ":") # 7.00pm -> 7:00pm
                    
                    try:
                        # Attempt to parse "Thu Nov 20 7:00pm"
                        # We append the year to parse it correctly
                        parse_str = f"{clean_date_str} {current_year}"
                        dt = datetime.datetime.strptime(parse_str, "%a %b %d %I:%M%p %Y")
                        
                        # Fix for year boundary (Dec -> Jan)
                        # If parsed date is more than 11 months in the past, it's probably next year
                        if (datetime.datetime.now() - dt).days > 330:
                            dt = dt.replace(year=current_year + 1)
                        
                        sort_key = dt.timestamp()
                        date_display = dt.strftime("%a, %b %d @ %I:%M %p")
                    except ValueError:
                        # Fallback if format is weird
                        sort_key = d.timestamp() # Put it at end of month list
                        date_display = raw_text

                    # 3. Link
                    link_tag = item.find('a', class_='preview')
                    link = link_tag['href'] if link_tag else url

                    listings.append({
                        "theater": "NWFF",
                        "location": "1515 12th Ave",
                        "title": title,
                        "date_display": date_display,
                        "link": link,
                        "sort_key": sort_key
                    })
                    
                except Exception as e:
                    continue
            
            # Be nice to the server
            time.sleep(1)
            
        except Exception as e:
            print(f"NWFF Error: {e}")

    return listings

def main():
    all_listings = []
    
    all_listings.extend(scrape_the_beacon())
    all_listings.extend(scrape_nwff())
    
    # Global Sort by Date
    all_listings.sort(key=lambda x: x['sort_key'])
    
    # Cleanup keys not needed for JSON
    for item in listings:
        if 'sort_key' in item: del item['sort_key']

    # Deduplicate (NWFF sometimes lists same event on month overlap)
    unique_listings = []
    seen = set()
    for item in all_listings:
        # Create a unique ID string
        uid = f"{item['theater']}{item['title']}{item['date_display']}"
        if uid not in seen:
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
    # Fix 'listings' reference error in main
    listings = [] # temp holder
    main()
