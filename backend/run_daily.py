#!/usr/bin/env python3
"""
每日数据抓取脚本
从原脚本复制并简化，供定时任务调用
"""
import sys
import os
import pymysql
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from sqlalchemy import create_engine

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Windows 下避免 print 含 Unicode 时 GBK 报错
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# URL 编码特殊字符: $ = %24, & = %26
engine = create_engine('mysql+pymysql://root_remote:0519mmwan%24%26PYJ@124.222.100.24:3306/Mydatabase')

current_token = None

def parse_xunlianying(xunlianying):
    """从训练营名称中解析国内/海外标识、期次日期，并去掉_国内后缀"""
    region = '国内'
    clean_name = xunlianying

    if xunlianying and '_国内' in xunlianying:
        region = '国内'
        clean_name = xunlianying.replace('_国内', '')
    elif xunlianying and '_海外' in xunlianying:
        region = '海外'
        clean_name = xunlianying.replace('_海外', '')

    # 解析期次日期，例如 【260411期】 -> 2026-04-11
    period_date = None
    import re
    match = re.search(r'【(\d{6})期】', clean_name)
    if match:
        period_str = match.group(1)  # e.g., "260411"
        year = int('20' + period_str[:2])  # 2026
        month = int(period_str[2:4])  # 04
        day = int(period_str[4:6])  # 11
        period_date = f'{year}-{month:02d}-{day:02d}'

    return region, clean_name, period_date

def connect_to_mysql():
    try:
        connection = pymysql.connect(
            host='124.222.100.24',
            port=3306,
            user='root_remote',
            password='0519mmwan$&PYJ',
            database='Mydatabase',
            charset='utf8mb4'
        )
        return connection
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

def _quote(col):
    return f"`{col}`"

def _normalize_key_value(val):
    """标准化键值，用于查重比较"""
    # 确保返回的是可哈希的标量值
    if val is None:
        return None
    if hasattr(val, 'strftime'):  # datetime object
        return val.strftime('%Y-%m-%d')
    # 如果是 pandas Series 或其他非标量，转为字符串
    if not isinstance(val, (str, int, float, bool)):
        return str(val)
    return val

def insert_data_to_mysql(data, table_name, key_columns, columns):
    connection = connect_to_mysql()
    cursor = connection.cursor()

    existing_data = {}
    cols_sql = ', '.join(_quote(c) for c in key_columns + columns)
    cursor.execute(f"SELECT {cols_sql} FROM `{table_name}`")
    for row in cursor.fetchall():
        try:
            key_tuple = tuple(_normalize_key_value(row[i]) for i in range(len(key_columns)))
        except Exception as e:
            print(f"加载 existing_data 时构建 key_tuple 异常: row={row}, error={e}")
            continue
        existing_data[key_tuple] = row[len(key_columns):]

    new_data = []
    update_data = []

    start_time = time.time()

    for index, row in data.iterrows():
        try:
            key_tuple = tuple(_normalize_key_value(row[col]) for col in key_columns)
        except Exception as e:
            print(f"构建 key_tuple 异常: row={row.to_dict() if hasattr(row, 'to_dict') else row}, error={e}")
            raise

        if key_tuple in existing_data:
            existing_row = list(existing_data[key_tuple])
            updated = False
            for col_index, col_name in enumerate(columns):
                if row[col_name] != existing_row[col_index]:
                    existing_row[col_index] = row[col_name]
                    updated = True
            if updated:
                update_data.append((existing_row, key_tuple))
        else:
            new_row = [row[col] for col in key_columns + columns]
            new_data.append(new_row)

    if new_data:
        placeholders = ', '.join(['%s'] * (len(key_columns) + len(columns)))
        all_columns = key_columns + columns
        sql = f"INSERT INTO `{table_name}` ({', '.join(_quote(c) for c in all_columns)}) VALUES ({placeholders})"
        cursor.executemany(sql, new_data)
        connection.commit()

    if update_data:
        for existing_row, key_tuple in update_data:
            set_clause = ', '.join([f"{_quote(col)} = %s" for col in columns])
            where_clause = ' AND '.join([f"{_quote(col)} = %s" for col in key_columns])
            sql = f"UPDATE `{table_name}` SET {set_clause} WHERE {where_clause}"
            cursor.execute(sql, existing_row + list(key_tuple))
            connection.commit()

    cursor.close()
    connection.close()

    end_time = time.time()
    elapsed_time = end_time - start_time

    if current_token is not None and current_token in tokens['token'].values:
        channel_name = tokens.loc[tokens['token'] == current_token, 'channel_name']
        print(f'渠道: {channel_name.iloc[0]}')
    print(f"Table: {table_name}, Inserted: {len(new_data)}, Updated: {len(update_data)}, Time: {elapsed_time:.2f}s")

