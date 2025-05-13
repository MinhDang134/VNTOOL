from bs4 import BeautifulSoup
import logging
import re


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
        '.number span.value',  # Selector chính
        '.number',  # Fallback 1
        'span.value',  # Fallback 2
        '.brand-id',  # Fallback 3
        '.id-value',  # Fallback 4
        '[data-id]',  # Fallback 5 - tìm theo attribute
        '.result-item .id',  # Fallback 6
        '.result-item .number',  # Fallback 7
        '.result-item span.value',  # Fallback 8
    ]
    
    # Thử từng selector
    for selector in id_selectors:
        logging.debug(f"Block {idx}: Trying selector '{selector}'")
        element = block.select_one(selector)
        
        if element:
            # Lấy text từ element
            raw_id = element.get_text(strip=True)
            if raw_id:
                logging.info(f"Block {idx}: Found ID '{raw_id}' using selector '{selector}'")
                return clean_id(raw_id), selector
            
            # Nếu không có text, thử lấy từ attribute
            raw_id = element.get('data-id') or element.get('id')
            if raw_id:
                logging.info(f"Block {idx}: Found ID '{raw_id}' from attribute using selector '{selector}'")
                return clean_id(raw_id), selector
    
    # Nếu không tìm thấy bằng selector, thử tìm bằng regex
    logging.debug(f"Block {idx}: No ID found with selectors, trying regex patterns")
    
    # Các pattern regex để tìm ID
    id_patterns = [
        r'ID:\s*([A-Z0-9,.-]+)',  # Pattern 1: "ID: 123456"
        r'Number:\s*([A-Z0-9,.-]+)',  # Pattern 2: "Number: 123456"
        r'([A-Z0-9]{1,2}\d{6,})',  # Pattern 3: "M1234567"
        r'(\d{3,}[,.]\d{3})',  # Pattern 4: "123,456"
        r'([A-Z]{2}-\d{1,3}[,.]\d{3})',  # Pattern 5: "VN-1,234"
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
    
    logging.warning(f"Block {idx}: No ID found using any method")
    return None, None

def parse_wipo_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    # Lấy từng block kết quả
    result_blocks = soup.select("li.flex.result.wrap")
    if not result_blocks:
        logging.warning("Parser: No result blocks found with selector 'li.flex.result.wrap'. HTML might have changed or no results.")
        return items

    logging.info(f"Found {len(result_blocks)} result blocks to parse")

    for idx, block in enumerate(result_blocks):
        item_data = {}
        
        # Log the block we're processing
        logging.debug(f"Processing block {idx + 1}/{len(result_blocks)}")

        # Brand name
        brand_name_tag = block.select_one(".brandName")
        item_data["brand_name"] = brand_name_tag.text.strip() if brand_name_tag else None
        logging.debug(f"Block {idx + 1}: Brand name = {item_data['brand_name']}")

        # Owner
        owner_tag = block.select_one(".owner span.value")
        item_data["owner"] = owner_tag.text.strip() if owner_tag else None
        logging.debug(f"Block {idx + 1}: Owner = {item_data['owner']}")

        # Extract ID using improved logic
        id_value, selector_used = extract_id_from_block(block, idx)
        item_data["application_or_registration_number"] = id_value
        if id_value:
            logging.info(f"Block {idx + 1}: Using ID '{id_value}' (found with selector: {selector_used})")
        else:
            logging.warning(f"Block {idx + 1}: Failed to extract ID")

        # Status & Registration date
        status_tag = block.select_one(".status span.value")
        parsed_status = None
        parsed_registration_date = None
        if status_tag:
            status_text = status_tag.text.strip()
            parts = status_text.split("(")
            parsed_status = parts[0].strip()
            if len(parts) > 1:
                parsed_registration_date = parts[-1].rstrip(")").strip()
        item_data["status"] = parsed_status
        item_data["registration_date"] = parsed_registration_date
        logging.debug(f"Block {idx + 1}: Status = {parsed_status}, Registration date = {parsed_registration_date}")

        # Product group (Nice class)
        product_group_tag = block.select_one(".class span.value")
        item_data["product_group"] = product_group_tag.text.strip() if product_group_tag else None
        logging.debug(f"Block {idx + 1}: Product group = {item_data['product_group']}")

        # Image/logo
        image_tag = block.select_one("img.logo")
        item_data["image_url"] = image_tag.get("src") if image_tag and image_tag.has_attr('src') else None
        logging.debug(f"Block {idx + 1}: Image URL = {item_data['image_url']}")

        # Tạo ID: Ưu tiên "number". Nếu không có, fallback nhưng log cảnh báo.
        generated_id = item_data.get("application_or_registration_number")
        if not generated_id:
            temp_id_name = str(item_data.get("brand_name", "")).strip()
            temp_id_owner = str(item_data.get("owner", "")).strip()
            if temp_id_name or temp_id_owner:
                generated_id = f"{temp_id_name}_{temp_id_owner}"
                logging.warning(
                    f"Parser: Block {idx + 1}: 'application_or_registration_number' not found. Using fallback ID '{generated_id}'. This might not be unique.")
            else:
                generated_id = f"temp_wipo_id_{idx}_{hash(str(block))}"
                logging.error(
                    f"Parser: Block {idx + 1}: Critical lack of data for ID generation. Using highly temporary ID: {generated_id}")

        # Kiểm tra xem các trường cần thiết cho DB có tồn tại không trước khi thêm
        if not generated_id or not item_data.get("brand_name"):
            logging.warning(
                f"Parser: Skipping item for block {idx + 1} due to missing critical data (ID or Name). ID: {generated_id}, Name: {item_data.get('brand_name')}")
            continue

        items.append({
            "id": generated_id,
            "name": item_data.get("brand_name"),
            "owner": item_data.get("owner"),
            "product_group": item_data.get("product_group"),
            "status": item_data.get("status"),
            "registration_date": item_data.get("registration_date"),
            "image_url": item_data.get("image_url"),
            "original_number": item_data.get("application_or_registration_number")
        })

    logging.info(f"Parser: Successfully parsed {len(items)} items from {len(result_blocks)} blocks.")
    return items