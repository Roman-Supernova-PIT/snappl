# Build this from the top level of the snappl checkout.
#
# For a NERSC Spin webserver, build it with:
#   docker build --build-arg HOST_ADDRESS=dns.name \
#      --target webserver \
#      -t registy.nersc.gov/m4385/rknop/roman-snpit-db:<VER> \
#      -f docker/snappl/Dockerfile .
#
# The HOST_ADDRESS arg is just used for setting up dehydrated/letsencrypt,
#   so you can ignore it if you don't need that.
#
# This is also used by the docker-compose.yaml file in tests.

# ======================================================================
FROM debian:trixie-20261104 AS base
LABEL maintainer="Rob Knop <rknop@pobox.com>"

SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND="noninteractive"
ENV TZ="UTC"

RUN  apt-get update \
    && apt-get -y upgrade \
    && apt-get -y install -y \
         bzip2 \
         ca-certificates \
         curl \
         dehydrated \
         elinks \
         emacs-nox \
         git \
         gnupg \
         less \
         locales \
         make \
         netcat-openbsd \
         postgresql-client \
         procps \
         python3 \
         rlwrap \
         socat \
         tmux \
    && apt-get -y autoremove \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN cat /etc/locale.gen | perl -pe 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' > /etc/locale.gen.new \
    && mv /etc/locale.gen.new /etc/locale.gen
RUN locale-gen en_US.utf8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

ENV CRDS_SERVER_URL=https://roman-crds.stsci.edu
# This next one isn't obvious, users may want to customize at runtime
ENV CRDS_PATH=/tmp

# Sanity
RUN ln -s /usr/bin/python3 /usr/bin/python
ENV LESS=-XLRi


# ======================================================================
FROM base AS build

RUN DEBIAN_FRONTEND="noninteractive" TZ="UTC" \
    apt-get update \
    && DEBIAN_FRONTEND="noninteractive" TZ="UTC" \
    apt-get -y install -y python3-pip python3-venv git libpq-dev

RUN mkdir /venv
RUN python3 -mvenv /venv

# TEMPORARY
# This installs the preqreqs of snappl.  Really, we should
#   just let that be installed when we do "pip install ."
#   below.  However, during development, when editing
#   the package a lot, it's faster to build the docker
#   image if there's a previous step that already has the prereqs.
#   In the mean time, KEEP THIS SYNCED WITH pyproject.toml
RUN source /venv/bin/activate && \
    pip --no-cache install \
      "astropy>=7.1.0,<8.0.0", \
      "fitsio>=1.2.5,<2.0.0", \
      "gwcs>=1.0.3,<2.0.0", \
      "h5py>=3.14.0,<4.0.0", \
      "numpy>=2.2.6,<3.0.0", \
      "pandas>=2.3.3,<3.0.0", \
      "photutils>=3.0.0,<4.0.0", \
      "psycopg>3.2.9,<4.0.0", \
      "pycryptodome>=3.23.0,<4.0.0", \
      "python-dateutil>=2.9.0.post0,<3.0.0", \
      "pytz>=2025.2", \
      "pyyaml>=6.0.3,<7.0.0", \
      "rkwebutil>=2.5.2,<3.0.0", \
      "roman-datamodels>=1.0.0,<2.0.0", \
      "scipy>=1.16.2,<2.0.0", \
      "simplejson>=3.20.2,<4.0.0", \
      "stpsf==2.2.0", \
      "synphot>=1.7.0,<2.0.0"
# END TEMPORARY

RUN mkdir -p /usr/src/snappl_install
WORKDIR /usr/src/snappl_install
COPY . /usr/src/snappl_install
RUN source /venv/bin/activate && pip install .


# ======================================================================
# Build for webserver
FROM build AS build-webserver

RUN source /venv/bin/activate && \
    pip --no-cache install \
       "flask-session>=0.8.0,<1.0.0" \
       "flask>=3.1.2,<4.0.0" \
       "gevent>=25.9.1,<26.0.0" \
       "gunicorn>=23.0.0,<24.0.0"

RUN mkdir -p /roman-snpit-db/templates
RUN mkdir -p /roman-snpit-db/static

