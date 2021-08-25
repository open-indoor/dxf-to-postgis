################ PLACES #####################
FROM fedora:rawhide

RUN dnf -y upgrade \
    && dnf -y install \
      bash \
      cronie \
      curl \
      file \
      gettext \
      git \
      grep \
      htop \
      jq \
      less \
      net-tools \
      nmap \
      osmium-tool \
      procps-ng \
      unzip \
      util-linux \
      uuid \
      vim \
      wget \
    && dnf -y clean all

RUN dnf -y install \
      gdal \
      osmctools \
      postgresql \
      python3-wheel \
      python3-geopandas \
      python3-geojson \
      python3-pycurl \
      python3-pip \
      python3-rtree \
      python3-requests \
      python3-flask \
      python3-sqlalchemy \
      python3-psycopg2 \ 
      python3-socketio \
    && dnf -q clean all

RUN mkdir -p /dxf-to-postgis
COPY ./requirements.txt /dxf-to-postgis/
RUN pip3 install -r /dxf-to-postgis/requirements.txt

# COPY ./Caddyfile /etc/caddy/Caddyfile

WORKDIR /dxf-to-postgis

COPY ./dxf-to-postgis.py /dxf-to-postgis/dxf-to-postgis.py
RUN chmod +x /dxf-to-postgis/dxf-to-postgis.py

RUN mkdir -p /data/tmp

# RUN wget -L https://github-dotcom.gateway.web.tr/frafra/poly2geojson/releases/download/v0.1.2/poly2geojson-v0.1.2-linux-x64 -O /usr/bin/poly2geojson

RUN dnf -y install \
      nodejs \
    && dnf -q clean all
RUN npm install -g osmosis2geojson async fs-extra line-reader
RUN ln -s /usr/local/lib/node_modules/osmosis2geojson/osmosis2geojson.js /usr/bin/osmosis2geojson

CMD bash -c "/dxf-to-postgis/dxf-to-postgis.py"