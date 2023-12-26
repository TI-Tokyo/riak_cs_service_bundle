.PHONY: ensure-dirs sources R16 build start start-quick stop clean

RIAK_VSN       	    ?= riak-3.2.0
RCS_VSN    	    ?= 3.2.3
STANCHION_VSN  	    ?= 3.0.0
RCSC_VSN            ?= 3.2.3

# select Dockerfiles. For apps that we build ourself, we use either
# the standard erlang:22.x base image (for 3.x tags), or the image
# with R16 that we have built specially (for 2.x tags)

RIAK_VSN_NUM = $(subst riak-,,$(subst riak_kv-,,$(RIAK_VSN)))
ifneq ($(patsubst 2.%,xx,$(RIAK_VSN_NUM)), $(RIAK_VSN_NUM))
RIAK_DOCKERFILE := Dockerfile-riak-2.x
else
ifneq ($(patsubst 3.0.%,xx,$(RIAK_VSN_NUM)), $(RIAK_VSN_NUM))
RIAK_DOCKERFILE := Dockerfile-riak-3.0.x
else
RIAK_DOCKERFILE := Dockerfile-riak-3.2.x
endif
endif

ifneq ($(RCS_VSN:2.%=xx), $(RCS_VSN))
RCS_DOCKERFILE := Dockerfile-riak_cs-2.x
else
ifneq ($(RCS_VSN:3.0.%=xx), $(RCS_VSN))
COMPOSE_FILE_VERSION := 3.0
RCS_DOCKERFILE := Dockerfile-riak_cs-3.0.x
else
COMPOSE_FILE_VERSION := 3.1
ifneq ($(RCS_VSN:3.1.%=xx), $(RCS_VSN))
RCS_DOCKERFILE := Dockerfile-riak_cs-3.1.x
else
ifneq ($(RCS_VSN:3.2.%=xx), $(RCS_VSN))
RCS_DOCKERFILE := Dockerfile-riak_cs-3.2.x
endif
endif
endif

ifneq ($(RCS_VSN:3.1.%=xx), $(RCS_VSN))
HAVE_STANCHION := yes
else
HAVE_STANCHION := no
ifneq ($(STANCHION_VSN:2.%=xx), $(STANCHION_VSN))
STANCHION_DOCKERFILE := Dockerfile-stanchion-2.x
else
STANCHION_DOCKERFILE := Dockerfile-stanchion-3.x
endif
endif
endif

HAVE_ELM_RCSC := $(shell echo "print(\""$(RCSC_VSN)"\" > \"3.2.2\")" | python -)

ifeq "$(HAVE_ELM_RCSC)" "True"
COMPOSE_FILE_VERSION := 3.1
RCSC_DOCKERFILE := Dockerfile-riak_cs_control-3.2.3+
else
COMPOSE_FILE_VERSION := 3.0
RCSC_DOCKERFILE := Dockerfile-riak_cs_control-3.x
endif


RIAK_PLATFORM_DIR ?= $(shell pwd)/p/riak
RCS_PLATFORM_DIR ?= $(shell pwd)/p/riak_cs

N_RIAK_NODES      ?= $(shell ./lib/nodes_from_topo riak)
N_RCS_NODES       ?= $(shell ./lib/nodes_from_topo rcs)
N_STANCHION_NODES ?= $(shell ./lib/nodes_from_topo stanchion)
N_RCSC_NODES      ?= $(shell ./lib/nodes_from_topo rcsc)
RCS_AUTH_V4       ?= on

RCS_BACKEND_1     ?= eleveldb
RCS_BACKEND_2     ?= bitcask

DOCKER_SERVICE_NAME ?= rcs-tussle-one

