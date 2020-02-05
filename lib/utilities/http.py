# pylint: disable=locally-disabled, missing-docstring, c-extension-no-member

from urllib.parse import urlparse
import socket
import re
import pycurl
import lib.constants as constants


class _ResponseHandler:
    """Simple class to handle the response data returned by an executed cURL.

    Attributes:
        data (dict): Dict which contains all response data from an executed cURL.

    """

    def __init__(self):
        self.data = {"version": None, "reason": None, "headers": {}, "body": None}

    def store_body(self, body):
        """Store the HTTP response content."""
        self.data["body"] = body.decode("iso-8859-1")

    def store_header(self, header):
        """Store the HTTP response headers."""
        header = header.decode("iso-8859-1")
        if ":" in header:
            name, value = header.split(":", 1)
            self.data["headers"][name.lower()] = value.strip()
        elif "http" in header.lower():
            match = re.search(r"(?i)HTTP\/(\S*)\s*\d+\s*(.*?)\s*$", header.strip())
            if match:
                self.data["version"] = match.group(1)
                self.data["reason"] = match.group(2)


def _parse_url(url):
    """Parse a given URL and split it into three required parts: scheme, domain and port."""
    data = {"scheme": None, "domain": None, "port": None}
    if url[:7] != "http://" and url[:8] != "https://":
        parts = list(urlparse(f"//{url}", scheme="http"))
    else:
        parts = list(urlparse(url))
    data["scheme"] = parts[0]
    if ":" in parts[1]:
        data["domain"], data["port"] = parts[1].split(":", 1)
    else:
        data["domain"] = parts[1]
        if data["scheme"] == "http":
            data["port"] = "80"
        elif data["scheme"] == "https":
            data["port"] = "443"
    return data


def _setup_curl(url, response_handler, **kwargs):
    """Setup the cURL request with all provided options."""
    version = str(kwargs.get("version", None))
    resolve = kwargs.get("resolve", None)
    headers = kwargs.get("headers", [])
    method = kwargs.get("method", "HEAD").upper()
    ignore_ssl = kwargs.get("ignore_ssl", False)
    curl = pycurl.Curl()
    if method == "GET":
        curl.setopt(pycurl.HTTPGET, 1)
    else:
        curl.setopt(pycurl.NOBODY, 3)
    if isinstance(headers, dict):
        headers = [f"{key}: {value}" for (key, value) in headers.items()]
    curl.setopt(pycurl.HTTPHEADER, headers)
    curl.setopt(pycurl.FOLLOWLOCATION, 1)
    # We're essentially sending the HTTP response body to /dev/null here.
    curl.setopt(pycurl.WRITEFUNCTION, lambda x: None)
    curl.setopt(pycurl.HEADERFUNCTION, response_handler.store_header)
    curl.setopt(pycurl.SSL_VERIFYPEER, bool(ignore_ssl))
    curl.setopt(pycurl.SSL_VERIFYHOST, bool(ignore_ssl))
    curl.setopt(pycurl.TIMEOUT, constants.CURL_TIMEOUT)
    if version in ("2.0", "2"):
        curl.setopt(pycurl.HTTP_VERSION, pycurl.CURL_HTTP_VERSION_2_0)
    elif version in ("1.0", "1"):
        curl.setopt(pycurl.HTTP_VERSION, pycurl.CURL_HTTP_VERSION_1_0)
    else:
        curl.setopt(pycurl.HTTP_VERSION, pycurl.CURL_HTTP_VERSION_1_1)
    if resolve is not None:
        try:
            socket.inet_aton(resolve)
            url_parts = _parse_url(url)
            curl.setopt(pycurl.RESOLVE, [f"{url_parts['domain']}:{url_parts['port']}:{resolve}"])
        except socket.error:
            pass
    curl.setopt(pycurl.URL, url)
    return curl


def http_request(url, **kwargs):
    """Function to perform HTTP requests via PyCurl and return the results.

    Args:
        url          (str) : The URL to cURL.
        **version    (str) : Keyword argument to optionally specify the HTTP version to use when
                             performing an HTTP request. Defaults to 1.1 if not specified.
        **resolve    (str) : Keyword argument to optionally specify the resolved IP
                             address for the provided domain in the `url` arg.
        **headers    (list): Keyword argument to optionally specify a list of HTTP header to
                             inject into the request body.
        **method     (str) : Keyword argument to optionally specify the HTTP method. Defaults to
                             GET.
        **ignore_ssl (bool): Keyword argument to optionally specify whether or not to disable SSL
                             checks. Defaults to False.

    Returns:
        dict: Returns a dictionary object with test results.

    """
    method = kwargs.get("method", "HEAD").upper()
    comment = None
    if method not in ("GET", "HEAD"):
        comment = f"Provided HTTP method of '{method}' is not supported. Using HEAD."
        method = "HEAD"
    result = {
        "url": url,
        "status": 0,
        "reason": None,
        "version": None,
        "method": method,
        "headers": {},
        "time_namelookup": None,
        "time_connect": None,
        "time_appconnect": None,
        "time_starttransfer": None,
        "time_total": None,
        "speed_download": None,
        "comment": comment,
        "failed": True,
    }
    response = _ResponseHandler()
    curl = _setup_curl(url, response, **kwargs)
    try:
        curl.perform()
        result["status"] = curl.getinfo(pycurl.HTTP_CODE)
        result["reason"] = response.data["reason"]
        result["version"] = response.data["version"]
        result["headers"] = response.data["headers"]
        result["time_namelookup"] = format(curl.getinfo(pycurl.NAMELOOKUP_TIME), ".3f")
        result["time_connect"] = format(curl.getinfo(pycurl.CONNECT_TIME), ".3f")
        result["time_appconnect"] = format(curl.getinfo(pycurl.APPCONNECT_TIME), ".3f")
        result["time_starttransfer"] = format(curl.getinfo(pycurl.STARTTRANSFER_TIME), ".3f")
        result["time_total"] = format(curl.getinfo(pycurl.TOTAL_TIME), ".3f")
        # Original value returned by cURL is Bps. I converted it to bps.
        result["speed_download"] = curl.getinfo(pycurl.SPEED_DOWNLOAD) * 8
        result["failed"] = False
    except pycurl.error as error:
        result["status"] = error.args[0]
        result["reason"] = error.args[1]
    curl.close()
    return result
