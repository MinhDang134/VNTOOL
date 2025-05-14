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
    # db tượng trưng cho db_session
    # concemodel tượng chưng cho brandModel
    # item_to_save thì tượng chưng cho valid item là những thông tin trả về từ result
    # thì sẽ truyền toàn bộ thông tin vào bảng này
    saved_count = 0 # cho mọi giá trị bằng 0 hêt lưu count
    processed_count = 0 # count đếm gì đó quyên mia hết rồi
    skipped_count = 0 # cho cout bằng 0 hết
    error_count = 0 # đếm lỗi bằng 0

    if not items_to_save: # nếu mà items_to_save mà éo có dữ liệu thì in như bên dưới
        logging.info(f"DB Save ({source_name}): No items to save.")
        return

    for item_detail in items_to_save: # nếu có dữ liệu thì duyêt từng cái in vào item_detail
        processed_count += 1 # tăng cái biến đếm xử lý lên 1
        item_id = item_detail.get("id") # thông qua cái item_detail lấy thông tin id ra lưu vào item_id
        
        # Kiểm tra ID
        if not item_id: # nếu mà item_id không có thì in ra cái này bỏ qua mọi thức bên dưới còn không thì tiếp tục
            logging.error(f"DB Save ({source_name}): Item skipped due to missing ID: {item_detail.get('name', 'N/A')}")
            skipped_count += 1
            continue

        try:
            # Kiểm tra xem record đã tồn tại chưa
            # nếu mà có dữ liệu thì chạy và đây
            # db lấy dữ liệu bảng và id
            existing_item = db_session.get(BrandModel, item_id)
            
            if existing_item: # nếu mà cả hai dữ liệu đều có thì
                logging.info(f"DB Save ({source_name}): Updating existing record for ID: {item_id}")
                # Cập nhật các trường từ dữ liệu mới
                for key, value in item_detail.items():  # bâ giờ thì sẽ duyệt từng phần từ lấy từ result cho ra key và , value
                    # cái này thì nó sẽ lấy ra thông tin cũ và ket của nó rồi nó sẽ set thông tin mới vào thay thế thông tincũ
                    if hasattr(existing_item, key) and value is not None:
                        setattr(existing_item, key, value)
                # Cập nhật source và last_updated
                existing_item.source = source_name # dữ liệu này nó sẽ gán để cho biết cái này được thay thế từ nguồn nào
                existing_item.last_updated = datetime.utcnow() # cũng như là thời gian được thay thế
            else:
                logging.info(f"DB Save ({source_name}): Adding new record for ID: {item_id}")
                # Tạo instance mới với dữ liệu từ parser
                # tạo một bảng dữ liệu khác từ parse hả
                brand_instance_data = { # tạo from bảng nè
                    "id": item_id, # thông qua item_id , và valid_iitems được truyền vào để lấy từng giá trị ,
                    "name": item_detail.get("name"),
                    "product_group": item_detail.get("product_group"),
                    "status": item_detail.get("status"),
                    "registration_date": item_detail.get("registration_date"),
                    "image_url": item_detail.get("image_url"),
                    "source": source_name,
                    "owner": item_detail.get("owner"),
                    "original_number": item_detail.get("original_number")
                }
                brand_instance = BrandModel(**brand_instance_data) # lưu toàn bộ cái thông tin vào brandModels
                db_session.add(brand_instance) # thêm cái bảng nagy vào database

            # Commit sau mỗi item để tránh lỗi ảnh hưởng đến toàn bộ batch
            db_session.commit() # commit lên
            saved_count += 1 # lưu counnt save count lên 10
            logging.info(f"DB Save ({source_name}): Successfully saved item {item_id}") # hiển thị thông tin source ra

        except Exception as e:
            db_session.rollback() # nếu mà lỗi thì nó gủi rolll back
            error_count += 1 # tăng lỗi lên 1
            logging.error(f"DB Save ({source_name}): Error processing/merging item (ID: {item_id}, Name: {item_detail.get('name')}). Rolled back for this item. Error: {str(e)}")
            continue

    # Log tổng kết
    logging.info(f"DB Save ({source_name}): Processing complete. " # hiển thị toàn bộ ra cái hóa quá trình thành công hay gì đó 
                f"Processed: {processed_count}, "
                f"Saved: {saved_count}, "
                f"Skipped: {skipped_count}, "
                f"Errors: {error_count}")

    return saved_count # return ra saved_count  là số lần thành công hay không


