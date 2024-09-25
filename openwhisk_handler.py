import asyncio
from scraper import scraper
from config import set_config

# OpenWhisk handler function
def main(params):
    vin = params.get('vin', "4T1BF22K5WU057633")
    part_type = params.get('part_type', "Tail Light")
    zip_code = params.get('zip_code', "77009")
    side = params.get('side')

    # Set configuration
    set_config(vin, part_type, zip_code, side)
    
    # Start the scraping process
    asyncio.run(scraper())

    return {"status": "task started"}
