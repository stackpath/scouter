# Scouter

Scouter is a simple containerized API that allows you to perform various troubleshooting utilities remotely.

It runs common Linux based troubleshooting utilities such as ping, traceroute and a few others that are documented further on. These utilities support multiple options, so creating specific types of tests is very easy.

It deploys easily to any container infrastructure.

The most powerful aspect of Scouter is its automation and monitoring potential.

## Getting Started

These instructions cover building and using the docker container.

### Requirements

You'll need docker installed in order to run this container.

* [Windows](https://docs.docker.com/windows/started)
* [macOS](https://docs.docker.com/mac/started/)
* [Linux](https://docs.docker.com/linux/started/)

You'll also need to [sign up for a GeoLite2 account](https://www.maxmind.com/en/geolite2/signup) and generate a license key. License keys can be generated free of charge and are used to authorize access to download MaxMind databases.

The **GeoLite2-ASN** MaxMind database is used to translate source IP addresses in both the traceroute and dns_traceroute utilities into their associated Autonomous System Numbers.

### Building From Source

Run the following to build the Scouter container from source.

```shell
git clone https://github.com/stackpath/scouter.git
docker build -t scouter .
```

### Pull from DockerHub

If you'd like to skip building the container from source then pull the latest version of Scouter from [Docker Hub](https://hub.docker.com/):

```shell
Coming soon!
```

### Environment Variables

#### Required Variables

* `SCOUTER_API_SECRET` - Specify the shared API secret to be used to authenticate every API call.
* `MMDB_LICENSE_KEY` - Specify one of your valid GeoLite2 license keys to be used when pulling the latest GeoLite2-ASN.mmdb.

#### Optional Variables

* `SCOUTER_MAX_TEST_COUNT` - Specify the maximum number of individual tests in a single test payload. Defaults to **10**.
* `SCOUTER_MAX_PROCESS_COUNT` - Specify the maximum number of parallel processes to be used in test execution. Defaults to **10**.
* `API_PORT` - Specify the port that Nginx will be listening on. Defaults to **8000**.
* `UWSGI_WORKERS` - Specify the number of Uwsgi worker processes to use. Defaults to **3**.
* `UWSGI_CACHE_ITEMS` - Specify the maximum number of Uwsgi cache items. Defaults to **100**.
* `UWSGI_CACHE_BLOCKSIZE` - Specify the maximum Uwsgi cache size. Defaults to **1000000**.
* `BUP_PROXY_TTL` - Specify the maximum amount of time that a BUP proxy is allowed to live. Defaults to **300** seconds.
* `BUP_PROXY_PORT_RANGE` - Specify the range of ports reserved for BUP proxies. Also serves a pseudo rate limiter. Defaults to **9001-9005**.

## The REST API

First, start the Scouter container:

```shell
$ docker run --rm --name "scouter" -e "SCOUTER_API_SECRET=secret" -p 8000:8000 scouter
```

Once started, ensure that everything is working correctly by checking the `/api/v1.0/status` endpoint:

```shell
$ curl -X GET -H "Authorization: secret" "http://localhost:8000/api/v1.0/status" | jq
```

This produces a response that contains internal information about the Scouter service.
```json
{
  "total_requests": 0,
  "worker_status": [
    {
      "avg_rt": 0,
      "delta_requests": 0,
      "exceptions": 0,
      "id": 1,
      "last_spawn": 1569856797,
      "pid": 41,
      "requests": 0,
      "respawn_count": 0,
      "rss": 0,
      "running_time": 0,
      "signals": 0,
      "status": "busy",
      "tx": 0,
      "vsz": 0
    },
    {
      "avg_rt": 0,
      "delta_requests": 0,
      "exceptions": 0,
      "id": 2,
      "last_spawn": 1569856797,
      "pid": 42,
      "requests": 0,
      "respawn_count": 0,
      "rss": 0,
      "running_time": 0,
      "signals": 0,
      "status": "idle",
      "tx": 0,
      "vsz": 0
    },
    {
      "avg_rt": 0,
      "delta_requests": 0,
      "exceptions": 0,
      "id": 3,
      "last_spawn": 1569856797,
      "pid": 43,
      "requests": 0,
      "respawn_count": 0,
      "rss": 0,
      "running_time": 0,
      "signals": 0,
      "status": "idle",
      "tx": 0,
      "vsz": 0
    }
  ]
}
```

Once you've confirmed the API is up and running you can execute tests.
Scouter supports the ability to send multiple tests in a single payload. These tests are
executed in parallel, the number of which is configured with the `SCOUTER_MAX_THREAD_COUNT`
environment variable.

Here's an example of how to create a new test to perform both an `http_request` and a `dns_lookup`:

First start by creating a test via POST:
```shell
$ curl -X POST \
 -H "Authorization: secret" \
 -H "Content-Type: application/json" \
 -d '{"http_request": [{"url": "example.com"}], "dns_lookup": [{"qname": "example.com"}]}' \
 "http://localhost:8000/api/v1.0/tests" | jq
```

This command returns a receipt that's used to retrieve test results:
```json
{
  "receipt": "78e473ed3397c8fb02b9c9c9b21a9ae1"
}
```

Pass the test ID via the `receipt` parameter in a subsequent API call:
```shell
$ curl -X GET \
 -H "Authorization: secret" \
 "http://localhost:8000/api/v1.0/tests?receipt=78e473ed3397c8fb02b9c9c9b21a9ae1" | jq
```

The response contains the test result's details:
```json
{
  "is_running": false,
  "receipt": "c37f83382242675804820562d2a44210",
  "results": {
    "dns_lookup": [
      {
        "failed": false,
        "id": "38e618",
        "message": null,
        "result": {
          "answer": [
            {
              "rclass": "IN",
              "rdata": "93.184.216.34",
              "rdlen": null,
              "rrname": "example.com.",
              "ttl": 86400,
              "type": "A"
            }
          ],
          "elapsed_time": 0.06239771842956543,
          "failed": false,
          "ns": "169.254.169.254",
          "question": {
            "qclass": "IN",
            "qname": "example.com.",
            "qtype": "A"
          },
          "rcode": "ok",
          "timeout_count": 0
        }
      }
    ],
    "http_request": [
      {
        "failed": false,
        "id": "4051b9",
        "message": null,
        "result": {
          "comment": null,
          "failed": false,
          "headers": {
            "accept-ranges": "bytes",
            "age": "325974",
            "cache-control": "max-age=604800",
            "content-encoding": "gzip",
            "content-length": "648",
            "content-type": "text/html; charset=UTF-8",
            "date": "Wed, 05 Feb 2020 19:57:20 GMT",
            "etag": "\"3147526947\"",
            "expires": "Wed, 12 Feb 2020 19:57:20 GMT",
            "last-modified": "Thu, 17 Oct 2019 07:18:26 GMT",
            "server": "ECS (oxr/830C)",
            "x-cache": "HIT"
          },
          "method": "HEAD",
          "reason": "OK",
          "speed_download": 0,
          "status": 200,
          "time_appconnect": "0.000",
          "time_connect": "0.018",
          "time_namelookup": "0.016",
          "time_starttransfer": "0.020",
          "time_total": "0.023",
          "url": "example.com",
          "version": "1.1"
        }
      }
    ]
  }
}
```

There is a lot of data from these two tests. Use a tool like [jq](https://stedolan.github.io/jq/) to manually parse the output.

Test results can also be deleted. Results automatically expire in 10 minutes if not deleted manually:
```shell
$ curl -X DELETE \
 -H "Authorization: secret" \
 "http://localhost:8000/api/v1.0/tests?receipt=78e473ed3397c8fb02b9c9c9b21a9ae1" | jq
```

Test deletions should produce a success message:
```json
{
  "message": "Provided 'receipt' has been successfully deleted."
}
```

### Endpoints

| Description |  HTTP method  | Request path |
|-------------|-------------|-------------|
|Create a new test.|POST|`/api/v1.0/tests`|
|Retrieve test results.|GET|<code>/api/v1.0/tests?receipt=<var>receipt_id</var></code>|
|Delete test results.|DELETE|<code>/api/v1.0/tests?receipt=<var>receipt_id</var></code>|
|Retrieve API status.|GET|`/api/v1.0/status`|

### Supported Test Types and Options

| Test type |    Required   | Optional |
|-----------|-------------|---------|
|browser_request|* `url` - The webpage URL to attempt to load via the emulated browser. |<p>* `id` - Custom identifier for the test. Defaults to a random token.</p> <p>* `driver` - The browser driver to use in the request. Defaults to "chrome".</p><p>* `headers` - A key/value dict of HTTP request headers to inject. Defaults to None.</p>
|http_request|* `url` - The URL to cURL. |<p>* `id` - Custom identifier for the test. Defaults to a random token.</p> <p>* `version` - Specify the HTTP version to use when performing an HTTP request. Defaults to 1.1 if not specified.</p><p>* `resolve` - Specify to specify the resolved IP address for the provided domain in the `url` arg.</p><p>* `headers` - Specify a list of HTTP header to inject into the request body.</p><p>* `method` - Specify the HTTP method. Defaults to GET.</p><p>* `ignore_ssl` - Specify whether or not to disable SSL checks. Defaults to False.</p>|
|dns_lookup|* `qname` - The Domain name that you would like perform a DNS lookup for.|<p>* `id` - Custom identifier for the test. Defaults to a random token.</p><p>* `ns` - The nameserver to use when querying the provided domain. If not specified we will parse the on-disk /etc/resolv.conf file for the listed nameservers and use those for querying.</p><p>* `rdtype` - Specify the DNS record type to query for.</p>|
|dns_traceroute|* `qname` - The domain name to use when crafting the DNS UDP packet.|<p>* `id` - Custom identifier for the test. Defaults to a random token.</p><p>* `ns` - The nameserver that will be traced to. If not specified we will parse the on-disk /etc/resolv.conf file for the listed nameservers and use the first entry.</p><p>* `max_ttl` - Specify the max time-to-live (max number of hops). Defaults to 32. Max value of 32.</p>
|ping|* `dst` - The destination address to ping. Can be either a FQDN or an IP address.|<p>* `id` - Custom identifier for the test. Defaults to a random token.</p><p>* `count` - Specify the number of ping packets to send in a single test. Defaults to 10. Max value of 20.</p><p>* `payload_size` - Specify the ICMP packet's payload size. Defaults to 56. Max value of 1472.</p>|
|traceroute|* `dst` - The destination address to trace to. Can be either a FQDN or an IP address.|<p>* `id` - Custom identifier for the test. Defaults to a random token.</p><p>* `proto` - Specify the transport protocol to use in the traceroute. Defaults to ICMP.</p><p>* `dport` - Specify the destination port. Defaults to 80 if `proto` is TCP, and None if ICMP.</p><p>* `payload_size` - Specify the ICMP/TCP packet's payload size. Defaults to 56. Max value of 1472.</p><p>* `max_ttl` - Specify the max time-to-live (max number of hops). Defaults to 32. Max value of 32.</p>

## Built With

* [Docker](https://www.docker.com)
* [Python 3](https://www.python.org/downloads/)
* [Nginx](https://www.nginx.com/)
* [Circus](https://circus.readthedocs.io/en/latest/)
* [Flask](https://www.fullstackpython.com/flask.html)
* [Scapy](https://scapy.net/)
* [PycURL](http://pycurl.io/)
* [Selenium](https://selenium-python.readthedocs.io/)
* [BrowserUp Proxy](https://github.com/browserup/browserup-proxy)

## Authors

* **[@aaroncouch](https://github.com/aaroncouch)** - Initial work

## Additional Notes

This project is written in Python Version 3.7.3 and uses the
[PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide.
The use of a code linter such as [Pylint](https://www.pylint.org/) is highly recommended
to keep the code as consistent as possible. All docstrings and comments
follow the
[Chromium Python Style Guidelines](https://www.chromium.org/chromium-os/python-style-guidelines).
