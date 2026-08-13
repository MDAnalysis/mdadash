Built-in Analysis Widgets
=========================

Here is a list of built-in analysis widgets and whether they support batching
and can run in parallel:

.. list-table::
   :widths: 20 60 10 10
   :header-rows: 1

   * - Widget
     - Description
     - Batching
     - Parallel
   * - :mod:`~mdadash.backend.analyses.acf`
     - Autocorrelation Function (ACF)
     - —
     - ✅
   * - :mod:`~mdadash.backend.analyses.com_distance`
     - Distance between two center-of-masses
     - ✅
     - ✅
   * - :mod:`~mdadash.backend.analyses.contacts`
     - Contacts within a cutoff
     - ✅
     - ✅
   * - :mod:`~mdadash.backend.analyses.custom_code`
     - Custom user-defined code
     - ✅
     - —
   * - :mod:`~mdadash.backend.analyses.dssp`
     - DSSP Analysis
     - ✅
     - ✅
   * - :mod:`~mdadash.backend.analyses.energies`
     - Widgets for various simulation energies
     - ✅
     - —
   * - :mod:`~mdadash.backend.analyses.helix_analysis`
     - Helix Analysis
     - ✅
     - ✅
   * - :mod:`~mdadash.backend.analyses.hydrogen_bonds`
     - 	Number of Hydrogen bonds
     - ✅
     - ✅
   * - :mod:`~mdadash.backend.analyses.janin`
     - Janin plot (Dihedral angles analysis)
     - —
     - —
   * - :mod:`~mdadash.backend.analyses.msd`
     - MSD Analysis
     - —
     - ✅
   * - :mod:`~mdadash.backend.analyses.native_contacts`
     - Native Contacts Analysis
     - ✅
     - ✅
   * - :mod:`~mdadash.backend.analyses.ramachandran`
     - Ramachandran plot (Dihedral angles analysis)
     - —
     - —
   * - :mod:`~mdadash.backend.analyses.rmsd`
     - RMSD Analysis
     - ✅
     - ✅
   * - :mod:`~mdadash.backend.analyses.rog`
     - Radii of Gyration
     - ✅
     - ✅

.. raw:: html

  <p style="text-align: center;">✅ Supported, ❌ Not supported, — Not applicable</p>

.. toctree::
   :hidden:

   ACF <autosummary/mdadash.backend.analyses.acf>
   COMDistance <autosummary/mdadash.backend.analyses.com_distance>
   Contacts <autosummary/mdadash.backend.analyses.contacts>
   Custom Code <autosummary/mdadash.backend.analyses.custom_code>
   DSSP <autosummary/mdadash.backend.analyses.dssp>
   Energies <autosummary/mdadash.backend.analyses.energies>
   Helix Analysis <autosummary/mdadash.backend.analyses.helix_analysis>
   Hydrogen bonds <autosummary/mdadash.backend.analyses.hydrogen_bonds>
   Janin Plot <autosummary/mdadash.backend.analyses.janin>
   MSD Analysis <autosummary/mdadash.backend.analyses.msd>
   Native Contacts <autosummary/mdadash.backend.analyses.native_contacts>
   Ramachandran Plot <autosummary/mdadash.backend.analyses.ramachandran>
   RMSD <autosummary/mdadash.backend.analyses.rmsd>
   ROG <autosummary/mdadash.backend.analyses.rog>
