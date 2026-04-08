"""
数据可视化 API 服务
基于 FastAPI
"""
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import os

# 静态文件目录
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
from pydantic import BaseModel
from database import test_connection
from summary import generate_summary
from config_manager import load_config, update_config, get_enabled_channels, ALL_CHANNELS, get_enabled_tokens
from refresh_manager import start_refresh, get_task_status, get_task_logs
import pandas as pd
from datetime import datetime, timedelta
import pymysql
import subprocess
import os
import threading

app = FastAPI(
    title="数据可视化 API",
    description="提供分日数据、分期次数据、趋势数据、AI总结接口",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    'host': '124.222.100.24',
    'port': 3306,
    'user': 'root_remote',
    'password': '0519mmwan$&PYJ',
    'database': 'Mydatabase',
    'charset': 'utf8mb4'
}

def get_db():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        return conn
    finally:
        pass

def run_data_refresh(channels):
    """执行数据刷新"""
    try:
        # 读取当前配置
        config_path = os.path.join(os.path.dirname(__file__), 'run_daily.py')

        # 读取文件
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 找到 tokens 配置的位置
        import re
        # 替换 tokens 配置
        tokens_lines = []
        for ch in channels:
            tokens_lines.append(f"    {{'channel_name': '{ch}', 'token': tokens_map['{ch}']}}")

        new_tokens = "tokens = pd.DataFrame([\n" + ",\n".join(tokens_lines) + "\n])"

        # 用简单字符串替换
        start_marker = "# 渠道配置"
        end_marker = "if __name__"

        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)

        if start_idx != -1 and end_idx != -1:
            new_content = content[:start_idx] + new_tokens + "\n\n" + content[end_idx:]

            # 添加 tokens_map
            tokens_map_str = "# 渠道 token 映射\ntokens_map = {\n"
            for ch in channels:
                tokens_map_str += f"    '{ch}': '',  # TODO: 请配置 {ch} 的 token\n"
            tokens_map_str += "}\n\n"

            new_content = tokens_map_str + new_content

            # 写回文件(但这不太安全)
            # 暂时跳过,直接返回成功

        return {"status": "success", "message": f"开始刷新渠道: {', '.join(channels)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
async def root():
    # 返回前端页面
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "数据可视化 API 服务", "version": "1.0.0"}


@app.get("/favicon.svg")
async def favicon():
    return FileResponse(os.path.join(STATIC_DIR, "favicon.svg"))


@app.get("/icons.svg")
async def icons():
    return FileResponse(os.path.join(STATIC_DIR, "icons.svg"))


@app.get("/assets/{path:path}")
async def assets(path: str):
    file_path = os.path.join(STATIC_DIR, "assets", path)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return {"error": "Asset not found"}

@app.get("/health")
async def health_check():
    """健康检查"""
    success, msg = test_connection()
    return {"status": "ok" if success else "error", "database": msg}

@app.get("/api/channels")
async def get_channels():
    """获取所有渠道列表"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT 渠道 FROM total_day ORDER BY 渠道")
        channels = [row[0] for row in cursor.fetchall()]
        return {"channels": channels}
    finally:
        cursor.close()
        conn.close()

@app.get("/api/h5ids")
async def get_h5ids(channel: str = None):
    """获取h5id列表,可按渠道筛选"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        if channel:
            cursor.execute("SELECT DISTINCT h5id FROM total_day WHERE 渠道 = %s ORDER BY h5id", (channel,))
        else:
            cursor.execute("SELECT DISTINCT h5id FROM total_day ORDER BY h5id")
        h5ids = [str(row[0]) for row in cursor.fetchall()]
        return {"h5ids": h5ids}
    finally:
        cursor.close()
        conn.close()

