ARG RCSC_VSN=3.0.0 \
    CS_HOST \
    CS_PORT=8080 \
    CS_PROTO="http" \
    CS_CONTROL_PORT=8090 \
    CS_ADMIN_KEY="admin-key" \
    CS_ADMIN_SECRET="admin-secret"

FROM erlang:25 AS compile-image
ARG RCSC_VSN

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y libssl-dev

EXPOSE 8090

ADD riak_cs_control-${RCSC_VSN} /usr/src/S
WORKDIR /usr/src/S

RUN make rel

FROM debian:bullseye AS runtime-image
ARG CS_HOST \
    CS_PORT \
    CS_PROTO \
    CS_CONTROL_PORT \
    CS_ADMIN_KEY \
    CS_ADMIN_SECRET

ENV CS_HOST=${CS_HOST} \
    CS_PORT=${CS_PORT:-8080} \
    CS_PROTO=${CS_PROTO:-http} \
    CS_CONTROL_PORT=${CS_CONTROL_PORT:-8090} \
    CS_ADMIN_KEY=${CS_ADMIN_KEY:-"admin-key"} \
    CS_ADMIN_SECRET=${CS_ADMIN_SECRET:-"admin-secret"} \
    LOG_DIR=/opt/riak_cs_control/log \
    LOGGER_LEVEL=info

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get -y install libssl1.1

COPY --from=compile-image /usr/src/S/_build/rel/rel/riak_cs_control /opt/riak_cs_control

# We can't start riak-cs it in CMD because at this moment as we don't
# yet know riak's addresses -- those are to be allocated by docker
# stack and need to be discovered after that.  All we can do is
# prepare the container, for a script run after docker stack deploy to
# do orchestration aid in the form of sed'ding the right values into
# riak-cs.conf.  It is unfortunate we have to plug a sleep loop for
# the process being monitored by docker, but that's one practical
# solution I have in mind now.

CMD while :; do sleep 1m; done
