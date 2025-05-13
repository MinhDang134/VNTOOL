from bs4 import BeautifulSoup
import logging


# Cấu hình logging nếu chưa có ở đâu khác (ví dụ: trong main.py)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_wipo_html(html: str)-> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    # Cần xác minh selector này dựa trên HTML thực tế của trang kết quả WIPO
    result_blocks = soup.select("div.brandName")
    if not result_blocks:
        logging.warning(
            "Parser: No result blocks found with selector 'li.result-viewed'. HTML might have changed or no results.")
        return items

    for idx, block in enumerate(result_blocks):
        item_data = {}  # Sử dụng dictionary để thu thập dữ liệu cho mỗi item

        try:
            # Cần xác minh selector div.brandName
            brand_name_tag = block.select_one("div.brandName")
            item_data["brand_name"] = brand_name_tag.text.strip() if brand_name_tag else None
        except Exception as e:
            logging.error(f"Parser: Error parsing brand_name for block {idx}: {e}", exc_info=True)
            item_data["brand_name"] = None

        try:
            # Cần xác minh selector .owner span.value
            owner_tag = block.select_one(".owner span.value")
            item_data["owner"] = owner_tag.text.strip() if owner_tag else None
        except Exception as e:
            logging.error(f"Parser: Error parsing owner for block {idx}: {e}", exc_info=True)
            item_data["owner"] = None

        status_text_from_html = None
        try:
            # Cần xác minh selector .status .value
            # Selector này có thể chứa cả status và ngày, ví dụ: "Registered (2020-01-01)"
            status_value_tag = block.select_one(".status .value")
            parsed_status = None
            parsed_registration_date = None

            if status_value_tag:
                status_text_from_html = status_value_tag.text.strip()
                parts = status_text_from_html.split("(")
                parsed_status = parts[0].strip()
                if len(parts) > 1:
                    parsed_registration_date = parts[-1].rstrip(")").strip()

            item_data["status"] = parsed_status
            item_data["registration_date"] = parsed_registration_date
        except Exception as e:
            logging.error(
                f"Parser: Error parsing status/registration_date (from text: '{status_text_from_html}') for block {idx}: {e}",
                exc_info=True)
            item_data["status"] = None
            item_data["registration_date"] = None

        try:
            # Cần xác minh selector img (có thể cần cụ thể hơn, ví dụ: img.mark-logo)
            image_tag = block.select_one("img")
            item_data["image_url"] = image_tag.get("src") if image_tag and image_tag.has_attr('src') else None
        except Exception as e:
            logging.error(f"Parser: Error parsing image_url for block {idx}: {e}", exc_info=True)
            item_data["image_url"] = None

        try:
            # Cần xác minh selector .label.niceclass + span.value
            # Đây là selector khá cụ thể, hãy kiểm tra kỹ HTML.
            # Một cách tiếp cận khác là tìm label bằng text rồi tìm sibling.
            product_group_tag = block.select_one(".label.niceclass + span.value")
            item_data["product_group"] = product_group_tag.text.strip() if product_group_tag else None
        except Exception as e:
            logging.error(f"Parser: Error parsing product_group for block {idx}: {e}", exc_info=True)
            item_data["product_group"] = None

        try:
            # Cần xác minh selector .number span.value
            number_tag = block.select_one(".number span.value")
            item_data[
                "application_or_registration_number"] = number_tag.text.strip() if number_tag else None  # Đổi tên cho rõ nghĩa
        except Exception as e:
            logging.error(f"Parser: Error parsing number for block {idx}: {e}", exc_info=True)
            item_data["application_or_registration_number"] = None

        # Tạo ID: Ưu tiên "number". Nếu không có, fallback nhưng log cảnh báo.
        # `item_data.get("application_or_registration_number")` là số đơn/số đăng ký
        generated_id = item_data.get("application_or_registration_number")
        if not generated_id:
            # Fallback ID: kết hợp tên thương hiệu và chủ sở hữu (có thể không duy nhất)
            temp_id_name = str(item_data.get("brand_name", "")).strip()
            temp_id_owner = str(item_data.get("owner", "")).strip()
            if temp_id_name or temp_id_owner:
                generated_id = f"{temp_id_name}_{temp_id_owner}"
                logging.warning(
                    f"Parser: Block {idx}: 'application_or_registration_number' not found. Using fallback ID '{generated_id}'. This might not be unique.")
            else:
                # Nếu không có thông tin gì cả, tạo ID dựa trên hash của block HTML để tránh trùng lặp trong 1 lần parse
                generated_id = f"temp_wipo_id_{idx}_{hash(str(block))}"
                logging.error(
                    f"Parser: Block {idx}: Critical lack of data for ID generation. Using highly temporary ID: {generated_id}")

        # Kiểm tra xem các trường cần thiết cho DB có tồn tại không trước khi thêm
        # Ví dụ: nếu 'id' và 'name' là bắt buộc trong DB
        if not generated_id or not item_data.get("brand_name"):
            logging.warning(
                f"Parser: Skipping item for block {idx} due to missing critical data (ID or Name). ID: {generated_id}, Name: {item_data.get('brand_name')}")
            continue

        items.append({
            "id": generated_id,
            "name": item_data.get("brand_name"),
            "owner": item_data.get("owner"),  # Thêm owner vào dictionary để lưu trữ
            "product_group": item_data.get("product_group"),
            "status": item_data.get("status"),
            "registration_date": item_data.get("registration_date"),
            "image_url": item_data.get("image_url"),
            "original_number": item_data.get("application_or_registration_number")  # Giữ lại số gốc nếu ID có thể khác
        })

    logging.info(f"Parser: Parsed {len(items)} items from HTML.")
    return items