def get_day_data_by_token(token):
    global current_token
    current_token = token
    channel_name = tokens.loc[tokens['token'] == token, 'channel_name']
    today = datetime.now().date()
    start_date = today - timedelta(days=2)

    for date in pd.date_range(start_date, today):
        date_str = date.strftime('%Y-%m-%d')
        url = f"https://api-h5.tangdou.com/course/board/export?token={token}&date={date_str}&dump_type=day&export=N"
        max_retries = 3
        retries = 0

        while retries < max_retries:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if 'total' in data and data['total']:
                    total_data = pd.DataFrame([{
                        '渠道': channel_name.iloc[0],
                        '领课时间': date_str,
                        'h5id': item['h5id'],
                        '支付成功例子数': item['payNum'],
                        '有效例子数': item['effectiveNum'],
                        '临时例子数': item['tmpNum'],
                        '加微例子数': item['addWcNum'],
                        '加微率': item['jiav_rate']
                    } for item in data['total']])
                    key_columns = ['领课时间', 'h5id']
                    columns = ['支付成功例子数', '有效例子数', '临时例子数', '加微例子数', '加微率', '渠道']
                    insert_data_to_mysql(total_data, 'total_day', key_columns, columns)

                # 处理 detail 数据，更新 data_day 表和 xunlianying_id 表
                if 'detail' in data and data['detail']:
                    data_detail = pd.DataFrame(data['detail'])
                    # 解析 linke_time 中的日期
                    data_detail['linke_time'] = data_detail['linke_time'].apply(lambda x: x['date']).str.split('.').str[0]
                    key_columns = ['user_id', 'linke_time']
                    columns = ['user_name', 'xunlianying', 'wx_relation', 'member_status', 'h5id', 'xe_id']
                    insert_data_to_mysql(data_detail, 'data_day', key_columns, columns)

                    # 更新 xunlianying_id 表：自动发现新训练营
                    print(f"发现 {len(data_detail['xunlianying'].unique())} 个训练营，开始更新 xunlianying_id 表...")
                    conn_xe = connect_to_mysql()
                    cur_xe = conn_xe.cursor()
                    try:
                        cur_xe.execute("SELECT COALESCE(MAX(`NO.`), 0) FROM xunlianying_id")
                        max_no = cur_xe.fetchone()[0]
                        cur_xe.execute("SELECT xunlianying, `NO.` FROM xunlianying_id")
                        existing_xe = {row[0]: row[1] for row in cur_xe.fetchall()}
                        print(f"当前 xunlianying_id 表有 {len(existing_xe)} 条记录，最大 NO. = {max_no}")
                    except Exception as e:
                        print(f"读取 xunlianying_id 表异常: {e}")
                        max_no = 0
                        existing_xe = {}
                    cur_xe.close()
                    conn_xe.close()

                    # 构建新训练营数据
                    new_xunlianying = data_detail[['xunlianying', 'xe_id']].drop_duplicates()
                    new_xunlianying = new_xunlianying.dropna(subset=['xunlianying', 'xe_id'])

                    # 解析国内/海外标识和训练营名称
                    new_xunlianying['region'] = new_xunlianying['xunlianying'].apply(lambda x: parse_xunlianying(x)[0])
                    new_xunlianying['xunlianying_clean'] = new_xunlianying['xunlianying'].apply(lambda x: parse_xunlianying(x)[1])
                    print(f"本次发现 {len(new_xunlianying)} 个训练营，其中 {len(new_xunlianying[new_xunlianying['region'] == '国内'])} 个国内，{len(new_xunlianying[new_xunlianying['region'] == '海外'])} 个海外")

                    # 新增的训练营在 NO. 最大值基础上 +1 递增；已存在的保留原 NO.
                    next_no = max_no + 1
                    def assign_no(xunlianying):
                        nonlocal next_no
                        try:
                            # 确保输入是字符串
                            if not isinstance(xunlianying, str):
                                xunlianying = str(xunlianying)
                            region, clean_name, period_date = parse_xunlianying(xunlianying)
                            # 确保 clean_name 是字符串
                            if not isinstance(clean_name, str):
                                clean_name = str(clean_name)
                            if clean_name in existing_xe:
                                return existing_xe[clean_name]
                            no = next_no
                            next_no += 1
                            return no
                        except Exception as e:
                            print(f"assign_no 异常 xunlianying={xunlianying}, type={type(xunlianying)}, error={e}")
                            return next_no
                    new_xunlianying['NO.'] = new_xunlianying['xunlianying'].map(assign_no)
                    new_xunlianying = new_xunlianying.rename(columns={'xe_id': 'xe_id', 'NO.': 'NO.', 'xunlianying_clean': 'xunlianying'})

                    key_columns_xe = ['xunlianying', 'xe_id']
                    columns_xe = ['NO.', 'region']
                    insert_data_to_mysql(new_xunlianying, 'xunlianying_id', key_columns_xe, columns_xe)
                break
            else:
                print(f"获取 {date_str} 数据失败，重试中... ({retries + 1}/{max_retries})")
                retries += 1
                time.sleep(5)

        if retries >= max_retries:
            print(f"跳过日期: {date_str}")

