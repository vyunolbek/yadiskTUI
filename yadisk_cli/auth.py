from typing import Optional

import yadisk

from yadisk_cli.config import load_config, save_token, load_token, delete_token


def get_client_from_token() -> Optional[yadisk.Client]:
    token_data = load_token()
    if token_data is None:
        return None
    token = token_data.get("access_token")
    if not token:
        return None
    client = yadisk.Client(token=token)
    try:
        if not client.check_token():
            if token_data.get("refresh_token"):
                try:
                    new_token = client.refresh_token(token_data["refresh_token"])
                    save_token(new_token)
                    client.token = new_token["access_token"]
                    if client.check_token():
                        return client
                except Exception:
                    pass
            delete_token()
            return None
    except Exception:
        return None
    return client


def save_token_and_get_client(token_data) -> Optional[yadisk.Client]:
    save_token(token_data)
    client = yadisk.Client(token=token_data["access_token"])
    print("Authentication successful!")
    return client


def login_with_token(token: str) -> Optional[yadisk.Client]:
    if not token:
        print("Error: OAuth token is required.")
        return None
    client = yadisk.Client(token=token)
    try:
        if not client.check_token():
            print("Token is invalid or expired.")
            return None
        save_token({"access_token": token})
        print("Authentication successful!")
        return client
    except Exception as e:
        print(f"Authentication failed: {e}")
        return None


def login_device_flow(client_id: str = "", client_secret: str = "") -> Optional[yadisk.Client]:
    if not client_id:
        config = load_config()
        client_id = config.get("yandex_client_id", "")
    if not client_secret:
        config = load_config()
        client_secret = config.get("yandex_client_secret", "")
    if not client_id:
        print("Error: Yandex OAuth client ID is required.")
        print("Register an app at https://oauth.yandex.com/client/new")
        print("Then set it with: yd config yandex_client_id YOUR_CLIENT_ID")
        return None
    if not client_secret:
        print("Error: Yandex OAuth client secret is required.")
        print("Set it with: yd config yandex_client_secret YOUR_CLIENT_SECRET")
        return None

    client = yadisk.Client(id=client_id, secret=client_secret)
    try:
        dc = client.get_device_code(scope="cloud_api:disk.read cloud_api:disk.write")
        print(f"Open this URL: {dc.verification_url}")
        print(f"Enter this code: {dc.user_code}")
        import time
        interval = dc.interval or 5
        expires_in = dc.expires_in or 300
        for _ in range(expires_in // interval):
            time.sleep(interval)
            try:
                token_data = client.get_token_from_device_code(dc.device_code)
                return save_token_and_get_client(token_data)
            except yadisk.exceptions.AuthorizationPendingError:
                continue
            except Exception as e:
                print(f"Authentication failed: {e}")
                return None
        print("Code expired. Please try again.")
        return None
    except Exception as e:
        print(f"Failed to start authentication: {e}")
        return None
