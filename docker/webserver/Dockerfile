# Build this from the top level of the checkout.
#
# Build it with
#   docker build --target webserver -t registy.nersc.gov/m4385/rknop/roman-snpit-db:<VER> \
#      -f docker/webserver/Dockerfile .
#

# ======================================================================

FROM debian:bookworm-20250630 AS base
LABEL maintainer="Rob Knop <rknop@pobox.com>"

SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND="noninteractive"
ENV TZ="UTC"

RUN  apt-get update \
    && apt-get -y upgrade \
    && apt-get -y install -y \
         python3 locales netcat-openbsd gnupg curl elinks postgresql-client make rlwrap socat \
         ca-certificates \
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
        "galsim>=2.7.2,<3.0.0" \
        "gwcs>=0.26.0,<0.27.0" \
        "h5py>=3.14.0,<4.0.0" \
        "numpy>=2.2.6,<3.0.0" \
        "pandas>=2.3.3,<3.0.0" \
        "photutils>=2.3.0,<3.0.0" \
        "pycryptodome>=3.23.0,<4.0.0" \
        "python-dateutil>=2.9.0.post0,<3.0.0" \
        "pytz>=2025.2" \
        "pyyaml>=6.0.3,<7.0.0" \
        "rkwebutil>=2.3.0,<3.0.0" \
        "roman-datamodels>=0.27.0,<0.28.0" \
        "scipy>=1.16.2,<2.0.0" \
        "simplejson>=3.20.2,<4.0.0"
# END TEMPORARY

RUN mkdir -p /usr/src/snappl_install
WORKDIR /usr/src/snappl_install
COPY . /usr/src/snappl_install
RUN source /venv/bin/activate && pip install .

RUN mkdir -p /roman-snpit-db/templates
RUN mkdir -p /roman-snpit-db/static

# Could save a wee bit of image size by making symbolic links instead of copying
RUN cp -p /venv/lib/python3.11/site-packages/rkwebutil/static/* /roman-snpit-db/static/
RUN cp -p /venv/lib/python3.11/site-packages/snappl/db/static/* /roman-snpit-db/static/
RUN cp -p /venv/lib/python3.11/site-packages/snappl/db/templates/* /roman-snpit-db/templates/


# ======================================================================
# This is for the test webserver.  It installs crappy keys so you
#   can connect via https.  It also installs the test SNPIT_CONFIG file.
# The production webserver is going to be on Spin and won't do
#   SSL management itself (the spin ingress handles that).
FROM base AS test

COPY --from=build /venv/ /venv/
COPY --from=build /roman-snpit-db/ /roman-snpit-db
ENV PATH=/venv/bin:$PATH

WORKDIR /roman-snpit-db
ENV PYTHONPATH=/roman-snpit-db

RUN mkdir /sessions

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
COPY --from=build /roman-snpit-db/ /roman-snpit-/db
ENV PATH=/venv/bin:$PATH

WORKDIR /roman-snpit-db
ENV PYTHONPATH=/roman-snpit-db

RUN mkdir /sessions

COPY docker/webserver/config-test.yaml /roman-snpit-db/
COPY docker/webserver/roman-snpit-server.py /roman-snpit-db/

ENTRYPOINT [ "tail", "-f", "/etc/issue" ]

# ======================================================================
# This is for the production webserver
FROM base AS webserver

COPY --from=build /venv/ /venv/
COPY --from=build /roman-snpit-db/ /roman-snpit-db
ENV PATH=/venv/bin:$PATH

WORKDIR /roman-snpit-db
ENV PYTHONPATH=/roman-snpit-db

RUN mkdir /sessions

EXPOSE 8080
# ENTRYPOINT [ "/venv/bin/gunicorn", "-b", "0.0.0.0:8080", "--access-logfile", "-", "--error-logfile", "-", "-k", "gevent", "--timeout", "300", "--workers", "10", "roman-snpit-server:application" ]
ENTRYPOINT [ "/venv/bin/gunicorn", "-b", "0.0.0.0:8080", "-k", "gevent", "--timeout", "300", "--workers", "10", "roman-snpit-server:application" ]
