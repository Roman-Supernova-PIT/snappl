###########################################
Environment and Database Maintainer's Guide
###########################################

.. contents::
   :depth: 3

Installing a new database on NERSC Spin
=======================================

**Important**: to do this, you probably need to be running on on ``x86_64`` Linux machine.  If you really know what you're doing, you may be able to build a ``x86_64`` image on another architecture, though it will probably be slow because the build process will need to emulate the architecture.  Things will work better if you just do things in the architecture that we also need to run in.

.. _spin-namespace:

Figure out your Spin namespace
------------------------------

Assuming you're doing this for the Roman SNPIT, you will will be working with the ``m4385`` nersc account.  First, make sure you can run spin by, on Perlmutter, doing::

  module load spin

Then, select the right account with::

  rancher context switch

Find the number that corresponds to ``production`` and ``m4385``, and give it that number.  If you don't see ``m4385`` on the list, then you don't yet have access to the Roman SNPIT spin area.

See what namespaces currently exist with::

  rancher namespaces

If you know you want to work in one of those (and you will know if you know; if you're setting up a new thing, you prbably don't want to work in one of those), good, remember it.  If not, you will need to make a new namespace with::

  rancher namespace create <namespace> -d "<comment>"

where ``<namespace>`` should *always* start with ``romanmansnpit``, and the ``<comment>`` should be a brief one line description of what this namespace is for.

.. _docker-image-tag:

Figure out the tag for your docker images
-----------------------------------------

To avoid confusion, we need to make sure that the docker images we make to run things on Spin do not have names that collide with each other.  Pick a tag that is a shortish string of text without spaces that indicates the database you're installing.  For instance, if I was making a dev database, I might choose the tag ``rknop-dev``.  If I was making a database for the nov2025 test run, I might just use ``nov2025`` as the tag.

I will sometimes add ``-yyyymmdd`` to the end of my tag so that I can explicitly update the image if necessary.


.. _postgres-password:

Pick a postgres password
------------------------

This actually doesn't need to be all that secure, because the postgres server is not going to be accessible from anywhere other than the small collection of virtual machines you'll be running on Spin within your namespace.  However, there's no reason not just to do it right.  Pick a good password.  Here is a python snippit that will do that::

  import secrets
  chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  pw = "".join( chars[ secrets.randbelow( len(chars) )] for i in range(16) )
  print( pw )

Stick this password in your password safe somewhere (you do use one, yes?).


Build the docker images
-----------------------

If you know what you're doing, you may be able to do this with ``podman-hpc`` on NERSC.  However, I (Rob) always do this on my laptop or desktop.  (Both of these are ``x86_64`` linux machines; see the warning above.)

You need to do this in a checkout of the `snappl repo <https://github.com/roman-Supernova-PIT/snappl>`_.

.. _postgres-docker-image:

Build the postgres docker image
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

From your snappl checkout::

  cd docker/postgres
  docker build --target postgres -t registry.nersc.gov/m4385/snpit-db-postgres:<tag> .

where ``<tag>`` is the :ref:`image tag<docker-image-tag>` you chose above.

Assuming all is well, push the docker image up to NERSC with::

  docker push registry.nersc.gov/m4385/snpit-db-postgres:<tag>

If it yells at you that you don't have access, you may need to log into the NERSC image registry with::

  docker login registry.nersc.gov

Give it your usual NERSC username and password (*without* the 6-digit OTP).

.. _webserver-docker-image:

Build the webserver docker image
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

From your snappl checkout::

  docker build --target webserver -t registry.nersc.gov/m4385/snpit-db-webserver:<tag> -f docker/webserver/Dockerfile .

where ``<tag>`` is the :ref:`image tag<docker-image-tag>` you chose above.

Assuming all is well, push the docker image up to NERSC with::

  docker push registry.nersc.gov/m4385/snpit-db-webserver:<tag>

again logging first if necessary.


Edit the Spin YAML files
------------------------

