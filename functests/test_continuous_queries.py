from __future__ import print_function
import akumulid_test_tools as att
import datetime
import itertools
import json
import math
import multiprocessing
import os
import sys
import time
import traceback
try:
    from urllib2 import urlopen
except ImportError:
    from urllib import urlopen

HOST = '127.0.0.1'
TCPPORT = 8282
HTTPPORT = 8181

"""
Test plan:
    Run two parallel processes.
    Process 1.
    - Write data in range [begin, mid] in a loop.
    - Long pause.
    - Write data in range (mid, end] in a loop.
    - Exit.
    Process 2.
    - Read all data in fwd direction in range [begin, end-window].
"""

def writer(dt, delta, nmsgs):
    try:
        chan = att.TCPChan(HOST, TCPPORT)

        # fill data in
        print("Sending {0} messages through TCP...".format(nmsgs))
        tags = {
            "tag": ['Foo'],
        }
        N1 = N/2 if N % 2 == 0 else N/2 + 1
        N2 = N/2
        for it in att.generate_messages(dt, delta, N1, 'test', **tags):
            chan.send(it)
        time.sleep(10)
        for it in att.generate_messages(dt + delta*N1, delta, N2, 'test', **tags):
            chan.send(it)
        time.sleep(10)
    except:
        traceback.print_exc()
        sys.exit(1)

def reader(dtstart, delta, N):
    window = att.get_window_width()
    end = dtstart + delta*(N-1) - window
    begin = dtstart
    timedelta = end - begin
    points_required = int(math.ceil((timedelta.seconds*1000000.0 + timedelta.microseconds) / (delta.seconds*1000000.0 + delta.microseconds))) + 1
    # We need to add 1 because query will include both begin and end timestamps.

    query_params = {
        "output": { "format":  "csv" },
    }
    query = att.makequery("test", begin, end, **query_params)
    queryurl = "http://{0}:{1}".format(HOST, HTTPPORT)
    response = urlopen(queryurl, json.dumps(query))

    exp_ts = begin
    exp_value = 0
    iterations = 0

    print("Test #6 - filter by tag")

    for line in response:
        try:
            columns = line.split(',')
            tagline = columns[0].strip()
            timestamp = att.parse_timestamp(columns[1].strip())
            value = float(columns[2].strip())

            exp_tags = 'test tag=Foo'

            att.check_values(exp_tags, tagline, 'ENDS', exp_ts, timestamp, exp_value*1.0, value, iterations)

            exp_ts += delta
            exp_value += 1
            iterations += 1
        except:
            print("Error at line: {0}".format(line))
            raise

    # Check that we received all values
    if iterations != points_required:
        raise ValueError("Expect {0} data points, get {1} data points".format(points_required, iterations))
    print("Test #6 passed")

def main(path, debug=False):
    if not os.path.exists(path):
        print("Path {0} doesn't exists".format(path))
        sys.exit(1)

    akumulid = att.Akumulid(path)
    if not debug:
        # Reset database
        akumulid.delete_database()
        akumulid.create_database()
        # start ./akumulid server
        print("Starting server...")
        akumulid.serve()
        time.sleep(5)
    else:
        print("Akumulid should be started first")
    try:

        dt = datetime.datetime.utcnow()
        delta = datetime.timedelta(milliseconds=1)
        nmsgs = 100000

        wproc = multiprocessing.Process(target=writer, args=[dt, delta, nmsgs])
        rproc = multiprocessing.Process(target=reader, args=[dt, delta, nmsgs])

        wproc.start()
        rproc.start()

        wproc.join()
        rproc.join()

    except:
        traceback.print_exc()
        sys.exit(1)
    finally:
        if not debug:
            print("Stopping server...")
            akumulid.stop()
            time.sleep(5)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Not enough arguments")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2] == 'debug' if len(sys.argv) == 3 else False)
else:
    raise ImportError("This module shouldn't be imported")