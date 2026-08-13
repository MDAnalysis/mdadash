Parallelization
===============

``mdadash`` supports running Widgets in parallel. It uses `Joblib`_ with the default
``loky`` backend to run the parallel jobs as separate processes. A global "Parallel Jobs"
under "Settings > Dashboard Configuration" in the dasboard controls the total number of jobs
that can run in parallel (``n_jobs`` param for `joblib.Parallel`_ call).

All the analyses that run in ``mdadash`` are CPU-bound and hence a Process-based parallelism
is chosen instead of Thread-based parallelism.

`IMDReader`_ uses `imdclient`_ to connect to a live MD simulation. Because of the use of a
network socket within `imdclient`_, this is not serializable by default. ``mdadash`` patches
`IMDReader`_ to remove `imdclient`_ from the serialization state since the trajectory is never
iterated using `imdclient`_ within a parallel job. This makes parallelization possible within
``mdadash`` for streaming trajectories.

A Widget class that supports a ``parallel`` :ref:`_run_mode <run-mode>` must implement 
:meth:`~mdadash.backend.widgets.base.WidgetBase.get_parallel_job` and
:meth:`~mdadash.backend.widgets.base.WidgetBase.apply_parallel_results` methods.

As mentioned in the docs for the
:meth:`~mdadash.backend.widgets.base.WidgetBase.get_parallel_job` and
:meth:`~mdadash.backend.widgets.base.WidgetBase.apply_parallel_results` methods, everything
needed by the Widget class (ouputs, updated internal state, etc) must be explicitly returned
back as return values from the parallel job and applied back to the Widget.

Given the choice of Process-based parallelism, there will be serialization and de-serialization
overheads involved when Widgets run in parallel mode. The type of analysis and the use of
batching should be considered when choosing the ``parallel`` :ref:`_run_mode <run-mode>` for
Widgets.

.. tip::

    :doc:`batching` can be used with Parallelization to limit the impact of the
    serialization and de-serialization overhead.

----

The list of all the Widgets that can be run in parallel can be found on the
:doc:`built_in_widgets` page.


.. _Joblib: https://joblib.readthedocs.io/en/stable/

.. _joblib.Parallel: https://joblib.readthedocs.io/en/stable/generated/joblib.Parallel.html

.. _IMDReader: https://docs.mdanalysis.org/stable/
    documentation_pages/coordinates/IMD.html

.. _imdclient: https://imdclient.readthedocs.io/en/latest/
