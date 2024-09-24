import asyncio
from scraper import process_scraper_task

# OpenWhisk handler function
def main(params):
    vin = params.get('vin')
    part_type = params.get('part_type')
    zip_code = params.get('zip_code')
    side = params.get('side')

    task_input = {
        "vin": vin,
        "part_type": part_type,
        "zip_code": zip_code,
        "side": side
    }

    # Start the scraping process
    asyncio.run(process_scraper_task(task_input))

    return {"status": "task started"}
