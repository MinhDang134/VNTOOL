from bs4 import BeautifulSoup # là phường thức có thể bóc tách dữ liệu ra từ html
import logging # dùng để hiện thông báo
import re # cung cấp biểu thức chính quy để tương tác với html
from typing import List, Dict, Any, Optional # là kiểu dữ liệu cũng cấp những kiểu dữ liệu dùng cho nhiều trường hợp
from selenium.webdriver.support.ui import WebDriverWait # cái này dùng cái này sẽ dùng để đợi một điều kiện cụ thể cho đến khi nó chạy xong thì sẽ đến cái khác
from selenium.webdriver.support import expected_conditions as EC # cung cấp tập hợp các điều kiện trước khi chạy webDriverWait
from selenium.webdriver.common.by import By # phương thức này sẽ dùng để chỉ định tìm kiếm những phần tử nào trên trang web
from selenium.common.exceptions import NoSuchElementException, TimeoutException
# NoSuchElementEXception : được lém ra khi không tìm thấy phần tử trong mảng
# TimeoutException : nó có chức năng là hiển thị lỗi nếu mà trong thời gian quy định chưa lấy được dữ liệu
import requests
import json
#chilll

# Cấu hình logging nếu chưa có ở đâu khác (ví dụ: trong main.py)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# hàm clean_id được truyền tham số raw_id và và phải trả ra kiểu str
def clean_id(raw_id: str) -> str:
    if not raw_id:
        logging.debug("clean_id: Không nhận được raw_id")
        return None
    
    logging.debug(f"clean_id: Đang xử lý raw_id: '{raw_id}'")
    
    cleaned = raw_id.strip()
    logging.debug(f"clean_id: Sau khi loại bỏ khoảng trắng: '{cleaned}'")
    
    if ',' in cleaned:
        numeric_part = cleaned.replace(',', '')
        if numeric_part.isdigit():
            cleaned = numeric_part
            logging.debug(f"clean_id: Đã xóa dấu phẩy từ ID số: '{cleaned}'")
        else:
            logging.debug(f"clean_id: ID chứa dấu phẩy nhưng không phải là số thuần túy, giữ nguyên dấu phẩy: '{cleaned}'")
            
    if not cleaned:
        logging.warning("clean_id: ID trống sau khi làm sạch")
        return None
        
    logging.debug(f"clean_id: ID cuối cùng sau khi làm sạch: '{cleaned}'")
    return cleaned


# một có tên là extract_id_from_clock  với tham số là block và id trả về kiểu tuple mảng hai chiều
# Cái tuple này nó sẽ chứa cái id của cái được làm sạch đó và cách để làm sạch
def extract_id_from_block(block, idx: int) -> tuple[str, str]:
    logging.info(f"Block {idx}: Bắt đầu trích xuất ID")
    logging.debug(f"Block {idx} HTML: {block.prettify()}")
    
    id_selectors = [
        '.number span.value',
        '.number',
        'span.value',
        '.brand-id',
        '.id-value',
        '[data-id]',
        '.result-item .id',
        '.result-item .number',
        '.result-item span.value',
        'div.id-section > span',
        '.application-number',
        'td.id-cell',
        'span[id]',
        'div[id]',
    ]
    
    for selector_index, selector in enumerate(id_selectors):
        element = block.select_one(selector)
        if element:
            raw_id = element.get_text(strip=True)
            logging.info(f"Block {idx}: Đã tìm thấy selector '{selector}' (lần thử {selector_index + 1}): '{raw_id}'")
            if raw_id:
                return clean_id(raw_id), selector
            raw_id = element.get('data-id') or element.get('id')
            if raw_id:
                logging.info(f"Block {idx}: Đã tìm thấy thuộc tính từ selector '{selector}' (lần thử {selector_index + 1}): '{raw_id}'")
                return clean_id(raw_id), selector
        else:
            logging.debug(f"Block {idx}: Không tìm thấy gì với selector '{selector}' (lần thử {selector_index + 1}).")
    
    data_st13 = block.get('data-st13')
    if data_st13:
        logging.info(f"Block {idx}: Đã tìm thấy ID từ thuộc tính data-st13: '{data_st13}'")
        return clean_id(data_st13), 'data-st13'
    
    logging.debug(f"Block {idx}: Không tìm thấy ID với các selector, đang thử với regex")
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
            logging.info(f"Block {idx}: Đã tìm thấy ID '{raw_id}' sử dụng mẫu regex '{pattern}'")
            return clean_id(raw_id), f"regex:{pattern}"
            
    logging.debug(f"Block {idx}: Không tìm thấy ID với regex, đang thử với các class span")
    for span in block.find_all('span'):
        class_names = span.get('class', [])
        if any('id' in name.lower() or 'number' in name.lower() for name in class_names):
            raw_id = span.get_text(strip=True)
            if raw_id:
                logging.info(f"Block {idx}: Đã tìm thấy ID '{raw_id}' trong span với các class {class_names}")
                return clean_id(raw_id), f"span_class:{class_names}"
                
    logging.warning(f"Block {idx}: Không tìm thấy ID bằng bất kỳ phương pháp nào sau khi thử {len(id_selectors)} selector và data-st13.")
    return None, None

