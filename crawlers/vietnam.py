import requests, time, random
from bs4 import BeautifulSoup


from database.connection import Session, engine
from database.models import get_brand_model, Base
from database.save import save_to_db
from database.partition import create_partition_table
from monitor.logger import log_change

request_log_vn = []
def parse_vietnam_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    items = []

    for row in soup.select("table.trademark-list tbody tr"):
        tds = row.find_all("td")
        items.append({
            "id": tds[0].text.strip(),
            "name": tds[1].text.strip(),
            "product_group": tds[2].text.strip(),
            "status": tds[3].text.strip(),
            "registration_date": tds[4].text.strip(),
            "image_url": row.select_one("img")["src"]
        })
    return items
def throttle_vietnam():
    now = time.time()
    request_log_vn.append(now)
    request_log_vn[:] = [t for t in request_log_vn if now - t <= 60]
    if len(request_log_vn) > 1000:
        time.sleep(10)
    time.sleep(random.uniform(0.05, 0.1))

def crawl_vietnam(month: str):
    page = 1
    session = Session()
    table = month.replace('-', '_')
    create_partition_table(table, engine)
    Brand = get_brand_model(f"brand_{table}")
    Base.metadata.create_all(engine)

    while True:
        url = f"https://vietnamtrademark.gov.vn/example?page={page}&month={month}"
        try:
            resp = requests.get(url)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[VietnamTrademark] Error fetching page {page}:", e)
            break

        throttle_vietnam()
        items = parse_vietnam_html(resp.text)
        if not items:
            break
        save_to_db(session, Brand, items, "VietnamTrademark")
        page += 1

def fetch_status_vietnam(brand_id):
    try:
        html = requests.get(f"https://vietnamtrademark.gov.vn/detail/{brand_id}").text
        parsed = parse_vietnam_html(html)
        return parsed[0]["status"] if parsed else None
    except Exception as e:
        print(f"[VietnamTrademark] Error fetching detail for {brand_id}:", e)
        return None