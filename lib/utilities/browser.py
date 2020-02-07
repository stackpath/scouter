# pylint: disable=locally-disabled, missing-docstring, no-member, wildcard-import

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from lib.proxy import *
import lib.constants as constants


def _format_har(har):
    """Format the retrieved HAR data from the proxy."""
    formatted_har = []
    for entry in har["log"]["entries"]:
        # Return the curl equivalent error codes on errors rather than sending a generic value of 0.
        if "_error" in entry["response"]:
            reason = entry["response"]["_error"]
            if "Unable to resolve host" in reason:
                entry["response"]["status"] = 6
            elif "Unable to connect to host" in reason:
                entry["response"]["status"] = 7
            elif "Response timed out" in reason:
                entry["response"]["status"] = 28
            elif "No response received" in reason:
                entry["response"]["status"] = 52
            entry["response"]["statusText"] = reason
            entry["failed"] = True
        else:
            entry["failed"] = False
        # Format the response headers.
        response_headers = {}
        for header in entry["response"]["headers"]:
            response_headers[header["name"].lower()] = header["value"]
        entry["response"]["headers"] = response_headers
        # Format timing information retrived from the request.
        del entry["timings"]["comment"]
        for key in entry["timings"]:
            if entry["timings"][key] == -1:
                entry["timings"][key] = 0
            entry["timings"][key] = float(entry["timings"][key])
        entry["timings"]["total"] = float(entry["time"])
        formatted_har.append(entry)
    return formatted_har


def _setup_chrome(proxy):
    """Setup the Google chromedriver to run as minimally as possible"""
    opt = webdriver.ChromeOptions()
    # Setup Chrome options to run as minimal as possible.
    opt.add_argument("--headless")
    opt.add_argument("--incognito")
    # Instruct Chrome to proxy all requests via our previously created proxy server.
    opt.add_argument(f"--proxy-server={proxy.proxy}")
    opt.add_argument("--no-sandbox")
    opt.add_argument("--disable-background-networking")
    opt.add_argument("--enable-features=NetworkService,NetworkServiceInProcess")
    opt.add_argument("--disable-background-timer-throttling")
    opt.add_argument("--disable-backgrounding-occluded-windows")
    opt.add_argument("--disable-breakpad")
    opt.add_argument("--disable-client-side-phishing-detection")
    opt.add_argument("--disable-default-apps")
    opt.add_argument("--disable-extensions")
    opt.add_argument("--disable-features=site-per-process,TranslateUI,BlinkGenPropertyTrees")
    opt.add_argument("--disable-hang-monitor")
    opt.add_argument("--disable-ipc-flooding-protection")
    opt.add_argument("--disable-popup-blocking")
    opt.add_argument("--disable-prompt-on-repost")
    opt.add_argument("--disable-renderer-backgrounding")
    opt.add_argument("--disable-sync")
    opt.add_argument("--force-color-profile=srgb")
    opt.add_argument("--metrics-recording-only")
    opt.add_argument("--no-first-run")
    opt.add_argument("--safebrowsing-disable-auto-update")
    opt.add_argument("--enable-automation")
    opt.add_argument("--password-store=basic")
    opt.add_argument("--use-mock-keychain")
    opt.add_argument("--hide-scrollbars")
    opt.add_argument("--mute-audio")
    # Accept untrusted certs.
    opt.add_argument("--ignore-certificate-errors")
    try:
        return webdriver.Chrome(chrome_options=opt)
    except WebDriverException as error:
        proxy.close()
        raise Exception(str(error))