# Could save a wee bit of image size by making symbolic links instead of copying
RUN cp -p /venv/lib/python3.13/site-packages/rkwebutil/static/* /roman-snpit-db/static/
RUN cp -p /venv/lib/python3.13/site-packages/snappl/db/static/* /roman-snpit-db/static/
RUN cp -p /venv/lib/python3.13/site-packages/snappl/db/templates/* /roman-snpit-db/templates/


# ======================================================================
# Build for tests
FROM build AS build-tests

WORKDIR /usr/src/snappl_install
RUN source /venv/bin/activate && pip install .[test]

WORKDIR /usr/src

# Note: as of this writing, the roman_imsim archive has both a branch
#   and a tag "v2.0".  That caused the git archive command to choke.
#   So, we use the specific git commit hash as the argument to git
#   archive.  (As of this writing, this version (or, presumably, later)
#   is needed, at least, for phrosty.)
RUN git clone https://github.com/matroxel/roman_imsim.git \
  && mkdir /roman_imsim \
  && cd roman_imsim \
  && git archive 21ea15a | tar -x -C /roman_imsim  \
  && cd .. \
  && rm -rf roman_imsim


# ======================================================================
# This is for the test webserver.  It installs crappy keys so you
#   can connect via https.  It also installs the test SNPIT_CONFIG file.
# The production webserver is going to be on Spin and won't do
#   SSL management itself (the spin ingress handles that).
FROM base AS webserver

COPY --from=build-webserver /venv/ /venv/
COPY --from=build-webserver /roman-snpit-db/ /roman-snpit-db
ENV PATH=/venv/bin:$PATH

WORKDIR /roman-snpit-db
ENV PYTHONPATH=/roman-snpit-db

RUN mkdir /sessions

COPY docker/snappl/key.pem /usr/src/key.pem
COPY docker/snappl/cert.pem /usr/src/cert.pem
COPY docker/snappl/config-test.yaml /roman-snpit-db/
COPY docker/snappl/roman-snpit-server.py /roman-snpit-db/

# For using dehydrated to get a LetsEncrypt cert.
# Manual work will still be required; gunicorn doesn't use these certs,
#   as the asumption is there's an ingress server, so the certs will
#   need to get moved to the ingress server.
# ALSO, important, you will need to save the account key that
#   gets created in /var/lib/dehydrated/accounts (the full directory),
#   and then later copy that back in before running dehydrated -c!
#   (...in fact... make /var/lib/dehydrated a pvc)
ARG HOST_ADDRESS=invalid.hostname
RUN mkdir /tmp/.well-known
RUN cat /etc/dehydrated/config | perl -pe 's/^WELLKNOWN=.*$/WELLKNOWN=\/tmp\/.well-known/' > /etc/dehydrated.config-new \
  && mv /etc/dehydrated.config-new /etc/dehydrated/config && rm -f /etc/dehydrated.config-new
RUN echo ${HOST_ADDRESS} >> /etc/dehydrated/domains.txt

ENTRYPOINT [ "tail", "-f", "/etc/issue" ]
# ENTRYPOINT [ "/venv/bin/gunicorn", "-b", "0.0.0.0:8080", "--access-logfile", "-", "--error-logfile", "-", "-k", "gevent", "--timeout", "300", "--workers", "10", "roman-snpit-server:application" ]
# ENTRYPOINT [ "/venv/bin/gunicorn", "-b", "0.0.0.0:8080", "-k", "gevent", "--timeout", "300", "--workers", "10", "roman-snpit-server:application" ]
# EXPOSE 8080


# ======================================================================
# This is for interaction.  It runs something that will stay up
#   that you can exec a shell on.
FROM base AS shell

COPY --from=build /venv/ /venv/
ENV PATH=/venv/bin:$PATH

WORKDIR /home

ENTRYPOINT [ "tail", "-f", "/etc/issue" ]


# ======================================================================
# For interaction, including the packages (and roman_imsim)
#   needed to run the tests in this directory.

FROM base AS tests

COPY --from=build-tests /venv/ /venv/
COPY --from=build-tests /roman_imsim/ /roman_imsim/
COPY --from=build-webserver /roman-snpit-db/ /roman-snpit-db/

ENV PATH=/venv/bin:$PATH
ENV PYTHONPATH=/roman_imsim

# This link is needed for our tests.
RUN ln -s /packages/photometry_test_data /photometry_test_data

# Need copies of the webserver config file for tests
COPY docker/snappl/config-test.yaml /roman-snpit-db/
COPY docker/snappl/roman-snpit-server.py /roman-snpit-db/

# Other config files needed in / for tests
COPY docker/snappl/default_snpit_pipeline_config.yaml /default_snpit_pipeline_config.yaml
COPY docker/snappl/snpit_test_config.yaml /snpit_test_config.yaml
COPY docker/snappl/test_config_for_db.yaml /test_config_for_db.yaml

WORKDIR /home

ENTRYPOINT [ "tail", "-f", "/etc/issue" ]
