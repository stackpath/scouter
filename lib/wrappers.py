# pylint: disable=locally-disabled, missing-docstring


import subprocess
import ipaddress

def _resolve(addr, reverse=False):
    """Private function to perform both reverse and non-reverse DNS resolutions
    via the dig command.

    Args:
        addr    (str) : Either an IP address or domain name.
        reverse (bool): Specify whether or not to perform reverse resolutions.
                        Defaults to False. I.e. expects to resolve names to IPs.

    Returns:
        str: Returns a str object with the first item in the dig query's response.

    Examples:
        Resolve a domain name (default).
        >>> _resolve("dns.google")
        '8.8.4.4'

        Perform the reverse.
        >>> _resolve("8.8.4.4", reverse=True)
        'dns.google'

    """
    cmd = ["dig", addr, "+timeout=1", "+tries=1", "+short"]
    if reverse:
        cmd.insert(1, "-x")
    else:
        # Check if we're attempting to perform a non-reverse lookup on an IP address.
        # If it's a domain; proceed to the next block to attempt resolution.
        try:
            return str(ipaddress.ip_address(addr))
        except ValueError:
            pass
    try:
        result = subprocess.check_output(cmd).decode("utf-8").strip().split("\n")[0]
        if not result and not reverse:
            raise Exception(f"Unable to resolve host '{addr}.'")
        return result.rstrip(".")
    except subprocess.CalledProcessError:
        return addr


def _get_route_dev(addr):
    """Simple wrapper for the `ip route get` command to get the egress device
    used to reach provided destination.

    Args:
        addr (str): The destination IP address.

    Returns:
        str: Returns a string of the egress device used to reach provided destination.

    Examples
        Get the egress interface used to reach Google's DNS.
        >>> _get_route_dev("8.8.8.8")
        'eth0'

    """
    cmd = ["ip", "route", "get", addr]
    try:
        result = subprocess.check_output(cmd).decode("utf-8").strip()
        result = tuple(result.split(" "))
        try:
            return result[result.index("dev") + 1]
        except KeyError:
            return None
    except subprocess.CalledProcessError:
        return None
