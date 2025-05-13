from database.connection import Session, engine
from database.models import get_brand_model, Base
from monitor.logger import log_change
from crawlers.vietnam import fetch_status_vietnam
from crawlers.wipo import fetch_status_from_site

def monitor_in_progress_brands():
    session = Session()
    for month in ["2024_04", "2024_05"]:
        Brand = get_brand_model(f"brand_{month}")
        Base.metadata.create_all(engine)
        brands = session.query(Brand).filter(Brand.status == "Đang giải quyết").all()
        for b in brands:
            current_source = b.source
            if current_source == "WIPO":
                new_status = fetch_status_from_site(b.id)
            elif current_source == "VietnamTrademark":
                new_status = fetch_status_vietnam(b.id)
            else:
                continue

            if new_status and new_status != b.status:
                log_change(b.id, b.status, new_status)
                b.status = new_status
        session.commit()