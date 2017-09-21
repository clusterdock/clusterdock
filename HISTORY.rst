=======
History
=======

1.1.0 (2017.09.21)
------------------

* Updated clusterdock.models.Node.execute to return a namedtuple with the
command's exit code and output.
* Added support for specifying host:container port mappings when creating a node.
* Added ip_address attribute to clusterdock.models.Node.

1.0.7 (2017.09.18)
------------------

* Removed DEFAULT_NAMESPACE to let topologies define their own.

1.0.6 (2017.09.04)
------------------

* Added put_file and get_file methods to clusterdock.models.Node.
* Made network an instance attribute of clusterdock.models.Cluster.

1.0.5 (2017.09.02)
------------------

* Added logic to pull missing images to clusterdock.models.

1.0.4 (2017.09.02)
------------------

* Fixed missing install requirement.

1.0.3 (2017.09.02)
------------------

* Cleaned up Node API.
* Added wait_for_permission and join_url_parts utility functions.

1.0.2 (2017.08.04)
------------------

* Updated how Cluster and Node objects are initialized.
* Added project logo.
* Doc improvements.

1.0.1 (2017.08.03)
------------------

* First release on PyPI.
