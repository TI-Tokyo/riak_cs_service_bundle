ARG RIAK_CS_CONTROL_VSN=1.0.2

FROM erlang:R16 AS compile-image
ARG RIAK_CS_CONTROL_VSN

RUN apt-get install -y git

WORKDIR /usr/src
RUN git clone -b ${RIAK_CS_CONTROL_VSN} --depth 2 https://github.com/TI-Tokyo/riak_cs_control
WORKDIR riak_cs_control

RUN make rel

RUN mv /usr/src/riak_cs_control/rel/riak_cs_control /opt/riak_cs_control

# We can't start riak-cs it in CMD because at this moment as we don't
# yet know riak's addresses -- those are to be allocated by docker
# stack and need to be discovered after that.  All we can do is
# prepare the container, for a script run after docker stack deploy to
# do orchestration aid in the form of sed'ding the right values into
# riak-cs.conf.  It is unfortunate we have to plug a sleep loop for
# the process being monitored by docker, but that's one practical
# solution I have in mind now.

EXPOSE 8090

CMD while :; do sleep 1m; done
