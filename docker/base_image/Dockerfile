# syntax=docker/dockerfile:1
#
# To build:
#   Must be in the top level of snappl checkout
#   (../.. relative to the directory of this Dockerfile)
#
#   WEBSERVER:
#   ----------
#   docker build --build-arg HOST_ADDRESS=dns.name \
#      --target webserver \
#      -t registy.nersc.gov/m4385/rknop/roman-snpit-db:<VER> \
#      -f docker/base_image/Dockerfile .
#
#   The HOST_ADDRESS arg is just used for setting up dehydrated/letsencrypt,
#     so you can ignore it if you don't need that.
#
#   AWS LAMBDA:
#   -----------
#   docker build --target lambda-aws-image \
#      -t <ROB PUT THE RIGHT THING HERE> \
#      --platform linux/amd64 \
#      --provenance=false \
#      --build-arg FUNCTION_DIR=/mnt/snpit-dev/env/lambda-handlers \
#      -f docker/base_image/Dockerfile .

# ======================================================================

FROM debian:trixie-20260623 AS base
LABEL maintainer="Rob Knop <rknop@pobox.com>"

SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND="noninteractive"
ENV TZ="UTC"

RUN  apt-get update \
    && apt-get -y upgrade \
    && apt-get -y install -y \
         python3 locales netcat-openbsd gnupg curl elinks postgresql-client make rlwrap socat \
         ca-certificates dehydrated \
         tmux emacs-nox less procps bzip2 \
    && apt-get -y autoremove \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN cat /etc/locale.gen | perl -pe 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' > /etc/locale.gen.new \
    && mv /etc/locale.gen.new /etc/locale.gen
RUN locale-gen en_US.utf8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

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

RUN source /venv/bin/activate && \
    pip --no-cache install \
       "flask-session>=0.8.0,<1.0.0" \
       "flask>=3.1.2,<4.0.0" \
       "gevent>=25.9.1,<26.0.0" \
       "gunicorn>=23.0.0,<24.0.0" \
       "psycopg>3.2.9,<4.0.0" \
       "pytest-timestamper==0.0.10" \
       "pytest>=8.4.2,<9.0.0" \
       "remote-pdb==2.1.0"

# TEMPORARY
# This installs the preqreqs of snappl.  Really, we should
#   just let that be installed when we do pip install .
#   below.  However, during development, when editing
#   the package a lot, it's faster to build the docker
#   image if there's a previous step that already has the prereqs.
#   In the mean time, KEEP THIS SYNCED WITH pyproject.toml
RUN source /venv/bin/activate && \
    pip --no-cache install \
        "astropy>=7.1.0,<8.0.0" \
        "fitsio>=1.2.5,<2.0.0" \
        "galsim==2.8.4" \
        "gwcs>=1.0.3,<2.0.0" \
        "h5py>=3.14.0,<4.0.0" \
        "numpy>=2.2.6,<3.0.0" \
        "pandas>=2.3.3,<3.0.0" \
        "photutils>=3.0.0,<4.0.0" \
        "pycryptodome>=3.23.0,<4.0.0" \
        "python-dateutil>=2.9.0.post0,<3.0.0" \
        "pytz>=2025.2" \
        "pyyaml>=6.0.3,<7.0.0" \
        "rkwebutil>=2.5.2,<3.0.0" \
        "roman-datamodels>=1.0.0,<2.0.0" \
        "scipy>=1.16.2,<2.0.0" \
        "simplejson>=3.20.2,<4.0.0" \
        "stpsf>=2.2.0,<3.0.0" \
        "synphot>=1.7.0,<2.0.0"
# END TEMPORARY

RUN mkdir -p /usr/src/snappl_install
WORKDIR /usr/src/snappl_install
COPY . /usr/src/snappl_install
RUN source /venv/bin/activate && pip install .


# ======================================================================
# This is for the test webserver.  It installs crappy keys so you
#   can connect via https.  It also installs the test SNPIT_CONFIG file.
# The production webserver is either on NERSC Spin, where the ingress
#   handles SSL, or on an AWS instance that's only available to our
#   own environment, so we just use http (no SSL).
FROM base AS test

COPY --from=build /venv/ /venv/
ENV PATH=/venv/bin:$PATH

RUN mkdir -p /roman-snpit-db/templates
RUN mkdir -p /roman-snpit-db/static