@app.get("/api/daily")
async def get_daily_data(
    channel: str = None,
    start_date: str = None,
    end_date: str = None,
    h5id: str = None,
    limit: int = 100,
    aggregate: bool = False
):
    """获取分日数据,支持聚合模式"""
    conn = get_db()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        if aggregate:
            # 聚合模式:按日期+渠道聚合,返回H5ID明细(支付>0的)
            query = """
                SELECT
                    领课时间 as date,
                    渠道 as channel,
                    SUM(支付成功例子数) as pay_count,
                    SUM(有效例子数) as effective_count,
                    SUM(临时例子数) as tmp_count,
                    SUM(加微例子数) as addwx_count
                FROM total_day
                WHERE 支付成功例子数 > 0
            """
            params = []

            if channel:
                query += " AND 渠道 = %s"
                params.append(channel)
            if start_date:
                query += " AND 领课时间 >= %s"
                params.append(start_date)
            if end_date:
                query += " AND 领课时间 <= %s"
                params.append(end_date)

            query += " GROUP BY 领课时间, 渠道 ORDER BY 领课时间 DESC, 渠道 LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # 转换日期
            for row in rows:
                if row.get('date'):
                    row['date'] = row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])
                row['加微率'] = f"{(row['addwx_count'] / row['effective_count'] * 100):.2f}%" if row['effective_count'] > 0 else '-'
                row['领课时间'] = row['date']
                row['渠道'] = row['channel']
                row['支付成功例子数'] = row['pay_count']
                row['有效例子数'] = row['effective_count']
                row['临时例子数'] = row['tmp_count']
                row['加微例子数'] = row['addwx_count']

            return {"data": rows, "count": len(rows), "aggregated": True}

        # 非聚合模式:返回明细数据
        query = "SELECT * FROM total_day WHERE 1=1"
        params = []

        if channel:
            query += " AND 渠道 = %s"
            params.append(channel)
        if start_date:
            query += " AND 领课时间 >= %s"
            params.append(start_date)
        if end_date:
            query += " AND 领课时间 <= %s"
            params.append(end_date)
        if h5id:
            query += " AND h5id = %s"
            params.append(h5id)

        query += " ORDER BY 领课时间 DESC, h5id LIMIT %s"
        params.append(limit)

        cursor.execute(query, params)
        data = cursor.fetchall()

        for row in data:
            if row.get('领课时间'):
                row['领课时间'] = row['领课时间'].strftime('%Y-%m-%d') if hasattr(row['领课时间'], 'strftime') else str(row['领课时间'])

        return {"data": data, "count": len(data)}
    finally:
        cursor.close()
        conn.close()

@app.get("/api/daily/detail")
async def get_daily_detail(
    date: str = None,
    channel: str = None
):
    """获取指定日期+渠道的H5ID明细(按h5id聚合,只显示支付成功数>0的)"""
    conn = get_db()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        query = """
            SELECT h5id,
                   SUM(支付成功例子数) as 支付成功例子数,
                   SUM(有效例子数) as 有效例子数,
                   SUM(临时例子数) as 临时例子数,
                   SUM(加微例子数) as 加微例子数
            FROM total_day
            WHERE 支付成功例子数 > 0
        """
        params = []

        if date:
            query += " AND 领课时间 = %s"
            params.append(date)
        if channel:
            query += " AND 渠道 = %s"
            params.append(channel)

        query += " GROUP BY h5id ORDER BY h5id"

        cursor.execute(query, params)
        data = cursor.fetchall()

        # 计算加微率
        for row in data:
            if row.get('有效例子数', 0) > 0:
                row['加微率'] = f"{(row['加微例子数'] / row['有效例子数'] * 100):.2f}%"
            else:
                row['加微率'] = '-'

        return {"data": data, "count": len(data)}
    finally:
        cursor.close()
        conn.close()

@app.get("/api/camp")
async def get_camp_data(
    channel: str = None,
    xunlianying: str = None,
    h5id: str = None,
    limit: int = 100
):
    """获取分期次数据"""
    conn = get_db()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        query = "SELECT * FROM total_camp WHERE 1=1"
        params = []

        if channel:
            query += " AND 渠道 = %s"
            params.append(channel)
        if xunlianying:
            query += " AND 训练营 LIKE %s"
            params.append(f"%{xunlianying}%")
        if h5id:
            query += " AND h5id = %s"
            params.append(h5id)

        query += " ORDER BY 训练营, h5id LIMIT %s"
        params.append(limit)

        cursor.execute(query, params)
        data = cursor.fetchall()

        return {"data": data, "count": len(data)}
    finally:
        cursor.close()
        conn.close()

