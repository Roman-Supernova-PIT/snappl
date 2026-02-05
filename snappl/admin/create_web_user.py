import argparse
import secrets
import base64
import uuid
import json

import Crypto
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA256
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA

import psycopg

from snappl.config import Config


def create_web_user( username, email, displayname, password ):
    cfg = Config.get()

    id = uuid.uuid4()
    salt = secrets.token_bytes( 16 )
    iv = secrets.token_bytes( 12 )

    keypair = RSA.generate( 4096, Crypto.Random.get_random_bytes )
    pubkey = keypair.publickey().export_key( "PEM" ).decode( 'utf-8' )
    privkey = keypair.export_key( "PEM" ).decode( 'utf-8' )
    privkey.replace( "-----BEGIN RSA PRIVATE KEY-----", "" )
    privkey.replace( "-----END RSA PRIVATE KEY-----", "" )
    privkey.replace( "\n", "" )

    initialkey = PBKDF2( password.encode('utf-8'), salt, 32, count=100000, hmac_hash_module=SHA256 )
    aeskey = AES.new( initialkey, AES.MODE_GCM, iv )
    # Print aeskey._key (byte array, so hex it or something) to see the raw key export
    encprivkey, tag = aeskey.encrypt_and_digest( privkey.encode('utf-8') )
    encprivkey = encprivkey + tag
    encprivkey = base64.b64encode( encprivkey ).decode( 'utf-8' )

    privkeydict = { 'privkey': encprivkey,
                    'salt': base64.b64encode( salt ).decode( 'utf-8' ),
                    'iv': base64.b64encode( iv ).decode( 'utf-8' )
                   }
    privkeyjson = json.dumps( privkeydict )

    # print( f"INSERT INTO authuser(id,username,displayname,email,pubkey,privkey) "
    #        f"VALUES('{id}','{username}','{displayname}','{email}',"
    #        "'{pubkey}','{privkeyjson}'::JSONB)" )

    pghost = cfg.value( 'system.db.postgres_host' )
    pgport = cfg.value( 'system.db.postgres_port' )
    pgdb = cfg.value( 'system.db.postgres_database' )
    pguser = cfg.value( 'system.db.postgres_username' )
    pgpasswd = cfg.value( 'system.db.postgres_password' )
    con = psycopg.connect( host=pghost, port=pgport, dbname=pgdb, user=pguser, password=pgpasswd )
    cursor = con.cursor()
    cursor.execute( "INSERT INTO authuser(id,username,displayname,email,pubkey,privkey) "
                    "VALUES (%(id)s,%(username)s,%(displayname)s,%(email)s,%(pubkey)s,%(privkey)s::JSONB)",
                    { 'id': id,
                      'username': username,
                      'displayname': displayname,
                      'email': email,
                      'pubkey': pubkey,
                      'privkey': privkeyjson
                     } )
    con.commit()
    con.close()


def main():
    parser = argparse.ArgumentParser( "make_password.py",
                                      description="Manually make a password for inserting into a rkauth database" )
    parser.add_argument( "-u", "--username", required=True )
    parser.add_argument( "-e", "--email", required=True )
    parser.add_argument( "-d", "--displayname", required=True )
    parser.add_argument( "-p", "--password", required=True )
    args = parser.parse_args()

    create_web_user( args.username, args.email, args.displayname, args.password )


# ======================================================================
if __name__ == "__main__":
    main()
