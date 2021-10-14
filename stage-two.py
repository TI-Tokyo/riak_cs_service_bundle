#!/usr/bin/env python

import json, sys, os, time, subprocess, httplib2, multiprocessing


# riak
# =======================

def check_preexisting_riak_data(nodes):
    have_old_data = False
    ni = 1
    for n in nodes:
        if docker_exec_proc(n, ["stat", "/opt/riak/data/%d/cluster_meta" % ni]).returncode == 0:
            #old_ip = docker_exec_proc(n, ["sed", "-nEe", "s/nodename = riak@(.+)/\1/p", "/etc/riak/riak.conf"]).stdout
            #print("  reip", old_ip, "to", n["ip"])
            #if docker_exec_proc(n, ["riak", "admin", "reip", "riak@" + old_ip, "riak@" + n["ip"]]).
            print("  deleting cluster_meta and ring dirs on", n["ip"])
            docker_exec_proc(n, ["rm", "-rf", "/opt/riak/data/%d/cluster_meta" % ni, "/opt/riak/data/%d/ring" % ni])
            have_old_data = True
        ni = ni + 1
    if have_old_data:
        print("Found preexisting data on Riak nodes")
    return have_old_data


def configure_riak_nodes(nodes):
    print("Configuring Riak nodes")
    ni = 1
    for n in nodes:
        p = docker_exec_proc(n, ["mkdir", "-p", "/opt/riak/data/%d" % ni])
        if p.returncode != 0:
            sys.exit("Failed to create data dir on riak node at %s: %s%s" % (n["ip"], p.stdout, p.stderr))
        p = docker_exec_proc(n, ["mkdir", "-p", "/opt/riak/log/%d" % ni])
        if p.returncode != 0:
            sys.exit("Failed to create log dir on riak node at %s: %s%s" % (n["ip"], p.stdout, p.stderr))
        #p = docker_exec_proc(n, ["chown", "-R", "riak:riak", "/var/lib/riak/data", "/var/log/riak"])
        #if p.returncode != 0:
        #    sys.exit("Failed to chown data or log dir on riak node at %s: %s%s" % (n["ip"], p.stdout, p.stderr))
        nodename = "riak@" + n["ip"]
        p1 = docker_exec_proc(n, ["sed", "-i", "-E",
                                  "-e", "s|nodename = riak@127.0.0.1|nodename = %s|" % nodename,
                                  "-e", "s|listener.http.internal = .+|listener.http.internal = 0.0.0.0:8098|",
                                  "-e", "s|listener.protobuf.internal = .+|listener.protobuf.internal = 0.0.0.0:8087|",
                                  "-e", "s|platform_data_dir = .+|platform_data_dir = /opt/riak/data/%d|" % ni,
                                  "-e", "s|mdc.data_root = .+|mdc.data_root = /opt/riak/data/%d/riak_repl|" % ni,
                                  "-e", "s|platform_log_dir = .+|platform_log_dir = /opt/riak/log/%d|" % ni,
                                  "/opt/riak/etc/riak.conf"])
        p2 = docker_exec_proc(n, ["sed", "-i", "-E",
                                  "-e", "s|/opt/riak/log|/opt/riak/log/%d|" % ni,
                                  "/opt/riak/etc/advanced.config"])
        if p1.returncode != 0 or p2.returncode != 0:
            sys.exit("Failed to configure riak node at %s: %s%s" % (n["ip"], p.stdout, p.stderr))
        ni = ni + 1

def start_riak_nodes(nodes):
    print("Starting Riak nodes:", end = '')
    with multiprocessing.Pool(len(nodes)) as p:
        p.starmap(start_riak_node, [(nodes[i], i) for i in range(len(nodes))])
    subprocess.run(['stty', 'sane'])
    print()
    print("Waiting for riak cluster to become ready:", end = '')
    with multiprocessing.Pool(len(nodes)) as p:
        p.starmap(wait_for_services, [(nodes[i], i) for i in range(len(nodes))])
    subprocess.run(['stty', 'sane'])
    print()

def start_riak_node(node, i):
    time.sleep(0.5 * i)
    p = docker_exec_proc(node, ["/opt/riak/bin/riak", "start"])
    if p.returncode != 0:
        if p.stdout == "Node is already running!\n":
            print(" (%d)" % i, end = '', flush = True)
            return
        sys.exit("Failed to start riak node at %s: %s%s" % (node["ip"], p.stdout, p.stderr))
    print(" [%d]" % i, end = '', flush = True)