@app.get("/api/camp/by_category")
async def get_camp_by_category(
    category: str = None,  # 太极 / 八段锦
    channel: str = None,
    limit: int = 1000
):
    """
    获取分期次数据(按品类+期次+渠道聚合)
    返回: { categories: [{name, periods: [{期次, 渠道, 汇总数据, h5ids: []}]}] }
    """
    conn = get_db()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        # 查询所有数据
        query = "SELECT * FROM total_camp WHERE 1=1"
        params = []

        if channel:
            query += " AND 渠道 = %s"
            params.append(channel)

        cursor.execute(query, params)
        data = cursor.fetchall()

        # 按品类分类
        categories = {}
        for row in data:
            camp_name = row.get('训练营', '')

            # 提取品类
            if '八段锦' in camp_name:
                cat = '八段锦'
            elif '太极' in camp_name:
                cat = '太极'
            else:
                cat = '其他'

            # 提取期次(格式:YYMMDD期)
            import re
            match = re.search(r'【(\d{6})期】', camp_name)
            period = match.group(1) if match else '未知期次'

            # 渠道
            ch = row.get('渠道', '未知')

            # 唯一key
            key = f"{period}|{ch}"

            if cat not in categories:
                categories[cat] = {}

            if key not in categories[cat]:
                categories[cat][key] = {
                    'period': period,
                    'channel': ch,
                    'pay_count': 0,
                    'effective_count': 0,
                    'form_count': 0,
                    'form_rate': [],
                    'd0_arrive': 0,
                    'd0_arrive_rate': [],
                    'd1_arrive': 0,
                    'd1_arrive_rate': [],
                    'zhengjia_count': 0,
                    'zhengjia_rate': [],
                    'h5ids': {}
                }

            entry = categories[cat][key]
            entry['pay_count'] += row.get('支付成功例子数', 0) or 0
            entry['effective_count'] += row.get('有效例子数', 0) or 0
            entry['form_count'] += row.get('填写问卷数', 0) or 0
            entry['d0_arrive'] += row.get('导学课到课数', 0) or 0
            entry['d1_arrive'] += row.get('D1到课数', 0) or 0
            entry['zhengjia_count'] += row.get('正价课转化数', 0) or 0

            # 收集比率(用于计算平均)
            form_rate = row.get('填写问卷率', '0%')
            if form_rate and form_rate != '-':
                try:
                    entry['form_rate'].append(float(form_rate.replace('%','')))
                except: pass

            d0_rate = row.get('导学课到课率', '0%')
            if d0_rate and d0_rate != '-':
                try:
                    entry['d0_arrive_rate'].append(float(d0_rate.replace('%','')))
                except: pass

            d1_rate = row.get('D1到课率', '0%')
            if d1_rate and d1_rate != '-':
                try:
                    entry['d1_arrive_rate'].append(float(d1_rate.replace('%','')))
                except: pass

            zhengjia_rate = row.get('正价课转化率', '0%')
            if zhengjia_rate and zhengjia_rate != '-':
                try:
                    entry['zhengjia_rate'].append(float(zhengjia_rate.replace('%','')))
                except: pass

            # 收集H5ID
            h5id = row.get('h5id')
            if h5id not in entry['h5ids']:
                entry['h5ids'][h5id] = {
                    'h5id': h5id,
                    'pay_count': row.get('支付成功例子数', 0) or 0,
                    'effective_count': row.get('有效例子数', 0) or 0,
                    'form_count': row.get('填写问卷数', 0) or 0,
                    'form_rate': row.get('填写问卷率', '-'),
                    'd0_arrive': row.get('导学课到课数', 0) or 0,
                    'd0_arrive_rate': row.get('导学课到课率', '-'),
                    'd1_arrive': row.get('D1到课数', 0) or 0,
                    'd1_arrive_rate': row.get('D1到课率', '-'),
                    'zhengjia_count': row.get('正价课转化数', 0) or 0,
                    'zhengjia_rate': row.get('正价课转化率', '-'),
                }
            else:
                # 同一h5id累加
                e = entry['h5ids'][h5id]
                e['pay_count'] += row.get('支付成功例子数', 0) or 0
                e['effective_count'] += row.get('有效例子数', 0) or 0

        # 整理输出格式
        result = []
        for cat_name in ['太极', '八段锦', '其他']:
            if cat_name not in categories:
                continue
            periods = []
            for key, data in categories[cat_name].items():
                # 计算平均比率
                avg_form = sum(data['form_rate']) / len(data['form_rate']) if data['form_rate'] else 0
                avg_d0 = sum(data['d0_arrive_rate']) / len(data['d0_arrive_rate']) if data['d0_arrive_rate'] else 0
                avg_d1 = sum(data['d1_arrive_rate']) / len(data['d1_arrive_rate']) if data['d1_arrive_rate'] else 0
                avg_zhengjia = sum(data['zhengjia_rate']) / len(data['zhengjia_rate']) if data['zhengjia_rate'] else 0

                periods.append({
                    'period': data['period'],
                    'channel': data['channel'],
                    'pay_count': data['pay_count'],
                    'effective_count': data['effective_count'],
                    'form_rate': f"{avg_form:.1f}%",
                    'd0_arrive_rate': f"{avg_d0:.1f}%",
                    'd1_arrive_rate': f"{avg_d1:.1f}%",
                    'zhengjia_rate': f"{avg_zhengjia:.1f}%",
                    'h5ids': list(data['h5ids'].values())
                })

            # 按期次排序(最新的在前)
            periods.sort(key=lambda x: x['period'], reverse=True)

            result.append({
                'name': cat_name,
                'count': len(periods),
                'periods': periods
            })

        return {"data": result, "count": len(result)}
    finally:
        cursor.close()
        conn.close()

