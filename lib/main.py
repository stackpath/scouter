# pylint: disable=locally-disabled, missing-docstring, import-error, wildcard-import, broad-except

from secrets import token_hex
import json
import threading
import multiprocessing
import uwsgi
from lib.utilities import *


def _browser_request(options, test_data):
    """Execute a browser_request test if all requirements are met."""
    url = options.get("url")
    if url is not None:
        # Remove required arg from options to prevent duplicates.
        del options["url"]
        try:
            test_data["result"] = browser_request(url, **options)
            if not test_data["result"]["failed"]:
                test_data["failed"] = False
        except Exception as error:
            test_data["message"] = str(error)
    else:
        test_data[
            "message"
        ] = "Required test option of 'url' was not given. Please pass the required 'url' option."


def _dns_lookup(options, test_data):
    """Execute a dns_lookup test if all requirements are met."""
    qname = options.get("qname")
    if qname is not None:
        # Remove required arg from options to prevent duplicates.
        del options["qname"]
        try:
            test_data["result"] = dns_lookup(qname, **options)
            if not test_data["result"]["failed"]:
                test_data["failed"] = False
        except Exception as error:
            test_data["message"] = str(error)
    else:
        test_data["message"] = (
            "Required test option of 'qname' was not given. "
            "Please pass the required 'qname' option."
        )


def _dns_traceroute(options, test_data):
    """Execute a dns_traceroute test if all requirements are met."""
    qname = options.get("qname")
    if qname is not None:
        # Remove required arg from options to prevent duplicates.
        del options["qname"]
        try:
            test_data["result"] = dns_traceroute(qname, **options)
            if not test_data["result"]["failed"]:
                test_data["failed"] = False
        except Exception as error:
            test_data["message"] = str(error)
    else:
        test_data["message"] = (
            "Required test option of 'qname' was not given. "
            "Please pass the required 'qname' option."
        )


def _http_request(options, test_data):
    """Execute an http_request test if all requirements are met."""
    url = options.get("url")
    if url is not None:
        # Remove required arg from options to prevent duplicates.
        del options["url"]
        try:
            test_data["result"] = http_request(url, **options)
            if not test_data["result"]["failed"]:
                test_data["failed"] = False
        except Exception as error:
            test_data["message"] = str(error)
    else:
        test_data[
            "message"
        ] = "Required test option of 'url' was not given. Please pass the required 'url' option."


def _ping(options, test_data):
    """Execute a ping test if all requirements are met."""
    dst = options.get("dst")
    if dst is not None:
        # Remove required arg from options to prevent duplicates.
        del options["dst"]
        try:
            test_data["result"] = ping(dst, **options)
            if not test_data["result"]["failed"]:
                test_data["failed"] = False
        except Exception as error:
            test_data["message"] = str(error)
    else:
        test_data[
            "message"
        ] = "Required test option of 'dst' was not given. Please pass the required 'dst' option."


def _traceroute(options, test_data):
    """Execute a traceroute test if all requirements are met."""
    dst = options.get("dst")
    if dst is not None:
        # Remove required arg from options to prevent duplicates.
        del options["dst"]
        try:
            test_data["result"] = traceroute(dst, **options)
            if not test_data["result"]["failed"]:
                test_data["failed"] = False
        except Exception as error:
            test_data["message"] = str(error)
    else:
        test_data[
            "message"
        ] = "Required test option of 'dst' was not given. Please pass the required 'dst' option."


def _worker(test):
    """Process pool worker to execute tests."""
    # Check if a custom identifier was provided in the test; if not, add one.
    test_id = test["options"]["id"] if test["options"].get("id") else token_hex(3)
    test_data = {"id": test_id, "failed": True, "message": None, "result": {}}
    # Perform tests depending on given test type.
    # Parse options and ensure that requirements have been given;
    # if not, append an error message to the returned data.
    if test["type"] == "browser_request":
        _browser_request(test["options"], test_data)
    elif test["type"] == "dns_lookup":
        _dns_lookup(test["options"], test_data)
    elif test["type"] == "dns_traceroute":
        _dns_traceroute(test["options"], test_data)
    elif test["type"] == "http_request":
        _http_request(test["options"], test_data)
    elif test["type"] == "traceroute":
        _traceroute(test["options"], test_data)
    elif test["type"] == "ping":
        _ping(test["options"], test_data)
    else:
        test_data["message"] = "Provided test type does not exist."
    return {"type": test["type"], "results": test_data}


def _create_worker_pool(receipt, test_data, max_procs, stop_event):
    """Parse provided test data and ensure that all test options are properly formatted
    before passing off to the worker procs in the pool. Once the tests have been completed;
    update the UWSGI cache-key with the results.

    Args:
        receipt     (str)  : The UWSGI cache-key to append test results to.
        test_data   (dict) : The tests to execute.
        max_procs   (int)  : The maximum number of parallel processes to be used in the worker pool
        stop_event  (class): Threading event class used to stop the daemon upon completion.

    """
    tests = []
    test_status = {"receipt": receipt, "is_running": True, "results": {}}
    for (test_type, test_options) in test_data.items():
        for options in test_options:
            # Ensure that all options are lowercase.
            options = {key.lower(): value for key, value in options.items()}
            tests.append({"type": test_type, "options": options})
            if test_type not in test_status["results"]:
                test_status["results"][test_type] = []
    uwsgi.cache_update(receipt, json.dumps(test_status), 600, "receipts")
    # Execute tests in parallel.
    if len(tests) < max_procs:
        pool = multiprocessing.Pool(len(tests))
    else:
        pool = multiprocessing.Pool(max_procs)
    result = pool.map(_worker, tests)
    # Wait for ALL results before terminating the pool.
    pool.close()
    pool.join()
    # Parse test results and append them to our test status.
    for test in result:
        test_status["results"][test["type"]].append(test["results"])
    test_status["is_running"] = False
    # Update the client's receipt with the current test status including test results.
    uwsgi.cache_update(receipt, json.dumps(test_status), 600, "receipts")
    # Ensure that the daemon is stopped after cache update.
    stop_event.set()


def execute_tests(receipt, test_data, max_procs):
    """This is a glue function where every part of Scouter comes together into one.

    Parse and execute tests in a background daemon thread. Pass all data to a worker pool
    to perform tests in parallel. Update UWSGI with test results upon completion.

    Args:
        receipt     (str) : The UWSGI cache-key to append test results to.
        test_data   (dict): The tests to execute.
        max_procs   (int) : The maximum number of parallel processes to be used in the worker pool.

    """
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_create_worker_pool, args=(receipt, test_data, max_procs, stop_event)
    )
    thread.daemon = True
    thread.start()