def _setup_firefox(proxy):
    """Setup the Mozilla geckodriver to run as minimally as possible"""
    opt = webdriver.FirefoxOptions()
    opt.add_argument("-headless")
    opt.add_argument("-private")
    opt.add_argument("-safe-mode")
    opt.add_argument("-no-remote")
    pro = webdriver.FirefoxProfile()
    # Instruct Firefox to proxy all requests via our previously created proxy server.
    pro.set_proxy(webdriver.Proxy({"httpProxy": proxy.proxy, "sslProxy": proxy.proxy}))
    # Accept untrusted certs.
    pro.accept_untrusted_certs = True
    try:
        return webdriver.Firefox(firefox_profile=pro, firefox_options=opt, log_path="/dev/null")
    except WebDriverException as error:
        proxy.close()
        raise Exception(str(error))


def _setup_proxy(headers):
    """Setup the BUP HTTP proxy used to capture HAR data."""
    proxy = None
    # Setup the proxy server used to capture har data.
    try:
        proxy = Proxy("localhost:8080")
        proxy.create_har()
        # The proxy client already does type checking to ensure that the passed headers to be
        # injected is a dictionary. Simply re-raise the exception if that is not the case.
        try:
            proxy.inject_headers(headers)
        except TypeError:
            proxy.close()
            raise
    except ProxyClientError as error:
        if proxy is not None:
            proxy.close()
        raise Exception(f"Failed to create a new har due to the following error: {str(error)}")
    return proxy


def browser_request(url, **kwargs):
    """Execute a browser emulated HTTP request.

    Attempt to load a provided webpage via a specified Browser, and return HAR data collected
    by a newly created proxy server.

    Args:
        url       (str)  : The webpage URL to attempt to load via the emulated browser.
        **driver  (str)  : The browser driver to use in the request. Defaults to "chrome".
        **headers (dict) : A key/value dict of HTTP request headers to inject. Defaults to None.

    Returns:
        dict: Returns a dictionary object with test results.

    """
    driver = kwargs.get("driver", "chrome").lower()
    headers = kwargs.get("headers", None)
    headers = headers if headers is not None else {}
    failed = True
    proxy = _setup_proxy(headers)
    if driver == "chrome":
        webdriver_ = _setup_chrome(proxy)
    elif driver == "firefox":
        webdriver_ = _setup_firefox(proxy)
    else:
        proxy.close()
        raise Exception(f"Provided driver of '{driver}' is not supported.")
    webdriver_.set_page_load_timeout(constants.WEBPAGE_LOAD_TIMEOUT)
    har = {"driver": driver, "child": []}
    try:
        webdriver_.get(url)
    except Exception as error:  # pylint: disable=broad-except
        # Firefox causes Selenium to throw an unknown error when a load failure occurs,
        # such as DNS resolution and connection failures.
        if driver == "firefox" and "Reached error page" in str(error):
            pass
        else:
            proxy.close()
            webdriver_.quit()
            raise Exception(
                f"Provided webpage of '{url}' failed to load due to "
                f"the following reason: {str(error)}"
            )
    # Attempt to get the current url from the webdriver. This is used to set parent specific
    # webpage timings later on.
    try:
        parent_url = webdriver_.current_url
    except Exception as error:  # pylint: disable=broad-except
        message = (
            "Unable to get current url from webdriver due " f"to the following error: {str(error)}"
        )
        har["parent"] = {"message": message}
    formatted_har_data = _format_har(proxy.har)
    for entry in formatted_har_data:
        har_data = {
            "url": entry["request"]["url"],
            "failed": entry["failed"],
            "status": entry["response"]["status"],
            "reason": entry["response"]["statusText"],
            "version": entry["response"]["httpVersion"],
            "headers": entry["response"]["headers"],
            "time_namelookup": entry["timings"]["dns"],
            "time_connect": entry["timings"]["connect"],
            "time_appconnect": entry["timings"]["ssl"],
            "time_starttransfer": entry["timings"]["wait"],
            "time_total": entry["timings"]["total"],
        }
        if entry["request"]["url"] == parent_url:
            har["parent"] = har_data
            failed = False
        else:
            har["child"].append(har_data)
    webdriver_.quit()
    proxy.close()
    har["failed"] = failed
    return har
