import datetime
from datetime import timezone
import time
import requests
import random
from stem import Signal
from stem.control import Controller
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from art import text2art
from db import save_page

print(text2art("DARKWEB    CRAWLER ",font="doom").center(200))

# Number of links to crawl
num_links_to_crawl = 100

# Sets the user agent to use for the request
user_agent = "HotJava/1.1.2 FCS"
headers = {'User-Agent': user_agent}

# Config: filters to skip certain paths, query params, and file extensions (22-33 https://github.com/scrape-do/python-web-crawler/blob/main/crawlerScrape-do.py)
EXCLUDED_PATHS = ["/login", "/signup", "/cart", "/checkout"]
EXCLUDED_QUERY_PARAMS = ["q=", "search=", "filter="]
SKIP_EXTENSIONS = (
    ".xml", ".json", ".pdf", ".jpg", ".jpeg", ".png", ".gif",
    ".svg", ".zip", ".rar", ".mp4", ".mp3", ".ico"
)

def should_skip_url(url):
    """Skip links that point to static files or undesired formats."""
    return url.lower().endswith(SKIP_EXTENSIONS)

# Extract_links function (58-81 https://github.com/scrape-do/python-web-crawler/blob/main/crawlerScrape-do.py)
def extract_links(html, base_url):
    """
    Extracts valid, same-domain or subdomain links from a page.
    Filters out paths and query strings you don't want to crawl.
    """
    soup = BeautifulSoup(html, "html.parser")
    base_domain = ".".join(urlparse(base_url).netloc.split(".")[-2:])
    links = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)

        if not parsed.netloc.endswith(base_domain):
            continue
        if any(path in parsed.path for path in EXCLUDED_PATHS):
            continue
        if any(q in parsed.query for q in EXCLUDED_QUERY_PARAMS):
            continue
        if should_skip_url(absolute):
            continue
        if absolute.startswith("http"):
            links.add(absolute)

    return links

# Initialize the controller for the Tor network
with Controller.from_port(port=9051) as controller:
    controller.authenticate()
    time.sleep(5)

    # Counter for IP-circut change
    change_NEWNYM = 10
    requests_since_NEWNYM = 0

    # Set the starting URLs
    urls = ['http://torrun2qbnatvz7teqdbrowcw3tzexpkbkac76romztnaq5ngqxyz5ad.onion',
            'https://v236xhqtyullodhf26szyjepvkbv6iitrhjgrqj4avaoukebkk6n6syd.onion']

    # Initialize the visited set and the link queue
    visited = set()
    queue = urls.copy()
    
    # Keywords found list
    hits = 0
    hits_list = []

    # Get keywords
    keywords = input('Enter keywords (comma separated): ').split(',')
    keywords = [k.strip().lower() for k in keywords]

    print(f"Starting session with selected keywords: {keywords}")
    print("-" * 80)

# Tor SOCKS proxy session
    session = requests.Session()
    session.proxies = {
        'http': 'socks5h://127.0.0.1:9050',
        'https': 'socks5h://127.0.0.1:9050'
    }

    link_count = 0
    try:
        while queue and link_count < num_links_to_crawl:
            link = queue.pop(0)
            
            if link in visited:
                continue

            print(f"Fetching ({link_count + 1}/{num_links_to_crawl}): {link}")
            
            # Randomized request rate
            time.sleep(random.uniform(1.5, 3.5))

            try:
                response = session.get(link, headers=headers, timeout=60)
                print(f"Response: {response.status_code}")
                
                if response.status_code != 200:
                    print(f"HTTP {response.status_code}: {link}")
                    visited.add(link)
                    link_count += 1
                    continue
                
                requests_since_NEWNYM += 1
                if requests_since_NEWNYM >= change_NEWNYM:
                    controller.signal(Signal.NEWNYM)
                    time.sleep(controller.get_newnym_wait())
                    requests_since_NEWNYM = 0

                print(f"Page loaded successfully")
                
                soup = BeautifulSoup(response.text, 'html.parser')

                # Extract
                page_text = soup.get_text().lower()
                title = soup.title.string if soup.title else "No title"
                matched_keywords = [k for k in keywords if k in page_text]

                # Information to be saved
                save_db = {
                    "url": link, "title": title, 
                    "http_status": response.status_code,
                    "keywords_matched": matched_keywords, 
                    "last_checked_at": datetime.datetime.now(timezone.utc)
                }
                
                # Keyword count, tracker and saving to the database
                if matched_keywords:
                    hits += 1
                    hits_list.append({
                    "url": link,
                    "title": title,
                    "keywords_matched": matched_keywords
                    })
                    save_page(save_db)

                # Pass response.text and link as base_url
                new_links_set = extract_links(response.text, link)
                new_links = 0
                for full_url in new_links_set:
                    if full_url not in visited and full_url not in queue:
                        queue.append(full_url)
                        print(f"Queued new link: {full_url}")
                        new_links += 1

                if new_links > 0:
                    print(f"Found {new_links} new link(s)")

                visited.add(link)
                link_count += 1
                
            # Error handling and the reason
            except requests.exceptions.Timeout:
                print(f"Timeout after 60s: {link}")
                visited.add(link)
                link_count += 1
            except requests.exceptions.ConnectionError as e:
                print(f"Connection failed: {link} - {e}")
                visited.add(link)
                link_count += 1
            except Exception as e:
                print(f"Error {link}: {e}")
                visited.add(link)
                link_count += 1

    except KeyboardInterrupt:
        print("\\nInterrupted!")
    
    finally:
        # Summary of the session
        print("="*80)
        print("Session complete")
        print(f"Total pages crawled: {len(visited)}")
        print(f"Total keyword hits: {hits}")
        print("Hits found:")
        for hit in hits_list:
            keywords_str = ", ".join(hit["keywords_matched"])
            print(f"   {hit['title']}: {hit['url']}  [matched: {keywords_str}]")
        print("="*80)
