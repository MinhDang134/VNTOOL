import time, random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from crawlers.parser import parse_wipo_html
from database.connection import Session, engine
from database.models import get_brand_model, Base
from database.save import save_to_db
from database.partition import create_partition_table
from database.trademark import upsert_trademark_master

request_log = []

def throttle():
    now = time.time()
    request_log.append(now)
    request_log[:] = [t for t in request_log if now - t <= 60]
    if len(request_log) > 1000:
        time.sleep(10)
    time.sleep(random.uniform(0.05, 0.1))

def crawl_wipo(month: str):
    print("[WIPO] crawl_wipo(month) currently not implemented for real URL.")

def save_to_db(session, BrandModel, items, source):
    saved_count = 0
    for item in items:
        try: # THÊM TRY-EXCEPT Ở ĐÂY
            brand = BrandModel(
                id=item["id"],
                name=item["name"],
                product_group=item["product_group"],
                status=item["status"],
                registration_date=item["registration_date"],
                image_url=item["image_url"],
                source=source
            )
            session.merge(brand)
            # Giả sử upsert_trademark_master cũng có thể gây lỗi và bạn muốn bắt nó
            upsert_trademark_master(session.bind, item, source)
            saved_count += 1
        except Exception as e:
            print(f"❌ Error processing item (ID: {item.get('id', 'N/A')}, Name: {item.get('name', 'N/A')}) for source {source}: {e}")
            # Tùy chọn: session.rollback() nếu bạn muốn hủy các thay đổi cho item lỗi này
            # và đảm bảo session sẵn sàng cho item tiếp theo.
            # Tuy nhiên, merge có thể không cần rollback ngay lập tức nếu lỗi xảy ra sau đó.
            # Nếu lỗi xảy ra trong upsert_trademark_master và nó đã thực hiện một phần commit,
            # việc rollback ở đây có thể phức tạp. Cần xem xét kỹ logic của upsert_trademark_master.

    if saved_count > 0: # Chỉ commit nếu có gì đó được thêm/thay đổi thành công
        try:
            session.commit()
            print(f"✅ Committed {saved_count} items to DB for source {source}.")
        except Exception as e:
            print(f"❌ Error committing batch to DB for source {source}: {e}")
            session.rollback() # Rollback nếu commit thất bại
    else:
        print(f"ℹ️ No new items to commit for source {source}.")

def crawl_wipo_by_name(name: str):
    session = Session()
    table = "brand_manual"
    create_partition_table(table, engine)
    Brand = get_brand_model(table)
    Base.metadata.create_all(engine)

    print(f"[WIPO] Searching for brand: {name} via user simulation")
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(options=options)
        driver.get("https://branddb.wipo.int/en/")

        input("[WIPO] ⏳ Hãy giải Captcha VÀ tìm kiếm RONALDO thủ công trên trình duyệt. Sau đó nhấn Enter...")

        WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.result-viewed"))
        )

        html = driver.page_source
        with open("debug_wipo_result.html", "w", encoding="utf-8") as f:
            f.write(html)
        driver.quit()
    except Exception as e:
        print(f"[WIPO] Error during Selenium interaction: {e}")
        return

    throttle()
    items = parse_wipo_html(html)
    print(f"🟢 Parsed {len(items)} items")
    for item in items:
        print(f"📦 Item: {item}")

    if not items:
        print("[WIPO] No results parsed.")
        return

    try:
        save_to_db(session, Brand, items, "WIPO")
        print(f"✅ Saved {len(items)} items for name: {name}")
    except Exception as e:
        print(f"❌ Error saving to DB: {e}")
