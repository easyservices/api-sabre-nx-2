# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

from typing import Optional

from src.nextcloud.config import get_nextcloud_base_url


class UserSettings:
    """ Base class for user settings."""
    NEXTCLOUD_USERNAME: str
    NEXTCLOUD_PASSWORD: str
    NEXTCLOUD_CALENDAR: str | None
    
    def __init__(
        self,
        NEXTCLOUD_USERNAME: str = "",
        NEXTCLOUD_PASSWORD: str = "",
        NEXTCLOUD_CALENDAR: str | None = None,
    ):
        self.NEXTCLOUD_USERNAME = NEXTCLOUD_USERNAME
        self.NEXTCLOUD_PASSWORD = NEXTCLOUD_PASSWORD
        self.NEXTCLOUD_CALENDAR = NEXTCLOUD_CALENDAR
    
def gen_nxtcloud_url_addressbook(username: str, addressbook_name: str = "contacts") -> str:
    """Generate the Nextcloud URL for the address book of a given user.
    
    Args:
        username (str): The username of the user.
        addressbook_name (str, optional): The name of the addressbook. Defaults to None.
        
    Returns:
        str: The generated Nextcloud URL for the address book.
    """
    if not username:
        raise ValueError("username is required")
    base_url = get_nextcloud_base_url()
    return f"{base_url}/remote.php/dav/addressbooks/users/{username}/{addressbook_name}/"
    
def gen_nxtcloud_url_calendar(username: str, calendar_name: str = "personal") -> str:
    """Generate the Nextcloud URL for the calendar of a given user.
    
    Args:
        username (str): The username of the user.
        calendar_name (str, optional): The name of the calendar. Defaults to None.
        
    Returns:
        str: The generated Nextcloud URL for the calendar.
    """
    if not username:
        raise ValueError("username is required")
    base_url = get_nextcloud_base_url()
    return f"{base_url}/remote.php/dav/calendars/{username}/{calendar_name}/"
