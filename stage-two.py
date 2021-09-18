#!/usr/bin/env python

import json, sys, time, subprocess, httplib2


def discover_nodes(tussle_name, pattern, required_nodes):
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
        if len(res) != required_nodes:
            time.sleep(1)
        else:
            print("Discovered these", pattern, "nodes:", [n["ip"] for n in res])
            return res



def start_riak_nodes(nodes):
    for n in nodes:
        print("Starting Riak at node", n["ip"])
        p = docker_exec_proc(n, ["riak", "start"])
        if p.returncode != 0:
            sys.exit("Failed to start riak node at %s: %s%s" % (n["ip"], p.stdout, p.stderr))
    for n in nodes:
        nodename = "riak@" + n["ip"]
        print("Waiting for service riak_kv on node", n["ip"])
        repeat = 10
        while repeat > 0:
            p = docker_exec_proc(n, ["riak", "admin", "wait-for-service", "riak_kv"])
            if p.stdout == "riak_kv is up\n":
                break
            else:
                time.sleep(1)
                repeat = repeat-1
        repeat = 10
        while repeat > 0:
            p = docker_exec_proc(n, ["riak", "admin", "ringready"])
            if p.returncode == 0:
                break
            else:
                time.sleep(1)
                repeat = repeat-1

def configure_riak_nodes(nodes):
    print("Configuring Riak nodes")
    for n in nodes:
        nodename = "riak@" + n["ip"]
        p = docker_exec_proc(n, ["sed", "-i", "-E",
                                 "-e", "s|nodename = riak@127.0.0.1|nodename = %s|" % nodename,
                                 "-e", "s|listener.http.internal = .+|listener.http.internal = 0.0.0.0:8098|",
                                 "-e", "s|listener.protobuf.internal = .+|listener.protobuf.internal = 0.0.0.0:8087|",
                                 "/etc/riak/riak.conf"])
        if p.returncode != 0:
            sys.exit("Failed to set nodename on riak node at %s: %s%s" % (n["ip"], p.stdout, p.stderr))


def join_riak_nodes(nodes):
    first = nodes[0]
    rest = nodes[1:]
    print("Joining nodes %s to %s" % ([n["ip"] for n in rest], first["ip"]))
    for n in rest:
        p = docker_exec_proc(n, ["riak", "admin", "cluster", "join", "riak@" + first["ip"]])
        if p.returncode != 0:
            sys.exit("Failed to execute a join command on node %s (%s): %s%s" %
                     (n["container"], n["ip"], p.stdout, p.stderr))
        print(p.stdout)
    print("Below are the cluster changes to be committed:")
    for n in nodes:
        p = docker_exec_proc(n, ["riak", "admin", "cluster", "plan", ">/dev/null"])
        if p.returncode != 0:
            sys.exit("Failed to execute a join command on node %s (%s): %s%s" % (n["container"], n["ip"], p.stdout, p.stderr))
        print(p.stdout)
    print("Committing changes now")
    for n in rest:
        p = docker_exec_proc(n, ["riak", "admin", "cluster", "commit", ">/dev/null"])
        if p.returncode != 0:
            sys.exit("Failed to execute a join command on node %s (%s): %s%s" % (n["container"], n["ip"], p.stdout, p.stderr))
        print(p.stdout)


def configure_rcs_nodes_1(rcs_nodes, riak_nodes, stanchion_node, auth_v4):
    n = 0
    m = 0
    print("Configuring Riak CS nodes")
    for rn in rcs_nodes:
        nodename = "riak_cs@" + rn["ip"]
        p = docker_exec_proc(rn, ["sed", "-i", "-E",
                                  "-e", "s|nodename = .+|nodename = %s|" % nodename,
                                  "-e", "s|listener = .+|listener = 0.0.0.0:8080|",
                                  "-e", "s|riak_host = .+|riak_host = %s:8087|" % riak_nodes[m]["ip"],
                                  "-e", "s|auth_v4 = .+|auth_v4 = %s|" % auth_v4,
                                  "-e", "s|anonymous_user_creation = .+|anonymous_user_creation = on|",
                                  "-e", "s|stanchion_host = .+|stanchion_host = %s:8085|" % stanchion_node["ip"],
                                  "/opt/riak-cs/etc/riak-cs.conf"])
        if p.returncode != 0:
            sys.exit("Failed to modify riak-cs.conf node at %s: %s%s" % (rn["ip"], p.stdout, p.stderr))
        n = n + 1
        m = m + 1
        if m > len(riak_nodes):
            m = 0

def configure_rcs_nodes_2(rcs_nodes, admin_key_id):
    print("Reonfiguring Riak CS nodes")
    for rn in rcs_nodes:
        p = docker_exec_proc(rn, ["sed", "-i", "-E",
                                  "-e", "s|anonymous_user_creation = on|anonymous_user_creation = off|",
                                  "-e", "s|admin.key = .+|admin.key = %s|" % admin_key_id,
                                  "/opt/riak-cs/etc/riak-cs.conf"])
        if p.returncode != 0:
            sys.exit("Failed to modify riak-cs.conf node at %s: %s%s" % (rn["ip"], p.stdout, p.stderr))

