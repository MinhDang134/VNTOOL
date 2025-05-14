from bs4 import BeautifulSoup # là phường thức có thể bóc tách dữ liệu ra từ html
import logging # dùng để hiện thông báo
import re # cung cấp biểu thức chính quy để tương tác với html
from typing import List, Dict, Any # là kiểu dữ liệu cũng cấp những kiểu dữ liệu dùng cho nhiều trường hợp
from selenium.webdriver.support.ui import WebDriverWait # cái này dùng cái này sẽ dùng để đợi một điều kiện cụ thể cho đến khi nó chạy xong thì sẽ đến cái khác
from selenium.webdriver.support import expected_conditions as EC # cung cấp tập hợp các điều kiện trước khi chạy webDriverWait
from selenium.webdriver.common.by import By # phương thức này sẽ dùng để chỉ định tìm kiếm những phần tử nào trên trang web
from selenium.common.exceptions import NoSuchElementException, TimeoutException
# NoSuchElementEXception : được lém ra khi không tìm thấy phần tử trong mảng
# TimeoutException : nó có chức năng là hiển thị lỗi nếu mà trong thời gian quy định chưa lấy được dữ liệu


# Cấu hình logging nếu chưa có ở đâu khác (ví dụ: trong main.py)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# hàm clean_id được truyền tham số raw_id và và phải trả ra kiểu str
def clean_id(raw_id: str) -> str:
    """Clean and validate ID from WIPO.
    Handles various ID formats:
    - Numeric IDs with commas (e.g., "545,892")
    - Alphanumeric IDs (e.g., "M1935158")
    - IDs with hyphens (e.g., "VN-1234")
    - Mixed format IDs
    """
    # nếu mà không có raw_id sẽ hiển thị lỗi bên dưới và trả về none
    if not raw_id:
        logging.debug("clean_id: Empty raw_id received")
        return None
    
    # Log the input
    #  hiển thị ra cái id mình lấy được
    logging.debug(f"clean_id: Processing raw_id: '{raw_id}'")
    
    # Remove extra whitespace
    # loại bỏ khoảng trắng nếu như có khoảng trắng nào
    cleaned = raw_id.strip()
    logging.debug(f"clean_id: After strip: '{cleaned}'")
    
    # Handle numeric IDs with commas
    # nếu dấu , có trong cái cái id đó thì ra sẽ thực hiện thay thế dấu , thành không có gì cả
    if ',' in cleaned:
        # Check if it's a numeric ID with commas
        numeric_part = cleaned.replace(',', '') # trong trường hợp này là thay dấu , thành khoảng trắng
        if numeric_part.isdigit(): # sau khi thay xong ta sẽ kiểm tra xem cái id này có phải là số không
            cleaned = numeric_part # nếu hoàn toàn là số thì nó sẽ được lưu vào cleaned
            logging.debug(f"clean_id: Removed commas from numeric ID: '{cleaned}'") # in ra là đã xóa dấu , từ id nào đó
        else:
            # hoặc không nó sẽ hiển thi  là có dấu phẩy nhưng hoàn toàn là số và dữ lại số
            logging.debug(f"clean_id: ID contains commas but is not purely numeric, keeping commas: '{cleaned}'")
    # Validate the cleaned ID
    # nếu mà cleand không có dữ liệu nó sẽ in ra là không có id nào sau khi được cleaning
    if not cleaned:
        logging.warning("clean_id: Empty ID after cleaning")
        return None
    # Log the final result
    # nếu có thì sẽ id cuối cùng là gì đó gì đó
    logging.debug(f"clean_id: Final cleaned ID: '{cleaned}'")
    return cleaned # in ra id đó


