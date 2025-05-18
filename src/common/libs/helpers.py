# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

from src.nextcloud.config import NEXTCLOUD_BASE_URL

class UserSettings:
    """ Base class for user settings."""
    NEXTCLOUD_USERNAME: str
    NEXTCLOUD_PASSWORD: str
    
    def __init__(self,
                 NEXTCLOUD_USERNAME: str = None,
                 NEXTCLOUD_PASSWORD: str = None,):
        self.NEXTCLOUD_USERNAME = NEXTCLOUD_USERNAME
        self.NEXTCLOUD_PASSWORD = NEXTCLOUD_PASSWORD

def gen_nxtcloud_url_addressbook(username: str) -> str:
    """Generate the Nextcloud URL for the address book of a given user.
    
    Args:
        username (str): The username of the user.
        
    Returns:
        str: The generated Nextcloud URL for the address book.
    """
    return f"{NEXTCLOUD_BASE_URL}/remote.php/dav/addressbooks/users/{username}/contacts/"

def gen_nxtcloud_url_calendar(username: str, calendar_name: str = None) -> str:
    """Generate the Nextcloud URL for the calendar of a given user.
    
    Args:
        username (str): The username of the user.
        calendar_name (str, optional): The name of the calendar. Defaults to None.
        
    Returns:
        str: The generated Nextcloud URL for the calendar.
    """
    if not calendar_name:
        calendar_name = "personal"
    return f"{NEXTCLOUD_BASE_URL}/remote.php/dav/calendars/{username}/{calendar_name}/"