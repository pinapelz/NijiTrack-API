import datetime
import pandas
from sklearn.linear_model import Ridge
import numpy as np
import os
from member_colors import member_groups

# Pure logic for creating a database connection
def create_database_connection():
    from sql.pg_handler import PostgresHandler
    hostname = os.environ.get("POSTGRES_HOST")
    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    database = os.environ.get("POSTGRES_DATABASE")
    return PostgresHandler(host_name=hostname, username=user, password=password, database=database, port=5432)

def get_subscribers_data():
    server = create_database_connection()
    query = 'SELECT sd.*, h.* FROM subscriber_data sd INNER JOIN "24h_historical" h ON sd.channel_id = h.channel_id ORDER BY sd.subscriber_count DESC'
    data = server.execute_query(query)
    channel_data_list = [{
        "channel_name": row[3],
        "profile_pic": row[2],
        "subscribers": row[4],
        "sub_org": row[5],
        "video_count": row[6],
        "views": row[8],
        "day_diff": int(row[4] - int(row[11]))
    } for row in data]
    return {"timestamp": datetime.datetime.now(), "channel_data": channel_data_list}

def get_twitch_data():
    server = create_database_connection()
    query = '''
        SELECT sd.*, h.*, ts.follower_count
        FROM subscriber_data sd
        INNER JOIN "24h_historical" h ON sd.channel_id = h.channel_id
        LEFT JOIN twitch_stats ts ON sd.channel_id = ts.channel_id
        ORDER BY sd.subscriber_count DESC
    '''
    data = server.execute_query(query)
    channel_data_list = []
    for row in data:
        youtube_subs = row[4]
        twitch_followers = row[-1] if row[-1] is not None else 0
        total_followers = youtube_subs + twitch_followers
        channel_data_list.append({
            "channel_name": row[3],
            "profile_pic": row[2],
            "subscribers": youtube_subs,
            "sub_org": row[5],
            "twitch_followers": twitch_followers,
            "total_sum": total_followers,
        })
    return {"timestamp": datetime.datetime.now(), "channel_data": channel_data_list}

def get_channel_timeseries(channel_name):
    server = create_database_connection()
    query = "SELECT * FROM subscriber_data_historical WHERE name = %s AND timestamp > %s ORDER BY TO_CHAR(timestamp, 'YYYY-MM-DD')"
    data = server.execute_query(query, (channel_name, os.environ.get("START_DATE"),))
    labels = []
    data_points = []
    seen_dates = set()
    for row in data:
        date_string = row[5].strftime("%Y-%m-%d")
        if date_string in seen_dates:
            continue
        labels.append(date_string)
        data_points.append(row[4])
        seen_dates.add(date_string)
    return {"labels": labels, "datasets": data_points}

def get_channel_7d(channel_name):
    server = create_database_connection()
    query = "SELECT * FROM subscriber_data_historical WHERE name = %s ORDER BY TO_CHAR(timestamp, 'YYYY-MM-DD')"
    data = server.execute_query(query, (channel_name,))
    labels = []
    data_points = []
    seen_dates = set()
    for row in data:
        date_string = row[5].strftime("%Y-%m-%d")
        if date_string in seen_dates:
            continue
        labels.append(date_string)
        data_points.append(row[4])
        seen_dates.add(date_string)
    return {"labels": labels[-7:], "datasets": data_points[-7:]}

def get_channel_milestones(channel_name, milestone_increment=10000):
    server = create_database_connection()
    current_milestone = 10000
    query = """
    SELECT subscriber_count, MIN(timestamp)
    FROM subscriber_data_historical
    WHERE name = %s
    GROUP BY subscriber_count
    ORDER BY subscriber_count ASC
    """
    data = server.execute_query(query, (channel_name,))
    dates = []
    milestones = []
    for row in data:
        subscriber_count = row[0]
        while subscriber_count >= current_milestone:
            dates.append(row[1].strftime("%Y-%m-%d"))
            milestones.append(current_milestone)
            current_milestone += milestone_increment
    return {"milestones": milestones, "dates": dates}

def get_channel_diffs(channel_name):
    server = create_database_connection()
    query = "SELECT * FROM subscriber_data_historical WHERE name = %s ORDER BY timestamp DESC"
    data = server.execute_query(query, (channel_name,))
    if not data:
        return {"diff_1d": None, "diff_7d": None, "diff_30d": None}
    now = datetime.datetime.now()
    latest = data[0][4]
    sub_1d = next((r[4] for r in data if (now - r[5]).days >= 1), None)
    sub_7d = next((r[4] for r in data if (now - r[5]).days >= 7), None)
    sub_30d = next((r[4] for r in data if (now - r[5]).days >= 30), None)
    return {
        "diff_1d": latest - sub_1d if sub_1d is not None else None,
        "diff_7d": latest - sub_7d if sub_7d is not None else None,
        "diff_30d": latest - sub_30d if sub_30d is not None else None,
    }

def get_channel_info(channel_name):
    def find_next_milestone(sc):
        return ((sc // 10000) + 1) * 10000 if sc < 100000 else ((sc // 100000) + 1) * 100000 if sc < 1000000 else ((sc // 1000000) + 1) * 1000000
    server = create_database_connection()
    data = server.execute_query("SELECT * FROM subscriber_data WHERE name = %s", (channel_name,))[0]
    historical = server.execute_query("SELECT * FROM subscriber_data_historical WHERE name = %s ORDER BY timestamp DESC", (channel_name,))
    current = historical[0][4]
    result = {
        "channel_id": data[1], "channel_name": data[3], "profile_pic": data[2], "subscribers": data[4],
        "sub_org": data[5], "video_count": data[6], "view_count": data[8],
        "diff_1d": None, "diff_7d": None, "diff_30d": None
    }
    now = datetime.datetime.now()
    for days, key in [(1, 'diff_1d'), (7, 'diff_7d'), (30, 'diff_30d')]:
        past_val = next((r[4] for r in historical if (now - r[5]).days >= days), None)
        result[key] = current - past_val if past_val is not None else None
    subs, dates, seen = [], [], set()
    for r in historical:
        ds = r[5].strftime("%Y-%m-%d")
        if ds in seen: continue
        subs.append(r[4])
        dates.append(ds)
        seen.add(ds)
    df = pandas.DataFrame({"subscribers": subs, "dates": pandas.to_datetime(dates)}).set_index("dates").sort_index()
    df = df[df.index > (now - datetime.timedelta(days=90))]
    try:
        model = Ridge(alpha=100)
        X = np.arange(len(df)).reshape(-1, 1)
        model.fit(X, df["subscribers"])
        next_m = find_next_milestone(current)
        days_left = int(((next_m - model.intercept_) / model.coef_)[0])
        result.update({
            "next_milestone": str(next_m),
            "days_until_next_milestone": str(days_left),
            "next_milestone_date": str((now.date() + datetime.timedelta(days=days_left))) if days_left >= 0 else "N/A"
        })
    except:
        result.update({"next_milestone": "N/A", "days_until_next_milestone": "N/A", "next_milestone_date": "N/A"})
    return result

def get_group_mappings():
    group_mappings = {}
    for name, group in member_groups.items():
        group_mappings.setdefault(group, []).append(name)
    return group_mappings
