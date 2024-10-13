.. _mmt_tutorial:

Montmorillonite
================

The Wyoming Montmorillonite is the most widely studied and used smectite. It is readily available for purchase from the Clay Mineral Society's `Source Clays`_, named SWy-1, SWy-2 or SWy-3 depending on when it was collected.

As it has been studied often, it is well characterised. The structure given by the Clay Mineral Society is:

.. math::

    Ca_{0.12} Na_{0.32} K_{0.05} [Si_{7.98} Al_{0.02} ]^{-0.02} [Al_{3.01} Fe(III)_{0.41} Mn_{0.01} Mg_{0.54} Ti_{0.02} ]^{-0.53} O_{20} (OH)_4

    \text{with an unbalanced charge of +0.05}

Titanium is often identified during clay analysis, but is attributed to TiO inclusions. Therefore, we will omit it in the input. Meanwhile, the ClayFF forcefield does not have any parameters for Mn, which is shown at the level of detection, and so we will also omit this.

Model Construction
------------------

The provided :code:`exp_clay.csv` file contains an entry called :code:`SWy-1`, which corresponds to this Wyoming Montmorillonite clay.

Let's examine the :code:`SWy1.yaml`, which is provided in the :code:`Tutorial` directory. This file contains all of the information necessary to build the clay model.

Please consult :ref:`YAML documentation <input_files_yaml>` for descriptions of the parameters.

YAML Parameters
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # =============================================================================
   # General specifications for clay model construction
   # =============================================================================

   OUTPATH: .

   # name of system to call according to CLAY_COMP (exp_clay.csv)
   SYSNAME: SWy-1

   # specify whether new clay model should be constructed:
   BUILD: new

   # name of .csv file with target stoichiometry
   CLAY_COMP: exp_clay.csv

   # clay type
   # available options in 'UCS' directory:
   CLAY_TYPE: CD21

   # -----------------------------------------------------------------------------

   # number of unit cells in x direction (Default 7)
   X_CELLS: 7

   # number of unit cells in y direction (Default 5)
   Y_CELLS: 5

   # number of unit cells in z direction (Default 3)
   N_SHEETS: 3

   # -----------------------------------------------------------------------------

   # interlayer solvent present or not (Default True)
   IL_SOLV: True

   # target hydrated interlayer spacing in A
   SPACING_WATERS: 20

   # -----------------------------------------------------------------------------

   # full simulation box height in A (Default 150.0)
   BOX_HEIGHT: 150.0

   # -----------------------------------------------------------------------------

   # Bulk solvent added or not (Default: True)
   BULK_SOLV: True

   # Ion species and concentration in mol/L name to add in bulk solvent
   BULK_IONS:
     Na: 0.1
     Cl: 0.05

   # -----------------------------------------------------------------------------

   # bash alias for used GROMACS version
   GMX: gmx

The model can then be constructed from within the :code:`Tutorial` directory using:

.. code-block:: bash

   ClayCode builder -f SWy1.yaml

.. _`Source Clays`: https://www.clays.org/source-and-special-clays/
