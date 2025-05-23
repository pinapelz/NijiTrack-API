import os.path
import urllib.request
import json
import configparser
import requests
import hashlib


def _read_file(path: str, lines=True) -> list:
    # reads a file and returns a list of lines
    with open(path, "r", encoding="utf-8") as file:
        if not lines:
            return file.read()
        return file.read().splitlines()


def get_excluded_channels():
    # gets excluded channels from exclude_channel.txt
    if not os.path.exists(os.path.join("data", "exclude_channel.txt")):
        open(os.path.join("data", "exclude_channel.txt"), "w").close()
    excluded_channels = _read_file(os.path.join("data", "exclude_channel.txt"))
    return excluded_channels

def update_excluded_channels(channel_ids: list):
    # add to exclude_channel.txt if not already there
    excluded_channels = get_excluded_channels()
    for channel_id in channel_ids:
        if channel_id not in excluded_channels:
            excluded_channels.append(channel_id)
    with open(os.path.join("data", "exclude_channel.txt"), "w", encoding="utf-8") as file:
        for channel_id in excluded_channels:
            file.write(channel_id + "\n")

def save_local_channels(data: list, path: str = "data"):
    """
    Save the channel names and ids locally for when the API is down
    """
    path = os.path.join(path, "channels.txt")
    excluded_channels = get_excluded_channels()
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
    with open(path, "w", encoding="utf-8") as file:
        for channel in data:
            if channel["id"] in excluded_channels:
                continue
            file.write(f"{channel['id']},{channel['english_name']}\n")


def get_local_channels(path: str = "data"):
    """
    Get the channel names and ids locally for when the API is down
    """
    path = os.path.join(path, "channels.txt")
    if not os.path.exists(path):
        raise Exception("Local channel data not found")
    with open(path, "r", encoding="utf-8") as file:
        rows = file.read().splitlines()
        return [tuple(row.split(":")) for row in rows]


def update_data_files(url: str) -> None:
    # Updates the local txt channel data stored in data folder
    if not os.path.exists(os.path.join("data", "channels.txt")):
        open(os.path.join("data", "channels.txt"), "w").close()
    urllib.request.urlretrieve(
        url + "channels.txt", os.path.join("data", "channels.txt")
    )
    # downloaded txt file from url and write to channels.txt

    if not os.path.exists(os.path.join("data", "exclude_channel.txt")):
        open(os.path.join("data", "exclude_channel.txt"), "w").close()
    urllib.request.urlretrieve(
        url + "exclude_channel.txt", os.path.join("data", "exclude_channel.txt")
    )


def load_config(ini_filepath: str) -> dict:
    config_object = configparser.ConfigParser()
    file = open(ini_filepath, "r")
    config_object.read_file(file)
    output_dict = {}
    sections = config_object.sections()
    for section in sections:
        output_dict[section] = {}
        for key in config_object[section]:
            output_dict[section][key] = config_object[section][key]
    return output_dict

def load_json_file(json_file_path: str) -> dict:
    with open(json_file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def compare_file_with_url(file_path, url):
    try:
        with open(file_path, "rb") as f:
            local_hash = hashlib.md5(f.read()).hexdigest()
        response = requests.get(url)
        response.raise_for_status()
        remote_hash = hashlib.md5(response.content).hexdigest()
        print(f"HASH RESULT: {file_path} | {url} ->  {local_hash == remote_hash}")
        return local_hash == remote_hash
    except Exception as e:
        print(f"Error comparing {file_path} and {url}: {e}")
        return False