Copy all the files in the ``spin/rknop_dev`` file to a place where you can edit them.  (Please do not edit the files there.)  You will need to edit all of them.  The edits you need to make are:

* **Update the namespace.**  In *every* file, replace the string ``romansnpit-rknop-dev`` with the :ref:`spin namespace <spin-namespace>` you're using.

* **Update postgres.yaml** : Make the following edits:

  * Find the line starting with ``nersc.gov/username`` and replace ``raknop`` with your NERSC username.
  * Find the line starting with ``nersc.gov/uid`` and replace ``95089`` with your NERSC UID.  (Run ``id`` on the command line to figure out what this is.)
  * Find the line starting with ``image:`` and replace the value after the colon with the :ref:`docker image you built and pushed for postgres<postgres-docker-image>`.

* **Update webserver.yaml** : Make the following edits

  * Find the line starting with ``nersc.gov/username`` and replace ``raknop`` with your NERSC username.
  * Find the line starting with ``nersc.gov/uid`` and replace ``95089`` with your NERSC UID.  (Run ``id`` on the command line to figure out what this is.)
  * Find the line starting with ``image:`` and replace the value after the colon with the :ref:`docker image you built and pushed for the webserver<webserver-docker-image>`.
  * Uncomment the line ``command: [ 'tail', '-f', '/etc/issue' ]``
  * Comment out (using ``#``) the lines at the bottom starting with ``- host: romansnpit-rknop-dev.lbl.gov`` all the way to the bottom of the file, but leaving the last ``---`` line uncommented.  (You will need to uncomment these again later after you've done further steps.)

* **Update secrets.yaml** : This one is a bit more involved.

  * First, you have to create a config file.  Create a file with these contents::

      system:
        webserver:
          flask_secret_key: <PUT FLASK SECRET KEY HERE>
          sessionstore: /sessions
          emailfrom: <YOUR EMAIL ADDRESS WHICH PROBABLY NEEDS TO BE AT LBL, IF NOT TALK TO ROB>
          smtpserver: smtp.lbl.gov
          smtpport: 25
          smtpusessl: False
          smtpusername: NULL
          smtppassword: NULL
        
        db:
          postgres_host: postgres
          postgres_port: 5432
          postgres_database: roman_snpit
          postgres_username: postgres
          postgres_password: <PUT THE POSTGRES PASSWORD HERE>
          # These next two are for debugging purposes and should always be false in production
          echoqueries: false
          alwaysexplain: false

    Replace the three things above that are in ``<ALL CAPS>``.  For the postgres password, put in the one you :ref:`created above<postgres-password>`.  For the flask secret key, generate another "good" password; it can be anything, it just shouldn't be the same as what's used anywhere else, and nobody else should have access to it.

  * Run::

      base64 -w 0 <configfile> > barf

    where ``<configfile>`` is the config file you created and edited.  Then, in ``secrets.yaml``, edit the line starting ``snpit_config.yaml:`` and replace ``PUT THE RIGHT THING HERE`` with the contents of the file ``barf``.

  * base64 encode your :ref:`postgres password<postgres-password>` with::

      echo -n "<postgres password>" | base64 - && echo

    Copy the single line of text that command produces, and replace ``PUT THE RIGHT THING HERE`` with that line of text in ``secrets.yaml`` on the line starting ``pgpasswd:``.  (Yes, the postgres password goes in two different places.)


Run the Initial Spin Servers and Create the Database Tables
-----------------------------------------------------------
    
Apply all (well, most) of the yaml files::

    export NAMESPACE=<your namespace>
    rancher kubectl --namespace $NAMESPACE apply -f secrets.yaml
    rancher kubectl --namespace $NAMESPACE apply -f postgres-pvc.yaml
    rancher kubectl --namespace $NAMESPACE apply -f webserver-sessions-pvc.yaml
    rancher kubectl --namespace $NAMESPACE apply -f postgres.yaml
    rancher kubectl --namespace $NAMESPACE apply -f webserver.yaml

Stop if you get error messages after any of these, and try to figure out what's going on.

Once you've done all of this, run::

  rancher kubectl --namespace $NAMESPACE get pods

If all is well, you should see the postgres and webserver 

Next, migrate the database.  Get a shell on the webserver machine (which currently isn't actually running the webserver) with::

  rancher kubectl --namespace $NAMESPACE exec -it <podname> -- /bin/bash

where ``<podname>`` is the name of the pod for the webserver with ``get pods`` above.  It will start with ``webserver``, but it will end with some (seemingly) random characters.

Once you have a shell on the webserver, run ``python`` and, then, interactively in python::

  >> from snappl.db.migrations.apply_migrations import apply_migrations
  >> apply_migrations()

If all is well, it will tell you it applied a bunch of ``.sql`` files and give you no errors.

Get a DNS name for the webserver
--------------------------------

This is potentially complicated.  Your webserver does actually already have a DNS name which was created by Spin.  To find the default Spin DNS name, look at the file ``webserver.yaml`` you created.  Find the line ``kind: Ingress``, and find the first line starting with ``- host:`` below that.  The hostname on that line is the Spin DNS name.  It will be::

  webserver.<namespace>.production.svc.spin.nersc.org

You can just use this as the database webserver, but it will *not* have a valid SSL certificate, which will cause problems with the spin dbclient.  (You can work around those problems, but it's better to do things right.)  E.g., I use ``romansnpit-rknop-dev.lbl.gov`` for my dev instance.  If you're at LBL, you can use https://iprequest.lbl.gov/ and ask for a CNAME that points to the Spin default DNS name.  If you aren't... you have to figure something out.

Get a Certificate for your DNS name
-----------------------------------

You can generate a privatey key and a certificate signing request with (on NERSC, or any system that has ``openssl`` installed)::

  openssl req -new -newkey rsa:2048 -pubkey -keyout your_server_name.priv -out your_server_name.csr -nodes

Replace ``your_server_name`` with the DNS name, only replace all periods with underscores.  (Truthfully, it doesn't matter exactly what you name these two files, as long as you keep track of them.)  That will ask you a bunch of questions, which you should answer correctly.  Do *not* give it a password; just hit Enter there to make the key passwordless.

You will use the ``.csr`` file you created to get a signed certificate.  If you're at LBL, you can go to https://certificates.lbl.gov and paste everything everything from the CSR file starting from the line ``-----BEGIN CERTIFICATE REQUEST-----`` to the bottom of the file into the text widget on that page.  If you're not at LBL... you need to figure something out.

Once you get the certificate, save it in the file ``your_server_name.cert``.  If you got your certificate from ``certificates.lbl.gov``, you want to save the "Certificate (w/ issue after), PEM encoded" certificate to that file.

Base64 encode both your private key and your certificate::

  base64 -w 0 your_server_name.cert > cert.barf
  base64 -w 0 your_server_name.priv > priv.barf

Edit the file ``cert.yaml``:

* Find the line starting ``tls.crt:``.  Replace ``PUT THE RIGHT THING HERE`` with the contents of ``cert.barf``.

* Find the line starting ``tls.key:``.  Replace ``PUT THE RIGHT THING HERE`` with the contents of ``priv.barf``.


Update the webserver to actually run the webserver
--------------------------------------------------

  * Edit the file ``webserver.yaml``:

    * Comment out the line ``command: [ 'tail', '-f', '/etc/issue' ]``

    * Uncomment all the lines at the bottom starting with ``- host: romansnpit-rknop-dev.lbl.gov``

    * Replace ``romansnpit-rknop-dev.lbl.gov`` (in two places!) with the DNS name of your webserver.

    * Remember to save the file.

  * Run::

      rancher kubectl --namespace $NAMESPACE apply -f webserver.yaml

    This will restart the webserver, now actually running the webserver.  Do::

      rancher kubectl --namespace $NAMESPACE get pods

    until you see the webserver is running.  Then, do::

      rancher kubectl --namespace $NAMESPACE logs <podname>

    make sure the logs look good.  If you see errors and stack dumps, that's not good.

    

  
  
