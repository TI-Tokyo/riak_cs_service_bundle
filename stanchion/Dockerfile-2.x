ARG STANCHION_VSN=2.1.2

FROM erlang:R16 AS compile-image
ARG STANCHION_VSN

RUN apt-get install -y git

WORKDIR /usr/src
RUN git clone -b ${STANCHION_VSN} --depth 2 https://github.com/TI-Tokyo/stanchion
WORKDIR stanchion

RUN make rel

RUN mv /usr/src/stanchion/rel/stanchion /opt/stanchion

# We can't start riak-cs it in CMD because at this moment as we don't
# yet know riak's addresses -- those are to be allocated by docker
# stack and need to be discovered after that.  All we can do is
# prepare the container, for a script run after docker stack deploy to
# do orchestration aid in the form of sed'ding the right values into
# riak-cs.conf.  It is unfortunate we have to plug a sleep loop for
# the process being monitored by docker, but that's one practical
# solution I have in mind now.

EXPOSE 8085

CMD while :; do sleep 1m; done
