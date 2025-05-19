"""
Module chứa các hàm để crawl dữ liệu từ trang web WIPO
"""

import time # dùng chỉ thời gian
import random # random một cái gì đó
import logging # hiển thị thông báo
import json # tương tác với kiểu dữ liệu json dumps , load
import os # kiểm tra đường dẫn của một cách gì đo s, biến môi trường , tạo thư mục
from datetime import datetime, timedelta # date time chỉ thời gian , timedelta có thể dùng thời gian để tính tóa
from functools import wraps # chức năng decorator chức năng bọc thêm logic cho một hàm
from typing import Optional, List, Dict, Any # khai báo nhiều kiểu dữ liệu , Opitional có thể cho phép null
from selenium import webdriver # có thể dùng với nhiều mục đích
from selenium.webdriver.common.by import By # tìm kiểm một cái dữ liệu thuộc tính nào đó cụ thể như id , trang thái ...
from selenium.webdriver.support.ui import WebDriverWait # chờ một cái dữ liệu từ đâu đó trả về rồi mới chạy tiêps
from selenium.webdriver.support import expected_conditions as EC #phần sử lý dữ liệu trước khi webdrive chạy và chờ
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
# timeout... nó sẽ giup webdrive này chạy trong một thời gian nhất định
# NosuchElementException ... là trả về khi không có dữ liệu nào
# webdriveException chắc là lỗi trong quá trình chạy webdrive
logger_wipo_fetch = logging.getLogger(__name__ + ".fetch_status") # # tạo một logger log để biết những cái nó làm trong khi chạy dự án
# Đảm bảo đường dẫn import là chính xác dựa trên cấu trúc thư mục của bạn
from crawlers.parser import parse_wipo_html # chuyển dữ liệu sang bên kia và xử lý lấy dữ liệu rồi lưu vào một list
from database.connection import Session, engine  # engine và session để tương tác và kết nối với cơ sở dữ liệu
from database.models import get_brand_model, Base  # Giả định các hàm này tồn tại
# from database.save import save_to_db # BỎ IMPORT NÀY, sử dụng hàm _save_wipo_items_to_db
from bs4 import BeautifulSoup
from database.partition import create_partition_table  # Giả định hàm này tồn tại
import urllib.parse # For URL encoding

# request_log nên được quản lý cẩn thận hơn nếu có nhiều instance crawler
request_log_wipo = []  # danh sách lưu lại những thứ khi gửi request

CACHE_DIR = "cache/wipo" # thư mục khi lấy dữ liệu về sẽ được lưu vào trong cache
CACHE_EXPIRY_DAYS = 7 #cache được lưu trong 7 ngày

