FROM erlang:24 AS compile-image
ARG RIAK_VSN

EXPOSE 8087 8098 9080

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y libssl-dev libpam0g-dev cmake

ADD riak-${RIAK_VSN} /usr/src/S
WORKDIR /usr/src/S

RUN make rel

FROM debian:bullseye AS runtime-image
ARG RIAK_VSN
ARG RCS_BACKEND_1
ARG RCS_BACKEND_2

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get -y install libssl1.1

COPY --from=compile-image /usr/src/S/rel/riak /opt/riak
ENV RIAK_PATH=/opt/riak

RUN sed -i \
    -e "s|storage_backend = bitcask|storage_backend = multi|" \
    /opt/riak/etc/riak.conf
RUN echo "buckets.default.allow_mult = true\nbuckets.default.merge_strategy = 2\n" \
    >>/opt/riak/etc/riak.conf

RUN sed -i \
    -e "s|]\\.|, \
    {riak_kv, [ \
      {multi_backend, \
          [{be_default,riak_kv_${RCS_BACKEND_1}_backend, \
               [{max_open_files,20}]}, \
           {be_blocks,riak_kv_${RCS_BACKEND_2}_backend, \
               []}]}, \
      {multi_backend_default,be_default}, \
      {multi_backend_prefix_list,[{<<\"0b:\">>,be_blocks}]}, \
      {storage_backend,riak_kv_multi_backend} \
     ]} \
     ].|" \
     /opt/riak/etc/advanced.config

RUN echo "riak soft nofile 65536\nriak hard nofile 65536\n" >>/etc/security/limits.conf

#USER riak

# We can't start riak it in CMD because at this moment as we don't yet
# know other riak nodes' addresses -- those are to be allocated by
# docker stack and need to be discovered after that.  All we can do is
# prepare the container, for a script run after docker stack deploy to
# do orchestration aid in the form of sed'ding the right values into
# riak.conf.  It is unfortunate we have to plug a sleep loop for the
# process being monitored by docker, but that's one practical solution
# I have in mind now.

CMD while :; do sleep 1m; done
