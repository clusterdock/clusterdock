===========
clusterdock
===========

.. image:: https://img.shields.io/pypi/l/clusterdock.svg
    :target: https://pypi.python.org/pypi/clusterdock

.. image:: https://img.shields.io/pypi/v/clusterdock.svg
        :target: https://pypi.python.org/pypi/clusterdock

.. image:: https://readthedocs.org/projects/clusterdock/badge/?version=latest
        :target: https://clusterdock.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://img.shields.io/pypi/pyversions/clusterdock.svg
    :target: https://pypi.python.org/pypi/clusterdock

-------------------

**clusterdock** is a Python 3 project that enables users to build,
start, and manage Docker container-based clusters. It uses a pluggable
system for defining new types of clusters using folders called *topologies* and
is a swell project, if I may say so myself.

-------------------

"I hate reading, make this quick."
==================================

Before doing anything, install a recent version of `Docker`_ to your machine. Next,
clone a clusterdock topology to your machine. For this example,
we'll use the `nodebase topology`_.
Assuming that you've already installed **clusterdock**, you could start a 2-node cluster:

.. _Docker: https://www.docker.com/
.. _nodebase topology: https://github.com/clusterdock/topology_nodebase

.. code-block:: console

    $ git clone https://github.com/clusterdock/topology_nodebase.git
    $ clusterdock start topology_nodebase
    2017-08-03 10:04:18 PM clusterdock.models   INFO     Starting cluster on network (cluster) ...
    2017-08-03 10:04:18 PM clusterdock.models   INFO     Starting node node-1.cluster ...
    2017-08-03 10:04:19 PM clusterdock.models   INFO     Starting node node-2.cluster ...
    2017-08-03 10:04:20 PM clusterdock.models   INFO     Cluster started successfully (total time: 00:00:01.621).

To list cluster nodes:

.. code-block:: console

    $ clusterdock ps

    For cluster `famous_hyades` on network cluster the node(s) are:
    CONTAINER ID     HOST NAME            PORTS              STATUS        CONTAINER NAME          VERSION    IMAGE
    a205d88beb       node-2.cluster                          running       nervous_sinoussi        1.3.3      clusterdock/topology_nodebase:centos6.6
    6f2825c596       node-1.cluster       8080->80/tcp       running       priceless_franklin      1.3.3      clusterdock/topology_nodebase:centos6.6

To SSH into a node and look around:

.. code-block:: console

    $ clusterdock ssh node-1.cluster
    [root@node-1 ~]# ls -l / | head
    total 64
    dr-xr-xr-x   1 root root 4096 May 19 20:48 bin
    drwxr-xr-x   5 root root  360 Aug  4 05:04 dev
    drwxr-xr-x   1 root root 4096 Aug  4 05:04 etc
    drwxr-xr-x   2 root root 4096 Sep 23  2011 home
    dr-xr-xr-x   7 root root 4096 Mar  4  2015 lib
    dr-xr-xr-x   1 root root 4096 May 19 20:48 lib64
    drwx------   2 root root 4096 Mar  4  2015 lost+found
    drwxr-xr-x   2 root root 4096 Sep 23  2011 media
    drwxr-xr-x   2 root root 4096 Sep 23  2011 mnt
    [root@node-1 ~]# exit

To see the complete usage message for the topology:

.. code-block:: console

    $ clusterdock start topology_nodebase -h
    usage: clusterdock start [-h] [--node-disks map] [--always-pull]
                             [--namespace ns] [--network nw] [-o sys] [-r url]
                             [--nodes node [node ...]]
                             topology

    Start a nodebase cluster

    positional arguments:
      topology              A clusterdock topology directory

    optional arguments:
      -h, --help            show this help message and exit
      --always-pull         Pull latest images, even if they're available locally
                            (default: False)
      --namespace ns        Namespace to use when looking for images (default:
                            clusterdock)
      --network nw          Docker network to use (default: cluster)
      -o sys, --operating-system sys
                            Operating system to use for cluster nodes (default:
                            centos6.6)
      -r url, --registry url
                            Docker Registry from which to pull images (default:
                            None)

    nodebase arguments:
      --node-disks map      Map of node names to block devices (default: None)

    Node groups:
      --nodes node [node ...]
                            Nodes of the nodes group (default: ['node-1',
                            'node-2'])

When you're done and want to clean up:

.. code-block:: console

    $ clusterdock manage nuke
    2017-08-03 10:06:28 PM clusterdock.actions.manage INFO     Stopping and removing clusterdock containers ...
    2017-08-03 10:06:30 PM clusterdock.actions.manage INFO     Removed user-defined networks ...

-------------------

More pages with words on them
=============================

.. toctree::
   :maxdepth: 2

   installation
   api
   authors
   contributing
   history
