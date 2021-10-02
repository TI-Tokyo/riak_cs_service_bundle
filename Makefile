.PHONY: ensure-dirs build up down clean

RIAK_VSN       	    ?= 3.0.7
RIAK_CS_VSN    	    ?= 3.0.0pre8
STANCHION_VSN  	    ?= 3.0.0pre8
RIAK_CS_CONTROL_VSN ?= 3.0.0pre3

# select Dockerfiles. For apps that we build ourself, we use either
# the standard erlang:22.x base image (for 3.x tags), or the image
# with R16 that we have built specially (for 2.x tags)

ifneq ($(RIAK_VSN:2.%=xx%), $(RIAK_VSN))
RIAK_DOCKERFILE := Dockerfile-2.x
else
RIAK_DOCKERFILE := Dockerfile-3.x
endif

ifneq ($(RIAK_CS_VSN:2.%=xx%), $(RIAK_CS_VSN))
RIAK_CS_DOCKERFILE := Dockerfile-2.x
else
RIAK_CS_DOCKERFILE := Dockerfile-3.x
endif

ifneq ($(STANCHION_VSN:2.%=xx%), $(STANCHION_VSN))
STANCHION_DOCKERFILE := Dockerfile-2.x
else
STANCHION_DOCKERFILE := Dockerfile-3.x
endif

# old  riak-cs-control won't build with R16
# (and it doesn't really matter anyway)
RIAK_CS_CONTROL_DOCKERFILE := Dockerfile-3.x


RIAK_PLATFORM_DIR ?= $(shell pwd)/p

N_RIAK_NODES     ?= 3
N_RCS_NODES      ?= 2
RCS_AUTH_V4      ?= on

S3_BENCHMARK_PATH   ?= skip
S3_BENCHMARK_PARAMS ?= "-t 5 -l 3 -d 30"
DO_PARALLEL_LOAD_TEST ?= 1

DOCKER_SERVICE_NAME ?= rcs-tussle-one

build-R16:
	(cd R16 && test -r openssl-1.0.2u.tar.gz || wget https://www.openssl.org/source/old/1.0.2/openssl-1.0.2u.tar.gz)
	(cd R16 && test -r OTP_R16B02_basho10.tar.gz || wget https://github.com/basho/otp/archive/refs/tags/OTP_R16B02_basho10.tar.gz)
	(cd R16 && test -r autoconf-2.59.tar.bz2 || wget http://ftp.gnu.org/gnu/autoconf/autoconf-2.59.tar.bz2)
	(cd R16 && docker build --tag erlang:R16 .)

build:
	@COMPOSE_FILE=docker-compose-scalable-build.yml \
	 RIAK_VSN=$(RIAK_VSN) \
	 RIAK_CS_VSN=$(RIAK_CS_VSN) \
	 STANCHION_VSN=$(STANCHION_VSN) \
	 RIAK_CS_CONTROL_VSN=$(RIAK_CS_CONTROL_VSN) \
	 RIAK_DOCKERFILE=$(RIAK_DOCKERFILE) \
	 RIAK_CS_DOCKERFILE=$(RIAK_CS_DOCKERFILE) \
	 STANCHION_DOCKERFILE=$(STANCHION_DOCKERFILE) \
	 RIAK_CS_CONTROL_DOCKERFILE=$(RIAK_CS_CONTROL_DOCKERFILE) \
	 docker-compose build \
	    --build-arg RIAK_VSN=$(RIAK_VSN) \
	    --build-arg RIAK_CS_VSN=$(RIAK_CS_VSN) \
	    --build-arg STANCHION_VSN=$(STANCHION_VSN) \
	    --build-arg RIAK_CS_CONTROL_VSN=$(RIAK_CS_CONTROL_VSN)

start: build ensure-dirs
	@docker swarm init >/dev/null 2>&1 || :
	@echo
	@echo =======================================================================
	@echo Starting bundle with RIAK_VSN=$(RIAK_VSN) and RIAK_CS_VSN=$(RIAK_CS_VSN)
	@export \
	 RIAK_VSN=$(RIAK_VSN) \
	 RIAK_CS_VSN=$(RIAK_CS_VSN) \
	 STANCHION_VSN=$(STANCHION_VSN) \
	 RIAK_CS_CONTROL_VSN=$(RIAK_CS_CONTROL_VSN) \
	 N_RIAK_NODES=$(N_RIAK_NODES) \
	 N_RCS_NODES=$(N_RCS_NODES) \
	 RIAK_PLATFORM_DIR=$(RIAK_PLATFORM_DIR) \
	 && docker stack deploy -c docker-compose-scalable-run.yml $(DOCKER_SERVICE_NAME) \
	 && ./stage-two.py \
		$(DOCKER_SERVICE_NAME) \
		$(N_RIAK_NODES) $(N_RCS_NODES)\
		$(RCS_AUTH_V4) \
	        $(S3_BENCHMARK_PATH) $(S3_BENCHMARK_PARAMS) \
	        $(DO_PARALLEL_LOAD_TEST)

stop:
	@COMPOSE_FILE=docker-compose-scalable-run.yml \
	    docker stack rm $(DOCKER_SERVICE_NAME)

ensure-dirs:
	@mkdir -p $(RIAK_PLATFORM_DIR){/data,/log}

clean:
	@sudo rm -rf $(RIAK_PLATFORM_DIR)