clone := git -c advice.detachedHead=false clone --depth 1
sources:
	@(export F="openssl-1.0.2u.tar.gz" && \
	 cd repos/R16 && test -r $$F || wget https://www.openssl.org/source/old/1.0.2/$$F)
	@(export F="autoconf-2.59.tar.bz2" && \
	 cd repos/R16 && test -r $$F || wget http://ftp.gnu.org/gnu/autoconf/$$F)
	@(export F="OTP_R16B02_basho10.tar.gz" && \
	 cd repos/R16 && test -r $$F || wget https://github.com/basho/otp/archive/refs/tags/$$F)

	@(test -d repos/riak-${RIAK_VSN} || \
	  ${clone} -b ${RIAK_VSN} \
	  https://github.com/TI-Tokyo/riak repos/riak-${RIAK_VSN})
	@(test -d repos/riak_cs-${RCS_VSN} || \
	  ${clone} -b ${RCS_VSN} \
	  https://github.com/TI-Tokyo/riak_cs repos/riak_cs-${RCS_VSN})
	@(test -d repos/stanchion-${STANCHION_VSN} || \
	  ${clone} -b ${STANCHION_VSN} \
	  https://github.com/TI-Tokyo/stanchion repos/stanchion-${STANCHION_VSN})
	@(test -d repos/riak_cs_control-${RCSC_VSN} || \
	  ${clone} -b ${RCSC_VSN} https://github.com/TI-Tokyo/riak_cs_control repos/riak_cs_control-${RCSC_VSN})

R16:
	(cd repos/R16 && docker build --tag erlang:R16 .)

build: sources
	@(cd docker && \
	  rsync -a ../repos/riak-$(RIAK_VSN) . && \
	  rsync -a ../repos/riak_cs-$(RCS_VSN) . && \
	  rsync -a ../repos/stanchion-$(STANCHION_VSN) . && \
	  rsync -a ../repos/riak_cs_control-$(RCSC_VSN) . && \
	  COMPOSE_FILE=compose-build-$(COMPOSE_FILE_VERSION).yml \
	  RIAK_VSN=$(RIAK_VSN) \
	  RCS_VSN=$(RCS_VSN) \
	  RCSC_VSN=$(RCSC_VSN) \
	  STANCHION_VSN=$(STANCHION_VSN) \
	  RIAK_DOCKERFILE=$(RIAK_DOCKERFILE) \
	  RCS_DOCKERFILE=$(RCS_DOCKERFILE) \
	  RCSC_DOCKERFILE=$(RCSC_DOCKERFILE) \
	  STANCHION_DOCKERFILE=$(STANCHION_DOCKERFILE) \
	  docker compose build \
	    --build-arg RIAK_VSN=$(RIAK_VSN) \
	    --build-arg RCS_VSN=$(RCS_VSN) \
	    --build-arg RCSC_VSN=$(RCSC_VSN) \
	    --build-arg STANCHION_VSN=$(STANCHION_VSN) \
	    --build-arg RCS_BACKEND_1=$(RCS_BACKEND_1) \
	    --build-arg RCS_BACKEND_2=$(RCS_BACKEND_2) && \
	  rm -rf riak-$(RIAK_VSN) \
	         riak_cs-$(RCS_VSN) \
	         stanchion-$(STANCHION_VSN) \
	         riak_cs_control-$(RCSC_VSN))


start: build ensure-dirs
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
	 N_STANCHION_NODES=$(N_STANCHION_NODES) \
	 N_RCSC_NODES=$(N_RCSC_NODES) \
	 RIAK_PLATFORM_DIR=$(RIAK_PLATFORM_DIR) \
	 RCS_PLATFORM_DIR=$(RCS_PLATFORM_DIR) \
	 RCS_AUTH_V4=$(RCS_AUTH_V4) \
	 HAVE_STANCHION=$(HAVE_STANCHION) \
	 && docker stack deploy -c docker/compose-run-$(COMPOSE_FILE_VERSION).yml $(DOCKER_SERVICE_NAME) \
	 && ./lib/prepare-tussle $(DOCKER_SERVICE_NAME)

stop:
	@docker stack rm $(DOCKER_SERVICE_NAME)
	@echo "Waiting until containers are stopped..."
	@docker container ls --filter "name=rcs-tussle-one" --format='{{.Names}}' | xargs docker wait >/dev/null 2>&1 || :

ensure-dirs:
	@mkdir -p $(RIAK_PLATFORM_DIR){/data,/log} $(RCS_PLATFORM_DIR)/log

clean: stop
	@sudo rm -rf $(RIAK_PLATFORM_DIR) $(RCS_PLATFORM_DIR)/log
