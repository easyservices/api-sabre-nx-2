# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

from . import load_config

# Load configuration
config = load_config()

## Base URL for the Nextcloud instance
## This URL is used to access the Nextcloud API and to generate download links for files
## stored in Nextcloud.
# It should point to the root of the Nextcloud installation, including the port number if necessary.
# For example, if your Nextcloud instance is running on https://example.com:8083,
NEXTCLOUD_BASE_URL = config['nextcloud'].get('base_url', 'https://nextcloud.example.com:8083')

# Base URL for the API proxy server
# This is the URL of the server that will handle API requests
# and forward them to the Nextcloud instance.
# it is used only for testings
API_BASE_PROXY_URL = config['nextcloud'].get('api_proxy_url', 'http://localhost:1260')