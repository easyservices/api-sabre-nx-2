from src.common.libs.helpers import UserSettings


class UsersSettings:
    """Class to hold user settings for tests only against a Nextcloud server."""
    USERS: dict[str, UserSettings] = {
        "a_test_user": UserSettings(
            NEXTCLOUD_USERNAME="a_test_user",
            NEXTCLOUD_PASSWORD="_a_very_unsecure_password_",
        ),
    }