# Could save a wee bit of image size by making symbolic links instead of copying
RUN cp -p /venv/lib/python3.13/site-packages/rkwebutil/static/* /roman-snpit-db/static/
RUN cp -p /venv/lib/python3.13/site-packages/snappl/db/static/* /roman-snpit-db/static/
RUN cp -p /venv/lib/python3.13/site-packages/snappl/db/templates/* /roman-snpit-db/templates/

RUN mkdir /sessions

WORKDIR /roman-snpit-db
ENV PYTHONPATH=/roman-snpit-db

COPY docker/webserver/key.pem /usr/src/key.pem
COPY docker/webserver/cert.pem /usr/src/cert.pem
COPY docker/webserver/config-test.yaml /roman-snpit-db/
COPY docker/webserver/roman-snpit-server.py /roman-snpit-db/

EXPOSE 8080
ENTRYPOINT [ "gunicorn", "--certfile", "/usr/src/cert.pem", "--keyfile", "/usr/src/key.pem", \
             "-w", "1", "--threads", "10", "-b", "0.0.0.0:8080", "--timeout", "0", "roman-snpit-server:application" ]


# ======================================================================
# This is for interaction.  It runs something that will stay up
#   that you can exec a shell on.
FROM base AS shell

COPY --from=build /venv/ /venv/
ENV PATH=/venv/bin:$PATH

WORKDIR /home

ENTRYPOINT [ "tail", "-f", "/etc/issue" ]


# ======================================================================
# This is for the production webserver
FROM base AS webserver

COPY --from=build /venv/ /venv/
COPY --from=build /roman-snpit-db/ /roman-snpit-db
ENV PATH=/venv/bin:$PATH

RUN mkdir -p /roman-snpit-db/templates
RUN mkdir -p /roman-snpit-db/static

# Could save a wee bit of image size by making symbolic links instead of copying
RUN cp -p /venv/lib/python3.13/site-packages/rkwebutil/static/* /roman-snpit-db/static/
RUN cp -p /venv/lib/python3.13/site-packages/snappl/db/static/* /roman-snpit-db/static/
RUN cp -p /venv/lib/python3.13/site-packages/snappl/db/templates/* /roman-snpit-db/templates/

RUN mkdir /sessions

WORKDIR /roman-snpit-db
ENV PYTHONPATH=/roman-snpit-db

RUN mkdir /sessions

COPY docker/webserver/roman-snpit-server.py /roman-snpit-db/

WORKDIR /roman-snpit-db
ENV PYTHONPATH=/roman-snpit-db

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

EXPOSE 8080
# ENTRYPOINT [ "/venv/bin/gunicorn", "-b", "0.0.0.0:8080", "--access-logfile", "-", "--error-logfile", "-", "-k", "gevent", "--timeout", "300", "--workers", "10", "roman-snpit-server:application" ]
ENTRYPOINT [ "/venv/bin/gunicorn", "-b", "0.0.0.0:8080", "-k", "gevent", "--timeout", "300", "--workers", "10", "roman-snpit-server:application" ]

# ======================================================================
# This is a build for the AWS lambda image
FROM build AS lambda-aws-build

RUN source /venv/bin/activate && \
    pip --no-cache install awslambdaric

# ======================================================================
# This is for the AWS lambda image.
#   This staging stage is my vain attempt
#   to make the final layer, which I'm
#   editing all the time, be small.
#   I would have thought that docker
#   would just do that without even the
#   stage business, but it's not working.
FROM base AS lambda-aws-image-staging

COPY --from=lambda-aws-build /venv/ /venv/

# ======================================================================
FROM lambda-aws-image-staging AS lambda-aws-image

ENV PATH=/venv/bin:$PATH

ENV CRDS_SERVER_URL=https://roman-crds.stsci.edu

# UGH.  What's the right way to do this?  Writing to
#   a bind-mounted S3 is going to be fraught.
# REALLY we don't want the lambda functions doing
#   anything that would trigger a download, but
#   we need to verify this.  There are some
#   packages in astronomer-land that do downloads
#   and write to your home directory when
#   you just import them, which is bad behavior.
ENV CRDS_PATH=/tmp

ENTRYPOINT [ "/venv/bin/python", "-m", "awslambdaric" ]
WORKDIR /tmp

# ****
# A hardcoded default python script directory.
# For production, point to the mounted script dir with
#   --build-arg /path/to/script/dir
#
RUN mkdir -p /test_function
RUN cat <<EOF > /test_function/helloworld.py
import os
import json
import subprocess
def handler(event, context):
    df = subprocess.run( ['df', '-h'], capture_output=True )
    ls = subprocess.run( ['ls', '-l', '/mnt/snpit-dev'], capture_output=True )
    try:
        files = os.listdir( "/mnt/snpit-dev" )
    except Exception as ex:
        files = str(ex)
    return { "message": "Hello, world!",
             "path": os.getenv( "PATH", None ),
             "pythonpath": os.getenv( "PYTHONPATH", None ),
             "direc": files,
             "df": df.stdout.decode('utf-8'),
             "ls": ls.stdout.decode('utf-8')
           }
EOF
#
# ****

ARG FUNCTION_DIR="/test_function"
ENV PYTHONPATH=${FUNCTION_DIR}
WORKDIR ${FUNCTION_DIR}

CMD [ "helloworld.handler" ]
