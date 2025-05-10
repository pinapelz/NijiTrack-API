import argparse
import os
from datetime import datetime

import dotenv
import pytz
from logger import *
from sql.pg_handler import PostgresHandler
from webapi.holodex import HolodexAPI
from webapi.youtube import YouTubeAPI
from enum import Enum

import fileutil as fs
import graph

class BucketType(Enum):
    B2 = 1
    R2 = 2

dotenv.load_dotenv()

DATA_SETTING = fs.load_json_file("sql_table_config.json")
logger = Logger("nijitrack-logs.txt")

def create_database_connection():
    """
    Creates a database connection using the environment variables
    :param: auth_append: str = "" - If you want to use a different set of variables for persisitance of sessions
    """
    hostname = os.environ.get("POSTGRES_HOST")
    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    database = os.environ.get("POSTGRES_DATABASE")
    port = os.environ.get("POSTGRES_PORT") if os.environ.get("POSTGRES_PORT") else 6543
    return PostgresHandler(host_name=hostname, username=user, password=password, database=database, port=port)

@track_task_time("Initializing Database")
def initialize_database(server: PostgresHandler):
    server.create_table(name = DATA_SETTING["TABLE_LIVE"], column = DATA_SETTING["LIVE_COLUMNS"])
    server.create_table(name = DATA_SETTING["TABLE_HISTORICAL"], column = DATA_SETTING["HISTORICAL_COLUMNS"])
    server.create_table(name = DATA_SETTING["TABLE_DAILY"], column = DATA_SETTING["DAILY_COLUMNS"])


@track_task_time("Inserting Live Data into Database")
def record_subscriber_data(data: list, force_refresh: bool = False):
    """
    Inserts subscriber data into the database. If the channel does not exist, it will insert a new row.
    Rows are only inserted into the historical table if it has been 24 hours since the last row or it does not exist.
    Rows are added to the live table regardless
    """
    def transform_sql_string(string: str) -> str:
        return string.encode("ascii", "ignore").decode().replace("'", "''")

    def update_data_records(data_tuple: tuple, refresh_daily: bool):
        if not server.check_row_exists(DATA_SETTING["TABLE_DAILY"], "channel_id", channel_id):
            server.insert_row(DATA_SETTING["TABLE_DAILY"], DATA_SETTING["DAILY_HEADER"], (data_tuple[0], data_tuple[3]))
            server.insert_row(table_name = DATA_SETTING["TABLE_HISTORICAL"], column = DATA_SETTING["HISTORICAL_HEADER"], data=data_tuple)
            return
        elif refresh_daily:
            server.update_row(DATA_SETTING["TABLE_DAILY"], "channel_id", channel_id, "sub_diff", sub_count)
            server.insert_row(table_name = DATA_SETTING["TABLE_HISTORICAL"], column = DATA_SETTING["HISTORICAL_HEADER"], data=data_tuple)

    def check_diff_refresh():
        last_updated = server.get_most_recently_added_row_time(DATA_SETTING["TABLE_HISTORICAL"])
        if last_updated is None or len(last_updated) == 0 or not last_updated[0]:
            print("Failed to get the most recently added row time.")
            return False
        last_updated = pytz.timezone('US/Pacific').localize(last_updated[0])
        utc_now = datetime.now(pytz.timezone('UTC'))
        pst_now = utc_now.astimezone(pytz.timezone('US/Pacific'))
        time_diff = pst_now - last_updated
        if time_diff.days >= 1:
            return True
        elif time_diff.days == 0 and time_diff.seconds >= 85800:
            return True
        else:
            logger.log(f"Time difference is {time_diff.days} days and {time_diff.seconds} seconds")
            return False
    exclude_channels = fs.get_excluded_channels()
    if force_refresh:
        should_update_historical_data = True
    else:
        should_update_historical_data = check_diff_refresh()
    for channel in data:
        channel_id = channel["id"]
        if channel_id in exclude_channels:
            continue
        pfp = channel["photo"]
        sub_count = channel["subscriber_count"]
        channel_name = channel["english_name"]
        sub_org = channel["group"]
        video_count = channel["video_count"]
        view_count = channel["view_count"]
        if channel_name is None:
            channel_name = channel["name"]
        if sub_org is None:
            sub_org = "Unknown"
        channel_name = transform_sql_string(channel_name)
        utc_now = datetime.now(pytz.timezone('UTC'))
        pst_now = utc_now.astimezone(pytz.timezone('US/Pacific'))
        formatted_time = pst_now.strftime('%Y-%m-%d %H:%M:%S')
        data_tuple = (channel_id, pfp, channel_name, sub_count, sub_org, video_count, view_count, formatted_time)
        historical_data_tuple = (channel_id, pfp, channel_name, sub_count, formatted_time)
        server.insert_row(table_name = DATA_SETTING["TABLE_LIVE"], column = DATA_SETTING["LIVE_HEADER"], data=data_tuple)
        update_data_records(historical_data_tuple, should_update_historical_data)


