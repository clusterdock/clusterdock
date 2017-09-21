=======
History
=======

1.1.0 (2017.09.21)
------------------

* Updated :py:meth:`clusterdock.models.Node.execute` to return a namedtuple with the
  command's exit code and output.
* Fixed bug around ``quiet`` argument to :py:meth:`clusterdock.models.Node.execute`.
* Added support for specifying ``host:container`` port mappings when creating a node.
* Added ``ip_address`` attribute to :py:class:`clusterdock.models.Node`.

1.0.7 (2017.09.18)
------------------

* Removed :py:const:`DEFAULT_NAMESPACE` to let topologies define their own.

1.0.6 (2017.09.04)
------------------

* Added :py:meth:`clusterdock.models.Node.put_file` and :py:meth:`clusterdock.models.Node.get_file`.
* Made ``network`` an instance attribute of :py:class:`clusterdock.models.Cluster`.

1.0.5 (2017.09.02)
------------------

* Added logic to pull missing images to :py:mod:`clusterdock.models`.

1.0.4 (2017.09.02)
------------------

* Fixed missing install requirement.

1.0.3 (2017.09.02)
------------------

* Cleaned up :py:class:`clusterdock.models.Node` API.
* Added wait_for_permission and join_url_parts utility functions.

1.0.2 (2017.08.04)
------------------

* Updated how Cluster and Node objects are initialized.
* Added project logo.
* Doc improvements.

1.0.1 (2017.08.03)
------------------

* First release on PyPI.
