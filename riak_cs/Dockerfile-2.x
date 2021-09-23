ARG RIAK_CS_VSN=2.1.2

FROM erlang:R16 AS compile-image
ARG RIAK_CS_VSN

RUN apt-get install -y git wget

WORKDIR /usr/src
RUN git clone -b ${RIAK_CS_VSN} --depth 2 https://github.com/TI-Tokyo/riak_cs
WORKDIR riak_cs

RUN make rel

RUN mv /usr/src/riak_cs/rel/riak-cs /opt/riak-cs

# We can't start riak-cs it in CMD because at this moment as we don't
# yet know riak's addresses -- those are to be allocated by docker
# stack and need to be discovered after that.  All we can do is
# prepare the container, for a script run after docker stack deploy to
# do orchestration aid in the form of sed'ding the right values into
# riak-cs.conf.  It is unfortunate we have to plug a sleep loop for
# the process being monitored by docker, but that's one practical
# solution I have in mind now.

EXPOSE 8080 8000

CMD while :; do sleep 1m; done
