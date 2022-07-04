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

def upsert_live(doc):
#    print("\nUpsert CAS: ")
    try:
        # key will equal: "airline_8091"
        key = doc["icao"]
        result = cb_live_coll.upsert(key, doc)
        print(result.cas)
    except Exception as e:
        print(e)

def upsert_document(doc):
#    print("\nUpsert CAS: ")
    try:
        # key will equal: "airline_8091"
        key = doc["type"] + "_" + str(doc["id"])
        result = cb_coll.upsert(key, doc)
        print(result.cas)
    except Exception as e:
        print(e)

# define your custom class by extending the TcpClient
#   - implement your handle_messages() methods
class ADSBClient(TcpClient):
    def __init__(self, host, port, rawtype):
        super(ADSBClient, self).__init__(host, port, rawtype)

    def handle_messages(self, messages):
        for msg, ts in messages:
            if len(msg) != 28:  # wrong data length
                continue

            df = pms.df(msg)

            if df != 17:  # not ADSB
                continue

            if pms.crc(msg) !=0:  # CRC fail
                continue

            icao = pms.adsb.icao(msg)
            tc = pms.adsb.typecode(msg)
       
            live = {
                tc: msg,
                'icao': icao,
                'ts': ts,
            }

            callsign = None
            category = None
            if tc >= 1 and tc <= 4:
                callsign = pms.adsb.callsign(msg)
                live['callsign'] = callsign
                category = pms.adsb.category(msg)
                live['category'] = category

            print(f"TC is {tc}")

            pos = None
            if tc >= 9 and tc <= 18 or tc >= 20 and tc <= 22:
                pos = pms.adsb.position_with_ref(msg, 43.01775, -89.52206)
                print(f"POS is {pos}")


            vel = None
            angle = None
            if tc > 4 and tc < 9 or tc == 19:
                vel = pms.adsb.velocity(msg)[0]
                angle = pms.adsb.velocity(msg)[1]
                print(f"VEL is {vel} ANGLE is {angle}")

            alt = None
            if tc >= 9 and tc <= 18 or tc >= 20 and tc <= 22:
                alt = pms.adsb.altitude(msg)

            selected_alt = None
            selected_hdg = None
            if tc == 29:
                selected_alt = pms.adsb.selected_altitude(msg)
                selected_hdg = pms.adsb.selected_heading(msg)

#            pms.tell(msg)

            # See if plane already exists
            try:
                #print("get")
                doc = cb_live_coll.get(icao)

                new_doc = doc.value
                new_doc[tc] = msg
                new_doc['ts'] = ts
                if pos:
                    new_doc['pos'] = pos
                if callsign:
                    new_doc['callsign'] = callsign
                if category:
                    new_doc['category'] = category
                if alt:
                    new_doc['alt'] = alt
                if vel:
                    new_doc['vel'] = vel
                if angle:
                    new_doc['angle'] = angle
                if selected_alt:
                    new_doc['selected_alt'] = selected_alt
                if selected_hdg:
                    new_doc['selected_hdg'] = selected_hdg
                print(f"Updating to {new_doc}")
                upsert_live(new_doc)
            except DocumentNotFoundException:
                print(f"Create new {live}")
                cb_live_coll.insert(icao, live)
        

                # upsert_document(doc)        


            # TODO: write you magic code here
            #print(ts, icao, tc, msg)

# run new client, change the host, port, and rawtype if needed
client = ADSBClient(host='127.0.0.1', port=30005, rawtype='beast')
client.run()
