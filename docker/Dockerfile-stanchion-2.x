FROM erlang:R16 AS compile-image
ARG STANCHION_VSN

EXPOSE 8085

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && install -y git wget g++ libpam0g-dev

ADD stanchion-${STANCHION_VSN} /usr/src/S
WORKDIR /usr/src/S

RUN git config --global url."https://".insteadOf git://
RUN make rel

RUN mv /usr/src/S/rel/stanchion /opt/stanchion

# We can't start riak-cs it in CMD because at this moment as we don't
# yet know riak's addresses -- those are to be allocated by docker
# stack and need to be discovered after that.  All we can do is
# prepare the container, for a script run after docker stack deploy to
# do orchestration aid in the form of sed'ding the right values into
# riak-cs.conf.  It is unfortunate we have to plug a sleep loop for
# the process being monitored by docker, but that's one practical
# solution I have in mind now.

CMD while :; do sleep 1m; done