def get_camp_data_by_token(token):
    global current_token
    current_token = token
    channel_name = tokens.loc[tokens['token'] == token, 'channel_name']
    xunlianying_id_sql = pd.read_sql('xunlianying_id', con=engine)
    xunlianying_id_sql_sorted = xunlianying_id_sql.sort_values(by='No.', ascending=False)

    for id in xunlianying_id_sql_sorted['xe_id'].head(15):
        xunlianying = xunlianying_id_sql[xunlianying_id_sql['xe_id'] == id]['xunlianying'].iloc[0]
        # 解析 region 和期次时间
        region, clean_name, period_date = parse_xunlianying(xunlianying)
        url = f"https://api-h5.tangdou.com/course/board/export?token={token}&xe_id={id}&dump_type=camp&export=N&show_order_quantity=Y"

        max_retries = 5
        retry_count = 0

        while retry_count < max_retries:
            try:
                response = requests.get(url, timeout=120)
                if response.status_code == 200:
                    data = response.json()
                    if 'total' in data and data['total']:
                        total_data = pd.DataFrame([{
                            '渠道': channel_name.iloc[0],
                            '训练营': clean_name,
                            'region': region,
                            '期次时间': period_date,
                            'h5id': item['h5id'],
                            '支付成功例子数': item['payNum'],
                            '有效例子数': item['effectiveNum'],
                            '填写问卷数': item['xiaoe_form_num'],
                            '填写问卷率': item['xiaoe_form_rate'],
                            '单向好友数': item['alone_friend_num'],
                            '导学课到课数': item['D0_arrive_num'],
                            '导学课到课率': item['D0_arrive_rate'],
                            '导学课完课数': item['D0_finish_num'],
                            '导学课完课率': item['D0_finish_rate'],
                            'D1到课数': item['D1_arrive_num'],
                            'D1到课率': item['D1_arrive_rate'],
                            'D1完课数': item['D1_finish_num'],
                            'D1完课率': item['D1_finish_rate'],
                            '正价课转化数': item['xiaoe_order_num']
                        } for item in data['total']])
                        total_data['正价课转化率'] = ((total_data['正价课转化数'] / total_data['有效例子数']) * 100).map("{:.2f}%".format)
                        key_columns = ['训练营', 'h5id']
                        columns = ['支付成功例子数', '有效例子数', '填写问卷数', '填写问卷率', '单向好友数',
                                   '导学课到课数', '导学课到课率', '导学课完课数', '导学课完课率', 'D1到课数', 'D1到课率', 'D1完课数', 'D1完课率',
                                   '正价课转化数', '正价课转化率', '渠道', 'region', '期次时间']
                        insert_data_to_mysql(total_data, 'total_camp', key_columns, columns)
                    break
                else:
                    print(f"获取 {xunlianying} 数据失败")
                    break
            except Exception as e:
                print(f"异常: {e}")
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"跳过训练营: {xunlianying}")
                    break
            time.sleep(5)

# 渠道配置 - 从 config_manager 读取
from config_manager import get_enabled_tokens

tokens = pd.DataFrame(get_enabled_tokens())

def process_channel(token):
    """处理单个渠道"""
    channel_name = token['channel_name']
    print(f">>> 开始处理渠道: {channel_name}")
    
    # Step 1: 获取分日数据
    print(f">>> Step 1: 获取分日数据...")
    get_day_data_by_token(token['token'])
    
    # Step 2: 获取分期次数据  
    print(f">>> Step 2: 获取分期次数据...")
    get_camp_data_by_token(token['token'])
    
    print(f">>> 渠道 {channel_name} 处理完成")

if __name__ == "__main__":
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    print(f"=== 开始每日数据抓取: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    
    if tokens.empty:
        print("❌ 没有配置任何渠道，请先在 Dashboard 中配置")
        exit(1)
    
    channel_list = tokens['channel_name'].tolist()
    print(f">>> 将刷新以下渠道: {', '.join(channel_list)}")
    print(f">>> 并行处理模式: {len(channel_list)} 个渠道同时进行")
    
    # 并行处理所有渠道
    with ThreadPoolExecutor(max_workers=len(channel_list)) as executor:
        futures = {executor.submit(process_channel, token): token['channel_name'] for _, token in tokens.iterrows()}
        
        for future in as_completed(futures):
            channel = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"❌ 渠道 {channel} 失败: {e}")
    
    print(f"\n=== 完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
