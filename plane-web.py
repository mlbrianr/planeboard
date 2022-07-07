#!/usr/bin/env python
# encoding: utf-8
import json
from flask import Flask, jsonify

from datetime import timedelta
# needed for any cluster connection
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
# needed for options -- cluster, timeout, SQL++ (N1QL) query, etc.
from couchbase.options import (ClusterOptions, ClusterTimeoutOptions,
                                       QueryOptions)

from geopy.distance import geodesic as GD

import configparser

config = configparser.ConfigParser()
config.read('plane-loader.ini')

auth = PasswordAuthenticator(config['couchbase']['user'], config['couchbase']['password'])
cluster = Cluster(f"couchbase://{config['couchbase']['servers']}", ClusterOptions(auth))

# Wait until the cluster is ready for use.
cluster.wait_until_ready(timedelta(seconds=5))

# get a reference to our bucket
cb = cluster.bucket("planes-live")

cb_coll_default = cb.default_collection()
cb_coll = cb_coll_default

app = Flask(__name__)

here=[ 43.01775, -89.52206 ]

categories = ['Light', 'Medium 1', 'Medium 2', 'High Vortex', 'Heavy', 'High Performance', 'Rotorcraft']

@app.route('/')
def index():
    result = cluster.query('SELECT * FROM `planes-live`._default._default AS t ORDER BY ts DESC LIMIT 50')


    distance_added_rows = []

    for row in list(result.rows()):
        try:
            ac_pos = (row['t']['pos'])
            row['t']['distance'] = round(GD(here, ac_pos).mi, 1)
        except KeyError:
            pass

        try:
            category_desc = categories[row['t']['category'] - 1]
            row['t']['cat_desc'] = category_desc
        except KeyError:
            pass

        distance_added_rows.append(row)

    sorted_rows = sorted(distance_added_rows, key=lambda x: x['t']['ts'], reverse=True)

    return(jsonify(sorted_rows))