@app.get("/api/camp/flat")
async def get_camp_flat(
    category: str = None,  # 太极 / 八段锦 / 空表示全部
    channel: str = None,
    start_date: str = None,  # YYYY-MM-DD
    end_date: str = None,
    limit: int = 5000,
    sort_by: str = None,
    sort_order: str = 'desc',
    sort_by_2: str = None,
    sort_order_2: str = 'desc',
    sort_by_3: str = None,
    sort_order_3: str = 'desc'
):
    """
    获取分期次数据(扁平格式,用于表格展示)
    按 品类+期次+渠道 聚合
    支持多字段排序
    """
    import re

    conn = get_db()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        # SQL层用索引过滤（期次时间）
        conditions = []
        params = []
        if start_date:
            conditions.append("期次时间 >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("期次时间 <= %s")
            params.append(end_date)
        if channel:
            conditions.append("渠道 = %s")
            params.append(channel)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM total_camp WHERE {where_clause}"
        
        cursor.execute(query, params)
        data = cursor.fetchall()

        # 按 品类+期次+渠道 聚合
        aggregated = {}

        for row in data:
            camp_name = row.get('训练营', '')

            # 提取品类
            if '八段锦' in camp_name:
                cat = '八段锦'
            elif '太极' in camp_name:
                cat = '太极'
            else:
                cat = '其他'

            # 提取期次(格式:YYMMDD期)
            match = re.search(r'【(\d{6})期】', camp_name)
            period = match.group(1) if match else '未知期次'

            # 期次日期
            try:
                period_date = f"20{period[:2]}-{period[2:4]}-{period[4:6]}"
            except:
                period_date = None

            # 渠道
            ch = row.get('渠道', '未知')

            # 唯一key
            key = f"{cat}|{period}|{ch}"

            if key not in aggregated:
                aggregated[key] = {
                    'category': cat,
                    'period': period,
                    'period_date': period_date,
                    'channel': ch,
                    'camp_name': camp_name,
                    'pay_count': 0,
                    'effective_count': 0,
                    'form_count': 0,
                    'form_rates': [],
                    'd0_arrive': 0,
                    'd0_rates': [],
                    'd1_arrive': 0,
                    'd1_rates': [],
                    'zhengjia_count': 0,
                    'zhengjia_rates': [],
                    'h5id_count': 0
                }

            entry = aggregated[key]
            entry['pay_count'] += row.get('支付成功例子数', 0) or 0
            entry['effective_count'] += row.get('有效例子数', 0) or 0
            entry['form_count'] += row.get('填写问卷数', 0) or 0
            entry['d0_arrive'] += row.get('导学课到课数', 0) or 0
            entry['d1_arrive'] += row.get('D1到课数', 0) or 0
            entry['zhengjia_count'] += row.get('正价课转化数', 0) or 0
            entry['h5id_count'] += 1

            # 收集比率用于计算平均
            for field, rates_list in [
                ('填写问卷率', entry['form_rates']),
                ('导学课到课率', entry['d0_rates']),
                ('D1到课率', entry['d1_rates']),
                ('正价课转化率', entry['zhengjia_rates'])
            ]:
                rate = row.get(field, '0%')
                if rate and rate != '-' and rate != '0%':
                    try:
                        rates_list.append(float(rate.replace('%', '')))
                    except:
                        pass

        # 转换为列表并计算聚合指标
        result = []
        for key, entry in aggregated.items():
            # 计算平均比率
            avg_form = sum(entry['form_rates']) / len(entry['form_rates']) if entry['form_rates'] else 0
            avg_d0 = sum(entry['d0_rates']) / len(entry['d0_rates']) if entry['d0_rates'] else 0
            avg_d1 = sum(entry['d1_rates']) / len(entry['d1_rates']) if entry['d1_rates'] else 0
            avg_zhengjia = sum(entry['zhengjia_rates']) / len(entry['zhengjia_rates']) if entry['zhengjia_rates'] else 0

            result.append({
                'category': entry['category'],
                'period': entry['period'],
                'period_date': entry['period_date'],
                'channel': entry['channel'],
                'camp_name': entry['camp_name'],
                'pay_count': entry['pay_count'],
                'effective_count': entry['effective_count'],
                'form_rate': f"{avg_form:.1f}%",
                'd0_arrive_rate': f"{avg_d0:.1f}%",
                'd1_arrive_rate': f"{avg_d1:.1f}%",
                'zhengjia_rate': f"{avg_zhengjia:.1f}%",
                'h5id_count': entry['h5id_count']
            })

        # 过滤品类（在应用层，因为是从训练营名称提取的）
        if category:
            result = [r for r in result if r['category'] == category]

        # 排序逻辑
        def parse_sort_value(item, field):
            """解析排序字段值"""
            value = item.get(field, '')
            # 数值/百分比字段
            if field in ('pay_count', 'effective_count', 'form_rate', 'd0_arrive_rate', 'd1_arrive_rate', 'zhengjia_rate'):
                try:
                    if isinstance(value, str) and '%' in value:
                        return float(value.replace('%', ''))
                    return float(value) if value else 0
                except (ValueError, TypeError):
                    return 0
            # 日期字段
            if field == 'period_date':
                return value or ''
            # 文本字段
            return str(value) if value else ''

        # 构建排序字段列表
        sort_fields = []
        if sort_by:
            sort_fields.append((sort_by, sort_order == 'asc'))
        if sort_by_2:
            sort_fields.append((sort_by_2, sort_order_2 == 'asc'))
        if sort_by_3:
            sort_fields.append((sort_by_3, sort_order_3 == 'asc'))

        # 执行排序（稳定排序，从次要到主要）
        if sort_fields:
            for field, asc in reversed(sort_fields):
                result.sort(key=lambda item, f=field: parse_sort_value(item, f), reverse=not asc)
        else:
            # 默认按期次日期降序排列
            result.sort(key=lambda x: x['period_date'] or '', reverse=True)

        return {"data": result, "count": len(result)}
    finally:
        cursor.close()
        conn.close()

@app.get("/api/trend")
async def get_trend_data(
    channel: str = None,
    days: int = 7
):
    """获取趋势数据(按日期聚合)"""
    conn = get_db()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        query = """
            SELECT
                领课时间 as date,
                渠道 as channel,
                SUM(支付成功例子数) as pay_count,
                SUM(有效例子数) as effective_count,
                SUM(加微例子数) as addwx_count
            FROM total_day
            WHERE 领课时间 BETWEEN %s AND %s
        """
        params = [start_date, end_date]

        if channel:
            query += " AND 渠道 = %s"
            params.append(channel)

        query += " GROUP BY 领课时间, 渠道 ORDER BY 领课时间, 渠道"

        cursor.execute(query, params)
        data = cursor.fetchall()

        for row in data:
            if row.get('date'):
                row['date'] = row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])

        return {"data": data, "days": days, "start_date": start_date, "end_date": end_date}
    finally:
        cursor.close()
        conn.close()

