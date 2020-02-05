# pylint: disable=locally-disabled, missing-docstring, no-member

import atexit
import time
import requests
from lib.proxy.exceptions import ProxyClientError


class Proxy:
    """Browserup-proxy client class to interface with the proxy server API.

    Args:
        host (str): The Browserup-proxy server host+port to use.

    """

    def __init__(self, host):
        self.host = f"http://{host}"
        self.port = None
        # Create a new proxy if resources are available. If not, sleep until they are.
        while self.port is None:
            try:
                res = None
                res = requests.post(f"{self.host}/proxy")
                res.raise_for_status()
                data = res.json()
                self.port = data["port"]
            except requests.exceptions.RequestException as error:
                if res and res.status_code == 456:
                    time.sleep(10)
                    continue
                raise ProxyClientError(str(error))
        url_parts = self.host.split(":")
        self.proxy = f"{url_parts[1][2:]}:{self.port}"
        self.proxy_url = f"{self.host}/proxy/{self.port}"
        # Configure the proxy.
        timeout_options = {
            "requestTimeout": "10000",
            "readTimeout": "10000",
            "connectionTimeout": "10000",
            "dnsCacheTimeout": "3000",
        }
        try:
            res = requests.put(f"{self.proxy_url}/timeout", timeout_options)
            res.raise_for_status()
        except requests.exceptions.RequestException as error:
            raise ProxyClientError(str(error))
        # Ensure that any created proxies are deleted upon exit.
        atexit.register(self.close)

    def create_har(self):
        """Create a new capture har on the newly created proxy."""
        har_options = {"captureHeaders": "true"}
        try:
            res = requests.put(f"{self.proxy_url}/har", har_options)
            res.raise_for_status()
        except requests.exceptions.RequestException as error:
            raise ProxyClientError(str(error))
        return res.status_code

    @property
    def har(self):
        """Simply get the captured har data from the proxy."""
        try:
            res = requests.get(f"{self.proxy_url}/har")
        except requests.exceptions.RequestException as error:
            raise ProxyClientError(str(error))
        return res.json()

    def inject_headers(self, headers):
        """Inject HTTP request headers into ALL request made by the proxy."""
        # Check if the provided headers are of type dict. If an empty dict is provided simply
        # simply return None and do nothing.
        if not isinstance(headers, dict):
            raise TypeError(
                "Provided headers must be a dictionary object where each key-value "
                "pair is the header name and value to be injected not a "
                f"{type(headers).__name__}."
            )
        if not headers:
            return None
        data = ""
        for (name, value) in headers.items():
            data += (
                f"request.headers().remove('{name}');"
                f"request.headers().add('{name}', '{value}');"
            )
        try:
            res = requests.post(
                f"{self.proxy_url}/filter/request",
                headers={"Content-Type": "text/plain"},
                data=data,
            )
        except requests.exceptions.RequestException as error:
            raise ProxyClientError(str(error))
        return res.status_code

    def close(self):
        """Delete the created proxy server from the provided Browserup-proxy server."""
        if self.proxy is not None:
            try:
                res = requests.delete(f"{self.proxy_url}")
                res.raise_for_status()
                self.proxy = None
            except requests.exceptions.RequestException as error:
                raise ProxyClientError(str(error))