def extract_brand_name_from_block(block, idx: int) -> tuple[str, str]:
    el = block.select_one('.brandName')
    if el and el.get_text(strip=True):
        name = el.get_text(strip=True)
        logging.info(f"Block {idx}: Đã tìm thấy tên thương hiệu '{name}' sử dụng selector '.brandName'")
        return name, '.brandName'
    logging.warning(f"Block {idx}: Không thể trích xuất tên thương hiệu với selector '.brandName'.")
    return None, None

def parse_wipo_html(html_content: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    result_items = soup.select('ul.results.listView.ng-star-inserted > li.flex.result.wrap.ng-star-inserted')

    for item in result_items:
        brand_name_el = item.select_one('.brandName')
        if not brand_name_el:
            continue
            
        trademark_id = item.get('data-st13', '')
        brand_name = brand_name_el.get_text(strip=True)
        
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
        
        owner_el = item.select_one('.owner span.value')
        if owner_el:
            result['owner'] = owner_el.get_text(strip=True)
            
        status_el = item.select_one('.status span.value')
        if status_el:
            result['status'] = status_el.get_text(strip=True)
            
        number_el = item.select_one('.number span.value')
        if number_el:
            result['number'] = number_el.get_text(strip=True)
            
        class_el = item.select_one('.class span.value')
        if class_el:
            result['nice_class'] = class_el.get_text(strip=True)
            
        country_el = item.select_one('.designation span.value')
        if country_el:
            result['country'] = country_el.get_text(strip=True)
            
        ipr_el = item.select_one('.ipr span.value')
        if ipr_el:
            result['ipr_type'] = ipr_el.get_text(strip=True)
            
        logo_el = item.select_one('img.logo[src^="data:image"]')
        if logo_el:
            result['logo'] = logo_el.get('src')
            
        results.append(result)
        
    logging.info(f"Parser: Đã trích xuất {len(results)} bản ghi nhãn hiệu hợp lệ từ HTML")
    return results

def get_brand_details_from_wipo_page(driver, item_id_st13: str) -> Dict[str, Any]:
    logging.info(f"Đang cố gắng lấy thông tin chi tiết cho ID (data-st13): {item_id_st13}")
    
    formatted_id = None
    
    if item_id_st13.startswith("ES") and "M" in item_id_st13:
        country_code = item_id_st13[:2]
        actual_id_part = item_id_st13[item_id_st13.find("M"):]
        formatted_id = f"{country_code}-{actual_id_part}"
    elif item_id_st13.startswith("KR"):
        country_code = item_id_st13[:2]
        actual_id_part = item_id_st13[-7:]
        formatted_id = f"{country_code}-{actual_id_part}"
    elif item_id_st13.startswith("VN"):
        country_code = item_id_st13[:2]
        actual_id_part = item_id_st13[-7:]
        formatted_id = f"{country_code}-{actual_id_part}"
    elif item_id_st13.startswith("IN"):
        country_code = item_id_st13[:2]
        actual_id_part = item_id_st13[-7:]
        formatted_id = f"{country_code}-{actual_id_part}"
    else:
        formatted_id = item_id_st13
    
    if not formatted_id:
        logging.error(f"Không thể xác định ID đã định dạng cho URL từ data-st13: {item_id_st13}")
        return None

    detail_url = f"https://branddb.wipo.int/branddb/en/showData.jsp?ID={formatted_id}"
    logging.info(f"Đang điều hướng đến trang chi tiết: {detail_url}")

    try:
        driver.get(detail_url)
        
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.keyInformation"))
        )
        logging.info("Trang chi tiết đã tải xong.")

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
            brand_name_el = driver.find_element(By.CSS_SELECTOR, "h2.brandTitle")
            details['name'] = brand_name_el.text.strip()
        except NoSuchElementException:
            logging.warning(f"Không tìm thấy tên thương hiệu trên trang chi tiết cho {formatted_id}")
        
        try:
            owner_el = driver.find_element(By.XPATH, "//span[contains(text(), 'Owner')]/following-sibling::span")
            details['owner'] = owner_el.text.strip()
        except NoSuchElementException:
            logging.warning(f"Không tìm thấy chủ sở hữu trên trang chi tiết cho {formatted_id}")
        
        try:
            status_el = driver.find_element(By.XPATH, "//span[contains(text(), 'Status')]/following-sibling::span")
            status_text = status_el.text.strip()
            if '(' in status_text:
                status, date = status_text.split('(', 1)
                details['status'] = status.strip()
                details['registration_date'] = date.rstrip(')').strip()
            else:
                details['status'] = status_text
        except NoSuchElementException:
            logging.warning(f"Không tìm thấy trạng thái trên trang chi tiết cho {formatted_id}")
        
        try:
            nice_class_el = driver.find_element(By.XPATH, "//span[contains(text(), 'Nice Classification')]/following-sibling::span")
            details['nice_class'] = nice_class_el.text.strip()
        except NoSuchElementException:
            logging.warning(f"Không tìm thấy phân loại Nice trên trang chi tiết cho {formatted_id}")
        
        try:
            country_el = driver.find_element(By.XPATH, "//span[contains(text(), 'Country')]/following-sibling::span")
            details['country'] = country_el.text.strip()
        except NoSuchElementException:
            logging.warning(f"Không tìm thấy quốc gia trên trang chi tiết cho {formatted_id}")
        
        try:
            ipr_el = driver.find_element(By.XPATH, "//span[contains(text(), 'IPR Type')]/following-sibling::span")
            details['ipr_type'] = ipr_el.text.strip()
        except NoSuchElementException:
            logging.warning(f"Không tìm thấy loại IPR trên trang chi tiết cho {formatted_id}")
        
        try:
            logo_el = driver.find_element(By.CSS_SELECTOR, "img.brandLogo")
            if logo_el and logo_el.get_attribute('src'):
                details['logo'] = logo_el.get_attribute('src')
        except NoSuchElementException:
            logging.warning(f"Không tìm thấy logo trên trang chi tiết cho {formatted_id}")
        
        logging.info(f"Đã trích xuất thành công thông tin chi tiết cho {formatted_id}: {details.get('name')}")
        return details

    except TimeoutException:
        logging.error(f"Quá thời gian chờ tải trang chi tiết cho {formatted_id}: {detail_url}")
        return None
    except Exception as e:
        logging.error(f"Lỗi khi xử lý trang chi tiết cho {formatted_id}: {e}")
        return None