def ensure_cache_dir():
    # hàm này nó sẽ kiểm tra cache/wipo đã được lưu hay chưa nêu chưa được lưu thì nó sẽ tự tạo ra cache đó
    """Ensure cache directory exists."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

# đây là phần sẽ lại cái mình search theo tên và bỏ khoảng trắng ra rồi làm tên file json luôn
def get_cache_path(brand_name: str) -> str:
    """Get cache file path for a brand name."""
    safe_name = "".join(c for c in brand_name if c.isalnum() or c in (' ', '-', '_')).strip()
    return os.path.join(CACHE_DIR, f"{safe_name}.json")

# cái này nó sẽ thiết lập ngày cũng như tính ngày của một cache
def is_cache_valid(cache_path: str) -> bool: # trả về true false
    """Check if cache file exists and is not expired."""
    if not os.path.exists(cache_path): # nếu chưa có trả về
        return False
    
    file_time = datetime.fromtimestamp(os.path.getmtime(cache_path)) # có rồi thì lấy thời gian hiên tại trừ trừ đi thời gian tồn tại của chache
    # nếu mà dữ liệu lớn hơn 7 đã đặt ra thì sẽ xóa cache đi
    return datetime.now() - file_time < timedelta(days=CACHE_EXPIRY_DAYS)

# lưu vào cache gồm tên , data list[dict,str,Angu
# gọi đến ensurecache_di xem đã tồn tại chưa
# mở cái cachce đó ra và gửi data với thời gian lên đó
def save_to_cache(brand_name: str, data: List[Dict[str, Any]]): # sau khi mà chuyển tên và data sau duyệ vào thì
    # đến các bước sau
    ensure_cache_dir() # chưa được lưu thì nó sẽ tự tạo thêm cache đó
    cache_path = get_cache_path(brand_name)  # tạo cache name khi mà điền thông tin gì thì nó sẽ tự lấy thông tin đó bỏ khoảng trắng rồi làm thành tên
    with open(cache_path, 'w', encoding='utf-8') as f: # dùng with là khi dùng hết tự đóng, w là model éo gì ấy quên rồi
        json.dump({ # đây là bước đây lên cache đây
            'timestamp': datetime.now().isoformat(), # đẩy thời gian và toàn bộ data
            'data': data # chuyền data
        }, f, ensure_ascii=False, indent=2) # cái này ép biết

# cái này nó sẽ lấy dữ liệu từ cache về rồi lưu vào trong một file json nào đó
def load_from_cache(brand_name: str) -> Optional[List[Dict[str, Any]]]:
    # truyền tên vào thì nó bắt buocuojc là in out put ra là một list dict bên trong
    """Load data from cache file if valid."""
    cache_path = get_cache_path(brand_name)  # truyền tên vào để sử dung làm tên của cache sau khi loại bỏ dấu "," các thứu
    if not is_cache_valid(cache_path):  # nếu mà chưa có tên của cái cache đó thì mình sẽ return none
        return None
    
    try: # nếu mà có file cache đó thì nó sẽ open cái đó theo model là r , r là gì quên mia rồi
        with open(cache_path, 'r', encoding='utf-8') as f: # mở lên gán tên là f
            cache_data = json.load(f) # tạo biên cache_data , lưu dữ liệu chuyển từ kiểu json sang kiểu đối tượng
            return cache_data.get('data') # cache_data lấy dữ liệu
    except Exception as e: # nếu mà lỗi thì sẽ vào đây  trường hợp nêu không lỗi thì sẽ có data nhưng alf đối tượng
        logging.error(f"Error loading cache for {brand_name}: {e}")
        return None

def throttle_wipo(min_delay=0.1, max_delay=0.2, max_req_per_min=500, sleep_on_exceed=15):
    """Throttles requests to avoid overwhelming the WIPO server."""
    global request_log_wipo
    now = time.time()
    request_log_wipo = [t for t in request_log_wipo if now - t <= 60]  # Giữ lại các request trong 60s qua

    if len(request_log_wipo) >= max_req_per_min:
        logging.warning(
            f"WIPO Crawler: Request limit ({max_req_per_min}/min) reached. Sleeping for {sleep_on_exceed} seconds.")
        time.sleep(sleep_on_exceed)
        request_log_wipo = [t for t in request_log_wipo if time.time() - t <= 60]  # Cập nhật lại sau khi sleep

    request_log_wipo.append(now)  # Log request hiện tại
    time.sleep(random.uniform(min_delay, max_delay))  # Chờ ngẫu nhiên


def _save_wipo_items_to_db(db_session, BrandModel, items_to_save, source_name="WIPO_Search"):
    saved_count = 0
    processed_count = 0
    skipped_count = 0
    error_count = 0

    if not items_to_save:
        logging.info(f"DB Save ({source_name}): No items to save.")
        return saved_count

    for item_detail in items_to_save:
        processed_count += 1
        item_id = item_detail.get("id")
        
        if not item_id:
            logging.error(f"DB Save ({source_name}): Item skipped due to missing ID: {item_detail.get('name', 'N/A')}")
            skipped_count += 1
            continue

        try:
            # Kiểm tra xem record đã tồn tại chưa
            existing_item = db_session.query(BrandModel).filter_by(id=item_id).first()
            
            if existing_item:
                logging.info(f"DB Save ({source_name}): Updating existing record for ID: {item_id}")
                # Cập nhật các trường từ dữ liệu mới
                for key, value in item_detail.items():
                    if hasattr(existing_item, key) and value is not None:
                        setattr(existing_item, key, value)
                # Cập nhật source và last_updated
                existing_item.source = source_name
                existing_item.last_updated = datetime.utcnow()
            else:
                logging.info(f"DB Save ({source_name}): Adding new record for ID: {item_id}")
                # Tạo instance mới với dữ liệu từ parser
                brand_instance_data = {
                    "id": item_id,
                    "name": item_detail.get("name"),
                    "product_group": item_detail.get("product_group"),
                    "status": item_detail.get("status"),
                    "country": item_detail.get("country"),  # Note: Capital C in Country
                    "source": source_name,
                    "owner": item_detail.get("owner"),
                    "number": item_detail.get("number"),  # Note: Capital N in Number
                    "ipr": item_detail.get("ipr"),
                    "image_url": item_detail.get("image_url"),
                    "created_at": datetime.utcnow(),
                    "last_updated": datetime.utcnow()
                }
                brand_instance = BrandModel(**brand_instance_data)
                db_session.add(brand_instance)

            # Commit sau mỗi item để tránh lỗi ảnh hưởng đến toàn bộ batch
            db_session.commit()
            saved_count += 1
            logging.info(f"DB Save ({source_name}): Successfully saved item {item_id}")

        except Exception as e:
            db_session.rollback()
            error_count += 1
            logging.error(f"DB Save ({source_name}): Error processing/merging item (ID: {item_id}, Name: {item_detail.get('name')}). Rolled back for this item. Error: {str(e)}")
            continue

    # Log tổng kết
    logging.info(f"DB Save ({source_name}): Processing complete. "
                f"Processed: {processed_count}, "
                f"Saved: {saved_count}, "
                f"Skipped: {skipped_count}, "
                f"Errors: {error_count}")

    return saved_count


def crawl_wipo(month: str):
    """Crawls WIPO for trademarks registered in a specific month."""
    logging.info(f"WIPO Crawler: Bắt đầu crawl dữ liệu cho tháng: {month}")
    
    try:
        # Validate month format (YYYY-MM)
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        logging.error(f"Định dạng tháng không hợp lệ: {month}. Định dạng yêu cầu: YYYY-MM")
        return None

    db_session = None
    driver = None
    html_content_for_parsing = None

    try:
        db_session = Session()
        table_name_for_brand = "trademark"
        create_partition_table(table_name_for_brand, engine)
        ConcreteBrandModel = get_brand_model(table_name_for_brand)

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36')

        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(60)

        wipo_search_url = "https://branddb.wipo.int/branddb/en/search/advanced"
        driver.get(wipo_search_url)
        logging.info(f"WIPO Crawler: Đã điều hướng đến {wipo_search_url}")

        user_interaction_prompt = (
            f"[YÊU CẦU TƯƠNG TÁC WIPO]\n"
            f"1. Trình duyệt Chrome đã mở tại trang WIPO Advanced Search.\n"
            f"2. Vui lòng GIẢI CAPTCHA (nếu có).\n"
            f"3. Trong phần 'Registration Date', chọn tháng: {month}\n"
            f"4. Nhấn nút 'Search' và đợi kết quả.\n"
            f"Sau đó, NHẤN ENTER ở đây để tiếp tục..."
        )
        input(user_interaction_prompt)

        if check_no_results(driver):
            logging.info(f"WIPO Crawler: Không tìm thấy kết quả cho tháng {month}")
            return None

        timeout = get_dynamic_timeout(driver)
        logging.info(f"WIPO Crawler: Sử dụng thời gian chờ động là {timeout} giây")

        results_css_selector = "li.result-viewed"
        WebDriverWait(driver, timeout).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, results_css_selector))
        )
        logging.info("WIPO Crawler: Đã tìm thấy các phần tử kết quả tìm kiếm.")

        html_content_for_parsing = driver.page_source

    except TimeoutException:
        logging.error(f"WIPO Crawler: Hết thời gian chờ kết quả tìm kiếm cho tháng {month}", exc_info=True)
        raise
    except WebDriverException as e:
        logging.error(f"WIPO Crawler: Lỗi WebDriverException: {e}", exc_info=True)
        raise
    except Exception as e:
        logging.error(f"WIPO Crawler: Lỗi không mong muốn: {e}", exc_info=True)
        raise
    finally:
        if driver:
            driver.quit()
        if db_session:
            db_session.close()

    if not html_content_for_parsing:
        logging.warning(f"WIPO Crawler: Không lấy được nội dung HTML cho tháng {month}")
        return None

    logging.info(f"WIPO Crawler: Đang phân tích HTML cho tháng {month}...")
    parsed_brand_items = parse_wipo_html(html_content_for_parsing)
    if not parsed_brand_items:
        logging.info(f"WIPO Crawler: Không có mục nào được phân tích từ HTML cho tháng {month}")
        return None

    valid_items = [item for item in parsed_brand_items if validate_brand_data(item)]
    if len(valid_items) != len(parsed_brand_items):
        logging.warning(f"WIPO Crawler: Đã lọc ra {len(parsed_brand_items) - len(valid_items)} mục không hợp lệ")

    cache_key = f"month_{month}"
    save_to_cache(cache_key, valid_items)
    if db_session and ConcreteBrandModel and valid_items:
        _save_wipo_items_to_db(db_session, ConcreteBrandModel, valid_items,
                               source_name=f"WIPO_Month_{month}")
    else:
        logging.error(f"WIPO Crawler: Không thể lưu các mục cho tháng {month}")

    return valid_items


def retry_on_failure(max_retries=3, delay=1, backoff=2):
    """Decorator for retrying functions on failure."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        logging.error(f"Function {func.__name__} failed after {max_retries} retries: {str(e)}")
                        raise
                    wait_time = delay * (backoff ** (retries - 1))
                    logging.warning(f"Function {func.__name__} failed, retrying in {wait_time} seconds... Error: {str(e)}")
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator

