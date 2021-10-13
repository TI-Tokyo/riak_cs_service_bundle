# Riak CS bundle in a docker container

This project provides a reference setup of a minimal suite of Riak CS,
Riak, Stanchion and Riak CS Control, built and run as a docker stack.

## Building and running

With `make start`, you will get riak\_cs, stanchion, riak\_cs\_control
and riak images created and their containers started, all properly
configured.  Applications versions can be defined in environment
variables `RIAK_VSN`, `RCS_VSN`, `RCSC_VSN` and `STANCHION_VSN` (with
"3.0.8", "3.0.0pre8", "3.0.0pre3", "3.0.0pre8", respectively, as
defaults).  Images for riak\_cs, riak\_cs\_control and stanchion are
built from source, pulled from repos at github.com/basho (riak)
github.com/TI-Tokyo (rest).

The number of nodes in riak cluster is defined by env var
`N_RIAK_NODES` (3 by default); likewise, `N_RCS_NODES` (2 by default)
defines the number of RIak CS nodes (with each _n_'th connected to
_n_'th Riak node, wrapping if the number of the latter is greater).

External addresses of Riak CS nodes and the node running Riak CS
Control will be printed at the end of `make start`.  Also, an admin user
will be created whose credentials can be copied and used in your s3 client.

The entire stack can be stopped with `make stop`.  Note that after
stopping, docker will not complete the tear-down of resources
immediately, sometimes causing a subsequent start to fail (the remedy
is usually to give it some time, until `docker service ls` no longer
lists services named rcs-tussle-one_*).

### Older versions of riak and riak_cs

Dockerfiles for versions 2.x of riak, riak\_cs and stanchion use
'erlang:R16' for the base image (which has, specifically, tag
OTP\_R16B02\_basho10 from github.com/basho/otp).  It will need to be
built, once, with `make R16`.

## Persisting state

Within containers, riak data dirs are bind-mounted to local filesystem
at `${RIAK_PLATFORM_DIR}/riak/data/${N}`, where `N` is the riak node
number (1-based).  Unless explicitly set, directories will be created
in "./p".  Similarly, riak logs can be found at
`${RIAK_PLATFORM_DIR}/riak/logs/${N}`.  To delete it, do `make clean`
(or `rm -rf p` manually).

## Load-testing

The bundle can run load tests, using
[s3-benchmark](https://github.com/TI-Tokyo/s3-benchmark). If you set an
environment variable `S3_BENCHMARK_PATH` (e.g., to
"../s3-benchmark/s3-benchmark", assuming it was cloned into a sister dir to
riak\_cs\_service\_bundle), `make start` will proceed to execute
s3-benchmark, with parameters "-t 5 -l 10 -d 30" (unless overridden in
env var `S3_BENCHMARK_PARAMS`), meaning 10 loops 30 sec each, in 3
threads.  If you set `DO_PARALLEL_LOAD_TEST` to 1 (which is the
default), a total of `N_RCS_NODES` instances of s3-benchmark will be
started in parallel, one per each riak\_cs node.

There is a script, "all-combos", that will build riak tags 2.2.6,
2.9.8 and 3.0.8, riak\_cs tags 2.1.3pre1 and 3.0.0pre8, and run the
load test in all riak+riak\_cs combinations, with results logged in
load-test-report.
