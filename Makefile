.PHONY: ensure-dirs sources R16 build start start-quick stop clean

RIAK_VSN       	    ?= 3.0.8
RCS_VSN    	    ?= 3.0.0pre8
STANCHION_VSN  	    ?= 3.0.0pre8
RCSC_VSN            ?= 3.0.0pre3

# select Dockerfiles. For apps that we build ourself, we use either
# the standard erlang:22.x base image (for 3.x tags), or the image
# with R16 that we have built specially (for 2.x tags)

ifneq ($(RIAK_VSN:2.%=xx%), $(RIAK_VSN))
RIAK_DOCKERFILE := Dockerfile-2.x
else
RIAK_DOCKERFILE := Dockerfile-3.x
endif

ifneq ($(RCS_VSN:2.%=xx%), $(RCS_VSN))
RCS_DOCKERFILE := Dockerfile-2.x
else
RCS_DOCKERFILE := Dockerfile-3.x
endif

ifneq ($(STANCHION_VSN:2.%=xx%), $(STANCHION_VSN))
STANCHION_DOCKERFILE := Dockerfile-2.x
else
STANCHION_DOCKERFILE := Dockerfile-3.x
endif

# old riak-cs-control won't build with R16
# (and it doesn't really matter anyway)
RCSC_DOCKERFILE := Dockerfile-3.x


RIAK_PLATFORM_DIR ?= $(shell pwd)/p

N_RIAK_NODES     ?= 3
N_RCS_NODES      ?= 2
RCS_AUTH_V4      ?= on
RIAK_TOPO        ?= "riak_topo.json"
RCS_TOPO         ?= "rcs_topo.json"

DOCKER_SERVICE_NAME ?= rcs-tussle-one

clone := git -c advice.detachedHead=false clone --depth 1
sources:
	@(export F="openssl-1.0.2u.tar.gz" && \
	 cd R16 && test -r $$F || wget https://www.openssl.org/source/old/1.0.2/$$F)
	@(export F="autoconf-2.59.tar.bz2" && \
	 cd R16 && test -r $$F || wget http://ftp.gnu.org/gnu/autoconf/$$F)
	@(export F="OTP_R16B02_basho10.tar.gz" && \
	 cd R16 && test -r $$F || wget https://github.com/basho/otp/archive/refs/tags/$$F)

	@(test -d riak/riak-${RIAK_VSN} || \
	  ${clone} -b riak-${RIAK_VSN} https://github.com/basho/riak riak/riak-${RIAK_VSN})
	@(test -d riak_cs/riak_cs-${RCS_VSN} || \
	  ${clone} -b ${RCS_VSN} \
	  https://github.com/TI-Tokyo/riak_cs riak_cs/riak_cs-${RCS_VSN})
	@(test -d stanchion/stanchion-${STANCHION_VSN} || \
	  ${clone} -b ${STANCHION_VSN} \
	  https://github.com/TI-Tokyo/stanchion stanchion/stanchion-${STANCHION_VSN})
	@(test -d riak_cs_control/riak_cs_control-${RCSC_VSN} || \
	  ${clone} -b ${RCSC_VSN} https://github.com/TI-Tokyo/riak_cs_control riak_cs_control/riak_cs_control-${RCSC_VSN})

R16:
	(cd R16 && docker build --tag erlang:R16 .)

build: sources
	@COMPOSE_FILE=docker-compose-build.yml \
	 RIAK_VSN=$(RIAK_VSN) \
	 RCS_VSN=$(RCS_VSN) \
	 RCSC_VSN=$(RCSC_VSN) \
	 STANCHION_VSN=$(STANCHION_VSN) \
	 RIAK_DOCKERFILE=$(RIAK_DOCKERFILE) \
	 RCS_DOCKERFILE=$(RCS_DOCKERFILE) \
	 RCSC_DOCKERFILE=$(RCSC_DOCKERFILE) \
	 STANCHION_DOCKERFILE=$(STANCHION_DOCKERFILE) \
	 docker-compose build \
	    --build-arg RIAK_VSN=$(RIAK_VSN) \
	    --build-arg RCS_VSN=$(RCS_VSN) \
	    --build-arg RCSC_VSN=$(RCSC_VSN) \
	    --build-arg STANCHION_VSN=$(STANCHION_VSN)

start: build ensure-dirs start-quick

start-quick:
	@docker swarm init >/dev/null 2>&1 || :
	@echo
	@echo "Starting bundle with RIAK_VSN=$(RIAK_VSN) and RCS_VSN=$(RCS_VSN)"
	@echo "======================================================================="
	@echo
	@export \
	 RIAK_VSN=$(RIAK_VSN) \
	 RCS_VSN=$(RCS_VSN) \
	 STANCHION_VSN=$(STANCHION_VSN) \
	 RCSC_VSN=$(RCSC_VSN) \
	 N_RIAK_NODES=$(N_RIAK_NODES) \
	 N_RCS_NODES=$(N_RCS_NODES) \
	 RIAK_PLATFORM_DIR=$(RIAK_PLATFORM_DIR) \
	 && docker stack deploy -c docker-compose-run.yml $(DOCKER_SERVICE_NAME) \
	 && ./prepare-tussle \
		$(DOCKER_SERVICE_NAME) \
		$(N_RIAK_NODES) $(N_RCS_NODES)\
		$(RCS_AUTH_V4) \
	        $(RIAK_TOPO) \
	        $(RCS_TOPO)

stop:
	@COMPOSE_FILE=docker-compose-run.yml \
	    docker stack rm $(DOCKER_SERVICE_NAME)

ensure-dirs:
	@mkdir -p $(RIAK_PLATFORM_DIR){/data,/log}

clean:
	@sudo rm -rf $(RIAK_PLATFORM_DIR)