def validate_brand_data(brand_data: Dict[str, Any]) -> bool:
    # nó sẽ truyền một cái bảng data và với kiểu dict cái đầu chắc là id còn cái còn lại éo biết , trả về bool là boolean trong python
    """Validate brand data before saving to database."""
    required_fields = ['id', 'name'] # cái này chắc là mẫu khung
    # nó sẽ trả về
    # nó sẽ lấy toàn bộ
    # à nghĩa là cái field in brand_dâta là nó sẽ kiểm tra hai cái điều kiện là một field trong brandata có những trường gì ,
    # thữ 2 là brand_data[fieldư] duyệt xem có kiểu dữ liệu bắt buộc không là id và name trường hợp này thì có lên nó trả về true

    return all(field in brand_data and brand_data[field] for field in required_fields)

def check_no_results(driver) -> bool:
    """Check if the search returned no results."""
    try:
        # Sử dụng các selector hợp lệ cho Selenium
        selectors = [
            ".no-results-message",
            ".search-results-empty",
            ".no-results",
            ".alert-info",
            ".search-results"
        ]
        
        # Kiểm tra từng selector
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        # Kiểm tra text content bằng JavaScript
                        text = driver.execute_script("return arguments[0].textContent", element)
                        if "no results" in text.lower() or "không tìm thấy" in text.lower():
                            logging.info(f"Found no results message: {text}")
                            return True
            except NoSuchElementException:
                continue
            except Exception as e:
                logging.warning(f"Error checking selector {selector}: {e}")
                continue
                
        # Kiểm tra thêm bằng JavaScript
        try:
            no_results = driver.execute_script("""
                return Array.from(document.querySelectorAll('*')).some(el => {
                    const text = el.textContent.toLowerCase();
                    return text.includes('no results') || 
                           text.includes('không tìm thấy') ||
                           text.includes('no trademarks found');
                });
            """)
            if no_results:
                logging.info("Found no results message using JavaScript")
                return True
        except Exception as e:
            logging.warning(f"Error checking no results with JavaScript: {e}")
            
        return False
    except Exception as e:
        logging.warning(f"Error checking no results: {e}")
        return False

def get_dynamic_timeout(driver) -> int:
    """Calculate dynamic timeout based on page load time."""
    try:
        load_time = driver.execute_script("return performance.timing.loadEventEnd - performance.timing.navigationStart")
        return min(max(int(load_time / 1000) * 3, 60), 180)  # Tăng thời gian chờ lên 60-180 giây
    except:
        return 120  # Tăng timeout mặc định lên 120 giây

