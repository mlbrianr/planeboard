#!/bin/env python
import pyModeS as pms
from datetime import timedelta, datetime
from time import time
from pyModeS.extra.tcpclient import TcpClient
# needed for any cluster connection
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
# needed for options -- cluster, timeout, SQL++ (N1QL) query, etc.
from couchbase.options import (ClusterOptions, ClusterTimeoutOptions,
                               QueryOptions, MutateInOptions)
from couchbase.exceptions import (
    CASMismatchException,
    CouchbaseException,
    DocumentExistsException,
    DocumentNotFoundException,
    PathExistsException,
    PathNotFoundException,
    SubdocCantInsertValueException,
    SubdocPathMismatchException)
import couchbase.subdocument as SD

import configparser

config = configparser.ConfigParser()
config.read('plane-loader.ini')

# Update this to your cluster
username = config['couchbase']['user']
password = config['couchbase']['password']
bucket_name = "planes"
cert_path = "path/to/certificate"
# User Input ends here.

# Connect options - authentication
auth = PasswordAuthenticator(
    username,
    password,
    # NOTE: If using SSL/TLS, add the certificate path.
    # We strongly reccomend this for production use.
    # cert_path=cert_path
)

# Get a reference to our cluster
# NOTE: For TLS/SSL connection use 'couchbases://<your-ip-address>' instead
cluster = Cluster(f"couchbase://{config['couchbase']['servers']}", ClusterOptions(auth, show_queries=True, enable_tracing=True))

# Wait until the cluster is ready for use.
cluster.wait_until_ready(timedelta(seconds=5))

# get a reference to our bucket
cb = cluster.bucket(bucket_name)

cb_coll_default = cb.default_collection()
cb_coll = cb_coll_default

cb_live = cluster.bucket('planes-live')
cb_live_coll = cb_live.default_collection()

def main():
    # Get current time
    sel_time = time() - 24*60*60
    print(f"time is {sel_time}")

    # N1QL search for planes with ts older
    query = f"DELETE FROM `planes-live` WHERE ts < {sel_time} RETURNING *"
    print(query)


    try:
        result = cluster.query(query)

        for row in result.rows():
            print(row)
    except CouchbaseException as ex:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