def wait_for_services(node, i):
    nodename = "riak@" + node["ip"]
    time.sleep(0.5 * i)
    repeat = 10
    while repeat > 0:
        p = docker_exec_proc(node, ["/opt/riak/bin/riak", "admin", "wait-for-service", "riak_kv"])
        if p.stdout == "riak_kv is up\n":
            break
        else:
            time.sleep(1)
            repeat = repeat-1
    repeat = 10
    while repeat > 0:
        p = docker_exec_proc(node, ["/opt/riak/bin/riak", "admin", "ringready"])
        if p.returncode == 0:
            break
        else:
            time.sleep(1)
            repeat = repeat-1
    print(" [%d]" % i, end = '', flush = True)

def which_riak_admin():
    vsn = os.getenv("RIAK_VSN")[0]
    if vsn == "2":
        return ["/opt/riak/bin/riak-admin"]
    if vsn == "3":
        return ["/opt/riak/bin/riak", "admin"]

def join_riak_nodes(nodes, riak_topo):
    riak_admin = which_riak_admin()
    first = nodes[0]
    rest = nodes[1:]
    print("Joining nodes %s to %s" % ([n["ip"] for n in rest], first["ip"]))
    for n in rest:
        p = docker_exec_proc(n, riak_admin + ["cluster", "join", "riak@" + first["ip"]])
        if p.returncode != 0:
            sys.exit("Failed to execute a join command on node %s (%s): %s%s" %
                     (n["container"], n["ip"], p.stdout, p.stderr))
        print(p.stdout)
    print("Below are the cluster changes to be committed:")
    for n in nodes:
        p = docker_exec_proc(n, riak_admin + ["cluster", "plan"])
        if p.returncode != 0:
            sys.exit("Failed to execute a join command on node %s (%s): %s%s" % (n["container"], n["ip"], p.stdout, p.stderr))
        print(p.stdout)
    print("Committing changes now")
    for n in rest:
        p = docker_exec_proc(n, riak_admin + ["cluster", "commit"])
        if p.returncode != 0:
            sys.exit("Failed to execute a join command on node %s (%s): %s%s" % (n["container"], n["ip"], p.stdout, p.stderr))
        print(p.stdout)


# riak_cs
# =======================

def preconfigure_rcs_nodes(rcs_nodes, riak_nodes, stanchion_node):
    n = 0
    m = 0
    print("Configuring Riak CS nodes")
    for rn in rcs_nodes:
        nodename = "riak_cs@" + rn["ip"]
        p = docker_exec_proc(rn, ["sed", "-i", "-E",
                                  "-e", "s|nodename = .+|nodename = %s|" % nodename,
                                  "-e", "s|listener = .+|listener = 0.0.0.0:8080|",
                                  "-e", "s|riak_host = .+|riak_host = %s:8087|" % riak_nodes[m]["ip"],
                                  "-e", "s|stanchion_host = .+|stanchion_host = %s:8085|" % stanchion_node["ip"],
                                  "-e", "s|anonymous_user_creation = .+|anonymous_user_creation = off|",
                                  "/opt/riak-cs/etc/riak-cs.conf"])
        if p.returncode != 0:
            sys.exit("Failed to modify riak-cs.conf node at %s: %s%s" % (rn["ip"], p.stdout, p.stderr))
        n = n + 1
        m = m + 1
        if m > len(riak_nodes):
            m = 0

def enable_anon_user_creation(node):
    print("Enabling anonymous user creation on node", node["ip"])
    p = docker_exec_proc(node, ["sed", "-i", "-E",
                                "-e", "s|anonymous_user_creation = .+|anonymous_user_creation = on|",
                                "/opt/riak-cs/etc/riak-cs.conf"])
    if p.returncode != 0:
        sys.exit("Failed to modify riak-cs.conf node at %s: %s%s" % (rn["ip"], p.stdout, p.stderr))

def enable_rcs_auth_bypass(node):
    print("Disabling admin auth on", node["ip"])
    docker_exec_proc(node, ["cp", "/opt/riak-cs/etc/advanced.config", "/opt/riak-cs/etc/advanced.config.backup"]).stdout
    docker_exec_proc(node, ["sed", "-zEie", "s/.+/[{riak_cs,[{admin_auth_enabled,false}]}]./", "/opt/riak-cs/etc/advanced.config"]).stdout

def restore_rcs_advanced_config(node):
    docker_exec_proc(node, ["mv", "/opt/riak-cs/etc/advanced.config.backup", "/opt/riak-cs/etc/advanced.config"])

