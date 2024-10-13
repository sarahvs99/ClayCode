.. _ill_tutorial:

Illite
=======

The term "illite" is often used to describe 2:1 minerals with a non-expandable interlayer. The specific mineral illite is a dioctahedral 2:1 phyllosilicate that is commonly found in soils and sedimentary rocks. The illite sold by the Clay Mineral Society's `Source Clays`_, named IMt-1 and IMt-2 has the following structure:

.. math::

    Mg_{0.09} Ca_{0.06} K_{1.37} [Si_{6.77} Al_{1.23} ]^{-1.23} [Al_{2.69} Fe^{III}_{0.76} Fe^{II}_{0.06} Mg_{0.43} Ti_{0.06} ]^{-0.44} O_{20} (OH)_4

Titanium is often identified during clay analysis, but is attributed to TiO inclusions. Therefore, we will omit in the input.

Model Construction
------------------

The provided :code:`exp_clay.csv` file contains an entry called :code:`IMt-1`, which corresponds to this illite clay **with** the iron oxidation states specified. It also contains an entry called :code:`IMt-2`, which corresponds to this illite clay but **without** the iron oxidation states specified.

There are three :code:`.yaml` files provided, one for each :code:`.csv` entry **without** bulk solvation (:code:`IMt1.yaml` and :code:`IMt2.yaml`) and another for :code:`IMt-1` **with** bulk solvation (:code:`IMt1_solv.yaml`).

IMt1.yaml
~~~~~~~~~~

.. code-block:: bash

   # =============================================================================
   # General specifications for clay model construction
   # =============================================================================

   OUTPATH: .

   # name of system to call according to CLAY_COMP (exp_clay.csv)
   SYSNAME: IMt-1

   # specify whether new clay model should be constructed:
   BUILD: new

   # name of .csv file with target stoichiometry
   CLAY_COMP: exp_clay.csv

   # clay type
   # available options in 'UCS' directory:
   CLAY_TYPE: CD21

   # -----------------------------------------------------------------------------

   # number of unit cells in x direction (Default 7)
   X_CELLS: 6

   # number of unit cells in y direction (Default 5)
   Y_CELLS: 4

   # number of unit cells in z direction (Default 3)
   N_SHEETS: 2

   # -----------------------------------------------------------------------------

   # interlayer solvent present or not (Default True)
   IL_SOLV: False

   # -----------------------------------------------------------------------------

   # full simulation box height in A (Default 150.0)
   BOX_HEIGHT: 30.0

   # -----------------------------------------------------------------------------

   # Bulk solvent added or not (Default: True)
   BULK_SOLV: False

   # -----------------------------------------------------------------------------

   # bash alias for used GROMACS version
   GMX: gmx


IMt1_solv.yaml
~~~~~~~~~~

.. code-block:: bash

   # =============================================================================
   # General specifications for clay model construction
   # =============================================================================

   OUTPATH: .

   # name of system to call according to CLAY_COMP (exp_clay.csv)
   SYSNAME: IMt-1

   # specify whether new clay model should be constructed:
   BUILD: new

   # name of .csv file with target stoichiometry
   CLAY_COMP: ./exp_clay.csv

   # clay type
   # available options in 'UCS' directory:
   CLAY_TYPE: CD21

   # -----------------------------------------------------------------------------

   # number of unit cells in x direction (Default 7)
   X_CELLS: 6

   # number of unit cells in y direction (Default 5)
   Y_CELLS: 4

   # number of unit cells in z direction (Default 3)
   N_SHEETS: 4

   # -----------------------------------------------------------------------------

   # interlayer solvent present or not (Default True)
   IL_SOLV: False

   # -----------------------------------------------------------------------------

   # full simulation box height in A (Default 150.0)
   BOX_HEIGHT: 100.0

   # -----------------------------------------------------------------------------

   # Bulk solvent added or not (Default: True)
   BULK_SOLV: True

   # -----------------------------------------------------------------------------

   # bash alias for used GROMACS version
   GMX: gmx

IMt2.yaml
~~~~~~~~~~

.. code-block:: bash

   # =============================================================================
   # General specifications for clay model construction
   # =============================================================================

   OUTPATH: .

   # name of system to call according to CLAY_COMP (exp_clay.csv)
   SYSNAME: IMt-2

   # specify whether new clay model should be constructed:
   BUILD: new

   # name of .csv file with target stoichiometry
   CLAY_COMP: ./exp_clay.csv

   # clay type
   # available options in 'UCS' directory:
   CLAY_TYPE: CD21

   # -----------------------------------------------------------------------------

   # number of unit cells in x direction (Default 7)
   X_CELLS: 6

   # number of unit cells in y direction (Default 5)
   Y_CELLS: 4

   # number of unit cells in z direction (Default 3)
   N_SHEETS: 3

   # -----------------------------------------------------------------------------

   # interlayer solvent present or not (Default True)
   IL_SOLV: False

   # -----------------------------------------------------------------------------

   # full simulation box height in A (Default 150.0)
   BOX_HEIGHT: 50.0

   # -----------------------------------------------------------------------------

   # Bulk solvent added or not (Default: True)
   BULK_SOLV: False

   BULK_IONS:
      Na: 0
      Cl: 0

   # -----------------------------------------------------------------------------

   # bash alias for used GROMACS version
   GMX: gmx

.. _`Source Clays`: https://www.clays.org/source-and-special-clays/