@retry_on_failure(max_retries=3)
def crawl_wipo_by_name(brand_name_to_search: str, force_refresh: bool = False):
    logging.info(f"WIPO Crawler: Bắt đầu crawl cho tên thương hiệu: '{brand_name_to_search}'")
    
    if not force_refresh:
        cached_data = load_from_cache(brand_name_to_search)
        if cached_data:
            logging.info(f"WIPO Crawler: Sử dụng dữ liệu đã cache cho '{brand_name_to_search}'")
            return cached_data

    db_session = None
    driver = None
    html_content_for_parsing = None

    try:
        db_session = Session()
        table_name_for_brand = "trademark"
        create_partition_table(table_name_for_brand, engine)
        ConcreteBrandModel = get_brand_model(table_name_for_brand)

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36')

        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(120)

        wipo_search_url = "https://branddb.wipo.int/branddb/en/"
        driver.get(wipo_search_url)
        logging.info(f"WIPO Crawler: Đã điều hướng đến {wipo_search_url}")

        user_interaction_prompt = (
            f"[YÊU CẦU TƯƠNG TÁC WIPO]\n"
            f"1. Trình duyệt Chrome đã mở tại trang WIPO.\n"
            f"2. Vui lòng GIẢI CAPTCHA (nếu có).\n"
            f"3. Thực hiện TÌM KIẾM thủ công cho tên thương hiệu: '{brand_name_to_search}'.\n"
            f"4. Đợi trang KẾT QUẢ TÌM KIẾM tải hoàn tất.\n"
            f"Sau đó, NHẤN ENTER ở đây để tiếp tục..."
        )
        input(user_interaction_prompt)

        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
        except TimeoutException:
            logging.warning("Hết thời gian tải trang, nhưng vẫn tiếp tục...")

        current_url = driver.current_url
        if not any(keyword in current_url.lower() for keyword in ['results', 'search', 'similarname']):
            logging.warning(f"WIPO Crawler: Không ở trang kết quả tìm kiếm. URL hiện tại: {current_url}")
            return None

        if check_no_results(driver):
            logging.info(f"WIPO Crawler: Không tìm thấy kết quả cho '{brand_name_to_search}'")
            return None

        results_selector = "ul.results.listView.ng-star-inserted > li.flex.result.wrap.ng-star-inserted"
        parsed_items_collector = []
        processed_item_ids = set()
        target_item_count = 30
        scroll_attempts_without_new_items = 0
        max_fruitless_scrolls = 3

        logging.info(f"Bắt đầu cuộn và phân tích tăng dần. Mục tiêu: {target_item_count} mục.")

        while len(parsed_items_collector) < target_item_count and scroll_attempts_without_new_items < max_fruitless_scrolls:
            initial_processed_count = len(processed_item_ids)
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, results_selector))
                )
                current_blocks_on_page = driver.find_elements(By.CSS_SELECTOR, results_selector)
                logging.info(f"Tìm thấy {len(current_blocks_on_page)} khối trên trang sau khi cuộn/chờ.")
            except TimeoutException:
                logging.info("Không tìm thấy khối kết quả nào trên trang hiện tại.")
                current_blocks_on_page = []

            new_items_found_this_scroll = False
            for block_idx, block_element in enumerate(current_blocks_on_page):
                try:
                    item_st13_id = block_element.get_attribute('data-st13')
                    if not item_st13_id:
                        logging.warning(f"Khối tại vị trí {block_idx} trên trang không có data-st13. Bỏ qua kiểm tra ID.")
                        continue
                except Exception:
                    logging.warning(f"Không thể lấy ID cho khối tại vị trí {block_idx} trên trang. Bỏ qua.")
                    continue

                if item_st13_id not in processed_item_ids:
                    new_items_found_this_scroll = True
                    logging.info(f"Tìm thấy mục mới: ID {item_st13_id}. Đang xử lý...")
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", block_element)
                        time.sleep(0.2)
                        WebDriverWait(block_element, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".brandName"))
                        )
                        logging.debug(f"Mục {item_st13_id} - .brandName có vẻ đã được tải để phân tích.")
                    except TimeoutException:
                        logging.warning(f"Mục {item_st13_id} - Hết thời gian chờ .brandName trước khi phân tích. Sẽ thử phân tích anyway.")
                    except Exception as e_detail_load:
                        logging.error(f"Mục {item_st13_id} - Lỗi khi đảm bảo tải chi tiết: {e_detail_load}")

                    single_item_data = {}
                    try:
                        name_el = block_element.find_element(By.CSS_SELECTOR, ".brandName")
                        single_item_data['name'] = name_el.text.strip()
                        try:

                            item_st13_id =block_element.get_attribute("data-st13")
                            if item_st13_id is not None:
                                single_item_data["id"] = item_st13_id
                        except NoSuchElementException:
                            logging.info("Lay id loi roi ")

                        owner_el = block_element.find_elements(By.CSS_SELECTOR, ".owner span.value")
                        if owner_el:
                            single_item_data['owner'] = owner_el[0].text.strip()
                        status_el = block_element.find_elements(By.CSS_SELECTOR, ".status span.value")
                        if status_el:
                            single_item_data['status'] = status_el[0].text.strip()
                        class_el = block_element.find_elements(By.CSS_SELECTOR, ".class span.value")
                        if class_el:
                            single_item_data['nice_class'] = class_el[0].text.strip()
                        country_el = block_element.find_elements(By.CSS_SELECTOR, ".designation span.value")
                        if country_el:
                            single_item_data['country'] = country_el[0].text.strip()
                        ipr_el = block_element.find_elements(By.CSS_SELECTOR, ".ipr span.value")
                        if ipr_el:
                            single_item_data['ipr_type'] = ipr_el[0].text.strip()
                        logo_el = block_element.find_elements(By.CSS_SELECTOR, "img.logo[src^='data:image']")
                        if logo_el:
                            single_item_data['logo'] = logo_el[0].get_attribute('src')
                        if single_item_data.get('name') and single_item_data.get('id'):
                            parsed_items_collector.append(single_item_data)
                            processed_item_ids.add(item_st13_id)
                            logging.info(f"Đã phân tích và thêm thành công mục ID (hiển thị): {single_item_data.get('id')}, st13: {item_st13_id}")
                        else:
                            logging.warning(f"Mục {item_st13_id} - Thiếu dữ liệu quan trọng sau khi thử phân tích. Không thêm vào.")
                    except Exception as e_parse:
                        logging.error(f"Lỗi phân tích mục {item_st13_id}: {e_parse}")

                    if len(parsed_items_collector) >= target_item_count:
                        break

            if len(parsed_items_collector) >= target_item_count:
                logging.info(f"Đã đạt đến số lượng mục mục tiêu là {target_item_count}.")
                break

            if not new_items_found_this_scroll:
                scroll_attempts_without_new_items += 1
                logging.info(f"Không tìm thấy mục mới trong lần cuộn này. Số lần cuộn không hiệu quả: {scroll_attempts_without_new_items}/{max_fruitless_scrolls}")
            else:
                scroll_attempts_without_new_items = 0

            if scroll_attempts_without_new_items >= max_fruitless_scrolls:
                logging.info("Đã đạt đến số lần cuộn không hiệu quả tối đa. Dừng cuộn.")
                break

            logging.info("Đang cuộn xuống để tải thêm mục...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        logging.info(f"Đã hoàn thành cuộn. Tổng số mục đã phân tích: {len(parsed_items_collector)}")
        all_results = parsed_items_collector

    except TimeoutException:
        logging.error(f"WIPO Crawler: Hết thời gian chờ kết quả tìm kiếm cho '{brand_name_to_search}'", exc_info=True)
        raise
    except WebDriverException as e:
        logging.error(f"WIPO Crawler: Lỗi WebDriverException: {e}", exc_info=True)
        raise
    except Exception as e:
        logging.error(f"WIPO Crawler: Lỗi không mong muốn: {e}", exc_info=True)
        raise
    finally:
        if driver:
            try:
                driver.quit()
                logging.info("WIPO Crawler: Đã đóng trình duyệt Chrome thành công.")
            except Exception as e:
                logging.error(f"WIPO Crawler: Lỗi khi đóng trình duyệt Chrome: {e}", exc_info=True)

    if not all_results:
        logging.warning(f"WIPO Crawler: Không lấy được nội dung HTML cho '{brand_name_to_search}'")
        if db_session:
            db_session.close()
        return None

    logging.info(f"WIPO Crawler: Đang phân tích HTML cho '{brand_name_to_search}'...")
    valid_items = [item for item in all_results if validate_brand_data(item)]
    if len(valid_items) != len(all_results):
        logging.warning(f"WIPO Crawler: Đã lọc ra {len(all_results) - len(valid_items)} mục không hợp lệ")

    save_to_cache(brand_name_to_search, valid_items)

    if db_session and ConcreteBrandModel and valid_items:
        _save_wipo_items_to_db(db_session, ConcreteBrandModel, valid_items,
                               source_name=f"WIPO_Search_{brand_name_to_search}")
        logging.info(f"WIPO Crawler: Đã lưu thành công {len(valid_items)} mục vào cơ sở dữ liệu")
    else:
        logging.error(f"WIPO Crawler: Không thể lưu các mục cho '{brand_name_to_search}'")

    if db_session:
        db_session.close()

    return valid_items


def get_next_page_url(current_url: str, start_value: int) -> str:
    """
    Tạo URL cho trang tiếp theo bằng cách tăng giá trị start
    """
    try:
        # Tách URL thành các phần
        base_url = current_url.split('&start=')[0]
        # Tạo URL mới với start value mới
        return f"{base_url}&start={start_value}"
    except Exception as e:
        logging.error(f"Lỗi khi tạo URL trang tiếp theo: {e}")
        return None

@retry_on_failure(max_retries=3)
def crawl_wipo_by_date_range(start_date_str: str, end_date_str: str, force_refresh: bool = False, max_pages: int = 10):
    logging.info(f"WIPO Crawler: bắt đầu search từ : {start_date_str} to {end_date_str}")

    try:
        # Construct the URL
        base_url = "https://branddb.wipo.int/en/advancedsearch/results"
        as_structure_template = {
            "_id": "ea9e",
            "boolean": "AND",
            "bricks": [{
                "_id": "ea9f",
                "key": "appDate",
                "strategy": "Range",
                "value": [start_date_str, end_date_str]
            }]
        }

        params = {
            "sort": "score desc",
            "strategy": "concept",
            "rows": "30",
            "asStructure": json.dumps(as_structure_template, separators=(',', ':')),
            "_": int(time.time() * 1000),
            "fg": "_void_",
            "start": "0"  # Bắt đầu từ trang đầu tiên
        }

        query_string = urllib.parse.urlencode(params)
        current_url = f"{base_url}?{query_string}"

        db_session = Session()
        table_name_for_brand = "trademark"
        create_partition_table(table_name_for_brand, engine)
        ConcreteBrandModel = get_brand_model(table_name_for_brand)

        chrome_options = webdriver.ChromeOptions()
        # chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36')

        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(120)

        all_results = []
        current_page = 0
        has_more_pages = True

        while has_more_pages and current_page < max_pages:
            try:
                logging.info(f"Đang xử lý trang {current_page + 1}")
                
                # Truy cập trang chính để khởi tạo session trước
                driver.get("https://branddb.wipo.int")
                driver.execute_script("sessionStorage.setItem('gbd.prev_enpoint', 'similarname');")

                # B1: Mở trang chính để init session
                driver.get("https://branddb.wipo.int/en/")
                WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")

                # B2: Chuyển hướng bằng JS sang trang advancedsearch để đảm bảo Angular xử lý đầy đủ
                driver.execute_script("window.location.href = '/en/advancedsearch';")

                # B3: Đợi advancedsearch thực sự được load
                WebDriverWait(driver, 30).until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "page-advancedsearch")
                ))

                # B4: Giờ mới set sessionStorage sau khi Angular đã active route
                driver.execute_script("sessionStorage.setItem('gbd.prev_enpoint', 'advancedsearch');")

                # B5: Sau đó mới build và điều hướng đến target URL
                driver.execute_script(f"window.location.href = '{current_url}';")

                try:
                    WebDriverWait(driver, 30).until(
                        lambda d: d.execute_script('return document.readyState') == 'complete'
                    )
                    logging.info("WIPO Crawler: Page load thành công")
                except TimeoutException:
                    logging.warning("WIPO Crawler: page load bị time out")

                # Check for no results
                if check_no_results(driver):
                    logging.info(f"WIPO Crawler: Không có trong khoảng này {start_date_str} - {end_date_str} at {driver.current_url}")
                    break

                # Thu nhỏ màn hình để hiển thị toàn bộ nội dung
                if not zoom_out_to_fit_all_content(driver):
                    logging.warning("Không thể thu nhỏ màn hình, sẽ sử dụng phương pháp cuộn trang thông thường")

                # Sau khi thu nhỏ màn hình, thêm đoạn code kiểm tra và xử lý
                if not zoom_out_to_fit_all_content(driver):
                    logging.warning("Không thể thu nhỏ màn hình, sẽ sử dụng phương pháp cuộn trang thông thường")
                
                # Đợi thêm một chút để đảm bảo tất cả phần tử đã được render
                time.sleep(5)
                
                # Kiểm tra số lượng phần tử hiển thị
                result_elements = driver.find_elements(By.CSS_SELECTOR, "ul.results.listView.ng-star-inserted > li.flex.result.wrap.ng-star-inserted")
                visible_elements = [el for el in result_elements if el.is_displayed()]
                logging.info(f"Tổng số phần tử tìm thấy: {len(result_elements)}, Số phần tử hiển thị: {len(visible_elements)}")
                
                # Nếu số lượng phần tử hiển thị ít hơn mong đợi, thử cuộn trang một chút
                if len(visible_elements) < 30:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.5);")
                    time.sleep(2)
                    result_elements = driver.find_elements(By.CSS_SELECTOR, "ul.results.listView.ng-star-inserted > li.flex.result.wrap.ng-star-inserted")
                    visible_elements = [el for el in result_elements if el.is_displayed()]

                # Danh sách các selector có thể có cho kết quả
                possible_selectors = [
                    "ul.results.listView.ng-star-inserted > li.flex.result.wrap.ng-star-inserted",
                    "ul.results > li.result",
                    "div.search-results-list > ul > li",
                    "li.result-viewed",
                    "div.result-item"
                ]

                parsed_items_collector = []
                processed_item_ids = set()
                result_elements = []

                # Thử từng selector cho đến khi tìm thấy kết quả
                for selector in possible_selectors:
                    try:
                        logging.info(f"Đang thử tìm kết quả với selector: {selector}")
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                        )
                        result_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if result_elements:
                            logging.info(f"Tìm thấy {len(result_elements)} kết quả với selector: {selector}")
                            break
                    except TimeoutException:
                        logging.warning(f"Không tìm thấy kết quả với selector: {selector}")
                        continue
                    except Exception as e:
                        logging.error(f"Lỗi khi tìm kiếm với selector {selector}: {e}")
                        continue

                if not result_elements:
                    logging.error("Không tìm thấy kết quả với bất kỳ selector nào")
                    # Thử tải lại trang trước khi dừng
                    try:
                        driver.refresh()
                        time.sleep(5)
                        result_elements = driver.find_elements(By.CSS_SELECTOR, "ul.results.listView.ng-star-inserted > li.flex.result.wrap.ng-star-inserted")
                        if not result_elements:
                            break
                    except Exception as e:
                        logging.error(f"Lỗi khi tải lại trang: {e}")
                        break

                # Lưu HTML để debug nếu cần
                debug_filename = f"debug_wipo_results_{start_date_str}_{end_date_str}_page_{current_page + 1}.html"
                with open(debug_filename, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                logging.info(f"Đã lưu HTML debug vào file: {debug_filename}")

                for element in result_elements:
                    try:
                        item_st13_id = element.get_attribute('data-st13')
                        if not item_st13_id or item_st13_id in processed_item_ids:
                            continue

                        # Parse dữ liệu từ phần tử
                        single_item_data = {}
                        single_item_data['id'] = item_st13_id

                        # Thử các selector khác nhau cho tên thương hiệu
                        name_selectors = [".brandName", ".name", "h2", ".title"]
                        for name_selector in name_selectors:
                            name_el = element.find_elements(By.CSS_SELECTOR, name_selector)
                            if name_el:
                                single_item_data['name'] = name_el[0].text.strip()
                                break

                        # Thử các selector khác nhau cho các trường khác
                        field_selectors = {
                            'country': [".designation span.value", ".country", ".origin"],
                            'ipr': [".ipr span.value", ".type", ".ipr-type"],
                            'number': [".number span.value", ".id", ".number"],
                            'owner': [".holderName span.value", ".owner span.value", ".owner"],
                            'status': [".status span.value", ".status"],
                            'product_group': [".niceClassification span.value", ".class span.value", ".nice-class"]
                        }

                        for field, selectors in field_selectors.items():
                            for selector in selectors:
                                elements = element.find_elements(By.CSS_SELECTOR, selector)
                                if elements:
                                    single_item_data[field] = elements[0].text.strip()
                                    break

                        # Tìm logo
                        img_selectors = ["img.logo[src]", "img[src]", ".logo img"]
                        for img_selector in img_selectors:
                            img_elements = element.find_elements(By.CSS_SELECTOR, img_selector)
                            if img_elements:
                                single_item_data['image_url'] = img_elements[0].get_attribute('src')
                                break

                        if single_item_data.get('id') and single_item_data.get('name'):
                            processed_item_ids.add(item_st13_id)
                            parsed_items_collector.append(single_item_data)
                            logging.info(f"Đã phân tích thành công mục: ID {single_item_data.get('id')}, Tên '{single_item_data.get('name')}'")

                    except Exception as e:
                        logging.error(f"Lỗi khi phân tích phần tử: {e}")

                # Lưu kết quả từ trang hiện tại vào database
                if parsed_items_collector:
                    valid_items = [item for item in parsed_items_collector if validate_brand_data(item)]
                    if valid_items:
                        _save_wipo_items_to_db(db_session, ConcreteBrandModel, valid_items,
                                           source_name=f"WIPO_DateRange_{start_date_str}_{end_date_str}_page_{current_page + 1}")
                        logging.info(f"Đã lưu {len(valid_items)} kết quả từ trang {current_page + 1} vào database")
                    all_results.extend(valid_items)

                # Kiểm tra xem có trang tiếp theo không
                try:
                    # Kiểm tra số lượng kết quả thực tế đã lấy được
                    actual_results = len(parsed_items_collector)
                    logging.info(f"Trang {current_page + 1}: Số kết quả thực tế: {actual_results}")

                    if actual_results == 0:
                        logging.warning(f"Không lấy được kết quả nào từ trang {current_page + 1}, thử tải lại trang...")
                        driver.refresh()
                        time.sleep(5)
                        continue

                    # Tạo URL cho trang tiếp theo
                    next_start = (current_page + 1) * 30
                    next_url = get_next_page_url(current_url, next_start)
                    if next_url:
                        # Đặt lại sessionStorage trước khi chuyển trang tiếp theo
                        driver.execute_script("sessionStorage.setItem('gbd.prev_enpoint', 'advancedsearch');")
                        driver.execute_script(f"window.location.href = '{next_url}';")

                        WebDriverWait(driver, 10).until(
                            lambda d: d.execute_script(
                                "return sessionStorage.getItem('gbd.prev_enpoint')"
                            ) == 'advancedsearch'
                        )

                        current_url = next_url
                        current_page += 1
                        logging.info(f"Chuyển sang trang {current_page + 1}")

                        # Random thời gian chờ giữa các trang (10-60 giây)
                        wait_time = random.randint(10, 60)
                        logging.info(
                            f"Đợi {wait_time} giây trước khi chuyển sang trang tiếp theo để tránh bị coi là bot...")
                        time.sleep(wait_time)
                    else:
                        logging.error("Không thể tạo URL cho trang tiếp theo")
                        has_more_pages = False

                except Exception as e:
                    logging.error(f"Lỗi khi chuyển trang: {e}")
                    # Tùy chọn: có thể dừng hoặc thử lại
                    break
                except Exception as e:
                    logging.error(f"Lỗi khi xử lý phân trang: {e}")
                    # Thử tải lại trang hiện tại
                    try:
                        driver.refresh()
                        time.sleep(5)
                        continue
                    except:
                        has_more_pages = False
                        break

            except Exception as e:
                logging.error(f"Lỗi khi xử lý trang {current_page + 1}: {e}")
                # Thử tải lại trang trước khi dừng
                try:
                    driver.refresh()
                    time.sleep(5)
                    continue
                except:
                    break

        logging.info(f"Đã hoàn thành crawl {current_page + 1} trang, tổng số kết quả: {len(all_results)}")

    except Exception as e:
        logging.error(f"WIPO Crawler: Lỗi không mong muốn: {e}", exc_info=True)
        return None
    finally:
        if driver:
            try:
                driver.quit()
                logging.info("WIPO Crawler: Đã đóng trình duyệt Chrome thành công.")
            except Exception as e:
                logging.error(f"WIPO Crawler: Lỗi khi đóng trình duyệt Chrome: {e}")

    if not all_results:
        logging.warning(f"WIPO Crawler: Không có kết quả nào cho khoảng thời gian '{start_date_str} - {end_date_str}'.")
        if db_session: 
            db_session.close()
        return []

    # Save to cache
    cache_key = f"daterange_{start_date_str}_{end_date_str}"
    save_to_cache(cache_key, all_results)

    if db_session:
        db_session.close()
        logging.info("WIPO Crawler: Đã đóng phiên cơ sở dữ liệu.")

    return all_results


def zoom_out_to_fit_all_content(driver):
    """
    Thu nhỏ màn hình để hiển thị toàn bộ nội dung trong một khung nhìn
    """
    try:
        # Đợi cho trang tải hoàn toàn
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        
        # Đặt kích thước viewport lớn hơn
        driver.set_window_size(1920, 3000)  # Tăng chiều cao viewport
        time.sleep(2)
        
        # Lấy kích thước hiện tại của trang và viewport
        page_height = driver.execute_script("""
            return Math.max(
                document.body.scrollHeight,
                document.documentElement.scrollHeight,
                document.body.offsetHeight,
                document.documentElement.offsetHeight
            );
        """)
        viewport_height = driver.execute_script("return window.innerHeight")
        
        # Tính toán tỷ lệ zoom cần thiết
        zoom_ratio = min(0.4, viewport_height / page_height * 0.9)
        
        # Áp dụng zoom out và thêm một số CSS để đảm bảo hiển thị
        driver.execute_script("""
            document.body.style.zoom = arguments[0];
            document.body.style.transform = 'scale(' + arguments[0] + ')';
            document.body.style.transformOrigin = 'top left';
            document.body.style.width = (100 / arguments[0]) + '%';
            document.body.style.height = (100 / arguments[0]) + '%';
        """, zoom_ratio)
        
        # Đợi trang web điều chỉnh
        time.sleep(3)
        
        # Kiểm tra và đảm bảo tất cả phần tử được hiển thị
        result_elements = driver.find_elements(By.CSS_SELECTOR, "ul.results.listView.ng-star-inserted > li.flex.result.wrap.ng-star-inserted")
        visible_count = len([el for el in result_elements if el.is_displayed()])
        
        logging.info(f"Đã thu nhỏ màn hình với tỷ lệ {zoom_ratio}. Số phần tử hiển thị: {visible_count}/{len(result_elements)}")
        
        # Nếu vẫn chưa đủ phần tử hiển thị, thử điều chỉnh lại
        if visible_count < len(result_elements):
            # Thử zoom out thêm
            zoom_ratio = zoom_ratio * 0.8
            driver.execute_script("""
                document.body.style.zoom = arguments[0];
                document.body.style.transform = 'scale(' + arguments[0] + ')';
                document.body.style.transformOrigin = 'top left';
                document.body.style.width = (100 / arguments[0]) + '%';
                document.body.style.height = (100 / arguments[0]) + '%';
            """, zoom_ratio)
            
            time.sleep(2)
            
            # Kiểm tra lại
            result_elements = driver.find_elements(By.CSS_SELECTOR, "ul.results.listView.ng-star-inserted > li.flex.result.wrap.ng-star-inserted")
            visible_count = len([el for el in result_elements if el.is_displayed()])
            logging.info(f"Đã điều chỉnh lại zoom với tỷ lệ {zoom_ratio}. Số phần tử hiển thị: {visible_count}/{len(result_elements)}")
            
            # Nếu vẫn chưa đủ, thử cuộn trang một chút
            if visible_count < len(result_elements):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.3);")
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.6);")
                time.sleep(1)
                
                # Kiểm tra lần cuối
                result_elements = driver.find_elements(By.CSS_SELECTOR, "ul.results.listView.ng-star-inserted > li.flex.result.wrap.ng-star-inserted")
                visible_count = len([el for el in result_elements if el.is_displayed()])
                logging.info(f"Sau khi cuộn: Số phần tử hiển thị: {visible_count}/{len(result_elements)}")
        
        return True
    except Exception as e:
        logging.error(f"Lỗi khi thu nhỏ màn hình: {e}")
        return False

