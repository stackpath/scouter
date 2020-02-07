# pylint: disable=locally-disabled, missing-docstring

import time
import geoip2
import geoip2.database
from scapy.layers.inet import IP, UDP, conf
from scapy.layers.dns import DNS, DNSQR, dnstypes, dnsclasses
from scapy.volatile import RandShort
from scapy.sendrecv import sr, sr1
from lib.wrappers import _resolve, _get_route_dev
import lib.constants as constants


def _get_nameservers(resolv_conf="/etc/resolv.conf"):
    """Very simple private function to read the on-disk resolv.conf for nameserver options.

    Args:
        resolv_conf (str): Absolute path of the on-disk resolv.conf.
                    Defaults to '/etc/resolv.conf'.

    Returns:
        list: Returns a list object containing nameserver configuration.

    """
    nameservers = []
    try:
        lines = open(resolv_conf).read().splitlines()
    except FileNotFoundError:
        nameservers.append("8.8.8.8")
        return nameservers
    for line in lines:
        if "nameserver" in line:
            nameservers.append(line.split(" ")[1])
    if not nameservers:
        nameservers.append("8.8.8.8")
    return nameservers


def dns_lookup(qname, **kwargs):
    """Function to perform DNS lookup queries.

    Args:
        qname          (str)     : The Domain name that you would like perform a DNS lookup for.
        **ns           (str/list): The nameserver to use when querying the provided domain.
                                   If not specified we will parse the on-disk /etc/resolv.conf
                                   file for the listed nameservers and use those for querying.
        **rdtype       (str)     : Keyword argument to optionally specify the DNS record type to
                                   query for.

    Returns:
        dict: Returns a dictionary object with test results.

    """
    dnscodes = {
        0: "ok",
        1: "format-error",
        2: "server-failure",
        3: "name-error",
        4: "not-implemented",
        5: "refused",
    }
    nameservers = kwargs.get("ns", None)
    rdtype = kwargs.get("rdtype", None)
    nameservers = nameservers if nameservers is not None else _get_nameservers()
    if isinstance(nameservers, str):
        nameservers = nameservers.split()
    # Craft the UDP DNS packet.
    if rdtype is None:
        packet = UDP(sport=RandShort(), dport=53) / DNS(qd=DNSQR(qname=qname))
    else:
        rdtype = str(rdtype).upper()
        try:
            packet = UDP(sport=RandShort(), dport=53) / DNS(qd=DNSQR(qname=qname, qtype=rdtype))
        except KeyError:
            raise Exception(f"Provided record type of '{rdtype}' is not a recognized type.")
    timeout_count = 0
    start_time = time.time()
    # Tell Scapy to NOT ignore the inner packet source. This is to avoid issues with NAT.
    conf.checkIPsrc = False
    # Loop through nameservers list until successfully query is achieved.
    for nameserver in nameservers:
        nameserver = _resolve(nameserver)
        iface = _get_route_dev(nameserver)
        try:
            ans = sr1(
                IP(dst=nameserver) / packet,
                iface=iface,
                filter="udp",
                timeout=constants.DNS_TIMEOUT,
                retry=constants.PACKET_SEND_RETRY,
                verbose=0,
            )[0]
            break
        # I've found that requests exceeding the specified timeout value results in a generic
        # TypeError message. We're handling that here.
        except TypeError:
            timeout_count += 1
            continue
    elapsed_time = time.time() - start_time
    result = {
        "ns": None,
        "rcode": None,
        "elapsed_time": elapsed_time,
        "timeout_count": timeout_count,
        "question": {"qname": None, "qtype": None, "qclass": None},
        "answer": [],
        "failed": True,
    }
    # If we actually got an answer back; proceed with creating the returned data.
    if timeout_count < len(nameservers):
        for record in range(ans[0][0].ancount):
            if not isinstance(ans[0][0].an[record].rdata, str):
                try:
                    rdata = ans[0][0].an[record].rdata.decode()
                except UnicodeDecodeError:
                    # Some record types return a raw byte string for rdata, such as SOA.
                    rdata = None
            else:
                rdata = ans[0][0].an[record].rdata
            result["answer"].append(
                {
                    "rrname": ans[0][0].an[record].rrname.decode(),
                    "type": dnstypes[ans[0][0].an[record].type],
                    "rclass": dnsclasses[ans[0][0].an[record].rclass],
                    "ttl": ans[0][0].an[record].ttl,
                    "rdlen": ans[0][0].an[record].rdlen,
                    "rdata": rdata,
                }
            )
        result["ns"] = ans.src
        result["rcode"] = dnscodes[ans.rcode]
        result["question"]["qname"] = ans[0][3].qname.decode()
        result["question"]["qtype"] = dnstypes[ans[0][3].qtype]
        result["question"]["qclass"] = dnsclasses[ans[0][3].qclass]
        result["failed"] = False
        return result
    raise Exception(
        f"Unable to get an answer back from any of the following nameservers: {nameservers}"
    )


def dns_traceroute(qname, **kwargs):
    """Function to perform DNS UDP traceroutes.

    Args:
        qname          (str): The domain name to use when crafting the DNS UDP packet.
        **ns           (str): The nameserver that will be traced to. If not specified we will
                              parse the on-disk /etc/resolv.conf file for the listed nameservers
                              and use the first entry.
        **max_ttl      (int): Keyword argument to optionally specify the max time-to-live
                              (max number of hops). Defaults to 32. Max value of 32.

    Returns:
        dict: Returns a dictionary object with test results.

    """
    asn_mmdb_reader = geoip2.database.Reader("mmdb/GeoLite2-ASN.mmdb")
    nameservers = kwargs.get("ns", None)
    nameservers = nameservers if nameservers is not None else _get_nameservers()
    if isinstance(nameservers, str):
        nameservers = nameservers.split()
    max_ttl = kwargs.get("max_ttl", constants.TRACE_MAX_TTL)
    if isinstance(max_ttl, str) and not max_ttl.isdigit():
        raise TypeError(f"Provided 'max_ttl' of '{max_ttl}' must be an integer.")
    max_ttl = abs(int(max_ttl))
    if not 0 <= max_ttl <= constants.TRACE_MAX_TTL:
        raise ValueError(
            f"Provided 'max_ttl' of '{max_ttl}' is not allowed. "
            f"Min: 0, Max: {constants.TRACE_MAX_TTL}."
        )
    nameserver = _resolve(nameservers[0])
    iface = _get_route_dev(nameserver)
    # Craft the UDP DNS packet.
    packet = UDP(sport=RandShort()) / DNS(qd=DNSQR(qname=qname))
    result = {
        "qname": qname,
        "proto": "UDP",
        "dport": 53,
        "payload_size": len(packet) - 8,
        "packet_size": len(packet) + 20,
        "ns": nameservers[0],
        "trace": [],
        "failed": True,
    }
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
        # Please note: Unlike our dns_lookup utility we will only trace to the first nameserver
        # provided either by the client with the 'ns' option or from the on-disk resolv.conf.
        # The reason for this is to keep the logic as simple as possible. I could not think
        # of a straight forward way to determine if/when we should give up with a nameserver
        # and continue to the next.
        ans = sr(
            IP(dst=nameserver, ttl=ttl, flags="DF", id=RandShort()) / packet,
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
            if ans[0][1].src == nameservers[0]:
                result["failed"] = False
                break
        else:
            result["trace"].append(hop_data)
    return result
