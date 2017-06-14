# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
import logging
import tarfile
from argparse import Namespace
from collections import OrderedDict
from datetime import datetime
from os import makedirs
from os.path import basename, dirname
from socket import getfqdn
from sys import stdout
from uuid import uuid4

import docker

from clusterdock import Constants
from clusterdock.cluster import Cluster, Node, NodeGroup
from clusterdock.docker_utils import (get_host_port_binding, is_image_available_locally,
                                      pull_image)
from clusterdock.topologies.cdh.cm import ClouderaManagerDeployment
from clusterdock.utils import wait_for_port_open

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CLDR_MGR_PRINCIPAL_PW = 'cldadmin'
CLDR_MGR_PRINCIPAL_USER = 'cloudera-scm/admin'
DEFAULT_CLOUDERA_NAMESPACE = Constants.DEFAULT.cloudera_namespace # pylint: disable=no-member
KDC_ACL_FILENAME = '/var/kerberos/krb5kdc/kadm5.acl'
KDC_CONF_FILENAME = '/var/kerberos/krb5kdc/kdc.conf'
KDC_HOST_NAME = 'kdc'
KDC_KEYTAB_FILENAME = '/etc/clusterdock/kerberos/sdc.keytab'
KDC_KRB5_CONF_FILENAME = '/etc/krb5.conf'
KERBEROS_VOLUME_DIR = '/etc/clusterdock/kerberos'

# A list of KDC configuration files to be updated on KDC Docker container
KDC_CONFIG_FILES = [
    KDC_ACL_FILENAME,
    KDC_CONF_FILENAME,
    KDC_KRB5_CONF_FILENAME
]

