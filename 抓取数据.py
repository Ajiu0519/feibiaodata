import sys
import pymysql
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# Windows 下避免 print 含 Unicode 时 GBK 报错
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# URL 编码特殊字符: $ = %24, & = %26
engine = create_engine('mysql+pymysql://root_remote:0519mmwan%24%26PYJ@124.222.100.24:3306/Mydatabase')

# 供 insert_data_to_mysql 打印渠道用（被定时刷新调用时由 get_*_by_token 设置）
current_token = None

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


#data=total_data
#table_name='total_camp'
def _quote(col):
    """列名用反引号包裹，避免 NO. 等含点或保留字导致 SQL 语法错误"""
    return f"`{col}`"

def insert_data_to_mysql(data, table_name, key_columns, columns):
    connection = connect_to_mysql()
    cursor = connection.cursor()

    existing_data = {}
    cols_sql = ', '.join(_quote(c) for c in key_columns + columns)
    cursor.execute(f"SELECT {cols_sql} FROM `{table_name}`")
    for row in cursor.fetchall():
        key_tuple = tuple(row[:len(key_columns)])
        existing_data[key_tuple] = row[len(key_columns):]

    new_data = []
    update_data = []

    start_time = time.time()  # 记录开始时间

    for index, row in data.iterrows():
        key_tuple = tuple(row[col] for col in key_columns)

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

    end_time = time.time()  # 记录结束时间
    elapsed_time = end_time - start_time  # 计算耗时

    # 输出汇总信息（current_token 由 get_*_by_token 在调用前设置）
    if current_token is not None and current_token in tokens['token'].values:
        channel_name = tokens.loc[tokens['token'] == current_token, 'channel_name']
        print(f'渠道: {channel_name.iloc[0]}')
    print(f"Table: {table_name}, Inserted Rows: {len(new_data)}, Updated Rows: {len(update_data)}, Time: {elapsed_time:.2f} seconds")

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
                        '渠道':channel_name.iloc[0],
                        '领课时间': date_str,
                        'h5id': item['h5id'],
                        '支付成功例子数': item['payNum'],
                        '有效例子数': item['effectiveNum'],
                        '临时例子数': item['tmpNum'],
                        '加微例子数': item['addWcNum'],
                        '加微率': item['jiav_rate']
                    } for item in data['total']])
                    key_columns = ['领课时间', 'h5id']
                    columns = ['支付成功例子数', '有效例子数', '临时例子数', '加微例子数', '加微率','渠道']
                    insert_data_to_mysql(total_data, 'total_day', key_columns, columns)

                if 'detail' in data and data['detail']:
                    data_detail = pd.DataFrame(data['detail'])
                    data_detail['linke_time'] = data_detail['linke_time'].apply(lambda x: x['date']).str.split('.').str[0]
                    key_columns = ['user_id', 'linke_time']
                    columns = ['user_name', 'xunlianying', 'wx_relation', 'member_status', 'h5id', 'xe_id']
                    insert_data_to_mysql(data_detail, 'data_day', key_columns, columns)

                    # 查询当前 xunlianying_id 表中 NO. 的最大值及已有记录，用于为新增行分配 NO.
                    conn_xe = connect_to_mysql()
                    cur_xe = conn_xe.cursor()
                    try:
                        cur_xe.execute("SELECT COALESCE(MAX(`NO.`), 0) FROM xunlianying_id")
                        max_no = cur_xe.fetchone()[0]
                        cur_xe.execute("SELECT xunlianying, `NO.` FROM xunlianying_id")
                        existing_xe = {row[0]: row[1] for row in cur_xe.fetchall()}
                    except Exception:
                        max_no = 0
                        existing_xe = {}
                    cur_xe.close()
                    conn_xe.close()

                    xunlianying_id = pd.DataFrame(columns=['xunlianying', 'xe_id'])
                    xunlianying_id['xunlianying'] = data_detail['xunlianying'].unique()
                    xunlianying_id['xe_id'] = data_detail['xe_id'].unique()
                    # 新增的 xunlianying 在 NO. 最大值基础上 +1 递增；已存在的保留原 NO.
                    next_no = max_no + 1
                    def assign_no(xunlianying):
                        nonlocal next_no
                        if xunlianying in existing_xe:
                            return existing_xe[xunlianying]
                        no = next_no
                        next_no += 1
                        return no
                    xunlianying_id['NO.'] = xunlianying_id['xunlianying'].map(assign_no)
                    key_columns_xe = ['xunlianying']
                    columns_xe = ['xe_id', 'NO.']
                    insert_data_to_mysql(xunlianying_id, 'xunlianying_id', key_columns_xe, columns_xe)
                break
            else:
                print(f"Failed to fetch data for {date_str}, retrying... ({retries + 1}/{max_retries})")
                retries += 1
                time.sleep(5)

        if retries >= max_retries:
            print(f"Max retries reached for {date_str}, skipping this date.")

def get_camp_data_by_token(token):
    global current_token
    current_token = token
    channel_name = tokens.loc[tokens['token'] == token, 'channel_name']
    xunlianying_id_sql = pd.read_sql('xunlianying_id', con=engine)
    xunlianying_id_sql_sorted = xunlianying_id_sql.sort_values(by='No.', ascending=False)
    for id in xunlianying_id_sql_sorted['xe_id'].head(15):
        #print(id)
        xunlianying = xunlianying_id_sql[xunlianying_id_sql['xe_id'] == id]['xunlianying'].iloc[0]
        #print(xunlianying)
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
                            '训练营': xunlianying,
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
                                   '正价课转化数','正价课转化率','渠道']
                        insert_data_to_mysql(total_data, 'total_camp', key_columns, columns)
                        #total_data.to_csv(f'{xunlianying}_total.csv', index=False)
                    break
                else:
                    print(f"Failed to fetch data for {xunlianying}, retrying... ")
                    print(response.status_code)
                    break
            except Exception as e:
                print(f"Exception occurred in get_camp_data_by_token: {e}")
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"Max retries reached for {xunlianying}. Skipping...")
                    break
            time.sleep(5)

tokens = pd.DataFrame([
    #{'channel_name': '北京九章', 'token': '2c82d5b1fdf4fc7ed260bbb52487b441JZ'},#静静
    {'channel_name': '星视点', 'token': '538FD95F068B9CB986307F81652DD931xqd'},
    #{'channel_name': '江苏数赢', 'token': '4AAFBA8646E5A10646070B7626DF87BBSY'},
    #{'channel_name': '师一师兄', 'token': '759D9D9E8591D86426E73AF6469705C5DSYSX'},
    #{'channel_name': '真数赢', 'token': '12a7f98ee24cb86d29ca3e659e5bbba1ZSY'},
    #{'channel_name': '跳动', 'token': '0308bd6d07412dc4628b0fe2cbf11eb8td'},
    #{'channel_name': '乐百年', 'token': '2CB92FB1E05EC868EF65A02AF90852B5'},
])

if __name__ == "__main__":
    for _, row in tokens.iterrows():
        token = row['token']
        print(token)
        #get_day_data_by_token(token)
        get_camp_data_by_token(token)
