ARG RCS_VSN=3.0.0

FROM erlang:22 AS compile-image
ARG RCS_VSN

ADD riak_cs/riak_cs-${RCS_VSN} /usr/src/S
WORKDIR /usr/src/S

EXPOSE 8080 8000

RUN ./rebar3 as rel release

FROM debian:buster AS runtime-image

RUN apt-get update && apt-get -y install libssl1.1

COPY --from=compile-image /usr/src/S/_build/rel/rel/riak-cs /opt/riak-cs

# We can't start riak-cs it in CMD because at this moment as we don't
# yet know riak's addresses -- those are to be allocated by docker
# stack and need to be discovered after that.  All we can do is
# prepare the container, for a script run after docker stack deploy to
# do orchestration aid in the form of sed'ding the right values into
# riak-cs.conf.  It is unfortunate we have to plug a sleep loop for
# the process being monitored by docker, but that's one practical
# solution I have in mind now.

CMD while :; do sleep 1m; done
