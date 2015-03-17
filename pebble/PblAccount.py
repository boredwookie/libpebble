from oauth2client.client import OAuth2WebServerFlow
from oauth2client.client import Credentials
from oauth2client.file import Storage

import sys
import os
import json
import datetime
import oauth2client.tools as tools
import argparse
import httplib2

AUTH_SERVER   = os.getenv("PEBBLE_OAUTH_SERVER", "https://auth.getpebble.com")
AUTHORIZE_URI = AUTH_SERVER + "/oauth/authorize"
TOKEN_URI     = AUTH_SERVER + "/oauth/token"

SDK_CLIENT_ID     = os.getenv("PEBBLE_OAUTH_APP_ID", "8b9140c7b1f101a84a26cab03e6b12273af36829d0e6540394dae61196fe5e7b")
SDK_CLIENT_SECRET = os.getenv("PEBBLE_OAUTH_APP_SECRET", "8fdcbceafcbca6f9fdb6432cfcc246180bb59bcea957795b12efb5527397e2a1")

flow = OAuth2WebServerFlow(
    client_id = SDK_CLIENT_ID,
    client_secret = SDK_CLIENT_SECRET,
    scope = "public",
    auth_uri = AUTHORIZE_URI,
    token_uri = TOKEN_URI
)

class PblAccount(object):
    def __init__(self, storage_file):
        self.storage = Storage(storage_file)

    def is_logged_in(self):
        return True if self.storage.get() else False

    def get_credentials(self):
        return self.storage.get()

    def get_token(self):
        return json.loads(self.storage.get().to_json())['access_token']

    def refresh_credentials(self):
        creds = self.get_credentials()
        if creds: creds.refresh(httplib2.Http())

    def get_access_token(self):
        creds = self.get_credentials()
        token_info = creds.get_access_token()
        return token_info.access_token

    # hack to fix null token expiration
    def set_expiration_to_long_time(self, creds):
        cred_str = creds.to_json()
        cred_json = json.loads(cred_str)
        cred_json['token_expiry'] = '2100-01-01T00:00:01Z'
        cred_new_json = json.dumps(cred_json)
        return Credentials.new_from_json(cred_new_json)

    def login(self):
        parser = argparse.ArgumentParser(description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            parents=[tools.argparser])
        parser.set_defaults(auth_host_port = [60000])

        flags = parser.parse_args([])
        creds = self.set_expiration_to_long_time(tools.run_flow(flow, self.storage, flags))

        self.storage.put(creds)


def get_default_account(storage_file):
   return PblAccount(storage_file)

