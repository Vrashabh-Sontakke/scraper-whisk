import os
from urllib.parse import quote_plus
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from apify import Actor

load_dotenv()

cred = credentials.Certificate('gcreds.json')
app = firebase_admin.initialize_app(cred)
db = firestore.client()


def get_max_count():
    return int(os.getenv("MAX_COUNT", 10))  # Default value is 10 if MAX_COUNT is not set in .env

def get_start_url():
    return str(os.getenv("START_URL", "https://www.car-part.com/cgi-bin/search.cgi"))


# Constructs the body for the POST request based on input parameters.
# =========================================================================================================================================================================================================================================================================================================================

def get_body(actor_input, page_num=None):
    vin = actor_input.get('vin')
    part_type = actor_input.get('part_type')
    zip_code = actor_input.get('zip_code')
    page_num = page_num or 1
    body = f'userDate=Select+Year&userVIN={vin}&userModel=Select+Make%2FModel&userPart={quote_plus(part_type)}&userLocation=All+States&userPreference=zip&userZip={zip_code}&userPage={page_num}&userInterchange=None&userDate2=Ending+Year&userSearch=int&Search+Car+Part+Inventory.x=26&Search+Car+Part+Inventory.y=19'
    return body


def get_form(soup, actor_input):
    form = soup.find('form', {'id': 'MainForm'})
    if not form:
        Actor.log.info(f"No MainForm found, trying form")
        form = soup.find('form', {'name': 'form'})
    if not form:
        body = get_body(actor_input)
        Actor.log.info(f"No form found either, returning form as body")
        Actor.log.info(f"body: {body}")
        return body, False
    
    if form:
        Actor.log.info(f"Yes form found")
        #action_url = 'https://www.car-part.com' + form['action']
        form_data = {}
        for input_tag in form.find_all('input'):
            name = input_tag.get('name')
            value = input_tag.get('value', '')
            if name:
                form_data[name] = value
        
        side = actor_input.get('side')

        radio_inputs = soup.find_all('input', {'type': 'radio'})
        
        if radio_inputs:
            
            Actor.log.info(f"Found radio inputs:")
            
            for radio_input in radio_inputs:
                
                id = radio_input.get('id')
                value = radio_input.get('value')
                label = radio_input.next_sibling.text.strip()

                Actor.log.info(f"radio_input: id:{id}, label: {label}, value: {value}")
                
                if side and radio_input.get('name') == 'dummyVar':

                    if side == 'Left' and 'LH' in label:
                        Actor.log.info(f"going with side: {side}, label: {label}")
                        Actor.log.info(f"value: {value}")
                        form_data['userInterchange'] = value
                        form_data['dummyVar'] = value
                        Actor.log.info(f"updating form_data")

                    if side == 'Right' and 'RH' in label:
                        Actor.log.info(f"going with side: {side}, label: {label}")
                        Actor.log.info(f"value: {value}")
                        form_data['userInterchange'] = value
                        form_data['dummyVar'] = value
                        Actor.log.info(f"updating form_data")


                if 'Non-Interchange' in label and 'only' not in label:
                    Actor.log.info(f"going with label: {label}")
                    Actor.log.info(f"value: {value}")
                    form_data['dbModel'] = value
                    Actor.log.info(f"updating form_data")
                
                elif 'Non-Interchange' in label and 'only' in label:
                    Actor.log.info(f"going with label: {label}")
                    Actor.log.info(f"value: {value}")
                    form_data['dbModel'] = value
                    Actor.log.info(f"updating form_data")
        else:
            Actor.log.info(f"No radio type inputs found")

        select_elements = soup.find_all('select')
        if select_elements:
            Actor.log.info(f"Found select type inputs:")
            for select_element in select_elements:
                name = select_element.get('name')
                selected_option = select_element.find('option', {'selected': True})
                if selected_option:
                    selected_value = selected_option.get('value')
                    form_data[name] = selected_value
                    Actor.log.info(f"{name}: {selected_value}")
                    Actor.log.info(f"updating form_data")
        else:
            Actor.log.info(f"No (date) select type inputs found")

        Actor.log.info(f"returning form_data: {form_data}")
        return form_data, True
    
    else:
        Actor.log.info(f"returning None, None")
        return None, None


def parse_year_part_model(td_html):
    text_parts = td_html.stripped_strings
    text_list = list(text_parts)

    if len(text_list) != 3:
        return {
            'year': None,
            'part': None,
            'model': None
        }
    year, part, model = text_list
    return {
        'year': year,
        'part': part,
        'model': model
    }


def parse_table_row(row):
    td_tags = row.find_all('td')

    if len(td_tags) != 8:
        return {
            "Year, Part, Model": None,
            "Description": None,
            "Miles": None,
            "Part Grade": None,
            "Stock Number": None,
            "US Price": None,
            "Dealer Info": None,
            "Dist Mile": None,
            "Image Link": None
        }

    # Extract the data according to the table headers
    year_part_model = parse_year_part_model(td_tags[0])
    description = td_tags[1].text.strip()
    miles = td_tags[2].text.strip()
    part_grade = td_tags[3].text.strip()
    stock_number = td_tags[4].text.strip()
    us_price = td_tags[5].text.strip()
    dealer_info = td_tags[6].text.strip()
    dist_mile = td_tags[7].text.strip()

    img_link = td_tags[1].find('img')['src'] if td_tags[1].find('img') else None

    return {
        **year_part_model,
        "Description": description,
        "Miles": miles,
        "Part Grade": part_grade,
        "Stock Number": stock_number,
        "US Price": us_price,
        "Dealer Info": dealer_info,
        "Dist Mile": dist_mile,
        "Image Link": img_link
    }


def parse_table(tables):
    tables = [t for t in tables if 'YearPartModel' in t.text]
    if not tables:
        return []
    table = tables[0]
    data = []
    rows = table.findAll('tr')
    for row in rows[1:]:
        item = parse_table_row(row)
        data.append(item)
    return data


async def process_response(response):
    soup = BeautifulSoup(response.content, 'html.parser')
    tables = soup.findAll('table')
    data = parse_table(tables)
    # get_count(data)
    return data


def find_pages(response):
    total_pages = 0
    soup = BeautifulSoup(response.content, 'html.parser')
    urls = soup.findAll('a')
    urls = [u.get('href') for u in urls if u.get('href')]
    page_urls = [f'https://www.car-part.com{u}' for u in urls if 'search.cgi?' and 'userPreference=zip' and 'userPage' in u]
    if page_urls:
        Actor.log.info(f"found other pages")
        for url in page_urls:
            params = url.split('&')
            for param in params:
                if param.startswith('userPage='):
                    page_number = int(param.split('=')[1])
                    total_pages = max(total_pages, page_number)
        return total_pages, page_urls
    Actor.log.info(f"no other pages found")
    return total_pages, None


def item_is_valid(item):
    price = item['US Price'].replace('$', '').replace(',', '').replace('actual', '').replace('Call','')
    if price.isdigit():
        item['US Price'] = price
        return item
    return {}


def save_to_firestore(item, db_name='carparts'):
    doc_ref = db.collection(db_name).document()
    doc_ref.set(item)