# một có tên là extract_id_from_clock  với tham số là block và id trả về kiểu tuple mảng hai chiều
# Cái tuple này nó sẽ chứa cái id của cái được làm sạch đó và cách để làm sạch
def extract_id_from_block(block, idx: int) -> tuple[str, str]:
    """Extract ID from a block using multiple strategies."""
    logging.info(f"Block {idx}: Starting ID extraction") # hiển thị ra số id được startding
    logging.debug(f"Block {idx} HTML: {block.prettify()}") # hiển thị id số mấy và block số mấy
    
    # Danh sách các selector để thử, theo thứ tự ưu tiên
    id_selectors = [ # danh sách các selector để thử
        '.number span.value',  # Selector chính cho block 1-9
        '.number',  # Fallback 1
        'span.value',  # Fallback 2
        '.brand-id',  # Fallback 3
        '.id-value',  # Fallback 4
        '[data-id]',  # Fallback 5 - tìm theo attribute
        '.result-item .id',  # Fallback 6
        '.result-item .number',  # Fallback 7
        '.result-item span.value',  # Fallback 8
        'div.id-section > span',  # Thêm selector giả định cho block 10+
        '.application-number',    # Thêm selector giả định cho block 10+
        'td.id-cell',             # Thêm selector giả định cho block 10+
        'span[id]',               # Thử các span có attribute id
        'div[id]',                # Thử các div có attribute id
    ]
    
    # Thử từng selector
    for selector_index, selector in enumerate(id_selectors): # tạo ra hai biến để để lưu giá trị mà id_selector trả về gồm id và cái tìm ra nó
        element = block.select_one(selector)
        if element:
            raw_id = element.get_text(strip=True)
            logging.info(f"Block {idx}: Selector '{selector}' (attempt {selector_index + 1}) found: '{raw_id}'")
            if raw_id:
                return clean_id(raw_id), selector
            # Nếu không có text, thử lấy từ attribute
            raw_id = element.get('data-id') or element.get('id')
            if raw_id:
                logging.info(f"Block {idx}: Selector '{selector}' (attempt {selector_index + 1}) found attribute: '{raw_id}'")
                return clean_id(raw_id), selector
        else:
            logging.debug(f"Block {idx}: Selector '{selector}' (attempt {selector_index + 1}) found nothing.")
    
    # Nếu không tìm thấy bằng selector, thử lấy từ thuộc tính data-st13 của thẻ <li>
    data_st13 = block.get('data-st13')
    if data_st13:
        logging.info(f"Block {idx}: Found ID from data-st13 attribute: '{data_st13}'")
        return clean_id(data_st13), 'data-st13'
    
    # Nếu không tìm thấy bằng selector, thử tìm bằng regex
    logging.debug(f"Block {idx}: No ID found with selectors, trying regex patterns")
    id_patterns = [
        r'ID:\s*([A-Z0-9,.-]+)',
        r'Number:\s*([A-Z0-9,.-]+)',
        r'([A-Z0-9]{1,2}\d{6,})',
        r'(\d{3,}[,.]\d{3})',
        r'([A-Z]{2}-\d{1,3}[,.]\d{3})',
    ]
    block_text = block.get_text()
    for pattern in id_patterns:
        match = re.search(pattern, block_text)
        if match:
            raw_id = match.group(1)
            logging.info(f"Block {idx}: Found ID '{raw_id}' using regex pattern '{pattern}'")
            return clean_id(raw_id), f"regex:{pattern}"
    # Nếu vẫn không tìm thấy, thử tìm trong tất cả các span có class chứa 'id' hoặc 'number'
    logging.debug(f"Block {idx}: No ID found with regex, trying span classes")
    for span in block.find_all('span'):
        class_names = span.get('class', [])
        if any('id' in name.lower() or 'number' in name.lower() for name in class_names):
            raw_id = span.get_text(strip=True)
            if raw_id:
                logging.info(f"Block {idx}: Found ID '{raw_id}' in span with classes {class_names}")
                return clean_id(raw_id), f"span_class:{class_names}"
    logging.warning(f"Block {idx}: No ID found using any method after trying {len(id_selectors)} selectors and data-st13.")
    return None, None

def extract_brand_name_from_block(block, idx: int) -> tuple[str, str]:
    el = block.select_one('.brandName')
    if el and el.get_text(strip=True):
        name = el.get_text(strip=True)
        logging.info(f"Block {idx}: Found brand name '{name}' using selector '.brandName'")
        return name, '.brandName'
    logging.warning(f"Block {idx}: Could not extract brand name with selector '.brandName'.")
    return None, None

