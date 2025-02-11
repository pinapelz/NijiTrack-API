from webapi.web_api import WebAPI
from typing import Iterable

EXCLUSION_OVERRIDE = ["UCXDytlJU6RL8D68VrPZGyIA"]
class HolodexAPI(WebAPI):
    """
    Class for interacting with the Holodex API
    """

    def __init__(self,api_key: str = None,member_count: int = 300,organization: str = "Nijisanji"):
        super().__init__(api_key=api_key, base_url="https://holodex.net/api/v2/")
        self.member_count = member_count
        self.organization = organization
        self._inactive_channels = []
        self._channel_data = []

    def get_subscriber_data(self) -> Iterable:
        """
        Gets data for all channels in a particular organization
        """
        members = self.member_count
        data = []
        active_channels = []
        offset = 0
        while members > 0:
            data += self._download_url(
                f"channels?type=vtuber&offset={offset}&limit=100&org={self.organization}"
            )
            members -= 100
            offset += 100
        for channel in data:
            print("DEBUG: ", channel["id"])
            try:
                additional_data = self.get_additional_data(channel["id"])
                channel["view_count"] = additional_data[0]
                channel["description"] = additional_data[1]
                if channel["inactive"] and channel["id"] not in EXCLUSION_OVERRIDE:
                    self._inactive_channels.append(channel["id"])
                    continue
                active_channels.append(channel)
            except (KeyError, TypeError, ValueError):
                print("DEBUG:","An error occured with parsing ", channel["id"], channel["name"])
                continue
        self._channel_data = active_channels
        return active_channels

    
    def get_additional_data(self, channel_id: str) -> tuple:
        """
        Gets additional data for a particular channel
        """
        data = self._download_url(f"channels/{channel_id}")
        return data["view_count"], data["description"]
    
    def set_organization(self, organization: str):
        """
        Sets the organization for the API
        """
        self.organization = organization
    
    def get_inactive_channels(self) -> list:
        """
        Gets the list of inactive channels
        """
        return self._inactive_channels

    def get_generated_channel_data(self) -> list:
        """
        Gets the list of channel data
        """
        return self._channel_data
