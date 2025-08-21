from dotenv import load_dotenv
import json
import requests
import sys
import os
import time
import argparse
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from sql.pg_handler import PostgresHandler
load_dotenv()


def download_site_as_html(url: str, timeout: int = 10, response_encoding=None) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response_encoding:
            response.encoding = response_encoding
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return ""

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


def get_list_of_channels(database: PostgresHandler):
    """
    Get list of channels from the live table
    Returns: List of tuples containing (name, channel_id)
    """
    import json
    with open(os.path.join(os.path.dirname(__file__), '..', 'sql_table_config.json'), 'r') as f:
        config = json.load(f)
    table_name = config['TABLE_LIVE']
    query = f"SELECT name, channel_id FROM {table_name}"
    try:
        result = database.execute_query(query)
        return [(row[0], row[1]) for row in result] if result else []
    except Exception as e:
        print(f"Error getting channels from database: {e}")
        return []


def check_missing_dates_for_channel(database: PostgresHandler, channel_id: str, from_date: str, to_date: str):
    """
    Check which dates are missing for a specific channel in the historical table
    Args:
        database: PostgresHandler instance
        channel_id: Channel ID to check
        from_date: Start date in YYYY-MM-DD format
        to_date: End date in YYYY-MM-DD format
    Returns: List of missing dates in YYYY-MM-DD format
    """
    with open(os.path.join(os.path.dirname(__file__), '..', 'sql_table_config.json'), 'r') as f:
        config = json.load(f)

    table_name = config['TABLE_HISTORICAL']
    start_date = datetime.strptime(from_date, '%Y-%m-%d')
    end_date = datetime.strptime(to_date, '%Y-%m-%d')

    all_dates = []
    current_date = start_date
    while current_date <= end_date:
        all_dates.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)
    query = f"""
    SELECT DISTINCT DATE(timestamp) as date_only
    FROM {table_name}
    WHERE channel_id = %s
    AND DATE(timestamp) BETWEEN %s AND %s
    ORDER BY date_only
    """

    try:
        result = database.execute_query(query, (channel_id, from_date, to_date))
        existing_dates = [row[0].strftime('%Y-%m-%d') for row in result] if result else []
        missing_dates = [date for date in all_dates if date not in existing_dates]
        return missing_dates
    except Exception as e:
        print(f"Error checking missing dates for channel {channel_id}: {e}")
        return all_dates


def convert_subscriber_count(sub_text: str) -> int:
    """
    Convert subscriber count text like '92.4K' to integer
    Args:
        sub_text: Subscriber count text (e.g., '92.4K', '1.2M', '5000')
    Returns: Integer subscriber count
    """
    if not sub_text:
        return 0
    clean_text = re.sub(r'[^\d.KMBkmb]', '', sub_text.upper())
    if 'K' in clean_text:
        number = float(clean_text.replace('K', ''))
        return int(number * 1000)
    elif 'M' in clean_text:
        number = float(clean_text.replace('M', ''))
        return int(number * 1000000)
    elif 'B' in clean_text:
        number = float(clean_text.replace('B', ''))
        return int(number * 1000000000)
    else:
        try:
            return int(float(clean_text))
        except ValueError:
            return 0


def scrape_socialblade_data_for_date(channel_id: str, target_date: str) -> dict:
    """
    Scrape subscriber count for a specific date from SocialBlade historical data
    Args:
        channel_id: YouTube channel ID
        target_date: Date in YYYY-MM-DD format
    Returns: Dictionary with scraped data for that date
    """
    url = f"https://socialblade.com/youtube/channel/{channel_id}"
    html_content = download_site_as_html(url)

    if not html_content:
        return {}

    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        tables = soup.find_all('table')
        subscriber_count = 0

        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    date_cell = cells[0].get_text().strip()
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_cell)
                    if date_match and date_match.group(1) == target_date:
                        if len(cells) >= 3:
                            sub_text = cells[2].get_text().strip()
                            subscriber_count = convert_subscriber_count(sub_text)
                            break

            if subscriber_count > 0:
                break
        if subscriber_count == 0:
            stats_elements = soup.find_all('p', class_='text-[1.25em]')
            for element in stats_elements:
                parent = element.parent
                if parent and 'subscribers' in parent.get_text().lower():
                    subscriber_count = convert_subscriber_count(element.get_text().strip())
                    break

        return {
            'subscriber_count': subscriber_count,
            'channel_id': channel_id,
            'date': target_date
        }
    except Exception as e:
        print(f"Error parsing SocialBlade data for {channel_id} on {target_date}: {e}")
        return {}


