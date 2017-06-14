FROM alpine:latest

ARG JDK_URL=http://download.oracle.com/otn-pub/java/jdk/8u131-b11/d54c1d3a095b4ff2b6607d096fa80163/jdk-8u131-linux-x64.tar.gz
ARG JCE_URL=http://download.oracle.com/otn-pub/java/jce/8/jce_policy-8.zip
ARG JDK_DIRECTORY=/usr/java/jdk1.8.0_131

RUN apk --no-cache --update add wget

RUN wget --no-check-certificate \
        --header "Cookie: oraclelicense=accept-securebackup-cookie" -O /tmp/jdk.tar.gz \
        "${JDK_URL}" && \
    mkdir -p /usr/java && \
    tar xf /tmp/jdk.tar.gz -C /usr/java && \
    rm /tmp/jdk.tar.gz

RUN apk --no-cache --update add unzip

RUN wget --no-check-certificate \
        --no-cookies --header "Cookie: oraclelicense=accept-securebackup-cookie" -O /tmp/unlimited_jce_policy.zip \
        "${JCE_URL}" && \
    unzip -jo -d ${JDK_DIRECTORY}/jre/lib/security /tmp/unlimited_jce_policy.zip && \
    rm /tmp/unlimited_jce_policy.zip

VOLUME ${JDK_DIRECTORY}

CMD ["/bin/true"]
