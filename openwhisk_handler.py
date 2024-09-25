import asyncio
from scraper import scraper
from config import set_config

# OpenWhisk handler function
def main(params):
    vin = params.get('vin')
    part_type = params.get('part_type')
    zip_code = params.get('zip_code')
    side = params.get('side')

    # Set configuration
    set_config(vin, part_type, zip_code, side)
    
    # Start the scraping process
    asyncio.run(scraper())

    return {"status": "task started"}

# Run the main function if this script is executed directly
if __name__ == "__main__":
    params = {
        "vin": "4T1BF22K5WU057633",
        "part_type": "Tail Light",
        "zip_code": "77009",
        "side": ""
    }
    response = main(params)
    print(response)  # Print the response for debugging