def start(args):
    primary_node_image = "{0}/{1}/clusterdock:{2}_{3}_primary-node".format(
        args.registry_url, args.namespace or DEFAULT_CLOUDERA_NAMESPACE,
        args.cdh_string, args.cm_string
    )

    secondary_node_image = "{0}/{1}/clusterdock:{2}_{3}_secondary-node".format(
        args.registry_url, args.namespace or DEFAULT_CLOUDERA_NAMESPACE,
        args.cdh_string, args.cm_string
    )
    images = [primary_node_image, secondary_node_image]

    if args.kerberos:
        kdc_node_image = "{0}/{1}/clusterdock:kdc".format(
            args.registry_url, args.namespace or DEFAULT_CLOUDERA_NAMESPACE
        )
        images.append(kdc_node_image)

    if args.java:
        java_image = "{0}/{1}/clusterdock:cdh_{2}".format(
            args.registry_url, args.namespace or DEFAULT_CLOUDERA_NAMESPACE,
            args.java
        )
        images.append(java_image)

    for image in images:
        if args.always_pull or args.only_pull or not is_image_available_locally(image):
            logger.info("Pulling image %s. This might take a little while...", image)
            pull_image(image)

    if args.only_pull:
        return

    CM_SERVER_PORT = 7180
    HUE_SERVER_PORT = 8888

    primary_node = Node(hostname=args.primary_node[0], network=args.network,
                        image=primary_node_image, ports=[CM_SERVER_PORT, HUE_SERVER_PORT],
                        volumes=[{'/etc/clusterdock/kerberos':'/etc/sdc/'}] if args.kerberos_principals else [],
                        **{'volumes_from': [java_image]} if args.java else {})

    secondary_nodes = [Node(hostname=hostname, network=args.network, image=secondary_node_image,
                            volumes=[{'/etc/clusterdock/kerberos':'/etc/sdc/'}] if args.kerberos_principals else [],
                            **{'volumes_from': [java_image]} if args.java else {})
                       for hostname in args.secondary_nodes]

    secondary_node_group = NodeGroup(name='secondary', nodes=secondary_nodes)
    node_groups = [NodeGroup(name='primary', nodes=[primary_node]),
                   secondary_node_group]

    if args.kerberos:
        kdc_node = Node(hostname=KDC_HOST_NAME, network=args.network,
                        image=kdc_node_image, volumes=[{KERBEROS_VOLUME_DIR: KERBEROS_VOLUME_DIR}])
        node_groups.append(NodeGroup(name='kdc', nodes=[kdc_node]))


    cluster = Cluster(topology='cdh', node_groups=node_groups, network_name=args.network)
    cluster.start()

    # Cloudera cluster nodes - these exclude kdc node
    cloudera_nodes = [primary_node] + secondary_nodes

    if args.kerberos:
        install_kdc_server(cluster, args.kerberos_principals)
        install_kerberos_libs(cluster)
        if args.kerberos_principals:
            create_users_on_cloudera_nodes(cluster, args.kerberos_principals)

    if args.java:
        set_cm_server_java_home(primary_node, '/usr/java/{0}'.format(args.java))

    '''
    A hack is needed here. In short, Docker mounts a number of files from the host into
    the container (and so do we). As such, when CM runs 'mount' inside of the containers
    during setup, it sees these ext4 files as suitable places in which to install things.
    Unfortunately, CM doesn't have a blacklist to ignore filesystem types and only including
    our containers' filesystem in the agents' config.ini whitelist is insufficient, since CM
    merges that list with the contents of /proc/filesystems. To work around this, we copy
    the culprit files inside of the container, which creates those files in aufs. We then
    unmount the volumes within the container and then move the files back to their original
    locations. By doing this, we preserve the contents of the files (which is necessary for
    things like networking to work properly) and keep CM happy.
    '''
    filesystem_fix_commands = []
    for file in ['/etc/hosts', '/etc/resolv.conf', '/etc/hostname', '/etc/localtime']:
        filesystem_fix_commands.append("cp {0} {0}.1; umount {0}; mv {0}.1 {0};".format(file))
    filesystem_fix_command = ' '.join(filesystem_fix_commands)
    cluster.ssh(filesystem_fix_command)

    change_cm_server_host(cluster, primary_node.fqdn)
    if len(secondary_nodes) > 1:
        additional_nodes = [node for node in secondary_nodes[1:]]
        remove_files(cluster, files=['/var/lib/cloudera-scm-agent/uuid',
                                     '/dfs*/dn/current/*'],
                     nodes=additional_nodes)

    # It looks like there may be something buggy when it comes to restarting the CM agent. Keep
    # going if this happens while we work on reproducing the problem.
    try:
        restart_cm_server(cluster)
        restart_cm_agents(cluster)
    except:
        pass

    logger.info('Waiting for Cloudera Manager server to come online...')
    cm_server_startup_time = wait_for_port_open(primary_node.ip_address,
                                                CM_SERVER_PORT, timeout_sec=180)
    logger.info("Detected Cloudera Manager server after %.2f seconds.", cm_server_startup_time)
    cm_server_web_ui_host_port = get_host_port_binding(primary_node.container_id,
                                                       CM_SERVER_PORT)

    logger.info("CM server is now accessible at http://%s:%s",
                getfqdn(), cm_server_web_ui_host_port)

    deployment = ClouderaManagerDeployment(cm_server_address=primary_node.ip_address)
    deployment.setup_api_resources()

    if len(cloudera_nodes) > 2:
        deployment.add_hosts_to_cluster(secondary_node_fqdn=secondary_nodes[0].fqdn,
                                        all_fqdns=[node.fqdn for node in cloudera_nodes])

    if args.java:
        deployment.update_all_hosts_configs(configs={
            'java_home': '/usr/java/{0}'.format(args.java)
        })

    deployment.update_cm_server_configs()
    deployment.update_database_configs()
    deployment.update_hive_metastore_namenodes()

    if args.include_service_types:
        # CM maintains service types in CAPS, so make sure our args.include_service_types list
        # follows the same convention.
        service_types_to_leave = args.include_service_types.upper().split(',')
        for service in deployment.cluster.get_all_services():
            if service.type not in service_types_to_leave:
                logger.info('Removing service %s from %s...', service.name, deployment.cluster.displayName)
                deployment.cluster.delete_service(service.name)
    elif args.exclude_service_types:
        service_types_to_remove = args.exclude_service_types.upper().split(',')
        for service in deployment.cluster.get_all_services():
            if service.type in service_types_to_remove:
                logger.info('Removing service %s from %s...', service.name, deployment.cluster.displayName)
                deployment.cluster.delete_service(service.name)

    hue_server_host_port = get_host_port_binding(primary_node.container_id, HUE_SERVER_PORT)
    for service in deployment.cluster.get_all_services():
        if service.type == 'HUE':
            logger.info("Once its service starts, Hue server will be accessible at http://%s:%s",
                        getfqdn(), hue_server_host_port)
            break

    realm = cluster.network_name.upper()
    if args.kerberos:
        logger.info('Updating config for kerberos...')
        kerberos_config = {'SECURITY_REALM': realm,
                           'KDC_HOST': KDC_HOST_NAME,
                           'KRB_MANAGE_KRB5_CONF': True,
                           'KRB_ENC_TYPES': 'aes256-cts-hmac-sha1-96'}
        deployment.cm.update_config(kerberos_config)

        logger.info('Importing kerberos admin credentials...')
        deployment.cm.import_admin_credentials('{}@{}'.format(CLDR_MGR_PRINCIPAL_USER, realm),
                                               CLDR_MGR_PRINCIPAL_PW).wait()

        logger.info('Configuring for kerberos...')
        config_kerberos_cmd = deployment.cluster.configure_for_kerberos()
        if not config_kerberos_cmd.wait().success:
            raise Exception('Failed to configure for kerberos.')

        logger.info('Deploying cluster client configuration...')
        cluster_client_config_cmd = deployment.cluster.deploy_cluster_client_config()
        if not cluster_client_config_cmd.wait().success:
            raise Exception('Failed to deploy cluster client configurations.')

        for service in deployment.cluster.get_all_services():
            if service.type == 'HUE':
                fix_for_hue_kerberos(cluster)
                break

    logger.info('Deploying client configuration...')
    client_config_cmd = deployment.cluster.deploy_client_config()
    if not client_config_cmd.wait().success:
        raise Exception("Failed to deploy client configurations.")

    if not args.dont_start_cluster:
        logger.info('Starting cluster...')
        if not deployment.cluster.start().wait().success:
            raise Exception('Failed to start cluster.')
        logger.info('Starting Cloudera Management service...')
        if not deployment.cm.get_service().start().wait().success:
            raise Exception('Failed to start Cloudera Management service.')

        deployment.validate_services_started()

    logger.info("We'd love to know what you think of our CDH topology for clusterdock! Please "
                "direct any feedback to our community forum at "
                "http://tiny.cloudera.com/hadoop-101-forum.")

