import httplib2, subprocess, json, time


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
            time.sleep(1)
        else:
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