class WipoParser:
    """
    Class để parse dữ liệu từ trang web WIPO
    """
    
    def __init__(self):
        """
        Khởi tạo WipoParser
        """
        pass
        
    def parse_trademark_details(self, html: str) -> Dict[str, Any]:
        """
        Parse thông tin chi tiết nhãn hiệu từ HTML
        
        Args:
            html: Chuỗi HTML chứa thông tin nhãn hiệu
            
        Returns:
            Dict chứa thông tin chi tiết nhãn hiệu
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Lấy thông tin cơ bản
            trademark_id = self._get_text(soup, '.trademark-id')
            name = self._get_text(soup, '.trademark-name')
            owner = self._get_text(soup, '.trademark-owner')
            status = self._get_text(soup, '.trademark-status')
            
            # Lấy ngày đăng ký và hết hạn
            registration_date = self._get_text(soup, '.registration-date')
            expiration_date = self._get_text(soup, '.expiration-date')
            
            # Lấy danh sách lớp sản phẩm/dịch vụ
            classes = self._get_classes(soup)
            
            return {
                "id": trademark_id,
                "name": name,
                "owner": owner,
                "status": status,
                "registration_date": registration_date,
                "expiration_date": expiration_date,
                "classes": classes
            }
            
        except Exception as e:
            print(f"Lỗi khi parse thông tin chi tiết: {str(e)}")
            return {}
            
    def _get_text(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        """
        Lấy text từ element được chọn
        
        Args:
            soup: BeautifulSoup object
            selector: CSS selector để chọn element
            
        Returns:
            Text của element hoặc None nếu không tìm thấy
        """
        element = soup.select_one(selector)
        return element.text.strip() if element else None
        
    def _get_classes(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        Lấy danh sách lớp sản phẩm/dịch vụ
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            List các dict chứa thông tin lớp
        """
        classes = []
        class_elements = soup.select('.trademark-class')
        
        for element in class_elements:
            class_info = {
                "number": self._get_text(element, '.class-number'),
                "description": self._get_text(element, '.class-description')
            }
            classes.append(class_info)
            
        return classes

