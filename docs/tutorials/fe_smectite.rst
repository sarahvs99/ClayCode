.. _fe_sm_tutorial:

Ferruginous Smectite
================

The term ferruginous smectite is used for dioctahedral smectites when the Fe^{3+} content is greater than 3%. The ferruginous smectite sold by the Clay Mineral Society's `Source Clays`_, named SWa-1, has an iron content of 12.6 wt%.
They are distinguished from Nontronites by only having partial substitution of aluminium by iron.

The structure given by the Clay Mineral Society is:

.. math::

    Mg_{0.18} Ca_{0.36} K_{0.01} [Si_{7.09} Al_{0.91} ]^{-0.91} [Al_{0.61} Fe^{III}_{3.08} Mg_{0.24} Ti_{0.02} ]^{-0.18} O_{20} (OH)_4

Titanium is often identified during clay analysis, but is attributed to TiO inclusions. Therefore, we will omit it in the input.

Model Construction
------------------

The provided :code:`exp_clay.csv` file contains an entry called :code:`SWa-1`, which corresponds to this ferruginous smectite clay.

Let's examine the :code:`SWya.yaml`, which is provided in the :code:`Tutorial` directory. This file contains all of the information necessary to build the clay model.

Please consult :ref:`YAML documentation <input_files_yaml>` for descriptions of the parameters.

YAML Parameters
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # =============================================================================
   # General specifications for clay model construction
   # =============================================================================

   OUTPATH: .

   # name of system to call according to CLAY_COMP (exp_clay.csv)
   SYSNAME: SWa-1

   # specify whether new clay model should be constructed:
   BUILD: new

   # name of .csv file with target stoichiometry
   CLAY_COMP: ./exp_clay.csv

   # clay type
   # available options in 'UCS' directory:
   CLAY_TYPE: TD21

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
   SPACING_WATERS: 10

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

The model can be constructed from within the :code:`Tutorial` directory using:

.. code-block:: bash

   ClayCode builder -f SWa1.yaml

.. _`Source Clays`: https://www.clays.org/source-and-special-clays/,