def parse_wipo_html(html_content: str) -> List[Dict[str, Any]]: # sau khi ;lấy được toàn bộ html của phần li đó thì
    # nó bắt ép  phải trả về một list với nhiều dict bên trong

    soup = BeautifulSoup(html_content, 'html.parser') # nó lấy toàn bộ cái source đó và phần tích từng phần ra
    results = [] # tạo một cái result tí chứa dữ liệu
    
    # Find all result items
    # dùng cái select lấy toàn bộ dự liệu trong ul và li trong file html
    result_items = soup.select('ul.results.listView.ng-star-inserted > li.flex.result.wrap.ng-star-inserted')

    # duyệt toàn bộ từ cái ul li đó
    for item in result_items:
        # Skip empty items (no brand name)
        # lấy ra cái .brandName nó thấy đầu tiên
        brand_name_el = item.select_one('.brandName')
        if not brand_name_el: # nếu mà không có name thì bỏ qua phần dưới rồi tiếp tục chạy có thì chạy xuống dưới
            continue
            
        # Extract basic info
        trademark_id = item.get('data-st13', '') # thông qua key data- st13 lấy được trademark_id
        brand_name = brand_name_el.get_text(strip=True) # lấy brand name nếu có .brandName lấy text và toàn bộ khoảng trắng
        # chillll
        # Initialize result dict with required fields
        result = { # tạo một cái khung chứa dữ liệu
            'id': trademark_id, # có trade id rồi
            'name': brand_name, # trade name
            'owner': None, # chưa có thì cho là none
            'status': None, # chưa có thì cho là none
            'number': None, # chưa có thì cho là none
            'nice_class': None, # chưa có thì cho là none
            'country': None, # chưa có thì cho là none
            'ipr_type': None, # chưa có thì cho là none
            'logo': None # chưa có thì cho là none
        }
        
        # Extract owner
        # lấy dữ liệu owner từ select_ one
        owner_el = item.select_one('.owner span.value')
        if owner_el:
            result['owner'] = owner_el.get_text(strip=True) # sau khi lấy được dữ liệu rồi thì gán vào bảng
            
        # Extract status
        # lấy dữ liệu status_el
        status_el = item.select_one('.status span.value')
        if status_el:
            result['status'] = status_el.get_text(strip=True) # lấy được thì gán vào bảng
            
        # Extract number
        # lấy number lấy được dữ liệu thì gán vào bảng
        number_el = item.select_one('.number span.value')
        if number_el:
            result['number'] = number_el.get_text(strip=True)
            
        # Extract Nice class
        # nice class là cái éo gì ấy chưa biết à nó là cái nhóm lấy được thì lưu vào
        class_el = item.select_one('.class span.value')
        if class_el:
            result['nice_class'] = class_el.get_text(strip=True)
            
        # Extract country
        # lấy được dữ liệu coutry thì lưu vào
        country_el = item.select_one('.designation span.value')
        if country_el:
            result['country'] = country_el.get_text(strip=True)
            
        # Extract IPR type
        # lấy được dữ liệu ipr_el thì lưu vào
        ipr_el = item.select_one('.ipr span.value')
        if ipr_el:
            result['ipr_type'] = ipr_el.get_text(strip=True)
            
        # Extract logo if exists
        # lấy được logo thì in vào logo lạ vl
        logo_el = item.select_one('img.logo[src^="data:image"]')
        if logo_el:
            result['logo'] = logo_el.get('src')
            
        results.append(result)
        # sau đó append toàn bộ thông tin vào bảng result trả về result
    logging.info(f"Parser: Extracted {len(results)} valid trademark records from HTML")
    return results # trả về result nè

