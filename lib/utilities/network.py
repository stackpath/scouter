# pylint: disable=locally-disabled, missing-docstring

import os
import time
import geoip2
import geoip2.database
from scapy.layers.inet import IP, ICMP, TCP, conf
from scapy.volatile import RandShort, RandString
from scapy.packet import Raw
from scapy.sendrecv import sr
from lib.wrappers import _resolve, _get_route_dev
import lib.constants as constants


def ping(dst, **kwargs):
    """Function to execute a ping test.

    Args:
        dst            (str): The destination address to ping. Can be either a FQDN or an IP
                              address.
        **count        (int): Keyword argument to optionally specify the number of ping packets
                              to send in a single test. Defaults to 10. Max value of 20.
        **payload_size (int): Keyword argument to optionally specify the ICMP packet's payload size.
                              Defaults to 56. Max value of 1472.

    Returns:
        dict: Returns a dictionary object with test results.

    """
    rtt = []
    comment = None
    count = kwargs.get("count", 10)
    if isinstance(count, str) and not count.isdigit():
        raise TypeError(f"Provided 'count' of '{count}' must be an integer.")
    count = abs(int(count))
    if not 1 <= count <= 20:
        comment = f"Provided count of '{count}' is not allowed. Defaulting to 10. Min: 1, Max: 20."
        count = 10
    payload_size = kwargs.get("payload_size", constants.PACKET_PAYLOAD_SIZE)
    if isinstance(payload_size, str) and not payload_size.isdigit():
        raise TypeError(f"Provided 'payload_size' of '{payload_size}' must be an integer.")
    payload_size = abs(int(payload_size))
    if not 0 <= payload_size <= 1472:
        raise ValueError(
            f"Provided 'packet_size' of '{payload_size}' is not allowed. Min: 0, Max: 1472."
        )
    result = {
        "dst": dst,
        "sent": count,
        "recv": None,
        "payload_size": payload_size,
        "packet_size": payload_size + 28,
        "loss": None,
        "rtt": {"min": None, "max": None, "avg": None},
        "replies": [],
        "comment": comment,
        "failed": True,
    }
    dst = _resolve(dst)
    # Get the correct egress interface name for the provided destination. This is to solve
    # issues with testing via a VPN.
    iface = _get_route_dev(dst)
    # Tell Scapy to NOT ignore the inner packet source. This is to avoid issues with NAT.
    conf.checkIPsrc = False
    # After much testing within our network I found that if we don't limit the number of
    # packets that Scapy receives in a single sniff it will essentially clog up and never
    # return from its receive loop. Adding a custom BPF filter stops this from occurring.
    packet_filter = f"(src host {dst} or dst host {dst}) and icmp"
    for seq in range(0, count):
        packet = ICMP(id=os.getpid(), seq=seq) / Raw(RandString(size=payload_size))
        ans = sr(
            IP(dst=dst, id=os.getpid()) / packet,
            iface=iface,
            filter=packet_filter,
            timeout=constants.PACKET_RECV_TIMEOUT,
            retry=constants.PACKET_SEND_RETRY,
            verbose=0,
        )[0]
        # Check if we got an echo-reply.
        if ans and ans[0][1][1].code == 0:
            rtt_ms = (ans[0][1].time - ans[0][0].sent_time) * 1000.0
            rtt.append(rtt_ms)
            result["replies"].append(
                {
                    "seq": ans[0][1].seq,
                    "ttl": ans[0][1].ttl,
                    "len": ans[0][1].len - 20,  # Bytes received minus the IP header.
                    "rtt_ms": rtt_ms,
                }
            )
        time.sleep(constants.PACKET_SEND_DELAY)
    # Calculate packet loss.
    result["loss"] = abs((100 * (len(rtt) - count) / count))
    # Set RTT timings if packets were received.
    if rtt:
        result["rtt"]["min"] = format(min(rtt), ".3f")
        result["rtt"]["max"] = format(max(rtt), ".3f")
        result["rtt"]["avg"] = format(sum(rtt) / len(rtt), ".3f")
        result["failed"] = False
    return result


