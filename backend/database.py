"""数据库连接模块"""
import pymysql
from sqlalchemy import create_engine
from contextlib import contextmanager

# 数据库配置
DB_CONFIG = {
    'host': '124.222.100.24',
    'port': 3306,
    'user': 'root_remote',
    'password': '0519mmwan$&PYJ',
    'database': 'Mydatabase',
    'charset': 'utf8mb4'
}

# SQLAlchemy 引擎
engine = create_engine(
    f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset={DB_CONFIG['charset']}",
    pool_pre_ping=True,
    pool_recycle=3600
)

@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()

def test_connection():
    """测试数据库连接"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            return True, '数据库连接成功'
    except Exception as e:
        return False, f'数据库连接失败: {str(e)}'
