FROM debian:buster

RUN apt-get update && apt-get install -y gcc autoconf make libncurses-dev zlib1g-dev

ADD openssl-1.0.2u.tar.gz /usr/src
WORKDIR /usr/src/openssl-1.0.2u
RUN ./config shared zlib && make -j4 V=0 && make V=0 install

ADD autoconf-2.59.tar.bz2 /usr/src
WORKDIR /usr/src/autoconf-2.59
RUN ./configure && make -j4 V=0 && make V=0 install

ADD OTP_R16B02_basho10.tar.gz /usr/src
WORKDIR /usr/src/otp-OTP_R16B02_basho10/
RUN MAKE="make -j4" ./otp_build setup -a --disable-hipe --without-odbc --enable-silent-rules
RUN make install

CMD bash