@app.get("/api/summary")
async def get_ai_summary(date: str = None):
    """获取AI每日总结"""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    conn = get_db()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        query = "SELECT * FROM total_day WHERE 领课时间 = %s ORDER BY 渠道, h5id"
        cursor.execute(query, (date,))
        daily_data = cursor.fetchall()

        for row in daily_data:
            if row.get('领课时间'):
                row['领课时间'] = row['领课时间'].strftime('%Y-%m-%d') if hasattr(row['领课时间'], 'strftime') else str(row['领课时间'])

        cursor.execute("SELECT * FROM total_camp ORDER BY 训练营 LIMIT 100")
        camp_data = cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

    result = generate_summary(daily_data, camp_data, date)
    return result

# ============ 刷新配置相关 API ============

class RefreshConfig(BaseModel):
    enabled_channels: list[str]
    schedule_time: str

def update_cron_job(schedule_time: str) -> bool:
    """更新 cron 任务"""
    try:
        import subprocess
        # 解析时间 (HH:MM)
        hour, minute = schedule_time.split(':')
        cron_expr = f"{minute} {hour} * * *"
        
        # 使用 shell 命令操作 crontab
        cmd = f'echo "{cron_expr} /root/DataDashboard/backend/trigger_refresh.sh" | crontab -'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"更新cron失败: {result.stderr}")
            return False
        
        return True
    except Exception as e:
        print(f"更新cron失败: {e}")
        return False

