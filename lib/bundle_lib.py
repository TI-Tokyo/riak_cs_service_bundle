# Copyright (c) 2021 TI Tokyo    All Rights Reserved.
#
# This file is provided to you under the Apache License,
# Version 2.0 (the "License"); you may not use this file
# except in compliance with the License.  You may obtain
# a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
# ---------------------------------------------------------------------

# Common functions used in various scripts in riak_cs_service_bundle.


import httplib2, subprocess, json, time, re, sys

def _wrap(x, X):
    if x > X:
        return wrap(x - X, X)
    else:
        return x

def get_topologies():
    riak_topo_from = "riak-topo.json"
    rcs_topo_from = "rcs-topo.json"
    try:
        with open(riak_topo_from) as f:
            riak_topo = json.load(f)
    except:
        riak_topo = {"cluster1": list(range(1, 4))}
    try:
        with open(rcs_topo_from) as f:
            rcs_topo = json.load(f)
    except:
        rcs_topo = {str(x):_wrap(x, 3) for x in range(1, 3)}
    return riak_topo, rcs_topo


def stanchion_node_id_for_rcs(rcs_node_id, riak_topo, rcs_topo):
    n = 0
    for rnn in riak_topo.values():
        if rcs_topo[str(rcs_node_id)] in rnn:
            return n + 1
        n = n + 1

def get_one_rcs_node_id_for_riak_cluster(cluster, rcs_topo):
    for n in rcs_topo.keys():
        if rcs_topo[n] in cluster:
            return int(n)


def expand_to_all_rcs_nodes(creds, rcs_nodes):
    riak_topo, rcs_topo = get_topologies()
    creds2 = creds.copy()
    i = 1
    for rn in rcs_nodes:
        if rn["ip"] not in creds.keys():
            creds2.update(creds_of_rcs_node_with_same_cluster(
                creds2, rn["ip"], i, rcs_nodes, riak_topo, rcs_topo))
        i = i + 1
    return creds2

def creds_of_rcs_node_with_same_cluster(creds, rn_ip, i, rcs_nodes, riak_topo, rcs_topo):
    j = 1
    for nj in rcs_nodes:
        if cluster_of(i, riak_topo, rcs_topo) == cluster_of(j, riak_topo, rcs_topo):
            return {rn_ip: creds[nj["ip"]]}
        j = j + 1

def cluster_of(ni, riak_topo, rcs_topo):
    for c, cnn in riak_topo.items():
        if rcs_topo[str(ni)] in cnn:
            return c

def discover_nodes(tussle_name, pattern, required_nodes = 0):
    network = "%s_net0" % (tussle_name)
    args = ["docker", "network", "inspect", network]
    while True:
        p = subprocess.run(args,
                           capture_output = True,
                           encoding = "utf8")
        if p.returncode != 0:
            sys.exit("Failed to discover riak nodes in %s_net0: %s\n%s" % (tussle_name, p.stdout, p.stderr))
        res = [{"ip": e["IPv4Address"].split("/")[0],
                "container": e["Name"]}
               for e in json.loads(p.stdout)[0]["Containers"].values()
               if tussle_name + "_" + pattern + "." in e["Name"]]
        if required_nodes and len(res) != required_nodes:
            time.sleep(.5)
        else:
            return sorted(res, key = lambda x: x["container"])


def find_external_ips(container):
    p = subprocess.run(args = ["docker", "container", "inspect", container],
                       capture_output = True,
                       encoding = 'utf8')
    cid = json.loads(p.stdout)[0]["Id"]
    p = subprocess.run(args = ["docker", "network", "inspect", "docker_gwbridge"],
                       capture_output = True,
                       encoding = 'utf8')
    ip = json.loads(p.stdout)[0]["Containers"][cid]["IPv4Address"].split("/")[0]
    return ip


def create_user(host, name, email):
    url = 'http://%s:%d/riak-cs/user' % (host, 8080)
    print("creating user at", url)
    conn = httplib2.Http()
    retries = 20
    while retries > 0:
        try:
            resp, content = conn.request(url, "POST",
                                         headers = {"Content-Type": "application/json"},
                                         body = json.dumps({"email": email, "name": name}))
            conn.close()
            if re.search("The specified email address has already been registered", content.decode()):
                sys.exit("attempt to create_user twice?")
            return json.loads(content)
        except ConnectionRefusedError:
            time.sleep(1)
            retries = retries - 1


def get_admin_user(host):
    url = 'http://%s:%d/riak-cs/users' % (host, 8080)
    conn = httplib2.Http()
    retries = 10
    while retries > 0:
        try:
            resp, content = conn.request(url, "GET",
                                         headers = {"Accept": "application/json"})
            conn.close()
            entries = [s for s in content.splitlines() if str(s).find("admin") != -1]
            if len(entries) == 0:
                time.sleep(1)
                retries = retries - 1
            else:
                if len(entries) > 1:
                    print("Multiple admin user records found, let's choose the first")
                return json.loads(entries[0])[0]
        except ConnectionRefusedError:
            time.sleep(2)
            retries = retries - 1


def docker_exec_proc_(n, cmd):
    return subprocess.run(args = ["docker", "exec", "-it", n["container"]] + cmd,
                          capture_output = True,
                          encoding = "utf8")

def docker_exec_proc(n, cmd, error_message = None):
    p = docker_exec_proc_(n, cmd)
    if p.returncode != 0:
        if error_message is None:
            error_message = "Command %s failed returning %d on node %s (%s):\n%s\n%s\n" % \
                (" ".join(cmd), p.returncode, n["container"], n["ip"], p.stdout, p.stderr)
        sys.exit(error_message)
    return p