def finalize_rcs_config(rcs_nodes, admin_key_id, auth_v4):
    print("Reonfiguring Riak CS nodes")
    if auth_v4:
        auth_v4_erl = "true"
    else:
        auth_v4_erl = "false"
    for rn in rcs_nodes:
        p = docker_exec_proc(rn, ["sed", "-i", "-E",
                                  "-e", "s|anonymous_user_creation = on|anonymous_user_creation = off|",
                                  "-e", "s|admin.key = .+|admin.key = %s|" % admin_key_id,
                                  "/opt/riak-cs/etc/riak-cs.conf"])
        if p.returncode != 0:
            sys.exit("Failed to modify riak-cs.conf node at %s: %s%s" % (rn["ip"], p.stdout, p.stderr))
        docker_exec_proc(rn, ["sed", "-zEie", "s/.+/[{riak_cs,[{auth_v4_enabled,%s}]}]./" % auth_v4_erl,
                              "/opt/riak-cs/etc/advanced.config"]).stdout


def start_rcs_nodes(nodes, do_restart = False):
    print("Starting Riak CS nodes:", end = '')
    with multiprocessing.Pool(len(nodes)) as p:
        p.starmap(start_rcs_node, [(nodes[i], i, do_restart) for i in range(len(nodes))])
    subprocess.run(['stty', 'sane'])
    print()

def start_rcs_node(node, i, do_restart):
    if do_restart:
        p = docker_exec_proc(node, ["/opt/riak-cs/bin/riak-cs", "stop"])
        print(" (%d)" % i, end = '', flush = True)
    p = docker_exec_proc(node, ["/opt/riak-cs/bin/riak-cs", "start"])
    if p.returncode != 0:
        sys.exit("Failed to start Riak CS at %s: %s%s" % (node["ip"], p.stdout, p.stderr))
    print(" [%d]" % i, end = '', flush = True)



# stanchion
# =======================

def preconfigure_stanchion_node(stanchion_node, riak_nodes):
    nodename = "stanchion@" + stanchion_node["ip"]
    print("Configuring Stanchion node")
    p = docker_exec_proc(stanchion_node, ["sed", "-i", "-E",
                                          "-e", "s|nodename = riak@127.0.0.1|nodename = %s|" % nodename,
                                          "-e", "s|listener = 127.0.0.1:8085|listener = 0.0.0.0:8085|",
                                          "-e", "s|riak_host = .+|riak_host = %s:8087|" % riak_nodes[0]["ip"],
                                          "/opt/stanchion/etc/stanchion.conf"])
    if p.returncode != 0:
        sys.exit("Failed to modify stanchion.conf node at %s: %s%s" % (stanchion_node["ip"], p.stdout, p.stderr))

def finalize_stanchion_config(stanchion_node, admin_key_id):
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



# riak_cs_control
# =======================

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



# helper functions
# ========================

def discover_nodes(tussle_name, pattern, required_nodes):
    print("Discovering", pattern, "nodes..")
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
        except:
            time.sleep(1)
            retries = retries - 1

def get_admin_user(host):
    url = 'http://%s:%d/riak-cs/users' % (host, 8080)
    print("Getting existing admin from", host)
    conn = httplib2.Http()
    retries = 10
    while retries > 0:
        try:
            resp, content = conn.request(url, "GET",
                                         headers = {"Accept": "application/json"})
            conn.close()
            entries = [s for s in content.splitlines() if str(s).find("admin") != -1]
            if len(entries) == 0:
                time.sleep(2)
                retries = retries - 1
            else:
                if len(entries) > 1:
                    print("Multiple admin user records found, let's choose the first")
                return json.loads(entries[0])[0]
        except ConnectionRefusedError:
            time.sleep(2)
            retries = retries - 1


def load_test(s3_benchmark_path, s3_benchmark_params, do_parallel, rcs_hosts, aws_key_id, aws_key_secret):
    if s3_benchmark_path == "skip":
        print("Skipping load-test (set S3_BENCHMARK_PATH to a path to s3-benchmark executable to enable it)")
        return
    if do_parallel:
        with multiprocessing.Pool(len(rcs_hosts)) as p:
            p.starmap(load_test_on_node,
                      [(h, s3_benchmark_path, s3_benchmark_params, aws_key_id, aws_key_secret)
                       for h in rcs_hosts])
    else:
        load_test_on_node(rcs_hosts[0], s3_benchmark_path, s3_benchmark_params, aws_key_id, aws_key_secret)


