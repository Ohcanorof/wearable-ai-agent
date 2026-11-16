# fetcher.py
#part 2, now we search for wearable device specs

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv
from tavily import TavilyClient
from targets import get_targets

#load env vars
load_dotenv()

#get the tavily api key from .env
API_KEY = os.getenv("TAVILY_API_KEY")

#store the results into the data folder
DATA_DIR = Path("data")

#need to limit how much we extract per device (pages)
MAX_PAGES =2

#will try only using apporved manufactured domains for each brand
OFFICIAL_DOMANINS = {
    "Apple": ["apple.com"],
    "Garmin": ["garmin.com"],
    "Oura": ["ouraring.com"],
    "WHOOP": ["whoop.com"],
    "Samsung": ["samsung.com"],
    "Fitbit": ["fitbit.com", "store.google.com"],
}

#creating a search query dinamically
#fstrings help insert vars into text
def create_search_query(device):
    """Build a search query using the device information."""

    brand = device["brand"]
    model = device["model"]

    query = (
        f"{brand} {model} official specifications "
        "battery life sensors GPS water resistance connectivity"
    )
    
    return query

def is_official_url(url, allowed_domains):
    """Check if a URL belongs to an approved domain."""
    try:
        parsed_url = urlparse(url)

        #we only accept secure https websites
        if parsed_url.scheme != "https":
            return False
        
        hostname = parsed_url.hostname
        if not hostname:
            return False

        hostname = hostname.lower()

        for domain in allowed_domains: 
            #we allow the domains themselves and any of its subdomains
            if hostname == domain or hostname.endswith("." + domain):
                return True

        return False

    except (ValueError, TypeError):
        return False

def search_device(device, client):
    """Search Tavily and keep only manufacturer URLs."""

    query =  create_search_query(device)
    brand = device["brand"]

    #stop if we dont have any defined apporved domains
    if brand not in OFFICIAL_DOMANINS:
        raise ValueError(f"No approved domains configured for {brand}")

    allowed_domains = OFFICIAL_DOMANINS[brand]

    print(f"Searching: {query}")

    # now we send the query to Tavily (first external API call)
    response =  client.search(
        query = query,
        search_depth = "basic",
        max_results = 5,
        include_domains = allowed_domains,
        include_answer = False,
        include_raw_content = False,
    )

    #extract these results from the response
    results = response.get("results", [])

    #keep the fields that we need
    official_sources = []
    seen_urls = set()

    #loop through results, return the title if it exists, but if it doesnt, return empty string
    for result in results:
        url = result.get("url", "")

        #need to verify the return url now
        if not is_official_url(url, allowed_domains):
            continue

        #avoid duplicate URLS
        if url in seen_urls:
            continue

        seen_urls.add(url)

        source = {
            "title": result.get("title", ""),
            "url": url,
            "snippet": result.get("content", ""),
            "full_content": None,
            "extraction_status": "not_attempted",
            "extraction_error": None,
        }
        official_sources.append(source)

    return official_sources[:MAX_PAGES]

def extract_pages(sources, client):
    """Retrieve fuller webpage text for approved URLS."""

    if not sources: 
        return sources

    urls = [source["url"] for source in sources]

    print(f"Extracting content from {len(urls)} official pages...")

    try:
        response = client.extract(
            urls=urls,
            extract_depth="basic",
            format="markdown",
            include_images=False,
        )
    except Exception as error:
        #keep any search snippets if the extraction does fail
        for source in sources:
            source["extraction_status"] = "failed"
            source["extraction_error"] = str(error)

        print(f"Extraction request failed!!! : {error}")
        return sources

    #match the successful extractions by url
    extracted_content = {
        result["url"]: result.get("raw_content", "")
        for result in response.get("results", [])
    }

    #matching failed extractions by url
    failed_urls = {
        result["url"]: result.get("error", "Unknown error")
        for result in response.get("failed_results", [])
    }

    for source in sources:
        url = source["url"]

        if extracted_content.get(url):
            source["full_content"] = extracted_content[url]
            source["extraction_status"] = "success"

        else:
            source["extraction_status"] = "failed"
            source["extraction_error"] = failed_urls.get(
                url,
                "No extracted content returned",
            )
    return sources

def save_results(data):
    """Save our collected evidence into a JSON file."""

    #create the directory if it doesnt exist yet
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    #create a filename using the brand and model
    brand = data["brand"].lower().replace(" ", "_")
    model = data["model"].lower().replace(" ", "_")

    filename = f"{brand}_{model}_sources.json"
    filepath = DATA_DIR / filename

    #write the data into a readable JSON format

    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(data, file, indent =4, ensure_ascii=False)

    print(f"Results saved to: {filepath}")
    return filepath

def main():
    """Run a complete search for one wearable device."""

    #stop early if the API key is missing (shouldnt be, but if you need to update it, go to .env and add it there if you are using this)
    if not API_KEY:
        raise ValueError("Mising TAVILY_API_KEY. check the .env file!!!")
    
    #now that we have the Tavily API key, init the API client
    client = TavilyClient(api_key=API_KEY)

    #get validated devices from targets.py
    devices = get_targets()

    #testing w/ Garmin Forerunner 265 for test 1 here (can change these if you want to test for other brands and models)
    device = next(
        (
            item for item in devices
            if item["brand"] == "Garmin"
            and item["model"] == "Forerunner 265"
        ),
        None,
    )

    if device is None:
        raise ValueError("Test device not found in targets.py")

    #search for any official sources
    sources = search_device(device, client)

    print(f"Official sources found: {len(sources)}")

    #extract the webpage content
    sources = extract_pages(sources, client)

    #build a more structured output
    data = {
        "brand": device["brand"],
        "model": device["model"],
        "category": device["category"],
        "query": create_search_query(device),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
    }

    #save search results and extraction statuses

    if sources:
        save_results(data)
    else:
        print("No approved sources found. No file was saved.")

    #report extraction results
    successful = sum(
        1 for source in sources
        if source["extraction_status"] == "success"
    )

    print(f"Successful extractions: {successful}/{len(sources)}")


if __name__ == "__main__":
    main()