def get_brand_details_from_wipo_page(driver, item_id_st13: str) -> Dict[str, Any]:
    """
    Lấy thông tin chi tiết của nhãn hiệu từ trang chi tiết WIPO.
    
    Args:
        driver: Selenium WebDriver instance
        item_id_st13: ID của nhãn hiệu (data-st13)
        
    Returns:
        Dictionary chứa thông tin chi tiết của nhãn hiệu hoặc None nếu có lỗi
    """
    logging.info(f"Attempting to fetch details for ID (data-st13): {item_id_st13}")
    
    # Bước 1: Tạo URL từ data-st13
    formatted_id = None
    
    # Xử lý các định dạng ID khác nhau
    if item_id_st13.startswith("ES") and "M" in item_id_st13:
        # Format: ES5019940M1935158 -> ES-M1935158
        country_code = item_id_st13[:2]
        actual_id_part = item_id_st13[item_id_st13.find("M"):]
        formatted_id = f"{country_code}-{actual_id_part}"
    elif item_id_st13.startswith("KR"):
        # Format: KR5019940000123 -> KR-0000123
        country_code = item_id_st13[:2]
        actual_id_part = item_id_st13[-7:]  # Lấy 7 số cuối
        formatted_id = f"{country_code}-{actual_id_part}"
    elif item_id_st13.startswith("VN"):
        # Format: VN5019940000123 -> VN-0000123
        country_code = item_id_st13[:2]
        actual_id_part = item_id_st13[-7:]  # Lấy 7 số cuối
        formatted_id = f"{country_code}-{actual_id_part}"
    elif item_id_st13.startswith("IN"):
        # Format: IN502013002483811 -> IN-2483811
        country_code = item_id_st13[:2]
        actual_id_part = item_id_st13[-7:]  # Lấy 7 số cuối
        formatted_id = f"{country_code}-{actual_id_part}"
    else:
        # Fallback: sử dụng ID gốc nếu không nhận dạng được format
        formatted_id = item_id_st13
    
    if not formatted_id:
        logging.error(f"Could not determine formatted ID for URL from data-st13: {item_id_st13}")
        return None

    detail_url = f"https://branddb.wipo.int/branddb/en/showData.jsp?ID={formatted_id}"
    logging.info(f"Navigating to detail page: {detail_url}")

    try:
        driver.get(detail_url)
        
        # Đợi trang chi tiết tải
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.keyInformation"))
        )
        logging.info("Detail page loaded.")

        # Parse trang chi tiết
        details = {
            'id': item_id_st13,
            'name': None,
            'owner': None,
            'status': None,
            'registration_date': None,
            'nice_class': None,
            'country': None,
            'ipr_type': None,
            'logo': None
        }
        
        try:
            # Lấy tên thương hiệu
            brand_name_el = driver.find_element(By.CSS_SELECTOR, "h2.brandTitle")
            details['name'] = brand_name_el.text.strip()
        except NoSuchElementException:
            logging.warning(f"Could not find brand name on detail page for {formatted_id}")
        
        try:
            # Lấy chủ sở hữu
            owner_el = driver.find_element(By.XPATH, "//span[contains(text(), 'Owner')]/following-sibling::span")
            details['owner'] = owner_el.text.strip()
        except NoSuchElementException:
            logging.warning(f"Could not find owner on detail page for {formatted_id}")
        
        try:
            # Lấy trạng thái và ngày đăng ký
            status_el = driver.find_element(By.XPATH, "//span[contains(text(), 'Status')]/following-sibling::span")
            status_text = status_el.text.strip()
            # Tách trạng thái và ngày đăng ký
            if '(' in status_text:
                status, date = status_text.split('(', 1)
                details['status'] = status.strip()
                details['registration_date'] = date.rstrip(')').strip()
            else:
                details['status'] = status_text
        except NoSuchElementException:
            logging.warning(f"Could not find status on detail page for {formatted_id}")
        
        try:
            # Lấy lớp Nice
            nice_class_el = driver.find_element(By.XPATH, "//span[contains(text(), 'Nice Classification')]/following-sibling::span")
            details['nice_class'] = nice_class_el.text.strip()
        except NoSuchElementException:
            logging.warning(f"Could not find Nice class on detail page for {formatted_id}")
        
        try:
            # Lấy quốc gia
            country_el = driver.find_element(By.XPATH, "//span[contains(text(), 'Country')]/following-sibling::span")
            details['country'] = country_el.text.strip()
        except NoSuchElementException:
            logging.warning(f"Could not find country on detail page for {formatted_id}")
        
        try:
            # Lấy loại IPR
            ipr_el = driver.find_element(By.XPATH, "//span[contains(text(), 'IPR Type')]/following-sibling::span")
            details['ipr_type'] = ipr_el.text.strip()
        except NoSuchElementException:
            logging.warning(f"Could not find IPR type on detail page for {formatted_id}")
        
        try:
            # Lấy logo
            logo_el = driver.find_element(By.CSS_SELECTOR, "img.brandLogo")
            if logo_el and logo_el.get_attribute('src'):
                details['logo'] = logo_el.get_attribute('src')
        except NoSuchElementException:
            logging.warning(f"Could not find logo on detail page for {formatted_id}")
        
        logging.info(f"Successfully extracted details for {formatted_id}: {details.get('name')}")
        return details

    except TimeoutException:
        logging.error(f"Timeout loading detail page for {formatted_id}: {detail_url}")
        return None
    except Exception as e:
        logging.error(f"Error processing detail page for {formatted_id}: {e}")
        return None