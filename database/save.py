# /home/minhdangpy134/DuAnWipoVNmark/database/save.py
import logging
from sqlalchemy.exc import SQLAlchemyError

# from datetime import datetime # Nếu bạn cần chuyển đổi ngày tháng

# Cấu hình logger cho module này (nếu chưa có logger chung)
logger = logging.getLogger(__name__)


# logging.basicConfig(level=logging.INFO) # Cấu hình cơ bản nếu cần test riêng file này

def save_to_db(db_session, ModelClass, items_to_save: list, source_name: str = "DefaultSource"):
    """
    Lưu một danh sách các mục đã được parse vào database.
    Quản lý commit và rollback cho cả batch.

    Args:
        db_session: Phiên làm việc (session) của SQLAlchemy.
        ModelClass: Class của model SQLAlchemy để tạo instance.
        items_to_save: Danh sách các dictionary, mỗi dict chứa dữ liệu cho một item.
        source_name: Tên nguồn dữ liệu (ví dụ: "VietnamTrademark", "WIPO_Search").
    """
    saved_count = 0
    processed_count = 0

    if not items_to_save:
        logger.info(f"DB Save ({source_name}): No items provided to save.")
        return

    for item_detail in items_to_save:
        processed_count += 1
        item_id = item_detail.get("id")  # Lấy ID từ item_detail
        item_name = item_detail.get("name", "N/A")

        if not item_id:  # ID là bắt buộc để merge
            logger.error(f"DB Save ({source_name}): Item skipped due to missing ID. Name: '{item_name}'")
            continue

        try:
            # Chuẩn bị dữ liệu cho model instance
            # Đảm bảo các key trong item_detail khớp với các cột trong ModelClass
            # và kiểu dữ liệu tương thích.
            instance_data = {
                "id": item_id,
                "name": item_name,
                "product_group": item_detail.get("product_group"),
                "status": item_detail.get("status"),
                "image_url": item_detail.get("image_url"),
                "source": source_name
                # Thêm các trường khác nếu ModelClass của bạn có
                # "owner": item_detail.get("owner"),
                # "original_number": item_detail.get("original_number")
            }

            # Xử lý registration_date (ví dụ: chuyển từ string sang Date object nếu cần)
            # Model `Brand` trong `get_brand_model` của bạn định nghĩa `registration_date = Column(Date)`
            reg_date_str = item_detail.get("registration_date")
            if reg_date_str:
                # Bạn cần một hàm để parse chuỗi ngày tháng này thành đối tượng date
                # Ví dụ: nếu định dạng là 'DD/MM/YYYY' hoặc 'YYYY-MM-DD'
                # from shared.utils import parse_date_string # Giả sử bạn có hàm tiện ích
                # instance_data["registration_date"] = parse_date_string(reg_date_str)
                # Nếu không có hàm parse, và dữ liệu đã là đối tượng date thì không cần
                # Nếu là string, và model yêu cầu Date, bạn sẽ gặp lỗi ở dòng model_instance = ModelClass(**instance_data)
                # Tạm thời gán thẳng, nhưng cần đảm bảo kiểu dữ liệu đúng.
                instance_data[
                    "registration_date"] = reg_date_str  # CẢNH BÁO: Cần chuyển đổi sang Date object nếu model yêu cầu!
                # Ví dụ: datetime.strptime(reg_date_str, '%d/%m/%Y').date()
                # Hoặc nếu nó đã là đối tượng Date thì không sao.

            model_instance = ModelClass(**instance_data)
            db_session.merge(model_instance)  # Merge để INSERT hoặc UPDATE dựa trên primary key 'id'

            # Nếu bạn có logic cụ thể sau khi merge cho từng loại (ví dụ WIPO khác Vietnam)
            # bạn có thể gọi một hàm khác ở đây, hoặc để logic đó trong crawler.
            # Ví dụ: upsert_trademark_master(db_session.bind, item_detail, source_name)
            # Hiện tại, hàm này là hàm lưu trữ chung.

            saved_count += 1
        except SQLAlchemyError as e_sql:  # Bắt lỗi SQLAlchemy cụ thể
            db_session.rollback()  # Quan trọng: rollback cho item lỗi này
            logger.error(
                f"DB Save ({source_name}): SQLAlchemyError processing item (ID: {item_id}, Name: {item_name}). Rolled back. Error: {e_sql}",
                exc_info=True)
        except Exception as e:  # Bắt các lỗi khác (ví dụ: lỗi kiểu dữ liệu khi gán vào model)
            db_session.rollback()
            logger.error(
                f"DB Save ({source_name}): General error processing item (ID: {item_id}, Name: {item_name}). Rolled back. Error: {e}",
                exc_info=True)

    if saved_count > 0:
        try:
            db_session.commit()
            logger.info(
                f"DB Save ({source_name}): Successfully committed {saved_count} out of {processed_count} processed items to DB.")
        except SQLAlchemyError as e_commit:
            logger.error(
                f"DB Save ({source_name}): SQLAlchemyError committing batch to DB. Rolling back. Error: {e_commit}",
                exc_info=True)
            db_session.rollback()
        except Exception as e_commit_other:
            logger.error(
                f"DB Save ({source_name}): General error committing batch to DB. Rolling back. Error: {e_commit_other}",
                exc_info=True)
            db_session.rollback()
    elif processed_count > 0:  # Đã xử lý item nhưng không có item nào được lưu thành công
        logger.info(
            f"DB Save ({source_name}): No items were successfully processed to commit out of {processed_count} items.")
    # else: (Đã log ở đầu hàm nếu items_to_save rỗng)