def get_cloudera_nodes(cluster):
    return cluster.get_nodes_by_node_group_names(['primary', 'secondary'])

def create_users_on_cloudera_nodes(cluster, kerberos_principals):
    commands = ['useradd -u {} -g hadoop {}'.format(uid, primary)
                for uid, primary in enumerate(kerberos_principals.split(','), start=1000)]
    cluster.ssh('; '.join(commands), get_cloudera_nodes(cluster))

def restart_cm_server(cluster):
    logger.info('Restarting CM server...')
    cluster.get_nodes_by_node_group_names(['primary'])[0].ssh('service cloudera-scm-server restart')

def restart_cm_agents(cluster):
    logger.info('Restarting CM agents...')
    cluster.ssh('service cloudera-scm-agent restart', get_cloudera_nodes(cluster))

def change_cm_server_host(cluster, server_host):
    change_server_host_command = (
        r'sed -i "s/\(server_host\).*/\1={0}/" /etc/cloudera-scm-agent/config.ini'.format(
            server_host
        )
    )
    logger.info("Changing server_host to %s in /etc/cloudera-scm-agent/config.ini...",
                server_host)
    cluster.ssh(change_server_host_command, get_cloudera_nodes(cluster))

def set_cm_server_java_home(node, java_home):
    set_cm_server_java_home_command = (
        'echo "export JAVA_HOME={0}" >> /etc/default/cloudera-scm-server'.format(java_home)
    )
    logger.info("Setting JAVA_HOME to %s in /etc/default/cloudera-scm-server...",
                java_home)
    node.ssh(set_cm_server_java_home_command)

