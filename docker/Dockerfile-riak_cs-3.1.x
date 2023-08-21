ARG RCS_VSN

FROM erlang:25 AS compile-image
ARG RCS_VSN

EXPOSE 8080 8000 8085

RUN apt-get -y install libssl-dev

ADD riak_cs-${RCS_VSN} /usr/src/S
WORKDIR /usr/src/S

RUN make rel

FROM debian:bullseye AS runtime-image

RUN apt-get update
RUN apt-get -y install libssl1.1

COPY --from=compile-image /usr/src/S/rel/riak-cs /opt/riak-cs
ENV RCS_PATH=/opt/riak-cs

# We can't start riak-cs it in CMD because at this moment as we don't
# yet know riak's addresses -- those are to be allocated by docker
# stack and need to be discovered after that.  All we can do is
# prepare the container, for a script run after docker stack deploy to
# do orchestration aid in the form of sed'ding the right values into
# riak-cs.conf.  It is unfortunate we have to plug a sleep loop for
# the process being monitored by docker, but that's one practical
# solution I have in mind now.

CMD while :; do sleep 1m; done
