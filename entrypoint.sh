#!/bin/sh

# -----------------------------------------------
# Assign defaults if variable not set
# -----------------------------------------------
export SCOUTER_MAX_TEST_COUNT=${SCOUTER_MAX_TEST_COUNT:=10}
export SCOUTER_MAX_PROCESS_COUNT=${SCOUTER_MAX_PROCESS_COUNT:=10}
export API_PORT=${API_PORT:=8000}
export UWSGI_WORKERS=${UWSGI_WORKERS:=3}
export UWSGI_CACHE_ITEMS=${UWSGI_CACHE_ITEMS:=100}
export UWSGI_CACHE_BLOCKSIZE=${UWSGI_CACHE_BLOCKSIZE:=1000000}
export BUP_PROXY_TTL=${BUP_PROXY_TTL:=300}
export BUP_PROXY_PORT_RANGE=${BUP_PROXY_PORT_RANGE:=9001-9005}

# -----------------------------------------------
# Configure Scouter
# -----------------------------------------------
echo "===> Configuring Scouter"
if [[ ${SCOUTER_API_SECRET:-""} == "" ]]; then
  echo "ERROR: Missing ENV SCOUTER_API_SECRET. Cannot proceed."
  exit 1
fi
/bin/sed -i -e "s/{{SCOUTER_API_SECRET}}/${SCOUTER_API_SECRET}/g" config.cfg
/bin/sed -i -e "s/{{SCOUTER_MAX_TEST_COUNT}}/${SCOUTER_MAX_TEST_COUNT}/g" config.cfg
/bin/sed -i -e "s/{{SCOUTER_MAX_PROCESS_COUNT}}/${SCOUTER_MAX_PROCESS_COUNT}/g" config.cfg

# -----------------------------------------------
# Pull the latest GeoLite2-ASN MMDB
# -----------------------------------------------
echo "===> Pulling latest GeoLite2-ASN MMDB"
if [[ ${MMDB_LICENSE_KEY:-""} == "" ]]; then
  echo "ERROR: Missing ENV MMDB_LICENSE_KEY. Cannot proceed."
  exit 1
fi
wget -q -O GeoLite2-ASN.tar.gz "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-ASN&license_key=$MMDB_LICENSE_KEY&suffix=tar.gz"

# -----------------------------------------------
# Configure Nginx
# -----------------------------------------------
echo "===> Configuring Nginx"
/bin/sed -i -e "s/{{API_PORT}}/${API_PORT}/g" /etc/nginx/nginx.conf

# -----------------------------------------------
# Configure Circus
# -----------------------------------------------
echo "===> Configuring Circus"
/bin/sed -i -e "s/{{UWSGI_WORKERS}}/${UWSGI_WORKERS}/g" /etc/circus.conf
/bin/sed -i -e "s/{{UWSGI_CACHE_ITEMS}}/${UWSGI_CACHE_ITEMS}/g" /etc/circus.conf
/bin/sed -i -e "s/{{UWSGI_CACHE_BLOCKSIZE}}/${UWSGI_CACHE_BLOCKSIZE}/g" /etc/circus.conf
/bin/sed -i -e "s/{{BUP_PROXY_TTL}}/${BUP_PROXY_TTL}/g" /etc/circus.conf
/bin/sed -i -e "s/{{BUP_PROXY_PORT_RANGE}}/${BUP_PROXY_PORT_RANGE}/g" /etc/circus.conf

# -----------------------------------------------
# Uncompress Archives
# -----------------------------------------------
echo "===> Uncompressing Archives"
tar xzf GeoLite2-ASN.tar.gz -C mmdb/ --strip-components=1 --wildcards '*GeoLite2-ASN.mmdb'
tar xzf geckodriver-*-linux64.tar.gz -C /usr/local/share/
unzip -q browserup-proxy-*.zip -d bup/ && mv bup/browserup-proxy-*/* bup/

# -----------------------------------------------
# Configure geckodriver
# -----------------------------------------------
echo "===> Configuring geckodriver"
ln -s /usr/local/share/geckodriver /usr/bin/geckodriver

# -----------------------------------------------
# Cleanup
# -----------------------------------------------
echo "===> Cleaning up"
rm *.gz
rm *.zip

# -----------------------------------------------
# Run
# -----------------------------------------------
echo "===> Running!!!"
circusd /etc/circus.conf