def remove_files(cluster, files, nodes):
    logger.info("Removing files (%s) from hosts (%s)...",
                ', '.join(files), ', '.join([node.fqdn for node in nodes]))
    cluster.ssh('rm -rf {0}'.format(' '.join(files)), nodes=nodes)

def install_kdc_server(cluster, kerberos_principals):
    logger.info('Installing kdc server on kdc node...')
    change_config_files(cluster)
    setup_kdc_server(cluster, kerberos_principals)

def change_config_files(cluster):
    """
    Files will be changed for Kerberos configuration reflecting:
    Kerberos configuration information, including the locations of KDCs and admin servers, 
    defaults for the current realm  etc.
    Access Control List (ACL).
    """
    logger.info('Changing config. files on kdc node...')

    kdc_node = cluster.get_nodes_by_node_group_names(['kdc'])[0]
    client = docker.Client()
    config_files = {}

    for kdc_conf_file in KDC_CONFIG_FILES:
        # docker.Client.get_archive returns a tuple containing the raw tar data stream and a
        # dict of stat information on the specified path. We only care about the former, so
        # we discard the latter.
        tarstream = io.BytesIO(client.get_archive(container=kdc_node.container_id,
                                                  path=kdc_conf_file)[0].read())
        with tarfile.open(fileobj=tarstream) as tarfile_:
            for tarinfo in tarfile_.getmembers():
                # tarfile.extractfile returns a file object, which, when read, returns a
                # bytes object.
                config_files[kdc_conf_file] = tarfile_.extractfile(tarinfo).read().decode()

    realm = cluster.network_name.upper()
    # Update configurations
    krb5_conf_data = config_files[KDC_KRB5_CONF_FILENAME]
    krb5_conf_data = krb5_conf_data.replace('EXAMPLE.COM', realm)
    krb5_conf_data = krb5_conf_data.replace('kerberos.example.com', '{}.{}'.format(KDC_HOST_NAME, cluster.network_name))
    krb5_conf_data = krb5_conf_data.replace('example.com', cluster.network_name)
    config_files[KDC_KRB5_CONF_FILENAME] = krb5_conf_data

    kdc_conf_data = config_files[KDC_CONF_FILENAME]
    kdc_conf_data = kdc_conf_data.replace('EXAMPLE.COM', realm)
    kdc_conf_data = kdc_conf_data.replace('[kdcdefaults]', '[kdcdefaults]\n max_renewablelife = 7d\n max_life = 1d')
    config_files[KDC_CONF_FILENAME] = kdc_conf_data

    acl_data = config_files[KDC_ACL_FILENAME]
    acl_data = acl_data.replace('EXAMPLE.COM', realm)
    config_files[KDC_ACL_FILENAME] = acl_data

    # Serialize them back to the kdc Docker container
    for kdc_conf_file in KDC_CONFIG_FILES:
        tarstream = io.BytesIO()
        with tarfile.open(fileobj=tarstream, mode='w') as tarfile_:
            encoded_file_contents = config_files[kdc_conf_file].encode()
            tarinfo = tarfile.TarInfo(basename(kdc_conf_file))
            tarinfo.size = len(encoded_file_contents)
            tarfile_.addfile(tarinfo, io.BytesIO(encoded_file_contents))
        tarstream.seek(0)
        client.put_archive(container=kdc_node.container_id, path=dirname(kdc_conf_file), data=tarstream)

