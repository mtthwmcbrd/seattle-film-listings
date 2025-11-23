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

def scrape_nwff_visual():
    print("--- Scraping NWFF (Visual Calendar) ---")
    listings = []
    
    # We scrape the main calendar page directly
    url = "https://nwfilmforum.org/calendar/"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Target the exact class from your screenshot
        items = soup.find_all('article', class_='preview-wrap')
        print(f"Found {len(items)} visual blocks on the calendar.")

        for item in items:
            try:
                # 1. Title
                # Your screenshot shows: <h1 class="preview__slide_bottom_title">
                title_tag = item.find(['h1', 'h2', 'h3'], class_=re.compile(r'title|bottom_text', re.I))
                if not title_tag: continue
                title = clean_text(title_tag.get_text())
                
                # Filter non-movies
                if any(x in title.lower() for x in ['workshop', 'camp', 'registration', 'call for']):
                    continue

                # 2. Date
                # Your screenshot shows: <div class="preview__slide_top_text"> "Thu Nov 20 <br> 7.00pm"
                date_tag = item.find('div', class_='preview__slide_top_text')
                
                date_display = "Check Website"
                sort_key = datetime.datetime.now().timestamp() + 99999

                if date_tag:
                    # Get text, turning <br> into spaces
                    text = date_tag.get_text(" ", strip=True)
                    # Result: "Thu Nov 20 7.00pm" or "Thu Nov 20 7:00pm"
                    
                    # Clean up dots in time (7.00 -> 7:00)
                    text = text.replace(".", ":") 
                    
                    # Regex to extract components: Month Day Time
                    # Matches: "Nov 20 ... 7:00 pm"
                    match = re.search(r'([A-Z][a-z]{2})\s(\d{1,2}).*?(\d{1,2}:\d{2}\s?[ap]m)', text, re.I)
                    
                    if match:
                        month_str, day_str, time_str = match.groups()
                        
                        # Guess the Year
                        now = datetime.datetime.now()
                        year = now.year
                        
                        # Parse month name to number
                        try:
                            month_dt = datetime.datetime.strptime(month_str, "%b")
                            month_num = month_dt.month
                            
                            # If we are in Dec and see Jan, it's next year
                            if now.month == 12 and month_num == 1:
                                year += 1
                            # If we are in Jan and see Dec, it's last year (ignore)
                            elif now.month == 1 and month_num == 12:
                                year -= 1 # Should filter out later if needed

                            # Combine into full date object
                            dt = datetime.datetime.strptime(f"{month_str} {day_str} {year} {time_str}", "%b %d %Y %I:%M%p")
                            
                            date_display = dt.strftime("%a, %b %d @ %I:%M %p")
                            sort_key = dt.timestamp()
                        except Exception as e:
                            # If strict parsing fails, just display the cleaned text
                            date_display = text
                    else:
                        date_display = text

                # 3. Link
                link_tag = item.find('a', href=True)
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
                # print(f"Skipping item: {e}")
                continue

    except Exception as e:
        print(f"NWFF Visual Error: {e}")
        
    return listings

def main():
    all_listings = []
    
    # 1. Beacon
    all_listings.extend(scrape_the_beacon())
    
    # 2. NWFF Visual
    nwff_data = scrape_nwff_visual()
    all_listings.extend(nwff_data)
    
    # Sort by date
    all_listings.sort(key=lambda x: x['sort_key'])
    
    # Deduplicate
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
