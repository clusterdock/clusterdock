FROM clusterdock/topology_nodebase:centos6.6

RUN yum -y install authconfig \
    krb5-server \
    krb5-workstation \
    pam_krb5

VOLUME /kdc

CMD ["/sbin/init"]
