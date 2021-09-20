# Riak CS bundle in a docker container

This project provides a reference setup of a minimal suite of Riak CS,
Riak, Stanchion and Riak CS Control, built and run as a docker stack.

## Building and running

With `make up`, you will get riak\_cs, stanchion, riak\_cs\_control
and riak images created and their containers started, all properly
configured.  Applications versions can be defined in environment
variables `RIAK_VSN`, `RIAK_CS_VSN`, `RIAK_CS_CONTROL_VSN` and
`STANCHION_VSN` (with "3.0.7", "3.0.0pre8", "3.0.0pre3", "3.0.0pre8",
respectively, as defaults).

Currently, images for riak\_cs, riak\_cs\_control and stanchion are
built from source, pulled from repos at github.com/TI-Tokyo, while
riak is installed from a deb package.

The number of nodes in riak cluster is defined by env var
`N_RIAK_NODES` (3 by default); likewise, `N_RCS_NODES` (2 by default)
defines the number of RIak CS nodes (with each _n_'th connected to
_n_'th Riak node, wrapping if the number of the latter is greater).

External addresses of Riak CS nodes and the node running Riak CS
Control will be printed at the end of `make up`.  Also, an admin user
will be created, whose credentials can be copied from the successful
run of `make up`.

The entire stack can be stopped with `make down`.

## Persisting state

Within containers, riak data dirs are bind-mounted to local filesystem
at `${RIAK_PLATFORM_DIR}/riak/data/${N}`, where `N` is the riak node
number (1-based).  Unless explicitly set, directories will be created
in "./p".  Similarly, riak logs can be found at
`${RIAK_PLATFORM_DIR}/riak/logs/${N}`.