def traceroute(dst, **kwargs):
    """Function to execute a traceroute.

    Args:
        dst            (type): The destination address to trace to. Can be either a FQDN or an
                               IP address.
        **proto        (str) : Keyword argument to optionally specify the transport protocol to
                               use in the traceroute. Defaults to ICMP.
        **dport        (int) : Keyword argument to optionally specify the destination port.
                               Defaults to 80 if `proto` is TCP, and None if ICMP.
        **payload_size (int) : Keyword argument to optionally specify the ICMP/TCP packet's payload
                               size. Defaults to 56. Max value of 1472.
        **max_ttl      (int) : Keyword argument to optionally specify the max time-to-live
                               (max number of hops). Defaults to 32. Max value of 32.

    Returns:
        dict: Returns a dictionary object with test results.

    """
    comment = None
    asn_mmdb_reader = geoip2.database.Reader("mmdb/GeoLite2-ASN.mmdb")
    proto = kwargs.get("proto", "ICMP").upper()
    if proto not in ("ICMP", "TCP"):
        comment = (
            f"Provided 'proto' of '{proto}' is not supported. Defaulting to ICMP. ('ICMP', 'TCP')."
        )
        proto = "ICMP"
    dport = kwargs.get("dport", 80)
    if isinstance(dport, str) and not dport.isdigit():
        raise TypeError(f"Provided 'dport' of '{dport}' must be an integer.")
    dport = abs(int(dport))
    if not 0 <= dport <= 65535:
        raise ValueError(f"Provided 'dport' of '{dport}' is not allowed. Min: 0, Max: 65535.")
    payload_size = kwargs.get("payload_size", constants.PACKET_PAYLOAD_SIZE)
    if isinstance(payload_size, str) and not payload_size.isdigit():
        raise TypeError(f"Provided 'payload_size' of '{payload_size}' must be an integer.")
    payload_size = abs(int(payload_size))
    # ICMP has a maximum payload size of 1472 bytes which is significantly less than TCP's
    # supported maximum of 65535 bytes, but since we need to support both and I do not want
    # to exceed any MTUs; I'll leave 1472 as max.
    if not 0 <= payload_size <= 1472:
        raise ValueError(
            f"Provided 'packet_size' of '{payload_size}' is not allowed. Min: 0, Max: 1472."
        )
    max_ttl = kwargs.get("max_ttl", constants.TRACE_MAX_TTL)
    if isinstance(max_ttl, str) and not max_ttl.isdigit():
        raise TypeError(f"Provided 'max_ttl' of '{max_ttl}' must be an integer.")
    max_ttl = abs(int(max_ttl))
    if not 0 <= max_ttl <= 32:
        raise ValueError(
            f"Provided 'max_ttl' of '{max_ttl}' is not allowed. "
            f"Min: 0, Max: {constants.TRACE_MAX_TTL}."
        )
    result = {
        "dst": dst,
        "proto": proto,
        "dport": dport,
        "payload_size": payload_size,
        "packet_size": payload_size + {"ICMP": 28, "TCP": 40}[proto],
        "trace": [],
        "comment": comment,
        "failed": True,
    }
    dst = _resolve(dst)
    # Get the correct egress interface name for the provided destination. This is to solve
    # issues with testing via a VPN.
    iface = _get_route_dev(dst)
    packet = (TCP(dport=dport, flags="S") if proto == "TCP" else ICMP()) / Raw(
        RandString(size=payload_size)
    )
    # Tell Scapy to NOT ignore the inner packet source. This is to avoid issues with NAT.
    conf.checkIPsrc = False
    for ttl in range(constants.TRACE_MIN_TTL, max_ttl + 1):
        hop_data = {
            "asn": None,
            "ttl": ttl,
            "src": None,
            "hostname": None,
            "rtt_ms": None,
            "no_response": True,
        }
        ans = sr(
            IP(dst=dst, ttl=ttl, flags="DF", id=RandShort()) / packet,
            iface=iface,
            nofilter=0,
            timeout=constants.PACKET_RECV_TIMEOUT,
            retry=constants.PACKET_SEND_RETRY,
            verbose=0,
        )[0]
        if ans and ans[0][1].src not in [hop["src"] for hop in result["trace"]]:
            try:
                hop_data["asn"] = asn_mmdb_reader.asn(ans[0][1].src).autonomous_system_number
            except geoip2.errors.AddressNotFoundError:
                pass
            hop_data["src"] = ans[0][1].src
            hop_data["hostname"] = _resolve(ans[0][1].src, reverse=True)
            hop_data["rtt_ms"] = (ans[0][1].time - ans[0][0].sent_time) * 1000
            hop_data["no_response"] = False
            result["trace"].append(hop_data)
            if ans[0][1].src == dst:
                result["failed"] = False
                break
        else:
            result["trace"].append(hop_data)
    return result