def configure_stanchion_node_1(stanchion_node, riak_nodes):
    nodename = "stanchion@" + stanchion_node["ip"]
    print("Configuring Stanchion node")
    p = docker_exec_proc(stanchion_node, ["sed", "-i", "-E",
                                          "-e", "s|nodename = riak@127.0.0.1|nodename = %s|" % nodename,
                                          "-e", "s|listener = 127.0.0.1:8085|listener = 0.0.0.0:8085|",
                                          "-e", "s|riak_host = .+|riak_host = %s:8087|" % riak_nodes[0]["ip"],
                                          "/opt/stanchion/etc/stanchion.conf"])
    if p.returncode != 0:
        sys.exit("Failed to modify stanchion.conf node at %s: %s%s" % (stanchion_node["ip"], p.stdout, p.stderr))

def configure_stanchion_node_2(stanchion_node, admin_key_id):
    print("Reconfiguring Stanchion node")
    p = docker_exec_proc(stanchion_node, ["sed", "-i", "-E",
                                          "-e", "s|admin.key = .+|admin.key = %s|" % admin_key_id,
                                          "/opt/stanchion/etc/stanchion.conf"])
    if p.returncode != 0:
        sys.exit("Failed to modify stanchion.conf node at %s: %s%s" % (stanchion_node["ip"], p.stdout, p.stderr))



def start_stanchion_node(node, do_restart = False):
    if do_restart:
        print("Stopping Stanchion at node", node["ip"])
        p = docker_exec_proc(node, ["/opt/stanchion/bin/stanchion", "stop"])
    print("Starting Stanchion at node", node["ip"])
    p = docker_exec_proc(node, ["/opt/stanchion/bin/stanchion", "start"])
    if p.returncode != 0:
        sys.exit("Failed to start Stanchion at %s: %s%s" % (node["ip"], p.stdout, p.stderr))

def start_rcs_nodes(nodes, do_restart = False):
    for n in nodes:
        if do_restart:
            print("Stopping Riak CS at node", n["ip"])
            p = docker_exec_proc(n, ["/opt/riak-cs/bin/riak-cs", "stop"])
        print("Starting Riak CS at node", n["ip"])
        p = docker_exec_proc(n, ["/opt/riak-cs/bin/riak-cs", "start"])
        if p.returncode != 0:
            sys.exit("Failed to start Riak CS at %s: %s%s" % (n["ip"], p.stdout, p.stderr))

def start_rcs_control(node, rcs_ip, user):
    p = subprocess.run(args = ["docker", "exec", "-it",
                               "--env", "CS_HOST=" + rcs_ip,
                               "--env", "CS_ADMIN_KEY=" + user["key_id"],
                               "--env", "CS_ADMIN_SECRET=" + user["key_secret"],
                               node["container"],
                               "/opt/riak_cs_control/bin/riak_cs_control", "daemon"],
                       capture_output = True,
                       encoding = "utf8")
    print(p.stdout, p.stderr)




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


def docker_exec_proc(n, cmd):
    return subprocess.run(args = ["docker", "exec", "-it", n["container"]] + cmd,
                          capture_output = True,
                          encoding = "utf8")

def create_user(host, name, email):
    url = 'http://%s:%d/riak-cs/user' % (host, 8080)
    conn = httplib2.Http()
    retries = 10
    while retries > 0:
        try:
            resp, content = conn.request(url, "POST",
                                         headers = {"Content-Type": "application/json"},
                                         body = json.dumps({"email": email, "name": name}))
            conn.close()
            return json.loads(content)
        except ConnectionRefusedError:
            time.sleep(2)
            retries = retries - 1


def main():
    tussle_name = sys.argv[1]
    required_riak_nodes = int(sys.argv[2])
    required_rcs_nodes = int(sys.argv[3])
    auth_v4 = sys.argv[4]

    rcs_nodes       = discover_nodes(tussle_name, "riak_cs", required_rcs_nodes)
    stanchion_nodes = discover_nodes(tussle_name, "stanchion", 1)
    rcsc_nodes      = discover_nodes(tussle_name, "riak_cs_control", 1)
    rcs_ext_ips = [find_external_ips(c["container"]) for c in rcs_nodes]
    rcsc_ext_ip = find_external_ips(rcsc_nodes[0]["container"])

    riak_nodes = discover_nodes(tussle_name, "riak", required_riak_nodes)
    configure_riak_nodes(riak_nodes)
    start_riak_nodes(riak_nodes)
    if len(riak_nodes) > 1:
        join_riak_nodes(riak_nodes)


    configure_rcs_nodes_1(rcs_nodes, riak_nodes, stanchion_nodes[0], auth_v4)
    configure_stanchion_node_1(stanchion_nodes[0], riak_nodes)
    start_stanchion_node(stanchion_nodes[0])
    start_rcs_nodes(rcs_nodes)

    admin_email = "admin@tussle.org"
    admin_name = "admin"
    user = create_user(rcs_ext_ips[0], admin_name, admin_email)
    print("Admin user (%s <%s>) creds:\n  key_id: %s\n  key_secret: %s\n"
          % (admin_name, admin_email,
             user["key_id"], user["key_secret"]))

    configure_stanchion_node_2(stanchion_nodes[0], user["key_id"])
    start_stanchion_node(stanchion_nodes[0], do_restart = True)

    configure_rcs_nodes_2(rcs_nodes, user["key_id"])
    start_rcs_nodes(rcs_nodes, do_restart = True)

    start_rcs_control(rcsc_nodes[0], rcs_nodes[0]["ip"], user)

    print("Riak CS external addresses are:")
    for ip in rcs_ext_ips:
        print("  %s" % ip)
    print("Riak CS Control external address is:\n  %s" % rcsc_ext_ip)

if __name__ == "__main__":
    main()