def setup_kdc_server(cluster, kerberos_principals):
    logger.info('Setting up kdc server ...')
    realm = cluster.network_name.upper()
    kdc_commands = [
        'kdb5_util create -s -r {realm} -P kdcadmin'.format(realm=realm),
        'kadmin.local -q "addprinc -pw {adminpw} admin/admin@{realm}"'.format(adminpw='acladmin', realm=realm),
        'kadmin.local -q "addprinc -pw {cldradminpw} {cldradmin}@{realm}"'.format(
            cldradmin=CLDR_MGR_PRINCIPAL_USER,
            cldradminpw=CLDR_MGR_PRINCIPAL_PW,
            realm=realm),
    ]

    # Add the following commands before starting kadmin daemon etc.
    if kerberos_principals:
        principal_list = ['{}@{}'.format(primary, realm) for primary in kerberos_principals.split(',')]
        create_principals_cmds = ['kadmin.local -q "addprinc -randkey {}"'.format(principal)
                                  for principal in principal_list]
        kdc_commands.extend(create_principals_cmds)
        create_keytab_cmd = 'kadmin.local -q "xst -norandkey -k {} {}" '.format(KDC_KEYTAB_FILENAME,
                                                                                ' '.join(principal_list))
        kdc_commands.append(create_keytab_cmd)

    kdc_commands.extend([
        'krb5kdc',
        'kadmind',
        'authconfig --enablekrb5 --update',
        'service sshd restart',
        'service krb5kdc restart',
        'service kadmin restart'
    ])
    kdc_command = '; '.join(kdc_commands)
    nodes = cluster.get_nodes_by_node_group_names(['kdc'])
    cluster.ssh(kdc_command, nodes)

    # Gather keytab file and krb5.conf file in KERBEROS_VOLUME_DIR directory which is mounted on host.
    if kerberos_principals:
        gather_files_cmds = [
            'chmod 644 {}'.format(KDC_KEYTAB_FILENAME),
            'cp {} {}'.format(KDC_KRB5_CONF_FILENAME, KERBEROS_VOLUME_DIR)
        ]
        gather_files_cmd = '; '.join(gather_files_cmds)
        cluster.ssh(gather_files_cmd, nodes)

def fix_for_hue_kerberos(cluster):
    """ Fix for Hue service as explained at:
    http://www.cloudera.com/documentation/manager/5-1-x/Configuring-Hadoop-Security-with-Cloudera-Manager/cm5chs_enable_hue_sec_s10.html
    """
    logger.info('Applying fix for hue...')
    realm = cluster.network_name.upper()
    kdc_hue_commands = [
        'kadmin.local -q "modprinc -maxrenewlife 90day krbtgt/{realm}"'.format(realm=realm),
        'kadmin.local -q "modprinc -maxrenewlife 90day +allow_renewable hue/{hue_node_name}@{realm}"'.format(
            realm=realm,
            hue_node_name=cluster.get_nodes_by_node_group_names(['primary'])[0].fqdn),
        'service krb5kdc restart',
        'service kadmin restart'
    ]
    kdc_hue_command = '; '.join(kdc_hue_commands)
    cluster.ssh(kdc_hue_command, cluster.get_nodes_by_node_group_names(['kdc']))

def install_kerberos_libs(cluster):
    logger.info('Installing kerberos libs on cloudera nodes ...')
    # Workaround for CentOS 6.6 issue with yum is available in
    # https://github.com/clusterdock/framework/commit/205f3ca1cac4d3037b194a209683f7a8793e3953
    # TODO: Once the node images based on latest centos images are available, remove installation of yum-plugin-ovl.
    cluster.ssh('yum -y -q install yum-plugin-ovl')
    cluster.ssh('yum -y -q install openldap-clients', cluster.get_nodes_by_node_group_names(['primary']))
    cluster.ssh('yum -y -q install krb5-libs krb5-workstation', get_cloudera_nodes(cluster))