@track_task_time("Running Holodex Generation")
def holodex_generation(server: PostgresHandler, force_refresh: bool = False):
    """
    Generates the data from the Holodex API
    """
    holodex_organizations = DATA_SETTING["HOLODEX_ORGS"].split(",")
    holodex = HolodexAPI(os.environ.get("HOLODEX_KEY"), organization="Phase%20Connect")
    for organization in holodex_organizations:
        holodex.set_organization(organization)
        subscriber_data = holodex.get_subscriber_data()
        record_subscriber_data(subscriber_data, force_refresh)
    return holodex.get_generated_channel_data(), holodex.get_inactive_channels()

@track_task_time("Running YouTube Generation")
def youtube_generation(server: PostgresHandler):
    """
    Generates the data from the YouTube API
    """
    ytapi = YouTubeAPI(os.environ.get("YOUTUBE_API_KEY"))
    server.clear_table(DATA_SETTING["TABLE_LIVE"])
    data = ytapi.get_data_all_channels(fs.get_local_channels())
    record_subscriber_data(data)
    return data

def combine_excluded_channel_ids(inactive_channel_data: list, excluded_channels: list):
    """
    Combines the local excluded channels with the inactive channels from the API
    """
    channel_ids = []
    for inactive_channel in inactive_channel_data:
        if inactive_channel in excluded_channels:
            continue
        channel_ids.append(inactive_channel)
    return channel_ids

def uploadFileToBucketB2(filepath: str) -> bool:
    from b2sdk.v2 import InMemoryAccountInfo, B2Api
    try:
        info = InMemoryAccountInfo()
        b2_api = B2Api(info)
        application_key_id = os.environ.get("B2_APP_ID")
        application_key = os.environ.get("B2_APP_KEY")
        bucket_name = os.environ.get("B2_BUCKET_NAME")
        file_info = {'how': 'good-file'}
        b2_api.authorize_account("production", application_key_id, application_key)
        b2_file_name = "graph.html"
        bucket = b2_api.get_bucket_by_name(bucket_name)
        bucket.upload_local_file(local_file=filepath, file_name=b2_file_name, file_info=file_info)
        return True
    except Exception as e:
        print("An error occured while attempting to upload to B2")
        print(e)
        return False

def uploadFileToBucketR2(filepath: str) -> bool:
    import boto3
    account_id = os.environ.get("R2_ACCOUNT_ID")
    access_key = os.environ.get("R2_ACCESS_KEY")
    secret_key = os.environ.get("R2_SECRET_KEY")
    bucket_name = os.environ.get("R2_BUCKET_NAME")
    s3 = boto3.resource(
        's3',
        endpoint_url=f'https://{account_id}.r2.cloudflarestorage.com',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key
    )
    try:
        with open(filepath, "rb") as f:
            s3.Bucket(bucket_name).upload_fileobj(f, filepath)
        return True
    except Exception as e:
        print("An error occurred while attempting to upload to R2")
        print(e)
        return False

def generate_api_routes(bucket_type: BucketType):
    import app
    api_subscribers = app.api_subscribers()
    print(api_subscribers)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NijiTrack - A Subscriber Tracker")
    parser.add_argument('--mode', choices=['yt', 'holodex'], help='Specify the data source to use (yt or holodex)')
    parser.add_argument('--b2', action='store_true', help="Use Backblaze B2 as the bucket upload source")
    parser.add_argument('--r2', action='store_true', help="Use Cloudflare R2 as the bucket upload source")
    parser.add_argument('--uploadGraph', action='store_true', help="Upload graph html to Backblaze B2")
    parser.add_argument('--uploadRoutes', action='store_true', help="Pre-generate every API route and upload it")
    parser.add_argument('--ff', action='store_true', help="Force a full refresh of all data (override daily refresh)")
    args = parser.parse_args()
    server = create_database_connection()
    initialize_database(server)
    if args.mode == 'yt':
        print("Using YouTube API")
        channel_data = youtube_generation(server)
        inactive_channels = fs.get_excluded_channels()
    else:
        if args.ff:
            print("Forcing a full refresh")
            channel_data, inactive_channels = holodex_generation(server, force_refresh=True)
        else:
            channel_data, inactive_channels = holodex_generation(server)
    fs.update_excluded_channels(inactive_channels)
    graph_html = graph.plot_subscriber_count_over_time(server, DATA_SETTING["TABLE_HISTORICAL"], exclude_channels=combine_excluded_channel_ids(inactive_channels, fs.get_excluded_channels()))
    with open("index.html", "w", encoding="utf-8") as file:
        file.write(graph_html)
    upstream_bucket = None
    if args.b2:
        upstream_bucket = BucketType.B2
    elif args.r2:
        upstream_bucket = BucketType.R2

    if args.uploadGraph:
        if upstream_bucket is None:
            print("Tried to upload graph but no remote source has been specified. Skipping....")
            match upstream_bucket:
                case BucketType.B2:
                    uploadFileToBucketB2("index.html")
                case BucketType.R2:
                    uploadFileToBucketR2("index.html")

    if args.uploadRoutes:
        if upstream_bucket is None:
            print("Tried to upload routes but no remote source has been specified. Skipping....")
        generate_api_routes(upstream_bucket)
