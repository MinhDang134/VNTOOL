from bs4 import BeautifulSoup
import logging
import re
from typing import List, Dict, Any
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException


# Cấu hình logging nếu chưa có ở đâu khác (ví dụ: trong main.py)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clean_id(raw_id: str) -> str:
    """Clean and validate ID from WIPO.
    Handles various ID formats:
    - Numeric IDs with commas (e.g., "545,892")
    - Alphanumeric IDs (e.g., "M1935158")
    - IDs with hyphens (e.g., "VN-1234")
    - Mixed format IDs
    """
    if not raw_id:
        logging.debug("clean_id: Empty raw_id received")
        return None
    
    # Log the input
    logging.debug(f"clean_id: Processing raw_id: '{raw_id}'")
    
    # Remove extra whitespace
    cleaned = raw_id.strip()
    logging.debug(f"clean_id: After strip: '{cleaned}'")
    
    # Handle numeric IDs with commas
    if ',' in cleaned:
        # Check if it's a numeric ID with commas
        numeric_part = cleaned.replace(',', '')
        if numeric_part.isdigit():
            cleaned = numeric_part
            logging.debug(f"clean_id: Removed commas from numeric ID: '{cleaned}'")
        else:
            logging.debug(f"clean_id: ID contains commas but is not purely numeric, keeping commas: '{cleaned}'")
    
    # Validate the cleaned ID
    if not cleaned:
        logging.warning("clean_id: Empty ID after cleaning")
        return None
        
    # Log the final result
    logging.debug(f"clean_id: Final cleaned ID: '{cleaned}'")
    
    return cleaned

def extract_id_from_block(block, idx: int) -> tuple[str, str]:
    """Extract ID from a block using multiple strategies."""
    logging.info(f"Block {idx}: Starting ID extraction")
    logging.debug(f"Block {idx} HTML: {block.prettify()}")
    
    # Danh sách các selector để thử, theo thứ tự ưu tiên
    id_selectors = [
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
    for selector_index, selector in enumerate(id_selectors):
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

def parse_wipo_html(html_content: str) -> List[Dict[str, Any]]:
    """
    Parse HTML content from WIPO search results page.
    
    Args:
        html_content: HTML string from WIPO search results page
        
    Returns:
        List of dictionaries containing extracted trademark information
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    # Find all result items
    result_items = soup.select('ul.results.listView.ng-star-inserted > li.flex.result.wrap.ng-star-inserted')
    
    for item in result_items:
        # Skip empty items (no brand name)
        brand_name_el = item.select_one('.brandName')
        if not brand_name_el:
            continue
            
        # Extract basic info
        trademark_id = item.get('data-st13', '')
        brand_name = brand_name_el.get_text(strip=True)
        
        # Initialize result dict with required fields
        result = {
            'id': trademark_id,
            'name': brand_name,
            'owner': None,
            'status': None,
            'number': None,
            'nice_class': None,
            'country': None,
            'ipr_type': None,
            'logo': None
        }
        
        # Extract owner
        owner_el = item.select_one('.owner span.value')
        if owner_el:
            result['owner'] = owner_el.get_text(strip=True)
            
        # Extract status
        status_el = item.select_one('.status span.value')
        if status_el:
            result['status'] = status_el.get_text(strip=True)
            
        # Extract number
        number_el = item.select_one('.number span.value')
        if number_el:
            result['number'] = number_el.get_text(strip=True)
            
        # Extract Nice class
        class_el = item.select_one('.class span.value')
        if class_el:
            result['nice_class'] = class_el.get_text(strip=True)
            
        # Extract country
        country_el = item.select_one('.designation span.value')
        if country_el:
            result['country'] = country_el.get_text(strip=True)
            
        # Extract IPR type
        ipr_el = item.select_one('.ipr span.value')
        if ipr_el:
            result['ipr_type'] = ipr_el.get_text(strip=True)
            
        # Extract logo if exists
        logo_el = item.select_one('img.logo[src^="data:image"]')
        if logo_el:
            result['logo'] = logo_el.get('src')
            
        results.append(result)
        
    logging.info(f"Parser: Extracted {len(results)} valid trademark records from HTML")
    return results

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