.. _tutorials:

Tutorials
===================

In this section, we will show how to set up the following systems:

- Wyoming :ref:`Montmorillonite <mmt_tutorial>`
- :ref:`Illite <ill_tutorial>`
- :ref:`Pyrophyllite <pyro_tutorial>`
- Uley :ref:`Nontronites <non_tutorial>`
- :ref:`Ferruginous Smectite <fe_sm_tutorial>`
- :ref:`Kaolinite <kao_tutorial>`
- :ref:`Layered Double Hydroxide <ldh_tutorial>`

The :ref:`Pyrophyllite tutorial <pyro_tutorial>` shows how to construct a system using only a .YAML file, the :ref:`Nontronites tutorial <non_tutorial>` discusses assigning iron distribution and oxidation and the :ref:`Kaolinite tutorial <kao_tutorial>` shows a situation where invalid atom types are encountered by ClayCode.

All necessary input files can be found in the :code:`Tutorial` directory. Each system has a corresponding .YAML file, and the :code:`exp_clay.csv` file contains clay structures corresponding to the `Clay Mineral Society`_'s Source Clays. :cite:p:`Sourceclays, Clays` Note, that Pyrophyllite's composition is not given in the .CSV file as it is fully described in the .YAML file.

.. _`Clay Mineral Society`: https://www.clays.org

.. bibliography::
   :style: plain
   :filter: False

   Sourceclays
   Clays
