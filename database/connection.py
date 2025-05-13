from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL # Import từ config.py đã đúng

engine = create_engine(DATABASE_URL)

# Session này là một factory, bạn sẽ gọi Session() để tạo một phiên làm việc
Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)