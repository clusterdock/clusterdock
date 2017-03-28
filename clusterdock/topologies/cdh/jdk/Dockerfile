FROM alpine:latest

ARG JDK_URL=http://download.oracle.com/otn-pub/java/jdk/8u121-b13/e9e7ea248e2c4826b92b3f075a80e441/jdk-8u121-linux-x64.tar.gz
ARG JDK_DIRECTORY=/usr/java/jdk1.8.0_121

RUN apk --no-cache --update add wget

RUN wget --no-check-certificate \
    --header "Cookie: oraclelicense=accept-securebackup-cookie" -O /tmp/jdk.tar.gz \
    "${JDK_URL}" && \
    mkdir -p /usr/java && \
    tar xf /tmp/jdk.tar.gz -C /usr/java && \
    rm /tmp/jdk.tar.gz

VOLUME ${JDK_DIRECTORY}

CMD ["/bin/true"]
