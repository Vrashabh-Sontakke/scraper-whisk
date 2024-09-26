import sys
import asyncio
import logging
from httpx import AsyncClient
from bs4 import BeautifulSoup
from utils import save_to_mongodb, process_response, item_is_valid, get_body, get_form, find_pages, get_max_count, get_start_url, get_proxy_url

# Logging Configuration (temporary)
logging.basicConfig(level=logging.INFO)  # Set level to INFO or DEBUG as needed
logger = logging.getLogger(__name__)

count = 0
max_count = get_max_count()
url = get_start_url()
lock = asyncio.Lock()  # Lock to synchronize access to count variable

async def fetch_with_retry(client, url, data, page_num=None):
    max_retries = 4
    retry_delay = 2  # Initial delay in seconds
    for attempt in range(max_retries):
        try:
            response = await client.post(url, data=data, timeout=90)
            if response.status_code == 200:
                return response
            else:
                logger.error(f"Request failed with status code: {response.status_code}")
                raise Exception(f"Request failed with status code: {response.status_code}")
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Request failed: {e}. Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                if page_num is not None:
                    logger.error(f"Failed to fetch data from Page: {page_num}, Status code: {response.status_code}")
                else:
                    logger.error(f"Failed to fetch data from {url}: Status code: {response.status_code}")
                logger.error(f"All retry attempts failed: {e}")
                raise Exception(f"All retry attempts failed: {e}")


async def scraper(car_input):
    global count
    # proxy_url = get_proxy_url()
    # if not proxy_url:
    #     logger.error("NGINX Proxy URL not set. Please configure NGINX_PROXY_URL in your environment.")
    #     return
    # else: 
    #     logger.info(f"Proxy URL: {proxy_url}")

    # Structure of input is defined in input_schema.json
    body = get_body(car_input)
    logger.info(f"got body: {body}")
    logger.info(f"URL: {url}") # url = "https://www.car-part.com/cgi-bin/search.cgi"

    #async with AsyncClient(proxies=proxy_url) as client:
    async with AsyncClient() as client:
        try:
            logger.info(f"fetching url with body")
            r = await fetch_with_retry(client, url, body)
                
            logger.info(f"extracting soup")
            soup = BeautifulSoup(r.text, 'html.parser')
            form, form_exists = get_form(car_input, soup)
            
            # Get total number of pages
            logger.info(f"looking for other pages, fetching url with form")
            r = await fetch_with_retry(client, url, form)
            total_pages, page_urls = find_pages(r)

            logger.info(f"page_urls: {page_urls}")

            if r.status_code == 200 and total_pages != 0 :

                logger.info(f"Total pages found: {total_pages}")
            
                if form_exists == True:
                    # Get initial form data
                    form_data = dict(form)

                # Loop through each page
                for page_num in range(1, total_pages + 1):
                    
                    # Process response and scrape data

                    if form_exists == True:
                        form_data['userPage'] = str(page_num) # Update the 'userPage' parameter with the current page number
                        logger.info(f"fetching url with form_data and page_num: {page_num}")
                        r = await fetch_with_retry(client, url, form_data, page_num)
                    
                    if form_exists == False:
                        #body = get_body(actor_input, page_num)
                        logger.info(f"fetching url with form as body and page_num: {page_num}")
                        r = await fetch_with_retry(client, url, form, page_num)

                    logger.info(f"processing response and extracting data from soup")
                    logger.info(f"r:{r}")
                    data = await process_response(r)

                    if data and len(data) > 0:

                        async with lock:

                            for item in data:

                                if item_is_valid(item):
                                    save_to_mongodb(item)
                                    print(item)
                                    logger.info(f'Page {page_num} - Data: {item}')
                                    count += 1

                                if count >= max_count:
                                    logger.info(f'Found {max_count} valid records, exiting the scraper')
                                    sys.exit(0)
                                    break
                            if count == 0:
                                logger.info(f"no valid item in data on page: {page_num}")
                                logger.info(f"Logging Data for Page: {page_num} : {data}")
                    else:
                        logger.info(f"no data found on page: {page_num}")


            if r.status_code == 200 and total_pages == 0 :

                logger.info(f"no other pages found")

                # Process response and scrape data
                if form_exists == True:
                    logger.info(f"fetching url with form")
                    r = await fetch_with_retry(client, url, form)
                
                if form_exists == False:
                    logger.info(f"fetching url with form as body")
                    r = await fetch_with_retry(client, url, form)

                logger.info(f"processing response and extracting data from soup")
                data = await process_response(r)

                if data and len(data) > 0:

                    async with lock:

                        for item in data:

                            if item_is_valid(item):
                                save_to_mongodb(item)
                                print(item)
                                logger.info(f'Data: {item}')
                                count += 1
                            if count >= max_count:
                                logger.info(f'Found {max_count} valid records, exiting the scraper')
                                sys.exit(0)
                                break
                        if count == 0:
                            logger.info(f"no valid item in data on page")
                            logger.info(f"Logging Data: {data}")
                else:
                    logger.info(f"no data found on page")

        except Exception as e:
            logger.error(f'Failed to process request: {e} \n')