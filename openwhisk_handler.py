import asyncio
from scraper import scraper

# OpenWhisk handler function
def main(params):
    vin = params.get('vin')
    part_type = params.get('part_type')
    zip_code = params.get('zip_code')
    side = params.get('side')

    car_input = {
        "vin": vin,
        "part_type": part_type,
        "zip_code": zip_code,
        "side": side
    }
    
    # Start the scraping process
    asyncio.run(scraper(car_input))

    return {"status": "task started"}

# Run the main function if this script is executed directly
if __name__ == "__main__":
    params = {
        "vin": "4T1BF22K5WU057633",
        "part_type": "Fender",
        "zip_code": "77009",
        "side": "Left"
    }
    response = main(params)
    print(response)  # Print the response for debugging
