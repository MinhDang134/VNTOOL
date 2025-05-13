import logging
from datetime import datetime

logging.basicConfig(filename="logs/brand_monitor.log", level=logging.INFO)

def log_change(brand_id, old_status, new_status):
    logging.info(f"{brand_id}: {old_status} → {new_status} @ {datetime.now()}")