def get_profile_pic_from_live(database: PostgresHandler, channel_id: str) -> str:
    """
    Get profile pic URL from live table for a given channel
    Args:
        database: PostgresHandler instance
        channel_id: YouTube channel ID
    Returns: Profile pic URL or placeholder if not found
    """
    with open(os.path.join(os.path.dirname(__file__), '..', 'sql_table_config.json'), 'r') as f:
        config = json.load(f)

    table_name = config['TABLE_LIVE']
    query = f"SELECT profile_pic FROM {table_name} WHERE channel_id = %s"

    try:
        result = database.execute_query(query, (channel_id,))
        if result and len(result) > 0:
            return result[0][0]
        else:
            return f"https://yt3.ggpht.com/placeholder"
    except Exception as e:
        print(f"Error getting profile pic for {channel_id}: {e}")
        return f"https://yt3.ggpht.com/placeholder"


def insert_historical_data(database: PostgresHandler, channel_id: str, name: str, subscriber_count: int, date: str):
    """
    Insert scraped data into historical table
    Args:
        database: PostgresHandler instance
        channel_id: YouTube channel ID
        name: Channel name
        subscriber_count: Subscriber count
        date: Date string in YYYY-MM-DD format
    """
    with open(os.path.join(os.path.dirname(__file__), '..', 'sql_table_config.json'), 'r') as f:
        config = json.load(f)

    table_name = config['TABLE_HISTORICAL']
    timestamp = f"{date} 00:00:00"  # Set to midnight
    profile_pic = get_profile_pic_from_live(database, channel_id)

    query = f"""
    INSERT INTO {table_name} (channel_id, profile_pic, name, subscriber_count, timestamp)
    VALUES (%s, %s, %s, %s, %s)
    """

    try:
        database.execute_query(query, (channel_id, profile_pic, name, subscriber_count, timestamp))
        print(f"  Inserted data for {date}: {subscriber_count} subscribers")
    except Exception as e:
        print(f"  Error inserting data for {date}: {e}")


def stub_insert_historical_data(database: PostgresHandler, channel_id: str, name: str, subscriber_count: int, date: str):
    """
    Stub function to print what would be inserted into historical table
    """
    timestamp = f"{date} 00:00:00"  # Set to midnight
    profile_pic = get_profile_pic_from_live(database, channel_id)

    print(f"  STUB: Would insert into historical table:")
    print(f"    Channel ID: {channel_id}")
    print(f"    Name: {name}")
    print(f"    Subscriber Count: {subscriber_count}")
    print(f"    Timestamp: {timestamp}")
    print(f"    Profile Pic: {profile_pic}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Recovery script for NijiTrack API')
    parser.add_argument('--from', dest='from_date', required=True,
                       help='Start date in YYYY-MM-DD format')
    parser.add_argument('--to', dest='to_date', required=True,
                       help='End date in YYYY-MM-DD format')
    parser.add_argument('--dry-run', action='store_true',
                       help='Only show what would be inserted, do not write to database')

    args = parser.parse_args()
    try:
        datetime.strptime(args.from_date, '%Y-%m-%d')
        datetime.strptime(args.to_date, '%Y-%m-%d')
    except ValueError:
        print("Error: Dates must be in YYYY-MM-DD format")
        sys.exit(1)
    if datetime.strptime(args.from_date, '%Y-%m-%d') > datetime.strptime(args.to_date, '%Y-%m-%d'):
        print("Error: From date cannot be later than to date")
        sys.exit(1)

    database = create_database_connection()
    channels = get_list_of_channels(database)

    print(f"Checking for missing dates from {args.from_date} to {args.to_date}")
    print(f"Found {len(channels)} channels to process")

    for name, channel_id in channels:
        print(f"\nProcessing channel: {name} ({channel_id})")
        missing_dates = check_missing_dates_for_channel(database, channel_id, args.from_date, args.to_date)

        if missing_dates:
            print(f"  Found {len(missing_dates)} missing dates")
            for date in missing_dates:
                print(f"    Processing date: {date}")
                socialblade_data = scrape_socialblade_data_for_date(channel_id, date)

                if socialblade_data and socialblade_data.get('subscriber_count', 0) > 0:
                    subscriber_count = socialblade_data['subscriber_count']
                    print(f"    Scraped subscriber count for {date}: {subscriber_count}")
                    if args.dry_run:
                        stub_insert_historical_data(database, channel_id, name, subscriber_count, date)
                    else:
                        insert_historical_data(database, channel_id, name, subscriber_count, date)
                else:
                    print(f"    Failed to scrape data for {channel_id} on {date}")
                time.sleep(1.0)
        else:
            print(f"  No missing dates found")