def load_test_on_node(rcs_host, s3_benchmark_path, s3_benchmark_params, aws_key_id, aws_key_secret):
    print("Running load test (%s %s) with Riak CS at %s:" % (s3_benchmark_path, s3_benchmark_params, rcs_host))
    p = subprocess.run(env = {"http_proxy": "http://" + rcs_host + ":8080"},
                       args = [s3_benchmark_path, "-a", aws_key_id, "-s", aws_key_secret] + s3_benchmark_params.split(" "),
                       capture_output = True,
                       encoding = 'utf8')
    print("load test completed with code %d:\n%s\n%s" % (p.returncode, p.stderr, p.stdout))
    with open("load-test-report", mode="a") as f:
        print("""
-------------------------------------
RIAK_VSN=%s RIAK_CS_VSN=%s node=%s
%s
""" % (os.getenv("RIAK_VSN"), os.getenv("RIAK_CS_VSN"), rcs_host, p.stdout),
              file=f)


def main():
    tussle_name = sys.argv[1]
    required_riak_nodes = int(sys.argv[2])
    required_rcs_nodes = int(sys.argv[3])
    auth_v4 = sys.argv[4]
    s3_benchmark_path = sys.argv[5]
    s3_benchmark_params = sys.argv[6]
    do_parallel_load_test = int(sys.argv[7])

    riak_nodes      = discover_nodes(tussle_name, "riak", required_riak_nodes)
    rcs_nodes       = discover_nodes(tussle_name, "riak_cs", required_rcs_nodes)
    stanchion_nodes = discover_nodes(tussle_name, "stanchion", 1)
    rcsc_nodes      = discover_nodes(tussle_name, "riak_cs_control", 1)

    riak_ext_ips = [find_external_ips(c["container"]) for c in riak_nodes]
    rcs_ext_ips = [find_external_ips(c["container"]) for c in rcs_nodes]
    rcsc_ext_ip = find_external_ips(rcsc_nodes[0]["container"])

    have_old_data = check_preexisting_riak_data(riak_nodes)

    configure_riak_nodes(riak_nodes)
    start_riak_nodes(riak_nodes)
    if len(riak_nodes) > 1:
        join_riak_nodes(riak_nodes, riak_topo = {"cluster1": "all"})


    preconfigure_rcs_nodes(rcs_nodes, riak_nodes, stanchion_nodes[0])
    preconfigure_stanchion_node(stanchion_nodes[0], riak_nodes)
    start_stanchion_node(stanchion_nodes[0])

    if not have_old_data:
        enable_anon_user_creation(rcs_nodes[0])
        start_rcs_nodes([rcs_nodes[0]])
        admin_email = "admin@tussle.org"
        admin_name = "admin"
        admin_user = create_user(rcs_ext_ips[0], admin_name, admin_email)
        print("\nAdmin user (%s <%s>) creds:\n  key_id: %s\n  key_secret: %s\n"
              % (admin_name, admin_email,
                 admin_user["key_id"], admin_user["key_secret"]))
    else:
        enable_rcs_auth_bypass(rcs_nodes[0])
        start_rcs_nodes([rcs_nodes[0]], do_restart = True)
        admin_user = get_admin_user(rcs_ext_ips[0])
        restore_rcs_advanced_config(rcs_nodes[0])
        print("\nPreviously created admin user (%s <%s>) creds:\n  key_id: %s\n  key_secret: %s\n"
              % (admin_user["name"], admin_user["email"],
                 admin_user["key_id"], admin_user["key_secret"]))

    finalize_stanchion_config(stanchion_nodes[0], admin_user["key_id"])
    start_stanchion_node(stanchion_nodes[0], do_restart = True)
    finalize_rcs_config(rcs_nodes, admin_user["key_id"], auth_v4)
    start_rcs_nodes(rcs_nodes, do_restart = True)

    start_rcs_control(rcsc_nodes[0], rcs_nodes[0]["ip"], admin_user)

    print("\nRiak external addresses:")
    for ip in riak_ext_ips:
        print("  %s" % ip)
    print("\nRiak CS external addresses:")
    for ip in rcs_ext_ips:
        print("  %s" % ip)
    print("\nRiak CS Control external address:\n  %s" % rcsc_ext_ip)

    load_test(s3_benchmark_path, s3_benchmark_params,
              do_parallel_load_test, rcs_ext_ips,
              admin_user["key_id"], admin_user["key_secret"])

if __name__ == "__main__":
    main()
