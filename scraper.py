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

def scrape_nwff_deep():
    print("--- Scraping NWFF (Films RSS + Deep Search) ---")
    listings = []
    
    # CORRECT FEED: 'post_type=film' gets the movies, not the news
    rss_url = "https://nwfilmforum.org/feed/?post_type=film"
    
    try:
        response = requests.get(rss_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser') # Use html.parser to avoid XML errors
        
        items = soup.find_all('item')
        print(f"Found {len(items)} films in RSS feed. Checking showtimes...")

        # Limit to first 15 items to keep script fast (movies usually stay in feed for a while)
        for item in items[:15]:
            try:
                title = item.title.get_text(strip=True)
                link = item.link.get_text(strip=True)
                
                # Cleanup Title (Remove " - Nov 20" etc)
                title = title.split(" &#8211; ")[0]
                title = clean_title(title)
                
                # Filter junk
                if any(x in title.lower() for x in ['workshop', 'camp', 'call for', 'registration']):
                    continue

                # DEEP SCRAPE: Visit the movie page to find the specific dates
                # We look for the class from your screenshot: 'preview__slide_top_text'
                # or standard time formats.
                try:
                    movie_page = requests.get(link, headers=HEADERS, timeout=10)
                    page_soup = BeautifulSoup(movie_page.content, 'html.parser')
                    
                    # 1. Look for the exact structure from your screenshot
                    # Your screenshot showed dates inside <div class="preview__slide_top_text">
                    date_tags = page_soup.find_all(class_='preview__slide_top_text')
                    
                    found_dates = []
                    
                    if date_tags:
                        for tag in date_tags:
                            # Text is like: "Thu Nov 20 <br> 7.00pm"
                            # We replace <br> with space
                            for br in tag.find_all("br"): br.replace_with(" ")
                            date_text = tag.get_text(" ", strip=True)
                            
                            # Clean it up: "Thu Nov 20 7.00pm" -> "Thu, Nov 20 @ 7:00 PM"
                            # Basic regex to catch "Nov 20" part
                            if re.search(r'\w{3}\s\d{1,2}', date_text):
                                found_dates.append(date_text)
                    
                    # 2. Fallback: Search for any text that looks like a date on the page
                    if not found_dates:
                        # Regex for "Month DD @ HH:MM" or similar
                        page_text = page_soup.get_text()
                        matches = re.findall(r'([A-Z][a-z]{2})\s(\d{1,2})\s@\s(\d{1,2}:\d{2}\s?[ap]m)', page_text, re.I)
                        for m in matches:
                            found_dates.append(f"{m[0]} {m[1]} @ {m[2]}")

                    # If we found dates, add a listing for EACH showtime
                    if found_dates:
                        for d_str in found_dates:
                             # Clean up string
                            d_str = d_str.replace(" .", ":").replace(".", ":")
                            
                            listings.append({
                                "theater": "NWFF",
                                "location": "1515 12th Ave",
                                "title": title,
                                "date_display": d_str, # Keep raw string if parsing is hard, usually readable enough
                                "link": link,
                                "sort_key": datetime.datetime.now().timestamp() # Default sort
                            })
                    else:
                        # If no specific dates found, just list "Check Website"
                        listings.append({
                            "theater": "NWFF",
                            "location": "1515 12th Ave",
                            "title": title,
                            "date_display": "Check Website for Showtimes",
                            "link": link,
                            "sort_key": datetime.datetime.now().timestamp() + 99999
                        })
                        
                    # Be nice to server
                    time.sleep(0.5)

                except Exception as e:
                    print(f"Failed to deep scrape {title}: {e}")
                    continue
                
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
    
    # 2. NWFF Deep Scrape
    nwff_data = scrape_nwff_deep()
    all_listings.extend(nwff_data)
    
    # Sort
    # Since deep scrape dates are hard to convert to timestamps perfectly without year,
    # we sort mostly by the Beacon timestamps, and append NWFF. 
    # A true sort would require complex date parsing logic.
    all_listings.sort(key=lambda x: x['sort_key'])
    
    # Remove Sort Key
    for item in all_listings:
        if 'sort_key' in item: del item['sort_key']

    # Deduplicate
    unique_listings = []
    seen = set()
    for item in all_listings:
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
    main()
