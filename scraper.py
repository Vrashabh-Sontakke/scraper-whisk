import os
import asyncio
from httpx import AsyncClient
from bs4 import BeautifulSoup
from utils import save_to_firestore, process_response, item_is_valid, get_body, get_form, find_pages, get_max_count, get_start_url

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
                raise Exception(f"Request failed with status code: {response.status_code}")
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Request failed: {e}. Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                if page_num is not None:
                    print(f"Failed to fetch data from Page: {page_num}, Status code: {response.status_code}")
                else:
                    print(f"Failed to fetch data from {url}: Status code: {response.status_code}")
                raise Exception(f"All retry attempts failed: {e}")


async def main():

    global count

    async with Actor:

        proxy_configuration = await Actor.create_proxy_configuration(
            groups=["RESIDENTIAL"],
            country_code="US",
        )

        proxy_url = await proxy_configuration.new_url()
        Actor.log.info(f"Proxy URL: {proxy_url}")

        # Structure of input is defined in input_schema.json
        actor_input = await Actor.get_input() or {}
        Actor.log.info(f"Actor Input: {actor_input}")
        body = get_body(actor_input)
        Actor.log.info(f"got Body: {body}")

        #url = "https://www.car-part.com/cgi-bin/search.cgi"
        Actor.log.info(f"URL: {url}")

        async with AsyncClient(proxies=proxy_url) as client:

            try:
                Actor.log.info(f"fetching url with body")
                r = await fetch_with_retry(client, url, body)
                    
                Actor.log.info(f"extracting soup")
                soup = BeautifulSoup(r.text, 'html.parser')
                form, form_exists = get_form(soup, actor_input)
                
                # Get total number of pages
                Actor.log.info(f"looking for other pages, fetching url with form")
                r = await fetch_with_retry(client, url, form)
                total_pages, page_urls = find_pages(r)

                if r.status_code == 200 and total_pages != 0 :

                    Actor.log.info(f"Total pages found: {total_pages}")
                
                    if form_exists == True:
                        # Get initial form data
                        form_data = dict(form)

                    # Loop through each page
                    for page_num in range(1, total_pages + 1):
                        
                        # Process response and scrape data

                        if form_exists == True:
                            form_data['userPage'] = str(page_num) # Update the 'userPage' parameter with the current page number
                            Actor.log.info(f"fetching url with form_data and page_num: {page_num}")
                            r = await fetch_with_retry(client, url, form_data, page_num)
                        
                        if form_exists == False:
                            #body = get_body(actor_input, page_num)
                            Actor.log.info(f"fetching url with form as body and page_num: {page_num}")
                            r = await fetch_with_retry(client, url, form, page_num)

                        Actor.log.info(f"processing response and extracting data from soup")
                        data = await process_response(r)

                        if data and len(data) > 0:

                            async with lock:

                                for item in data:

                                    if item_is_valid(item):
                                        save_to_firestore(item)
                                        await Actor.push_data(item)
                                        Actor.log.info(f'Page {page_num} - Data: {item}')
                                        count += 1

                                    if count >= max_count:
                                        Actor.log.info(f'Found {max_count} valid records, exiting the scraper')
                                        await Actor.exit()
                                        break
                                if count == 0:
                                    Actor.log.info(f"no valid item in data on page: {page_num}")
                                    Actor.log.info(f"Logging Data for Page: {page_num} : {data}")
                        else:
                            Actor.log.info(f"no data found on page: {page_num}")


                if r.status_code == 200 and total_pages == 0 :

                    Actor.log.info(f"no other pages found")

                    # Process response and scrape data
                    if form_exists == True:
                        Actor.log.info(f"fetching url with form")
                        r = await fetch_with_retry(client, url, form)
                    
                    if form_exists == False:
                        Actor.log.info(f"fetching url with form as body")
                        r = await fetch_with_retry(client, url, form)

                    Actor.log.info(f"processing response and extracting data from soup")
                    data = await process_response(r)

                    if data and len(data) > 0:

                        async with lock:

                            for item in data:

                                if item_is_valid(item):
                                    save_to_firestore(item)
                                    await Actor.push_data(item)
                                    Actor.log.info(f'Data: {item}')
                                    count += 1
                                if count >= max_count:
                                    Actor.log.info(f'Found {max_count} valid records, exiting the scraper')
                                    await Actor.exit()
                                    break
                            if count == 0:
                                Actor.log.info(f"no valid item in data on page")
                                Actor.log.info(f"Logging Data: {data}")
                    else:
                        Actor.log.info(f"no data found on page")

            except Exception as e:
                Actor.log.error(f'Failed to process request: {e} \n')