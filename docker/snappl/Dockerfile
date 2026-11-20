# This has four final build-targets:
#    shell : A shell that has snappl installed and a running database and webserver.
#            It assumess you're using the RUNDIR/packages standard.  Use this
#            for development.
#
#    tests: A shell that is used for running snappl tests in snappl/tests.
#
#    webserver: A production webserver.  See below.
#
#    test-webserver: The webserver used for running snappl tests.
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
# For a webserver running on an AWS EC2 instance, build it with:
#    TODO

# ======================================================================
FROM debian:trixie-20261104 AS base
LABEL maintainer="Rob Knop <rknop@pobox.com>"

ARG USERID=0
ARG GROUPID=0
ENV USERID=${USERID}
ENV GROUPID=${GROUPID}

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
#
# This does NOT do a pip install .[test] in snappl, becasue
#   almost certainly you will want to do pip install -e .[test] in
#   the snappl checkout inside the container when actually
#   developing.

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
# This is for interaction.  It runs something that will stay up
#   that you can exec a shell on.
FROM base AS shell

COPY --from=build /venv/ /venv/
ENV PATH=/venv/bin:$PATH

# So the user can pip install
RUN chown -R ${USERID}:${GROUPID} /venv

# Create directories for stuff that docker-compose.yaml uses
RUN mkdir -p /dev_storage && chown ${USERID}:${GROUPID} /dev_storage
RUN mkdir -p /temp_dir && chown ${USERID}:${GROUPID} /temp_dir
RUN mkdir -p /crds_cache && chown ${USERID}:${GROUPID} /crds_cache

# Work in what our docs call RUNDIR
WORKDIR /home

COPY docker/snappl/snpit_test_config.yaml /snpit_test_config.yaml
ENV SNPIT_CONFIG=/snpit_test_config.yaml
ENV SNPIT_DEFAULT_CONFIG=/snpit_test_config.yaml

ENTRYPOINT [ "tail", "-f", "/etc/issue" ]


# ======================================================================
# For interaction, including the packages (and roman_imsim)
#   needed to run the tests in this directory.

FROM base AS tests


COPY --from=build-tests /venv/ /venv/
COPY --from=build-tests /roman_imsim/ /roman_imsim/
COPY --from=build-webserver /roman-snpit-db/ /roman-snpit-db/

# So the user can pip install
RUN chown -R ${USERID}:${GROUPID} /venv

ENV PATH=/venv/bin:$PATH
ENV PYTHONPATH=/roman_imsim

# Create directories for stuff that docker-compose.yaml uses
RUN mkdir -p /dev_storage && chown ${USERID}:${GROUPID} /dev_storage
RUN mkdir -p /temp_dir && chown ${USERID}:${GROUPID} /temp_dir
RUN mkdir -p /crds_cache && chown ${USERID}:${GROUPID} /crds_cache

# This link is needed for our tests.
RUN ln -s /packages/photometry_test_data /photometry_test_data

# The tests need the direct-to-db config file in addition to the regular one
COPY docker/snappl/test_db_config.yaml /test_db_config.yaml
COPY docker/snappl/snpit_test_config.yaml /snpit_test_config.yaml

# This will get overridden by the init_config fixture in snappl/tests/conftest.py
# But it's here so that somebody just running python in a test shell will have
#   a default config that works.
ENV SNPIT_CONFIG=/snpit_test_config.yaml
ENV SNPIT_DEFAULT_CONFIG=/snpit_test_config.yaml

WORKDIR /home

ENTRYPOINT [ "tail", "-f", "/etc/issue" ]


# ======================================================================
# This is for the production webserver.
#
# It does NOT use SSL; you would need to modify the entrypoint to do that
#   with something that passes --keyfile and --certfile to gunicorn.
#   (On NERSC Spin, you do not want SSL; that's handled externally#
#   by the ingress.)
#
# There is some stuff so that you can use letsencrypt (via dehydrated).
#   That was put in during the two week gap when LBL wasn't able to
#   issue certificates....  If you aren't using letsencrypt, you can
#   ignore this.  See comments below, there is hand-work required.

FROM base AS webserver

COPY --from=build-webserver /venv/ /venv/
COPY --from=build-webserver /roman-snpit-db/ /roman-snpit-db
ENV PATH=/venv/bin:$PATH

# So the user can pip install
RUN chown -R ${USERID}:${GROUPID} /venv

WORKDIR /roman-snpit-db
ENV PYTHONPATH=/roman-snpit-db

RUN mkdir -p /sessions && chown ${USERID}:${GROUPID} /sessions

# The actual webap code that gunicorn will run
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

ENTRYPOINT [ "/venv/bin/gunicorn", "-b", "0.0.0.0:8080", "--error-logfile", \
             "-", "-k", "gevent", "--timeout", "300", "--workers", "10", \
             "roman-snpit-server:application" ]
EXPOSE 8080


# ======================================================================
# This is for the test webserver used in snappl tests.

FROM webserver AS test-webserver

# Config files used in tests
COPY docker/snappl/test_db_config.yaml /test_db_config.yaml
COPY docker/snappl/test_webserver_config.yaml /test_webserver_config.yaml

# Config file for test webserver
ENV SNPIT_CONFIG=/test_webserver_config.yaml
ENV SNPIT_DEFAULT_CONFIG=/test_webserver_conifg.yaml

# Crappy self-signed keys for use in tests.  Never use these in production.
COPY docker/snappl/key.pem /usr/src/key.pem
COPY docker/snappl/cert.pem /usr/src/cert.pem

ENTRYPOINT [ "gunicorn", "--certfile", "/usr/src/cert.pem", "--keyfile", "/usr/src/key.pem", \
           "-w", "1", "--threads", "10", "-b", "0.0.0.0:8080", "--timeout", "0", "roman-snpit-server:application" ]