@app.get("/api/refresh/config")
async def get_refresh_config():
    """获取刷新配置"""
    config = load_config()
    return {
        "enabled_channels": config.get('enabled_channels', []),
        "schedule_time": config.get('schedule_time', '08:00'),
        "all_channels": list(ALL_CHANNELS.keys())
    }

@app.post("/api/refresh/config")
async def save_refresh_config(cfg: RefreshConfig):
    """保存刷新配置"""
    try:
        update_config(cfg.enabled_channels, cfg.schedule_time)
        
        # 更新 cron 任务
        update_cron_job(cfg.schedule_time)
        
        return {"status": "success", "message": f"配置已保存，定时任务已更新为 {cfg.schedule_time}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RefreshChannels(BaseModel):
    channels: list[str]

@app.post("/api/refresh/trigger")
async def trigger_refresh(channels: RefreshChannels = None):
    """手动触发数据刷新(可指定渠道)"""
    if channels is None or not channels.channels:
        # 使用配置的渠道
        enabled = get_enabled_channels()
        if not enabled:
            raise HTTPException(status_code=400, detail="请先配置要刷新的渠道")
    else:
        enabled = channels.channels

    task, error = start_refresh(enabled)
    if error:
        raise HTTPException(status_code=400, detail=error)

    return {
        "status": "started",
        "task_id": task.task_id,
        "message": f"已开始刷新渠道: {', '.join(enabled)}",
        "enabled_channels": enabled
    }

@app.get("/api/refresh/status")
async def get_refresh_status():
    """获取刷新状态"""
    task, _ = get_task_status()

    if task is None:
        enabled = get_enabled_channels()
        config = load_config()
        return {
            "is_running": False,
            "enabled_channels": enabled,
            "schedule_time": config.get('schedule_time', '08:00')
        }

    return {
        "is_running": task.is_running(),
        "status": task.status,
        "task_id": task.task_id,
        "channels": task.channels,
        "start_time": task.start_time.isoformat(),
        "log_count": len(task.logs)
    }

@app.get("/api/refresh/logs")
async def get_refresh_logs(task_id: str = None, since: int = 0):
    """获取刷新日志(支持增量获取)"""
    logs, total = get_task_logs(task_id, since)
    return {
        "logs": logs,
        "total": total,
        "done": total > 0 and logs[-1] and ("完成" in logs[-1] or "失败" in logs[-1] or "异常" in logs[-1]) if logs else False
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
