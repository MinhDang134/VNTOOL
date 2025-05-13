from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Date, DateTime
from datetime import datetime

Base = declarative_base()

def get_brand_model(table_name):
    class Brand(Base):
        __tablename__ = table_name
        id = Column(String, primary_key=True)
        name = Column(String)
        product_group = Column(String)
        status = Column(String)
        registration_date = Column(Date)
        image_url = Column(String)
        source = Column(String)
        created_at = Column(DateTime, default=datetime.utcnow)
    return Brand