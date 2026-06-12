Getting Started
===============

This page details how to get started with ``mdadash``.

Installation
~~~~~~~~~~~~

``mdadash`` can be installed in any of the following ways depending on
your Python environment:

.. code:: sh

   pip install mdadash

or

.. code:: sh

   uv add mdadash

or

.. code:: sh

   conda install mdadash

or

.. code:: sh

   mamba install mdadash

Run
~~~

Once the package is installed, it can be run using the ``mdadash``
command to start the dashboard server:

.. code:: sh

   mdadash --topology <topology_filename> --trajectory <trajectory_url>

Example:

.. code:: sh

   mdadash --topology start.gro --trajectory imd://localhost:8889

To see a list of all the available options:

.. code:: sh

   mdadash -h

.. code:: sh

   $ mdadash -h
   usage: mdadash [-h] --topology TOPOLOGY --trajectory TRAJECTORY [--dashboard-port DASHBOARD_PORT] [--dashboard-host DASHBOARD_HOST]
                  [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [-v]

   Start the MDA Dashboard server

   options:
     -h, --help            show this help message and exit
     --topology TOPOLOGY   Topology filepath (required)
     --trajectory TRAJECTORY
                           Trajectory URL (of the form 'imd://host:port') (required)
     --dashboard-port DASHBOARD_PORT
                           Port to run the dashboard server on (default: 8000)
     --dashboard-host DASHBOARD_HOST
                           Host address to bind dashboard server to (default: 127.0.0.1)
     --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                           Set the logging level (default: INFO)
     -v, --version         Show the dashboard version and exit

Dashboard
~~~~~~~~~

The dashboard can be accessed by navigating to
`<http://127.0.0.1:8000>`__ from any browser.

   Note: Both the dashboard host and post can be customized using the
   ``mdadash`` command line options.