def fetch_status_from_site(brand_id: str) -> str | None:
    logger_wipo_fetch.info(f"Đang cố gắng lấy trạng thái cho ID thương hiệu WIPO: {brand_id}")

    if not brand_id:
        logger_wipo_fetch.warning("Thiếu ID thương hiệu, không thể lấy trạng thái WIPO.")
        return None

    driver = None
    try:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36')

        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(45)

        logger_wipo_fetch.warning(
            f"fetch_status_from_site cho ID WIPO {brand_id} CHƯA ĐƯỢC TRIỂN KHAI ĐẦY ĐỦ. Đang trả về giá trị tạm thời.")
        return "Đang xử lý (WIPO Placeholder)"

    except TimeoutException:
        logger_wipo_fetch.error(f"Hết thời gian khi cố gắng lấy trạng thái cho ID WIPO {brand_id}.", exc_info=True)
        if driver:
            try:
                with open(f"debug_wipo_status_timeout_{brand_id}.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                logger_wipo_fetch.info(f"Đã lưu HTML khi hết thời gian cho ID WIPO {brand_id}.")
            except:
                pass
        return None
    except WebDriverException as e_wd:
        logger_wipo_fetch.error(f"Lỗi WebDriverException cho ID WIPO {brand_id}: {e_wd}", exc_info=True)
        return None
    except Exception as e:
        logger_wipo_fetch.error(f"Lỗi không mong muốn khi lấy trạng thái cho ID WIPO {brand_id}: {e}", exc_info=True)
        return None
    finally:
        if driver:
            driver.quit()

def get_real_search_url_by_date(driver, start_date, end_date):

    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import time

    driver.get("https://branddb.wipo.int/en/advancedsearch")
    # Đợi trang tải xong
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script('return document.readyState') == 'complete'
    )
    time.sleep(2)  # Đợi thêm cho chắc chắn các trường đã render

    # Sử dụng selector đúng cho input ngày
    date_inputs = driver.find_elements(By.CSS_SELECTOR, "input[placeholder='YYYY-MM-DD']")
    if len(date_inputs) < 2:
        raise Exception("Không tìm thấy đủ 2 trường nhập ngày!")

    start_input = date_inputs[0]
    end_input = date_inputs[1]
    start_input.clear()
    start_input.send_keys(start_date)
    end_input.clear()
    end_input.send_keys(end_date)

    time.sleep(1)
    # Nhấn nút Search
    try:
        search_btn = driver.find_element(By.XPATH, "//button[contains(., 'Search') or contains(@aria-label, 'Search')]")
        search_btn.click()
    except Exception as e:
        logging.error(f"Không tìm thấy hoặc không click được nút Search. Cần kiểm tra lại selector. Lỗi: {e}")
        raise

    # Đợi trang kết quả tải xong
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script('return document.readyState') == 'complete'
    )
    time.sleep(2)
    return driver.current_url