def crawl_wipo(month: str):
    """Crawls WIPO for trademarks registered in a specific month."""
    logging.info(f"WIPO Crawler: Starting crawl for month: {month}")
    # thông báo là sẽ bắt đầu crawl dữ liệu từ tháng nào
    
    try:
        # Validate month format (YYYY-MM)
        datetime.strptime(month, "%Y-%m") # thử xem cái định dang có phài là Y-m không
    except ValueError: # nếu mà không phải định dạng y - m thì sẽ hiện ra lỗi
        logging.error(f"Invalid month format: {month}. Expected format: YYYY-MM")
        return None

    db_session = None # khai báo db
    driver = None # khái báo chrom drive
    html_content_for_parsing = None # lấy dữ liệu từ html

    try:
        db_session = Session() # khái báo cơ sở dữ liệu để dùng thôi
        table_name_for_brand = "trademark" #  tabel name tí có lưu thông tin gì thì lưu
        create_partition_table(table_name_for_brand, engine) # tạo ra  3 tition truyền đường dẫn db và truyền tên bảng vào
        ConcreteBrandModel = get_brand_model(table_name_for_brand) # truyền table name vào để lấy thông tin bảng hay sao ấy

        chrome_options = webdriver.ChromeOptions() # thông qua webdriver mở chrom lên
        chrome_options.add_argument('--no-sandbox') # thiết lập giao diện chrome thôi
        chrome_options.add_argument('--disable-dev-shm-usage') # thiết lập giao diện chrom
        chrome_options.add_argument('--start-maximized') # thiết lập giao diện chrom
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36') # thiết lập giao diện chrom

        driver = webdriver.Chrome(options=chrome_options) # khởi tạo chrom lên
        driver.set_page_load_timeout(60) #  thời gian load page trong vòng 60s

        # Navigate to WIPO advanced search
        wipo_search_url = "https://branddb.wipo.int/branddb/en/search/advanced" # link trang wipo để lên trang advanced
        driver.get(wipo_search_url) # lấy link trang web đó
        logging.info(f"WIPO Crawler: Navigated to {wipo_search_url}")
        # tạo ra một cái from cho người dùng biết truyền vào input
        user_interaction_prompt = (
            f"[WIPO INTERACTION REQUIRED]\n"
            f"1. Trình duyệt Chrome đã mở tại trang WIPO Advanced Search.\n"
            f"2. Vui lòng GIẢI CAPTCHA (nếu có).\n"
            f"3. Trong phần 'Registration Date', chọn tháng: {month}\n"
            f"4. Nhấn nút 'Search' và đợi kết quả.\n"
            f"Sau đó, NHẤN ENTER ở đây để tiếp tục..."
        )
        input(user_interaction_prompt)

        # Check for no results
        if check_no_results(driver): # check nếu không có kết quả thì trả về none
            logging.info(f"WIPO Crawler: No results found for month {month}")
            return None

        # Get dynamic timeout
        # tính toán thời gian chờ phù hợp để nó không bị time out sớm
        timeout = get_dynamic_timeout(driver)
        logging.info(f"WIPO Crawler: Using dynamic timeout of {timeout} seconds") # hiển thị ra cảnh báo


        results_css_selector = "li.result-viewed" # đường dẫn html
        WebDriverWait(driver, timeout).until( # webdrive sẽ truyền driver là chrom và thời gian tham out vào cho đến khi mà nó trả về được giá trị
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, results_css_selector))
        )
        logging.info("WIPO Crawler: Search results page elements located.")

        html_content_for_parsing = driver.page_source # cái này là khi drive đã trả về dữ liệu trong cái khoảng đó thì lấy được cả source của phần đó

    except TimeoutException: # quá trình lỗi khi mà hết thời gian
        logging.error(f"WIPO Crawler: Timeout waiting for search results for month {month}", exc_info=True)
        raise
    except WebDriverException as e: # lõi khi mà gì đó
        logging.error(f"WIPO Crawler: WebDriverException occurred: {e}", exc_info=True)
        raise
    except Exception as e: # hiển thị lỗi
        logging.error(f"WIPO Crawler: Unexpected error: {e}", exc_info=True)
        raise
    finally: # cuối cùng dù có chạy hay không
        if driver: # drive là chrom sẽ tắt
            driver.quit() # tắt
        if db_session: # database cũng sẽ tắt
            db_session.close() # đóng database

    if not html_content_for_parsing: # không trả về html thì in ra cái này , trả về none
        logging.warning(f"WIPO Crawler: No HTML content retrieved for month {month}")
        return None

    logging.info(f"WIPO Crawler: Parsing HTML for month {month}...")
    parsed_brand_items = parse_wipo_html(html_content_for_parsing)# truyền toàn bộ mà li.result gì đó cho parse_wipo sử lý
    # sau khi lấy được toàn bộ thông tin từ bảng result rồi thì sẽ quay lại đây lưu vào parsed_brand_items
    if not parsed_brand_items: # nếu mà dữ liệu không được trả về thì hiện ra thông bao sau
        logging.info(f"WIPO Crawler: No items parsed from HTML for month {month}")
        return None

    # Validate items before saving
    # cái trường hợp này như sau nó sẽ duyệt từng bảng result nè với điều kiện là những bảng result đó phải đáp ứng điều kiện alf
    valid_items = [item for item in parsed_brand_items if validate_brand_data(item)]
    # trường hợp này nó sẽ lấy từng item nếu mà cái kia trả về true khi cso 2 thuộc tính bắt buộc là id và name
    # thì luôn đúng rồi thì nó sẽ duyệt từ đầu đến hết luôn
    if len(valid_items) != len(parsed_brand_items): # nếu mà độ dài của valid_item và cái kia nó khác nhau sẽ in ra cái bên dưới
        logging.warning(f"WIPO Crawler: Filtered out {len(parsed_brand_items) - len(valid_items)} invalid items")

    # Save to cache
    cache_key = f"month_{month}" # save dữ liệu theo tháng khi lưu vào cache
    save_to_cache(cache_key, valid_items) # lưu vào cache thì truyền key và valid_item là cái sau khi duyên từ phần từ đó vào
    # sau khi mà đẩy thtoong tin lên cache rồi thì
    if db_session and ConcreteBrandModel and valid_items: # nếu mà db và thông tin bảng valid_item đều có dữ liêu thì
        _save_wipo_items_to_db(db_session, ConcreteBrandModel, valid_items, # nó sẽ trả về số lần save vào database
                               source_name=f"WIPO_Month_{month}")
    else: # nếu không thì in ra cái này
        logging.error(f"WIPO Crawler: Cannot save items for month {month}")

    return valid_items # trả về valid_items nghĩa là cái from kết quả ấy


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
    # sau khi truyền name vào rồi thì nó cũng chuyền một cái boolean gì đó đéo bíc phải làm gì
    logging.info(f"WIPO Crawler: Starting crawl for brand name: '{brand_name_to_search}'")
    # thông báo crawler dữ liệu từ brand name là Ronaldo
    
    # Check cache first
    if not force_refresh: # nếu mà cái này nó không sai thì nó sẽ vào đây
        cached_data = load_from_cache(brand_name_to_search) # truyền tên vào cái load from cache
        # nhận được data là dữ liệu theo rang đối tượng rồi
        if cached_data: # nếu mà có dữ liệu thì in ra logg và return ra
            logging.info(f"WIPO Crawler: Using cached data for '{brand_name_to_search}'")
            return cached_data

    db_session = None # gán db bằng none
    driver = None # webdrive tí mở chrom lên
    html_content_for_parsing = None #phân lưu dữ liệu html

    try:
        db_session = Session() # khai báo sectio tí lưu cơ sở dữ liệu
        table_name_for_brand = "trademark" # tên bảng
        create_partition_table(table_name_for_brand, engine) # truyền tên bảng và ,link url vào
        ConcreteBrandModel = get_brand_model(table_name_for_brand) # trả về cái bảng from

        chrome_options = webdriver.ChromeOptions() # mở chrom
        chrome_options.add_argument('--no-sandbox') # cấu hình chrom
        chrome_options.add_argument('--disable-dev-shm-usage')# cấu hình chrom
        chrome_options.add_argument('--start-maximized')# cấu hình chrom
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36')# cấu hình chrom

        driver = webdriver.Chrome(options=chrome_options) # mở chrom
        driver.set_page_load_timeout(120) # setup 120 chạy

        wipo_search_url = "https://branddb.wipo.int/branddb/en/" # link chạy
        driver.get(wipo_search_url) # getlinkchay
        logging.info(f"WIPO Crawler: Navigated to {wipo_search_url}") # điều hướng đến trang

        user_interaction_prompt = (
            f"[WIPO INTERACTION REQUIRED]\n"
            f"1. Trình duyệt Chrome đã mở tại trang WIPO.\n"
            f"2. Vui lòng GIẢI CAPTCHA (nếu có).\n"
            f"3. Thực hiện TÌM KIẾM thủ công cho tên thương hiệu: '{brand_name_to_search}'.\n"
            f"4. Đợi trang KẾT QUẢ TÌM KIẾM tải hoàn tất.\n"
            f"Sau đó, NHẤN ENTER ở đây để tiếp tục..."
        )
        input(user_interaction_prompt) # hiện consolose cho người dùng enter
        
        # Đợi trang load xong
        try:
            WebDriverWait(driver, 10).until( # nó chờ webdrive chạy trong vòng 10 s rồi in ra script như sau
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
        except TimeoutException:  # nếu mà hết thời gian không tìm được cái gì thì nó sẽ hiện ra thông báo bên dưới
            logging.warning("Page load timeout, but continuing anyway...")

        # Kiểm tra URL để xác nhận đã chuyển sang trang kết quả
        current_url = driver.current_url # xem cái chrom nó lưu cái trang hiện tại
        if not any(keyword in current_url.lower() for keyword in ['results', 'search', 'similarname']):
            logging.warning(f"WIPO Crawler: Not on search results page. Current URL: {current_url}")
            return None # mấy cái phần này chịu

        # Check for no results
        if check_no_results(driver): # cái này check xem có dự liệu nào trả về từ chrom không, nếu không có thì sẽ hiển thị cái lỗi dưới
            logging.info(f"WIPO Crawler: No results found for '{brand_name_to_search}'")
            return None

        # --- LOGIC CUỘN VÀ PARSE TỪNG BLOCK ---
        # cho một cái đường link để mà khoanh dùng tùm kiếm dữ liệu ul > li
        results_selector = "ul.results.listView.ng-star-inserted > li.flex.result.wrap.ng-star-inserted"
        parsed_items_collector = [] # chưa biết làm gì
        processed_item_ids = set() # chưa biết làm gì
        target_item_count = 30 # mục tiêu biến count là 30 phần
        scroll_attempts_without_new_items = 0 # chiua chưa biết lý do
        max_fruitless_scrolls = 3 # số làn cuộn tối đa
        # hiển thị bằng một cái log
        logging.info(f"Starting incremental scroll and parse. Target: {target_item_count} items.")
        # điều kiện này luôn đúng khi độ dài của parsed_item_colllector nhỏ hơn target và số lần bắt đầu scroll nhỏ hơn max số lần được
        while len(parsed_items_collector) < target_item_count and scroll_attempts_without_new_items < max_fruitless_scrolls:

            initial_processed_count = len(processed_item_ids)
            try: # nếu mà webdrive nó lên nó lấy được css_seclector các thứu thì sẽ đến bước bên dưới
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, results_selector))
                ) # block_on_page hiện tại sẽ là chrom tìm tất cả các element mà nó thỏa mã cái điều kiện được tìm ra
                current_blocks_on_page = driver.find_elements(By.CSS_SELECTOR, results_selector)
                logging.info(f"Found {len(current_blocks_on_page)} blocks on page after scroll/wait.")
            except TimeoutException:# lỗi thì nó sẽ sẽ chạy vào đây
                # và trả về một cái list rỗng chưa lưu được dữ liệu
                logging.info("No result blocks found on page currently.")
                current_blocks_on_page = []

            new_items_found_this_scroll = False
            for block_idx, block_element in enumerate(current_blocks_on_page):
                try:
                    item_st13_id = block_element.get_attribute('data-st13')
                    if not item_st13_id:
                        logging.warning(f"Block at index {block_idx} on page has no data-st13. Skipping for ID check for now or implement fallback ID.")
                        continue
                except Exception:
                    logging.warning(f"Could not get any ID for block at index {block_idx} on page. Skipping.")
                    continue

                if item_st13_id not in processed_item_ids:
                    new_items_found_this_scroll = True
                    logging.info(f"New item found: ID {item_st13_id}. Processing...")
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", block_element)
                        time.sleep(0.2)
                        WebDriverWait(block_element, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".brandName"))
                        )
                        logging.debug(f"Item {item_st13_id} - .brandName seems loaded for parsing.")
                    except TimeoutException:
                        logging.warning(f"Item {item_st13_id} - Timeout waiting for .brandName before parsing. Will attempt parsing anyway.")
                    except Exception as e_detail_load:
                        logging.error(f"Item {item_st13_id} - Error ensuring detail load: {e_detail_load}")

                    # Parse từng block bằng Selenium (cơ bản)
                    single_item_data = {}
                    try:
                        name_el = block_element.find_element(By.CSS_SELECTOR, ".brandName")
                        single_item_data['name'] = name_el.text.strip()
                        try:
                            id_el = block_element.find_element(By.CSS_SELECTOR, ".number span.value")
                            single_item_data['id'] = id_el.text.strip().replace(',', '')
                        except NoSuchElementException:
                            single_item_data['id'] = item_st13_id
                        # Thêm các trường khác nếu muốn
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
                            logging.info(f"Successfully parsed and added item ID (display): {single_item_data.get('id')}, st13: {item_st13_id}")
                        else:
                            logging.warning(f"Item {item_st13_id} - Missing critical data after attempting to parse. Not added.")
                    except Exception as e_parse:
                        logging.error(f"Error parsing item {item_st13_id}: {e_parse}")

                    if len(parsed_items_collector) >= target_item_count:
                        break

            if len(parsed_items_collector) >= target_item_count:
                logging.info(f"Reached target item count of {target_item_count}.")
                break

            if not new_items_found_this_scroll:
                scroll_attempts_without_new_items += 1
                logging.info(f"No new items found on this scroll. Fruitless scroll attempts: {scroll_attempts_without_new_items}/{max_fruitless_scrolls}")
            else:
                scroll_attempts_without_new_items = 0

            if scroll_attempts_without_new_items >= max_fruitless_scrolls:
                logging.info("Max fruitless scroll attempts reached. Stopping scroll.")
                break

            logging.info("Scrolling down to load more items...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        logging.info(f"Finished scrolling. Total items parsed: {len(parsed_items_collector)}")
        all_results = parsed_items_collector

    except TimeoutException:
        logging.error(f"WIPO Crawler: Timeout waiting for search results for '{brand_name_to_search}'", exc_info=True)
        raise
    except WebDriverException as e:
        logging.error(f"WIPO Crawler: WebDriverException occurred: {e}", exc_info=True)
        raise
    except Exception as e:
        logging.error(f"WIPO Crawler: Unexpected error: {e}", exc_info=True)
        raise
    finally:
        if driver:
            try:
                driver.quit()
                logging.info("WIPO Crawler: Chrome driver quit successfully.")
            except Exception as e:
                logging.error(f"WIPO Crawler: Error quitting Chrome driver: {e}", exc_info=True)

    if not all_results:
        logging.warning(f"WIPO Crawler: No HTML content retrieved for '{brand_name_to_search}'")
        if db_session:
            db_session.close()
        return None

    logging.info(f"WIPO Crawler: Parsing HTML for '{brand_name_to_search}'...")
    # all_results đã là list các dict, không cần parse lại
    valid_items = [item for item in all_results if validate_brand_data(item)]
    if len(valid_items) != len(all_results):
        logging.warning(f"WIPO Crawler: Filtered out {len(all_results) - len(valid_items)} invalid items")

    # Save to cache
    save_to_cache(brand_name_to_search, valid_items)

    if db_session and ConcreteBrandModel and valid_items:
        _save_wipo_items_to_db(db_session, ConcreteBrandModel, valid_items,
                               source_name=f"WIPO_Search_{brand_name_to_search}")
        logging.info(f"WIPO Crawler: Successfully saved {len(valid_items)} items to database")
    else:
        logging.error(f"WIPO Crawler: Cannot save items for '{brand_name_to_search}'")

    if db_session:
        db_session.close()
        logging.info("WIPO Crawler: Database session closed.")

    return valid_items


@retry_on_failure(max_retries=3)
def crawl_wipo_by_date_range(start_date_str: str, end_date_str: str, force_refresh: bool = False):
    """
    Crawls WIPO for trademarks registered within a specific date range.
    The process runs in headless mode.
    """
    logging.info(f"WIPO Crawler: Starting crawl for date range: {start_date_str} to {end_date_str}")

    # Validate date format (YYYY-MM-DD)
    try:
        datetime.strptime(start_date_str, "%Y-%m-%d")
        datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        logging.error(f"Invalid date format. Expected YYYY-MM-DD. Received: {start_date_str}, {end_date_str}")
        return None

    # Cache key based on date range
    cache_key = f"daterange_{start_date_str}_{end_date_str}"
    if not force_refresh:
        cached_data = load_from_cache(cache_key)
        if cached_data:
            logging.info(f"WIPO Crawler: Using cached data for date range '{start_date_str} - {end_date_str}'")
            return cached_data

    db_session = None
    driver = None
    all_results = []

    try:
        # Construct the URL
        base_url = "https://branddb.wipo.int/en/advancedsearch/results"
        as_structure_template = {
            "_id": "460a",  # This ID might change or be dynamic, assuming it's stable for now
            "boolean": "AND",
            "bricks": [{
                "_id": "460a", # This ID might also change
                "key": "appDate",
                "strategy": "Range",
                "value": [start_date_str, end_date_str]
            }]
        }
        
        params = {
            "sort": "score desc",
            "strategy": "concept",
            "rows": "30", # The crawler will scroll for more if needed
            "asStructure": json.dumps(as_structure_template),
            "_": int(time.time() * 1000), # Timestamp for cache busting
            "fg": "_void_"
        }
        
        query_string = urllib.parse.urlencode(params)
        target_url = f"{base_url}?{query_string}"
        logging.info(f"WIPO Crawler: Constructed URL: {target_url}")

        db_session = Session()
        table_name_for_brand = "trademark" # Assuming the same table
        create_partition_table(table_name_for_brand, engine)
        ConcreteBrandModel = get_brand_model(table_name_for_brand)

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36')

        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(120) # Increased timeout

        logging.info(f"WIPO Crawler: Navigating to URL (headless): {target_url}")
        driver.get(target_url)
        
        # Wait for page to indicate it has loaded, e.g. by checking for a known element or document.readyState
        try:
            WebDriverWait(driver, 30).until( # Increased wait time
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            logging.info("WIPO Crawler: Page 'document.readyState' is 'complete'.")
        except TimeoutException:
            logging.warning("WIPO Crawler: Page load timeout (readyState), but continuing detection...")

        # Check for no results (important to do this early)
        if check_no_results(driver):
            logging.info(f"WIPO Crawler: No results found for date range {start_date_str} - {end_date_str} at {driver.current_url}")
            return None # Return empty list or None, consistent with other functions

        # --- ADAPTED SCROLLING AND PARSING LOGIC from crawl_wipo_by_name ---
        # This selector might be different for advanced search results, adjust if necessary
        results_selector = "ul.results.listView.ng-star-inserted > li.flex.result.wrap.ng-star-inserted"
        # Fallback selectors if the primary one fails, WIPO's structure can be inconsistent.
        # These are examples, might need inspection of actual advanced search result page structure.
        fallback_results_selectors = [
            "ul.results > li.result", # Simpler selector
            "div.search-results-list > ul > li" 
        ]

        parsed_items_collector = []
        processed_item_ids = set() # To avoid duplicates if items reappear during scroll
        # target_item_count can be very large for a date range, so we might rely more on fruitless scrolls
        # For now, let's keep a high target or remove it and rely on scroll_attempts.
        # Let's make target_item_count configurable or remove it for date range search if it implies fetching ALL.
        # For now, let's aim for a significant number, but fruitless scrolls will be the primary stop condition.
        # target_item_count = 1000 # Example, adjust as needed or make it dynamic
        scroll_attempts_without_new_items = 0
        max_fruitless_scrolls = 5 # Increased fruitless scrolls
        
        current_results_selector = None

        logging.info("WIPO Crawler: Starting incremental scroll and parse for date range.")

        # Try to find which selector works
        for sel_idx, r_selector in enumerate([results_selector] + fallback_results_selectors):
            try:
                WebDriverWait(driver, 15).until( # Wait a bit for elements with this selector
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, r_selector))
                )
                # Check if elements are actually found and visible
                test_elements = driver.find_elements(By.CSS_SELECTOR, r_selector)
                if test_elements and any(el.is_displayed() for el in test_elements):
                    current_results_selector = r_selector
                    logging.info(f"WIPO Crawler: Using results selector: '{current_results_selector}'")
                    break
                else:
                    logging.debug(f"WIPO Crawler: Selector '{r_selector}' found elements but none visible or list empty.")
            except TimeoutException:
                logging.debug(f"WIPO Crawler: Selector '{r_selector}' not found on page after 15s wait (selector attempt {sel_idx+1}).")
        
        if not current_results_selector:
            logging.error(f"WIPO Crawler: Could not find any valid results list selector on page {driver.current_url}. HTML snapshot might be needed for debugging.")
            # Potentially save page source here for debugging
            # with open(f"debug_wipo_daterange_no_selector_{start_date_str}_{end_date_str}.html", "w", encoding="utf-8") as f:
            #    f.write(driver.page_source)
            return None


        while scroll_attempts_without_new_items < max_fruitless_scrolls:
            initial_item_count_this_loop = len(parsed_items_collector)
            new_items_found_this_scroll = False
            
            try:
                # Ensure elements are present before trying to find them
                WebDriverWait(driver, 20).until( # Increased wait for items to appear
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, current_results_selector))
                )
                current_blocks_on_page = driver.find_elements(By.CSS_SELECTOR, current_results_selector)
                logging.info(f"WIPO Crawler: Found {len(current_blocks_on_page)} blocks on page using '{current_results_selector}'. Parsed so far: {len(parsed_items_collector)}")
            except TimeoutException:
                logging.info(f"WIPO Crawler: No result blocks found with selector '{current_results_selector}' after waiting. Current URL: {driver.current_url}")
                current_blocks_on_page = [] # No blocks found this iteration

            if not current_blocks_on_page and not parsed_items_collector: # No blocks ever found
                 if check_no_results(driver): # Double check if "no results" appeared after some dynamic load
                    logging.info(f"WIPO Crawler: Re-checked and confirmed no results found for date range {start_date_str} - {end_date_str}.")
                    # No need to save empty cache or DB entries if truly no results
                    return None 
                 else: # No blocks, but no "no results" message either, could be an error page or unexpected structure
                    logging.warning(f"WIPO Crawler: No result blocks found and no 'no results' message. Page might be incorrect. URL: {driver.current_url}")
                    # Consider saving HTML for debugging
                    # with open(f"debug_wipo_daterange_no_blocks_{start_date_str}_{end_date_str}.html", "w", encoding="utf-8") as f:
                    #    f.write(driver.page_source)
                    break # Exit scroll loop


            for block_idx, block_element in enumerate(current_blocks_on_page):
                # Using data-st13 as a unique ID from the page if available
                item_st13_id = block_element.get_attribute('data-st13')
                if not item_st13_id: # Fallback if data-st13 is not present
                    # Try to generate a temporary ID based on content if possible, or use index
                    # For now, if no st13, we might parse it and see if a DB ID can be extracted later
                    logging.debug(f"Block at index {block_idx} on page has no data-st13. Parsing to find primary ID.")
                
                # If we have st13, check if already processed
                if item_st13_id and item_st13_id in processed_item_ids:
                    continue # Already processed this item, skip

                # Scroll the element into view
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", block_element)
                    time.sleep(0.3) # Small delay for content to potentially load after scroll
                    # Wait for a key element within the block to be present (e.g., brand name)
                    WebDriverWait(block_element, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".brandName")) # Common selector
                    )
                except TimeoutException:
                    logging.warning(f"Timeout waiting for .brandName in block (st13: {item_st13_id}, index: {block_idx}). Attempting parse anyway.")
                except Exception as e_scroll:
                    logging.warning(f"Error scrolling/waiting for block detail (st13: {item_st13_id}, index: {block_idx}): {e_scroll}")

                # Parse the individual block
                single_item_data = {}
                try:
                    # ID - Try st13 first, then from .number span.value, then potentially others
                    # The main 'id' for the database should be the application/registration number
                    id_el = block_element.find_elements(By.CSS_SELECTOR, ".number span.value") # International Registration Number
                    if id_el:
                        single_item_data['id'] = id_el[0].text.strip().replace(',', '')
                    elif item_st13_id: # Use st13 if number isn't found, though number is preferred
                         single_item_data['id'] = item_st13_id 
                    # else: logging.warning(f"Could not find a primary ID for block (st13:{item_st13_id})")

                    name_el = block_element.find_elements(By.CSS_SELECTOR, ".brandName")
                    if name_el: single_item_data['name'] = name_el[0].text.strip()
                    
                    owner_elements = block_element.find_elements(By.CSS_SELECTOR, ".holderName span.value") # Adjusted selector based on common patterns
                    if not owner_elements: # Fallback or alternative selector
                        owner_elements = block_element.find_elements(By.CSS_SELECTOR, ".owner span.value")
                    if owner_elements: single_item_data['owner'] = owner_elements[0].text.strip()

                    status_elements = block_element.find_elements(By.CSS_SELECTOR, ".status span.value")
                    if status_elements: single_item_data['status'] = status_elements[0].text.strip()
                    
                    # Add more fields as identified in `parse_wipo_html` or `crawl_wipo_by_name`
                    # Example: product_group (Nice Classification) often in ".niceClassification span.value" or similar
                    nice_class_elements = block_element.find_elements(By.CSS_SELECTOR, ".niceClassification span.value")
                    if not nice_class_elements: # Fallback for class/product group
                         nice_class_elements = block_element.find_elements(By.CSS_SELECTOR, ".class span.value") # from by_name
                    if nice_class_elements: single_item_data['product_group'] = nice_class_elements[0].text.strip()
                    
                    # Registration Date / Application Date might be available directly
                    # These might be trickier if not in a standard "label: value" format within each block
                    # For now, we rely on the overall date range filter of the search
                    # `original_number` might also be useful if different from `id`
                    
                    img_elements = block_element.find_elements(By.CSS_SELECTOR, "img.logo[src]") # More general image selector
                    if img_elements: single_item_data['image_url'] = img_elements[0].get_attribute('src')

                    # Crucial: Validate if we got essential data (ID and Name)
                    if single_item_data.get('id') and single_item_data.get('name'):
                        if item_st13_id: # Add st13 if we have it, useful for tracking processed items
                            processed_item_ids.add(item_st13_id)
                        # If item_st13_id was not found, we use the extracted 'id' for processed_item_ids,
                        # assuming it's unique enough for the current page load.
                        elif single_item_data.get('id'):
                             processed_item_ids.add(single_item_data.get('id'))


                        parsed_items_collector.append(single_item_data)
                        new_items_found_this_scroll = True
                        logging.info(f"Successfully parsed item: ID {single_item_data.get('id')}, Name '{single_item_data.get('name')}'. Total collected: {len(parsed_items_collector)}")
                    else:
                        logging.warning(f"Item (st13: {item_st13_id}, index: {block_idx}) - Missing critical data (ID or Name) after parsing. Data: {single_item_data}")

                except NoSuchElementException:
                    logging.warning(f"Could not find expected element within block (st13: {item_st13_id}, index: {block_idx}). Skipping this block.")
                except Exception as e_parse_block:
                    logging.error(f"Error parsing block (st13: {item_st13_id}, index: {block_idx}): {e_parse_block}", exc_info=True)
            
            # After processing all current blocks on page
            if new_items_found_this_scroll:
                scroll_attempts_without_new_items = 0 # Reset counter
            else:
                # Check if we are at the bottom of the page
                # clientHeight: This is the inner height of an element in pixels. It includes padding but not the horizontal scrollbar height, border, or margin.
                # scrollTop: This property gets or sets the number of pixels that an element's content is scrolled vertically.
                # scrollHeight: This is the height of an element's content, including content not visible on the screen due to overflow.
                at_bottom = driver.execute_script("return (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 100;") # 100px buffer

                if at_bottom:
                    logging.info("WIPO Crawler: Scrolled to the bottom of the page and no new items found.")
                    break # Exit loop if at bottom and no new items

                scroll_attempts_without_new_items += 1
                logging.info(f"WIPO Crawler: No new items found on this scroll. Fruitless scroll attempts: {scroll_attempts_without_new_items}/{max_fruitless_scrolls}")

            if scroll_attempts_without_new_items >= max_fruitless_scrolls:
                logging.info("WIPO Crawler: Max fruitless scroll attempts reached. Stopping scroll.")
                break

            # Scroll down to load more items
            logging.info("WIPO Crawler: Scrolling down to load more items...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(3,5)) # Increased sleep after scroll for content to load

        all_results = parsed_items_collector
        logging.info(f"WIPO Crawler: Finished scrolling. Total items parsed: {len(all_results)}")

    except TimeoutException as e:
        logging.error(f"WIPO Crawler: Timeout during operation for date range {start_date_str}-{end_date_str}. URL: {driver.current_url if driver else 'N/A'}", exc_info=True)
        # Optionally save page source on timeout
        if driver:
            try:
                debug_filename = f"debug_wipo_daterange_timeout_{start_date_str}_{end_date_str}.html"
                with open(debug_filename, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                logging.info(f"Saved page source to {debug_filename} on timeout.")
            except Exception as ex_save:
                logging.error(f"Failed to save page source on timeout: {ex_save}")
        # Do not return partial results on timeout, as they might be incomplete. Indicate failure.
        return None
    except WebDriverException as e:
        logging.error(f"WIPO Crawler: WebDriverException occurred for date range {start_date_str}-{end_date_str}: {e}", exc_info=True)
        return None # Indicate failure
    except Exception as e:
        logging.error(f"WIPO Crawler: Unexpected error for date range {start_date_str}-{end_date_str}: {e}", exc_info=True)
        return None # Indicate failure
    finally:
        if driver:
            try:
                driver.quit()
                logging.info("WIPO Crawler: Chrome driver quit successfully for date range crawl.")
            except Exception as e_quit:
                logging.error(f"WIPO Crawler: Error quitting Chrome driver: {e_quit}", exc_info=True)
        # db_session is closed outside if data is to be saved.

    if not all_results:
        logging.warning(f"WIPO Crawler: No items collected for date range '{start_date_str} - {end_date_str}'.")
        if db_session: db_session.close()
        return [] # Return empty list if no results parsed, after checks for "no results found" page

    # Validate items before saving
    valid_items = [item for item in all_results if validate_brand_data(item)]
    if len(valid_items) != len(all_results):
        logging.warning(f"WIPO Crawler: Filtered out {len(all_results) - len(valid_items)} invalid items (missing ID or Name).")

    # Save to cache
    save_to_cache(cache_key, valid_items)
    logging.info(f"WIPO Crawler: Saved {len(valid_items)} items to cache for key '{cache_key}'.")

    # Save to DB
    if db_session and ConcreteBrandModel and valid_items:
        saved_count = _save_wipo_items_to_db(db_session, ConcreteBrandModel, valid_items,
                               source_name=f"WIPO_DateRange_{start_date_str}_{end_date_str}")
        logging.info(f"WIPO Crawler: Attempted to save {len(valid_items)} items to database. Successfully saved: {saved_count}")
    elif not valid_items:
        logging.info(f"WIPO Crawler: No valid items to save to database for date range {start_date_str}-{end_date_str}.")
    else:
        logging.error(f"WIPO Crawler: Cannot save items for date range '{start_date_str} - {end_date_str}' due to missing db_session or ConcreteBrandModel.")

    if db_session:
        db_session.close()
        logging.info(f"WIPO Crawler: Database session closed for date range crawl.")

    return valid_items


def fetch_status_from_site(brand_id: str) -> str | None:
    """
    Lấy trạng thái hiện tại của một thương hiệu từ trang WIPO dựa trên brand_id.
    Hàm này cần được triển khai đầy đủ. Hiện tại chỉ là khung sườn.

    Args:
        brand_id: ID của thương hiệu (ví dụ: số đơn quốc tế, số đăng ký WIPO).

    Returns:
        Chuỗi trạng thái nếu tìm thấy, ngược lại là None.
    """
    logger_wipo_fetch.info(f"Attempting to fetch status for WIPO brand ID: {brand_id}")

    if not brand_id:
        logger_wipo_fetch.warning("Brand ID is missing, cannot fetch WIPO status.")
        return None

    # Bước 1: Xây dựng URL đến trang chi tiết hoặc trang tìm kiếm.
    # URL này phụ thuộc vào cách WIPO cấu trúc. Bạn cần nghiên cứu:
    # - Có URL trực tiếp đến trang chi tiết dựa trên brand_id không?
    # - Hay bạn cần vào trang tìm kiếm, nhập brand_id, rồi click vào kết quả?
    # Ví dụ (CẦN THAY THẾ BẰNG URL VÀ LOGIC ĐÚNG):
    # detail_page_url = f"https://branddb.wipo.int/branddb/en/detail/{brand_id}" # URL GIẢ ĐỊNH
    # Hoặc, bạn có thể cần tự động hóa việc tìm kiếm `brand_id` trên trang WIPO.

    driver = None
    try:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--headless')  # Chạy ẩn để không làm phiền
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36')

        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(45)  # Thời gian chờ tải trang

        # --- LOGIC LẤY TRANG VÀ PARSE HTML ---
        # Đây là phần phức tạp nhất và bạn cần tự tìm hiểu cấu trúc trang WIPO:
        # 1. Điều hướng đến URL phù hợp (trang tìm kiếm hoặc trang chi tiết nếu có).
        #    Ví dụ: driver.get(search_url_wipo)
        #
        # 2. Nếu là trang tìm kiếm:
        #    - Tìm ô input, nhập brand_id: driver.find_element(...).send_keys(brand_id)
        #    - Tìm nút submit, click: driver.find_element(...).click()
        #    - Chờ kết quả tìm kiếm (hoặc trang chi tiết) tải: WebDriverWait(...)
        #    - Nếu có nhiều kết quả, bạn có thể cần click vào đúng kết quả để đến trang chi tiết.
        #
        # 3. Khi đã ở trang chi tiết của thương hiệu:
        #    - Chờ cho phần tử chứa trạng thái xuất hiện:
        #      status_selector = "selector.cho.truong.status" # <<< THAY BẰNG SELECTOR THỰC TẾ
        #      WebDriverWait(driver, 30).until(
        #          EC.presence_of_element_located((By.CSS_SELECTOR, status_selector))
        #      )
        #    - Lấy HTML của trang: html_detail = driver.page_source
        #    - Parse HTML bằng BeautifulSoup: soup = BeautifulSoup(html_detail, "html.parser")
        #    - Trích xuất trạng thái:
        #      status_element = soup.select_one(status_selector)
        #      if status_element:
        #          current_status = status_element.text.strip()
        #          logger_wipo_fetch.info(f"Fetched status for WIPO ID {brand_id}: {current_status}")
        #          return current_status
        #      else:
        #          logger_wipo_fetch.warning(f"Could not find status element for WIPO ID {brand_id} using selector '{status_selector}'.")
        #          # Lưu HTML để debug nếu không tìm thấy
        #          with open(f"debug_wipo_status_notfound_{brand_id}.html", "w", encoding="utf-8") as f:
        #              f.write(html_detail)
        #          return None

        # VÌ LOGIC TRÊN CHƯA ĐƯỢC IMPLEMENT, TRẢ VỀ GIÁ TRỊ PLACEHOLDER HOẶC NONE
        logger_wipo_fetch.warning(
            f"fetch_status_from_site for WIPO ID {brand_id} is NOT YET FULLY IMPLEMENTED. Returning placeholder.")
        # return None # Hoặc một giá trị mặc định để test
        return "Đang xử lý (WIPO Placeholder)"  # Ví dụ placeholder

    except TimeoutException:
        logger_wipo_fetch.error(f"Timeout while trying to fetch status for WIPO ID {brand_id}.", exc_info=True)
        if driver:  # Lưu HTML nếu có lỗi timeout để debug
            try:
                with open(f"debug_wipo_status_timeout_{brand_id}.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                logger_wipo_fetch.info(f"HTML on timeout for WIPO ID {brand_id} saved.")
            except:
                pass  # Bỏ qua nếu không lưu được
        return None
    except WebDriverException as e_wd:
        logger_wipo_fetch.error(f"WebDriverException for WIPO ID {brand_id}: {e_wd}", exc_info=True)
        return None
    except Exception as e:
        logger_wipo_fetch.error(f"Unexpected error fetching status for WIPO ID {brand_id}: {e}", exc_info=True)
        return None
    finally:
        if driver:
            driver.quit()

def get_real_search_url_by_date(driver, start_date, end_date):
    """
    Mở trang advanced search, nhập ngày bắt đầu/kết thúc, nhấn Search và lấy URL kết quả (có _id động).
    """
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