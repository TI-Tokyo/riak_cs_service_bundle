.PHONY: ensure-dirs build up down clean

RIAK_VSN       	    ?= 3.0.7
RIAK_CS_VSN    	    ?= 3.0.0pre8
STANCHION_VSN  	    ?= 3.0.0pre8
RIAK_CS_CONTROL_VSN ?= 3.0.0pre3

RIAK_PLATFORM_DIR      ?= $(shell pwd)/p

N_RIAK_NODES     ?= 3
N_RCS_NODES      ?= 2
RCS_AUTH_V4      ?= on

DOCKER_SERVICE_NAME ?= rcs-tussle-one

build-R16:
	(cd R16 && test -r openssl-1.0.2u.tar.gz || wget https://www.openssl.org/source/old/1.0.2/openssl-1.0.2u.tar.gz)
	(cd R16 && test -r OTP_R16B02_basho10.tar.gz || wget https://github.com/basho/otp/archive/refs/tags/OTP_R16B02_basho10.tar.gz)
	(cd R16 && test -r autoconf-2.59.tar.bz2 || wget http://ftp.gnu.org/gnu/autoconf/autoconf-2.59.tar.bz2)
	(cd R16 && docker build --tag erlang:R16 .)

build:
	@COMPOSE_FILE=docker-compose-scalable-build.yml \
	docker-compose build \
	    --build-arg RIAK_VSN=$(RIAK_VSN) \
	    --build-arg RIAK_CS_VSN=$(RIAK_CS_VSN) \
	    --build-arg STANCHION_VSN=$(STANCHION_VSN) \
	    --build-arg RIAK_CS_CONTROL_VSN=$(RIAK_CS_CONTROL_VSN)

up: build ensure-dirs
	@docker swarm init >/dev/null || :
	@COMPOSE_FILE=docker-compose-scalable-run.yml \
	 N_RIAK_NODES=$(N_RIAK_NODES) \
	 N_RCS_NODES=$(N_RCS_NODES) \
	 RIAK_PLATFORM_DIR=$(RIAK_PLATFORM_DIR) \
	    docker stack deploy -c docker-compose-scalable-run.yml $(DOCKER_SERVICE_NAME) \
	 && ./stage-two.py \
		$(DOCKER_SERVICE_NAME) \
		$(N_RIAK_NODES) \
		$(N_RCS_NODES) \
		$(RCS_AUTH_V4)

down:
	@COMPOSE_FILE=docker-compose-scalable-run.yml \
	    docker stack rm $(DOCKER_SERVICE_NAME)

ensure-dirs:
	@mkdir -p $(RIAK_PLATFORM_DIR){/data,/log}

clean:
	@sudo rm -rf $(RIAK_PLATFORM_DIR)
