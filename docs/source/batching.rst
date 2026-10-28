Batching
========

`IMDReader`_ provides support for reading MD simulation data via the `IMDv3 Protocol`_
in MDAnalysis since `Release 2.10.0`_.

Since IMD streams data in real-time from a running simulation, it has fundamental constraints
that differ from traditional trajectory readers and this leads to some `Important Limitations`_
in `IMDReader`_.

Buffered Access
---------------

To support buffered, time-dependent analyses in `mdadash`_, a
:class:`~mdadash.backend.kernel.core.BufferedTrajectory` is introduced.

The original trajectory is wrapped by the :class:`~mdadash.backend.kernel.core.BufferedTrajectory`
to provide buffered access to the last ``n`` timesteps, where ``n`` is the configured batch size.

.. code-block:: python

    u.trajectory = BufferedTrajectory(u, config["batch_size"])

``trajectory[index]`` can be used to access individual frames. Index values can range from 0 to the
configured batch size ``n``. The batch size ``n`` is available via the ``trajectory.buffer_size``
attribute.

When a Widget class supports :ref:`batching <run-frequency>` and implements the 
:meth:`~mdadash.backend.widgets.base.WidgetBase.run_batch` method, the trajectory can be iterated
this way to access the last ``n`` timesteps.

Here is a typical compute batch block used in the code for :doc:`built_in_widgets`:

.. code-block:: python

    def _compute_batch(self):
        """Compute for current batch"""
        values = []
        for i in range(self.u.trajectory.buffer_size):
            _ = self.u.trajectory[i]  # set the trajectory to frame i
            values.append(self._compute_current_frame())
        return values


Vectorized operations
~~~~~~~~~~~~~~~~~~~~~

:class:`~mdadash.backend.kernel.core.BufferedTrajectory` maintains individual arrays that are
available within a single timestep (like positions, velocities, frame numbers, etc) as contiguous
arrays across the whole buffer. For example, the positions for all the frames in the buffer can be
accessed using ``self.u.trajectory._positions``. When widgets run in batch mode, this enables the
use of vectorized operations on these arrays.

The available contiguous arrays are:

* ``self.u.trajectory._steps``
* ``self.u.trajectory._frames``
* ``self.u.trajectory._times``
* ``self.u.trajectory._unitcells``
* ``self.u.trajectory._positions``
* ``self.u.trajectory._velocities`` (if the timesteps have velocities)
* ``self.u.trajectory._forces`` (if the timesteps have forces)

:class:`~mdadash.backend.kernel.core.BufferedTrajectory` uses the above arrays as a ring buffer.
For this reason, only in the batch mode (which gets invoked for each chunk of the buffer) they
will be chronologically correct. Vectorized operations can be used even in the non-batch mode,
but due to the nature of a ring buffer, a two split approach of the arrays will be needed in that
case.

.. tip::

    Examples of using vectorized operations can be found in :mod:`~mdadash.backend.analyses.com_distance`
    and :mod:`~mdadash.backend.analyses.rog` widgets in batch mode.


AnalysisBase support
--------------------

MDAnalysis provides an `AnalysisBase`_, which is the base class for defining multi-frame analysis.

A lot of built-in MDAnalysis `Analysis modules`_ derive from `AnalysisBase`_.

The :class:`~mdadash.backend.kernel.core.BufferedTrajectory` enables using these analysis
modules in the Widget classes, which are not possible with `IMDReader`_.

.. note::

    The total number of frames as seen by the `AnalysisBase`_-based classes will be the
    configured Buffer / batch size during a full ``analysis.run()`` invocation.

Here is an example of using an `AnalysisBase`_-based class within the Widget code by the
:mod:`Native Contacts <mdadash.backend.analyses.native_contacts>` built-in Widget.

.. code-block:: python

    from MDAnalysis.analysis import contacts
    .....

    def _create_contacts(self):
        """Update atom groups when selection phrases change"""
        self.contacts = contacts.Contacts(
            self.u,
            .....

    def _compute_batch(self):
        """Compute values for current batch"""
        self.contacts.run()
        values = []
        for i, (_, q) in enumerate(self.contacts.results.timeseries):
            .....


`AnalysisBase`_-based classes can also be used per-frame by passing the current frame as
shown in this example:

.. code-block:: python

    def _compute_current_frame(self):
        """Compute values for current frame"""
        self.contacts.run(frames=[self.u.trajectory.frame])
        .....


----

The list of all the Widgets that support batching can be found on the
:doc:`built_in_widgets` page.


.. _mdadash: https://github.com/MDAnalysis/mdadash

.. _IMDReader: https://docs.mdanalysis.org/stable/
    documentation_pages/coordinates/IMD.html

.. _Important Limitations: https://docs.mdanalysis.org/stable/
    documentation_pages/coordinates/IMD.html#important-limitations

.. _IMDv3 Protocol: https://imdclient.readthedocs.io/en/latest/protocol_v3.html

.. _Release 2.10.0: https://www.mdanalysis.org/2025/10/26/release-2.10.0/

.. _AnalysisBase: https://docs.mdanalysis.org/stable/
    documentation_pages/analysis/base.html#MDAnalysis.analysis.base.AnalysisBase

.. _Analysis modules: https://docs.mdanalysis.org/stable/
    documentation_pages/analysis_modules.html