def fetch_wipo_data(start_date: str, end_date: str, rows: int = 30, start: int = 0) -> List[Dict[str, Any]]:
    """
    Lấy dữ liệu nhãn hiệu trực tiếp từ API của WIPO
    
    Args:
        start_date: Ngày bắt đầu theo định dạng YYYY-MM-DD
        end_date: Ngày kết thúc theo định dạng YYYY-MM-DD
        rows: Số kết quả trên mỗi trang
        start: Vị trí bắt đầu cho phân trang
        
    Returns:
        Danh sách các bản ghi nhãn hiệu
    """
    url = "https://branddb.wipo.int/branddb/jaxrs/advancedsearch/search"
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://branddb.wipo.int",
        "Referer": "https://branddb.wipo.int/en/advancedsearch/results",
    }
    
    payload = {
        "asStructure": {
            "_id": "ea9e",
            "boolean": "AND",
            "bricks": [
                {
                    "_id": "ea9f",
                    "key": "appDate",
                    "strategy": "Range",
                    "value": [start_date, end_date]
                }
            ]
        },
        "strategy": "concept",
        "sort": "score desc",
        "rows": rows,
        "start": start
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        data = response.json()
        docs = data.get("docs", [])
        
        results = []
        for doc in docs:
            result = {
                'id': doc.get('id', ''),
                'name': doc.get('mn', ''),  # mn = tên nhãn hiệu
                'owner': doc.get('on', ''),  # on = tên chủ sở hữu
                'status': doc.get('st', ''),  # st = trạng thái
                'number': doc.get('an', ''),  # an = số đơn đăng ký
                'nice_class': doc.get('nc', ''),  # nc = phân loại Nice
                'country': doc.get('co', ''),  # co = quốc gia
                'ipr_type': doc.get('it', ''),  # it = loại sở hữu trí tuệ
                'logo': doc.get('im', '')  # im = hình ảnh
            }
            results.append(result)
            
        logging.info(f"Đã lấy thành công {len(results)} bản ghi từ API WIPO")
        return results
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Lỗi khi lấy dữ liệu từ API WIPO: {str(e)}")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Lỗi khi phân tích phản hồi JSON từ API WIPO: {str(e)}")
        return []
    except Exception as e:
        logging.error(f"Lỗi không mong muốn khi lấy dữ liệu WIPO: {str(e)}")
        return []