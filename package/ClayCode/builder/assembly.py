#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
r""":mod:`ClayCode.builder.assembly` --- Assembly of clay models
==============================================================="""
from __future__ import annotations

import copy
import logging
import os
import re
import shutil
import tempfile
from functools import cached_property
from pathlib import Path
from typing import Any, Callable, List, Literal, Optional, Type, Union

import numpy as np
import pandas as pd
from ClayCode.builder.claycomp import InterlayerIons, UCData
from ClayCode.builder.topology import TopologyConstructor
from ClayCode.core.classes import (
    Dir,
    FileFactory,
    GROFile,
    TOPFile,
    set_mdp_freeze_groups,
    set_mdp_parameter,
)
from ClayCode.core.consts import (
    ANGSTROM,
    FF,
    GRO_FMT,
    LINE_LENGTH,
    MDP,
    MDP_DEFAULTS,
)
from ClayCode.core.gmx import (
    GMXCommands,
    add_gmx_args,
    check_box_lengths,
    gmx_command_wrapper,
)
from ClayCode.core.lib import (
    add_ions_n_mols,
    add_ions_neutral,
    add_resnum,
    center_clay,
    check_insert_numbers,
    run_em,
    select_outside_clay_stack,
    write_insert_dat,
)
from ClayCode.core.utils import backup_files, get_header, get_subheader
from MDAnalysis import AtomGroup, Merge, ResidueGroup, Universe
from MDAnalysis.units import constants
from numpy._typing import NDArray

__all__ = ["Builder", "Sheet", "Solvent"]

logger = logging.getLogger(__name__)


class Builder:
    __tmp_outpath: Type[
        tempfile.TemporaryDirectory
    ] = tempfile.TemporaryDirectory()
    __tmp_file: Type[
        tempfile.NamedTemporaryFile
    ] = tempfile.NamedTemporaryFile(dir=__tmp_outpath.name, delete=False)

    def __init__(self, build_args: Type["BuildArgs"]):
        self.args = build_args
        self.sheet = Sheet(
            self.args._uc_data,
            uc_ids=self.args.sheet_uc_weights.index.values,
            uc_numbers=self.args.sheet_uc_weights.values,
            x_cells=self.args.x_cells,
            y_cells=self.args.y_cells,
            fstem=self.args.filestem,
            outpath=self.args.outpath,
        )
        self.top = TopologyConstructor(self.args._uc_data, self.args.ff)
        self.__il_solv: Union[None, GROFile] = None
        self.__stack: Union[None, GROFile] = None
        self.__box_ext: bool = False
        logger.info(get_header(f"Building {self.args.name} model"))
        logger.finfo(f"{self.args.n_sheets} sheets")
        x_dim: float = self.sheet.x_cells * self.sheet.uc_dimensions[0]
        y_dim: float = self.sheet.y_cells * self.sheet.uc_dimensions[1]
        logger.finfo(
            kwd_str="Sheet dimensions: ",
            message=f"{x_dim:.2f} {ANGSTROM} X {y_dim:.2f} {ANGSTROM} "
            f"({self.sheet.x_cells} unit cells X {self.sheet.y_cells} unit cells)",
        )
        if self.args.box_height > self.sheet.uc_dimensions[2]:
            logger.finfo(
                kwd_str="Box height: ",
                message=f"{self.args.box_height:.1f} {ANGSTROM}",
            )
        else:
            logger.finfo("Will set box height to clay height")
        self.gmx_commands: GMXCommands = GMXCommands(
            gmx_alias=self.args.gmx_alias
        )
        self.em_prms = self.gmx_commands.mdp_defaults.copy()
        self.em_prms.update(self.args.mdp_parameters["EM"])
        check_box_lengths(
            self.em_prms, [self.sheet.dimensions[0], self.sheet.dimensions[1]]
        )

    @property
    def extended_box(self) -> bool:
        """
        :return: Whether a bulk space has been added to the clay stack.
        :rtype: bool"""
        return self.__box_ext

    def solvate_clay_sheets(self, backup: bool = False) -> None:
        """Generate interlayer solvent sheets.
        :param backup: Whether to back up existing files.
        :type backup: bool
        :return: None"""
        logger.info(get_subheader("2. Generating interlayer solvent."))
        solvent: Solvent = Solvent(
            x_dim=self.sheet.dimensions[0],
            y_dim=self.sheet.dimensions[1],
            n_mols=self.args.n_waters,
            z_dim=self.args.il_solv_height,
            gmx_commands=self.gmx_commands,
            z_padding=self.args.z_padding,
        )
        spc_file: GROFile = self.get_filename("interlayer", suffix=".gro")
        if backup:
            backup_files(self.args.outpath / spc_file.name)
            backup_files(self.args.outpath / spc_file.top.name)
        solvent.write(spc_name=spc_file, topology=self.top)
        self.il_solv: GROFile = spc_file

    @staticmethod
    def construct_solvent(
        solvate: bool,
        ion_charge: Union[int, float],
        solvate_add_func: Callable[[bool], Any],
        ion_add_func: Callable[[], Any],
        solvent_remove_func: Callable[[], Any],
        solvent_rename_func: Optional[Callable[[], Any]] = None,
        backup: bool = False,
    ) -> None:
        """Construct solvent workflow.
        :param solvate: Whether to solvate the clay stack.
        :type solvate: bool
        :param ion_charge: Charge of the system.
        :type ion_charge: Union[int, float]
        :param solvate_add_func: Function to add solvent.
        :type solvate_add_func: Callable[[bool], Any]
        :param ion_add_func: Function to add ions.
        :type ion_add_func: Callable[[], Any]
        :param solvent_remove_func: Function to remove solvent.
        :type solvent_remove_func: Callable[[], Any]
        :param solvent_rename_func: Function to rename solvent.
        :type solvent_rename_func: Optional[Callable[[], Any]]
        :param backup: Whether to backup existing files.
        :type backup: bool
        :return: None"""
        if not solvate and ion_charge == 0:
            pass
        elif solvate or ion_charge != 0:
            solvate_add_func(backup=backup)
            if ion_charge != 0:
                ion_add_func()
                if not solvate:
                    solvent_remove_func()
                elif solvent_rename_func:
                    solvent_rename_func()

    def rename_il_solv(self) -> None:
        """Rename interlayer solvent residues from 'SOl' to 'iSL'.
        :return: None"""
        il_u: Universe = Universe(str(self.il_solv))
        il_resnames: NDArray = il_u.residues.resnames
        il_resnames: list = list(
            map(lambda resname: re.sub("SOL", "iSL", resname), il_resnames)
        )
        il_u.residues.resnames: NDArray = il_resnames
        self.il_solv.universe: Universe = il_u
        self.il_solv.write(topology=self.top)
        self.il_solv = self.il_solv

    def run_em(
        self,
        freeze_clay: Optional[
            Union[List[Union[Literal["Y"], Literal["N"]]], bool]
        ] = ["Y", "Y", "Y"],
        backup=False,
    ) -> None:
        """Run energy minimisation.
        :param freeze_clay: Whether to freeze the clay stack during energy minimisation. If a list of three booleans is provided, the corresponding dimensions will be frozen. If True, all three dimensions will be frozen. If False, no dimensions will be frozen.
        :type freeze_clay: Optional[Union[List[Union[Literal["Y"], Literal["N"]]], bool]]
        :param backup: Whether to backup existing files.
        :type backup: bool
        :return: None"""
        logger.info(get_subheader("Minimising energy"))
        if freeze_clay:
            if isinstance(freeze_clay, bool):
                freeze_dims = ["Y", "Y", "Y"]
            else:
                freeze_dims = freeze_clay
            freeze_grps = np.unique(self.clay.residues.resnames)
        else:
            freeze_grps = None
            freeze_dims = None
        result = run_em(
            crdin=self.stack,
            topin=self.stack.top,
            odir=self.args.outpath,
            outname=f"{self.stack.stem}_em",
            gmx_commands=self.gmx_commands,
            freeze_grps=freeze_grps,
            freeze_dims=freeze_dims,
        )
        outpath = Dir(self.args.outpath)
        crd_top_files = [
            *outpath.gro_filelist,
            *outpath.itp_filelist,
            *outpath._get_filelist(ext=".top"),
            *outpath._get_filelist(ext=".csv"),
            *outpath._get_filelist(ext=".mdp"),
            *outpath._get_filelist(ext=".edr"),
            *outpath._get_filelist(ext=".trr"),
            *outpath._get_filelist(ext=".log"),
        ]
        em_files = []
        backups = []
        for file in outpath.iterdir():
            if file not in crd_top_files and not file.is_dir():
                file.unlink(missing_ok=True)
            else:
                if file.stem.split("_")[-1] == "em":
                    if outpath.name != "EM":
                        em_path = outpath / "EM"
                        os.makedirs(em_path, exist_ok=True)
                        if backup:
                            backups.append(
                                backup_files(new_filename=em_path / file.name)
                            )
                        shutil.move(file, em_path / file.name)
                        file = em_path / file.name
                    if file.suffix == ".gro":
                        self.stack = file
                        logger.finfo(
                            f"Wrote final output from energy minimisation to {str(file.parent)!r}:"
                        )
                    em_files.append(file.name)
        if backups:
            logger.finfo(
                "\t" + "\n\t".join([backup for backup in backups if backup]),
                initial_linebreak=True,
            )
        em_files = "'\n\t - '".join(sorted(em_files))
        logger.info(f"\t - '{em_files}'")
        return result

    def conclude(self):
        """Conclude model setup.
        Copy final files to output directory.
        :return: None"""
        logger.info(get_subheader("Finishing up"))
        self.stack: GROFile = self.args.outpath / self.stack.name
        add_resnum(crdin=self.stack, crdout=self.stack)
        self.__tmp_outpath.cleanup()
        logger.debug(
            f"Wrote final coordinates and topology to {self.stack.name!r} and {self.stack.top.name!r}"
        )
        logger.set_file_name(final="builder")
        logger.finfo(
            f"Log for this setup written to {str(logger.logfilename)!r}"
        )
        logger.info(get_header(f"{self.args.name} model setup complete"))

    def remove_il_solv(self, min_height=1.0) -> None:
        """Remove interlayer solvent if interlayer needs to have ions but no solvent.
        :return None"""
        logger.finfo("Removing interlayer solvent", initial_linebreak=True)
        il_u: Universe = Universe(str(self.il_solv))
        il_atoms: AtomGroup = il_u.select_atoms("not resname SOL iSL")
        self.il_solv.universe = il_atoms
        self.il_solv.write(topology=self.top)
        self.il_solv = self.il_solv

    def extend_box(self, backup) -> None:
        """Extend simulation box to specified height.
        :param backup: Whether to back up existing files.
        :type backup: bool
        :return: None"""
        if type(self.args.box_height) in [int, float]:
            if self.args.box_height > self.stack.universe.dimensions[2]:
                logger.finfo(
                    f"Extending simulation box to {self.args.box_height:.1f} {ANGSTROM}"
                )
                self.remove_SOL()
                self.center_clay_in_box()
                self.__box_ext: bool = True
                ext_boxname: GROFile = self.get_filename("ext", suffix=".gro")
                if backup:
                    backup_files(self.args.outpath / ext_boxname.name)
                    backup_files(self.args.outpath / ext_boxname.top.name)
                self.stack.reset_universe()
                box_u: Universe = self.stack.universe
                box_u.universe.dimensions[2] = self.args.box_height
                self.stack: GROFile = ext_boxname
                self.stack.universe = box_u
                self.stack.write(topology=self.top)
                logger.finfo("Centering clay in box", initial_linebreak=False)
                self.center_clay_in_box()
                logger.finfo(
                    f"Saving extended box as {self.stack.stem!r}\n",
                    initial_linebreak=False,
                )
            else:
                self.__box_ext: bool = False
        check_box_lengths(self.em_prms, self.stack.universe.dimensions[:3])

    def remove_SOL(self) -> None:
        """Remove solvent molecules from clay stack.
        :return: None"""
        box_u: Universe = self.stack.universe
        box_u: AtomGroup = box_u.select_atoms("not resname SOL")
        self.stack.universe = box_u
        self.stack.write(topology=self.top)
        add_resnum(crdin=self.stack, crdout=self.stack)
        self.stack.write(topology=self.top)

    def solvate_box(self, extra=1.5, backup=False) -> None:
        """Solvate bulk space.
        :param extra: Offset for solvation.
        :type extra: float
        :param backup: Whether to back up existing files.
        :type backup: bool
        :return: None"""

        if self.extended_box is True:
            logger.finfo("Adding bulk solvation:")
            solv_box_crd: GROFile = self.get_filename("solv", suffix=".gro")
            if backup:
                backup_files(self.args.outpath / solv_box_crd.name)
                backup_files(self.args.outpath / solv_box_crd.top.name)
            self.remove_SOL()
            self.gmx_commands.run_gmx_solvate(
                p=self.stack.top,
                pp=solv_box_crd.top,
                cp=self.stack,
                radius=0.105,
                scale=0.57,
                o=solv_box_crd,
                maxsol=0,
                box="{} {} {}".format(
                    *self.stack.universe.dimensions[:3] * 0.10
                ),
            )
            solv_box_u: Universe = solv_box_crd.universe.copy()
            not_sol: AtomGroup = solv_box_u.select_atoms("not resname SOL")
            sol: AtomGroup = solv_box_u.select_atoms("resname SOL")
            _sol = self.select_molecules_outside_clay(sol, extra=extra)
            logger.finfo(
                f"\tInserted {_sol.n_atoms} {np.unique(_sol.resnames)[0]} molecules"
            )
            sol = _sol
            solv_box_u: AtomGroup = not_sol + sol
            solv_box_crd.universe: Union[
                Universe, AtomGroup, ResidueGroup
            ] = solv_box_u
            solv_box_crd.write(self.top)

            self.stack: GROFile = solv_box_crd
            self.stack.write(self.top)
            logger.finfo(f"Saving solvated box as {self.stack.stem!r}\n")
        else:
            logger.finfo("Skipping bulk solvation.\n")

    @cached_property
    def __ion_sel_str(self) -> str:
        return " ".join(self.args.ff["ions"]["atomtypes"].df["at-type"])

    def remove_bulk_ions(self):
        """Remove ions from bulk space.
        :return: None"""
        stack_u = self.stack.universe
        il_ions = stack_u.select_atoms(f"resname {self.__ion_sel_str}")
        il_ions = self.select_molecules_outside_clay(il_ions, extra=0)
        stack_atoms = stack_u.atoms - il_ions
        self.stack.universe = stack_atoms
        self.stack.write(topology=self.top)

    @property
    def clay(self):
        """Clay atoms.
        :return: AtomGroup of clay atoms.
        :rtype: AtomGroup"""
        return self.stack.universe.select_atoms(
            f"resname {self.args.uc_stem}*"
        )

    def select_molecules_outside_clay(
        self, atomgroup: AtomGroup, extra: Union[int, float] = 0
    ) -> AtomGroup:
        """Select molecules outside clay stack.
        :param atomgroup: AtomGroup to select from.
        :type atomgroup: AtomGroup
        :param extra: Offset to add to clay boundaries.
        :type extra: Union[int, float]
        :return: AtomGroup of molecules outside clay stack.
        :rtype: AtomGroup"""
        atom_group: AtomGroup = select_outside_clay_stack(
            atom_group=atomgroup, clay=self.clay, extra=extra
        )
        residue_groups = atom_group.split("residue")
        for residue_group in residue_groups:
            if residue_group.n_atoms != residue_group.residues.atoms.n_atoms:
                atom_group -= residue_group
        return atom_group

    @property
    def clay_min(self) -> float:
        """Minimum z-coordinate of clay atoms.
        :return: Minimum z-coordinate of clay atoms.
        :rtype: float"""
        return np.min(self.clay.positions[:, 2])

    @property
    def clay_max(self) -> float:
        """Maximum z-coordinate of clay atoms.
        :return: Maximum z-coordinate of clay atoms.
        :rtype: float"""

        return np.max(self.clay.positions[:, 2])

    def add_bulk_ions(self, backup=False) -> None:
        """Add bulk ions to bulk space.
        :param backup: Whether to back up existing files.
        :type backup: bool
        """
        if self.extended_box is True:
            logger.finfo("Adding bulk ions:")
            outcrd: GROFile = self.get_filename("solv", "ions", suffix=".gro")
            if backup:
                backup_files(self.args.outpath / outcrd.name)
                backup_files(self.args.outpath / outcrd.top.name)
            shutil.copy(self.stack, outcrd)
            outcrd.write(topology=self.top)
            self.stack: GROFile = outcrd
            logger.debug(
                f"before n_atoms: {self.stack.universe.atoms.n_atoms}"
            )
            self.remove_bulk_ions()
            logger.debug(f"after n_atoms: {self.stack.universe.atoms.n_atoms}")
            # TODO: use monovalent bulk ion from Ions class
            ion_df: pd.DataFrame = self.args.bulk_ion_df
            pion: str = self.args.default_bulk_pion[0]
            nion: str = self.args.default_bulk_nion[0]
            bulk_x, bulk_y, bulk_z = self.stack.universe.dimensions[:3]
            bulk_z -= np.abs(self.clay_max - self.clay_min)
            replaced: int = 0
            ion_charge = 0
            for ion, values in ion_df.iterrows():
                charge, conc = values
                n_ions: int = np.rint(
                    bulk_z
                    * bulk_x
                    * bulk_y
                    * constants["N_Avogadro"]
                    * conc
                    * 1e-27
                ).astype(
                    int
                )  # 1 mol/L = 10^-27 mol/A
                logger.finfo(
                    f"\tAdding {conc} mol/L ({n_ions} atoms) {ion} ions to bulk"
                )
                logger.debug(
                    f"before n_atoms: {self.stack.universe.atoms.n_atoms}"
                )
                ion_charge += int(charge * n_ions)
                # TODO: use ion df with actual numbers that consider charge
                replaced += add_ions_n_mols(
                    odir=self.__tmp_outpath.name,
                    crdin=self.stack,
                    topin=self.stack.top,
                    ion=ion,
                    charge=int(charge),
                    n_atoms=n_ions,
                    gmx_commands=self.gmx_commands,
                )
                logger.debug(
                    f"after n_atoms: {self.stack.universe.atoms.n_atoms}"
                )
                self.stack.reset_universe()
                self.stack.write(self.top)
            excess_charge = int(self.args.il_ions.clay_charge + ion_charge)
            logger.finfo(f"\tNeutralising charge:")
            if excess_charge != 0:
                neutral_bulk_ions = InterlayerIons(
                    excess_charge,
                    ion_ratios=self.args.bulk_ions,
                    n_ucs=1,
                    neutral=True,
                )
                for ion, values in neutral_bulk_ions.df.iterrows():
                    charge, n_ions = values
                    replaced += add_ions_n_mols(
                        odir=self.__tmp_outpath.name,
                        crdin=self.stack,
                        topin=self.stack.top,
                        ion=ion,
                        charge=int(charge),
                        n_atoms=n_ions,
                        gmx_commands=self.gmx_commands,
                    )
                    logger.debug(
                        f"after n_atoms: {self.stack.universe.atoms.n_atoms}"
                    )
                    logger.finfo(f"\t\tAdded {n_ions} {ion} ions to bulk")
                    self.stack.reset_universe()
                    self.stack.write(self.top)
            logger.debug(f"n_atoms: {self.stack.universe.atoms.n_atoms}")
            logger.finfo(f"\t\tReplaced {replaced} SOL molecules")
            logger.finfo(
                f"Saving solvated box with ions as {self.stack.stem!r}"
            )
            self.stack.reset_universe()
            self.stack.write(self.top)
            processed_top = Path("processed.top")
            processed_top.unlink(missing_ok=True)
        else:
            logger.finfo("\tSkipping bulk ion addition.")

    def stack_sheets(self, extra=2.0, backup=False) -> None:
        try:
            il_crds: GROFile = self.il_solv
            il_u: Universe = il_crds.universe
            if (
                "SOL" in il_u.residues.resnames
                or "iSL" in il_u.residues.resnames
            ):
                for residue in il_u.residues:
                    if residue.resname in ["SOL", "iSL"]:
                        residue.atoms.guess_bonds()
                        assert len(residue.atoms.bonds) == 2
                sol = il_u.select_atoms("resname iSL SOL")
                sol.positions = sol.unwrap(compound="residues")
            il_solv = True
        except AttributeError:
            il_solv = False
        sheet_universes = []
        sheet_heights = []
        if il_solv is not False:
            logger.info(get_subheader("3. Assembling box"))
            logger.finfo("Combining clay sheets and interlayer")
        else:
            logger.finfo("Combining clay sheets")
        for sheet_id in range(self.args.n_sheets):
            self.sheet.n_sheet = sheet_id
            sheet_u = self.sheet.universe.copy()
            sheet_u.dimensions[2] = sheet_u.dimensions[2] + extra
            if il_solv is not False:
                il_u_copy = il_u.copy()
                il_ions = il_u_copy.select_atoms("not resname SOL iSL")
                il_ions.positions = np.roll(il_ions.positions, 3, axis=0)
                if sheet_id == self.args.n_sheets - 1:
                    il_u_copy.residues.resnames = list(
                        map(
                            lambda resname: re.sub("iSL", "SOL", resname),
                            il_u_copy.residues.resnames,
                        )
                    )
                il_u_copy.atoms.translate([0, 0, sheet_u.dimensions[2]])
                new_dimensions: NDArray = sheet_u.dimensions
                sheet_u: Universe = Merge(sheet_u.atoms, il_u_copy.atoms)
                sheet_u.dimensions = new_dimensions
                sheet_u.dimensions[2] = (
                    sheet_u.dimensions[2] + il_u_copy.dimensions[2] + extra
                )
            else:
                sheet_u.dimensions[2] = sheet_u.dimensions[2] + (2 * extra)
            sheet_u.atoms.translate([0, 0, sheet_id * sheet_u.dimensions[2]])
            sheet_universes.append(sheet_u.atoms.copy())
            sheet_heights.append(sheet_u.dimensions[2])
        combined: Universe = Merge(*sheet_universes)
        combined.dimensions = sheet_u.dimensions
        new_dimensions = combined.dimensions
        new_dimensions[2] = np.sum(sheet_heights)
        new_dimensions[3:] = [90.0, 90.0, 90.0]
        combined.dimensions = new_dimensions
        combined.atoms.pack_into_box(box=combined.dimensions, inplace=True)
        crdout: GROFile = self.get_filename(suffix=".gro")
        if backup:
            backup_files(self.args.outpath / crdout.name)
            backup_files(self.args.outpath / crdout.top.name)
        crdout.universe: Universe = combined
        logger.finfo(
            kwd_str=f"\tClay stack height: ",
            message=f"{combined.dimensions[2]:2.2f} {ANGSTROM}",
        )
        crdout.write(self.top)
        add_resnum(crdin=crdout, crdout=crdout)
        self.stack: GROFile = crdout
        logger.finfo(f"Saved sheet stack as {self.stack.stem!r}\n")

    def __path_getter(self, property_name) -> GROFile:
        path = getattr(self, f"__{property_name}")
        if path is not None:
            return path
        else:
            logger.debug(f"No {property_name} filename defined.")

    @property
    def stack(self) -> GROFile:
        """Clay stack GRO filename.
        :return: Clay stack GRO filename.
        :rtype: GROFile"""
        return self.__path_getter("stack")

    @stack.setter
    def stack(self, stack: Union[Path, str, GROFile]) -> None:
        """Set clay stack GRO filename.
        :param stack: Clay stack GRO filename.
        :type stack: Union[Path, str, GROFile]
        :return: None"""
        self.__path_setter_copy("stack", stack, backup=False)

    def write_sheet_crds(self, backup=False) -> None:
        """Write clay sheet coordinates.
        :param backup: Whether to back up existing files.
        :type backup: bool
        :return: None"""
        logger.info(get_subheader("1. Generating clay sheets."))
        for sheet_id in range(self.args.n_sheets):
            self.sheet.n_sheet: int = sheet_id
            self.sheet.write_gro(backup=backup)
        self.sheet.n_sheet = None

    def write_sheet_top(self) -> None:
        """Write clay sheet topology to TOP file.
        :return: None"""
        for sheet_id in range(self.args.n_sheets):
            self.top.reset_molecules()
            self.sheet.n_sheet: int = sheet_id
            self.top.add_molecules(self.sheet.universe)
            self.top.write(self.sheet.get_filename(suffix=".top"))
        self.sheet.n_sheet = None

    def get_filename(
        self,
        *solv_ion_args,
        suffix=None,
        sheetnum: Optional[int] = None,
        tcb_spec=None,
    ) -> Union[GROFile, TOPFile]:
        """Get filename for coordinates/topology.
        :param solv_ion_args: solvation/ion keywords.
        :type solv_ion_args: Any
        :param suffix: Filename suffix.
        :type suffix: Optional[str]
        :param sheetnum: Sheet number.
        :type sheetnum: Optional[int]
        :param tcb_spec: top, center bottom unit cell type specifier.
        :type tcb_spec: Optional[str]
        :return: Filename.
        :rtype: Union[GROFile, TOPFile]"""
        if sheetnum is not None:
            sheetnum: str = f"_{int(sheetnum)}"
        else:
            sheetnum: str = ""
        if tcb_spec is not None:
            if tcb_spec in ["T", "C", "B"]:
                tcb_spec: str = f"_{tcb_spec}"
            else:
                raise ValueError(
                    f'{tcb_spec} was given for "tcb". Accepted '
                    '"tcb_spec" values are "T", "C", "B".'
                )
        else:
            tcb_spec = ""
        solv_ion_list: list = ["solv", "ions"]
        arg_list: list = [s for s in solv_ion_list if s in solv_ion_args]
        other_args: set = set(solv_ion_args) - set(arg_list)
        for a in sorted(other_args):
            arg_list.append(a)
        fstem: str = f"{self.args.filestem}{sheetnum}{tcb_spec}"
        fstem: str = "_".join([fstem, *arg_list])
        try:
            suffix: str = suffix.strip(".")
            suffix: str = f".{suffix}"
        except AttributeError:
            suffix: str = ""
        logger.debug(
            f"{self.__tmp_outpath.name} exists: {Path(self.__tmp_outpath.name).is_dir()}"
        )
        path: Union[TOPFile, GROFile] = FileFactory(
            f"{self.__tmp_outpath.name}/{fstem}{suffix}"
        )
        return path

    @property
    def il_solv(self) -> GROFile:
        return self.__path_getter("il_solv")

    @il_solv.setter
    def il_solv(self, il_solv: Union[Path, str, GROFile]) -> None:
        self.__path_setter_copy("il_solv", il_solv)

    def __path_setter_copy(
        self, property_name: str, file: Union[Path, str, GROFile], backup=False
    ) -> None:
        path: GROFile = getattr(self, property_name, None)
        if path is None:
            path = file
        if path is not None:
            shutil.copy(path, self.args.outpath / path.name)
            logger.debug(
                f"\nResetting {property_name}\nCopied {path.name} to {self.args.outpath.name}"
            )
            try:
                shutil.copy(path.top, self.args.outpath / path.top.name)
            except FileNotFoundError:
                path.write(topology=self.top)
                shutil.copy(path.top, self.args.outpath / path.top.name)
            finally:
                logger.debug(
                    f"Copied {path.top.name} to {self.args.outpath.name}\n"
                )
        file = FileFactory(Path(file).with_suffix(".gro"))
        file.description = f"{file.stem.split('_')[0]} " + " ".join(
            property_name.split("_")
        )
        setattr(self, f"__{property_name}", file)

    def add_il_ions(self) -> None:
        logger.finfo("Adding interlayer ions:", initial_linebreak=True)
        infile: GROFile = self.il_solv
        with tempfile.NamedTemporaryFile(
            suffix=self.il_solv.suffix
        ) as temp_outfile:
            temp_gro: GROFile = GROFile(temp_outfile.name)
            shutil.copy(infile, temp_gro)
            dr: NDArray = self.sheet.dimensions[:3] / 10
            dr[-1] *= 0.4
            if isinstance(self.args.n_il_ions, dict):
                for ion, n_ions in self.args.n_il_ions.items():
                    if n_ions != 0:
                        logger.finfo(f"\tInserting {n_ions} {ion} atoms")
                        with tempfile.NamedTemporaryFile(
                            suffix=".gro"
                        ) as ion_gro:
                            ion_u: Universe = Universe.empty(
                                n_atoms=1,
                                n_residues=1,
                                n_segments=1,
                                atom_resindex=[0],
                                residue_segindex=[0],
                                trajectory=True,
                            )
                            ion_u.add_TopologyAttr("name", [ion])
                            ion_u.add_TopologyAttr("resname", [ion])
                            ion_u.dimensions = np.array(
                                [*self.sheet.dimensions, 90, 90, 90]
                            )
                            ion_u.atoms.positions = np.zeros((3,))
                            ion_u.atoms.write(ion_gro.name)
                            # determine positions for adding ions
                            with tempfile.NamedTemporaryFile(
                                suffix=".dat"
                            ) as posfile:
                                write_insert_dat(
                                    n_mols=n_ions, save=posfile.name
                                )
                                assert Path(posfile.name).is_file()
                                (
                                    insert_err,
                                    insert_out,
                                ) = self.gmx_commands.run_gmx_insert_mols(
                                    f=temp_gro,
                                    ci=ion_gro.name,
                                    ip=posfile.name,
                                    nmol=n_ions,
                                    o=temp_gro,
                                    replace="SOL",
                                    dr="{} {} {}".format(*dr),
                                )
                            center_clay(
                                crdname=temp_gro, crdout=temp_gro, uc_name=ion
                            )
                            _ = Universe(temp_gro)
                            assert Path(temp_gro).is_file()
                            replace_check: int = check_insert_numbers(
                                add_repl="Added", searchstr=insert_err
                            )
                            if replace_check != n_ions:
                                raise ValueError(
                                    f"Number of inserted molecules ({replace_check}) does not match target number "
                                    f"({n_ions})!"
                                )
            infile.universe: Universe = temp_gro.universe
            infile.write(topology=self.top)
            self.il_solv: GROFile = infile

    def center_clay_in_box(self) -> None:
        center_clay(self.stack, self.stack, uc_name=self.args.uc_stem)
        self.stack.reset_universe()


class Sheet:
    def __init__(
        self,
        uc_data: UCData,
        uc_ids: List[int],
        uc_numbers: List[int],
        x_cells: int,
        y_cells: int,
        fstem: str,
        outpath: Path,
        n_sheet: int = None,
    ):
        self.uc_data: UCData = uc_data
        self.uc_ids: list = uc_ids
        self.uc_numbers: list = uc_numbers
        self.dimensions: NDArray = self.uc_data.dimensions[:3] * [
            x_cells,
            y_cells,
            1,
        ]
        self.x_cells: int = x_cells
        self.y_cells: int = y_cells
        self.fstem: str = fstem
        self.outpath: Path = outpath
        self.__n_sheet = None
        self.n_sheet = n_sheet
        self.__random = None

    def __adjust_z_to_bbox(self):
        u_file = self.filename
        u = u_file.universe
        u.atoms.translate([0, 0, self.uc_data.bbox_z_shift])
        u.dimensions[2] = self.uc_data.bbox_height
        u_file.universe = u
        u_file.write()

    def get_filename(self, suffix: str) -> Union[GROFile, TOPFile]:
        return FileFactory(
            self.outpath / f"{self.fstem}_{self.n_sheet}{suffix}"
        )

    @property
    def n_sheet(self) -> Union[int, None]:
        if self.__n_sheet is not None:
            return self.__n_sheet
        else:
            raise AttributeError("No sheet number set!")

    @n_sheet.setter
    def n_sheet(self, n_sheet: int):
        if type(n_sheet) == int:
            self.__n_sheet: int = n_sheet
            self.__random = np.random.default_rng(n_sheet)
        else:
            if n_sheet is not None:
                logger.error(f"Got {n_sheet}: Sheet number must be integer!\n")
            self.__n_sheet = None
            self.__random = None

    @property
    def random_generator(self) -> Union[None, np.random._generator.Generator]:
        if self.__random is not None:
            return self.__random
        else:
            raise AttributeError("No sheet number set!")

    @property
    def uc_array(self) -> NDArray:
        uc_array: NDArray = np.repeat(self.uc_ids, self.uc_numbers)
        return sorted(uc_array)

    @property
    def filename(self) -> GROFile:
        return self.get_filename(suffix=".gro")

    def write_gro(self, backup=False) -> None:
        filename: GROFile = self.filename
        filename.description = (
            f'{self.filename.stem.split("_")[0]} sheet {self.n_sheet}'
        )
        if filename.is_file() and backup:
            logger.debug(
                f"\n{filename.parent}/{filename.name} already exists, creating backup."
            )
            backup_files(filename)
        gro_df: pd.DataFrame = self.uc_data.gro_df
        uc_array = self.uc_array.copy()
        self.random_generator.shuffle(uc_array)
        sheet_df = pd.concat(
            [
                gro_df.filter(regex=f"[A-Z]([A-Z]|[0-9]){uc_id}", axis=0)
                for uc_id in uc_array
            ]
        )
        sheet_df.reset_index(["atom-id"], inplace=True)
        sheet_df["atom-id"] = np.arange(1, len(sheet_df) + 1)
        sheet_df = sheet_df.loc[:, ["at-type", "atom-id", "x", "y", "z"]]
        sheet_n_atoms: int = len(sheet_df)
        sheet_df = sheet_df.astype(
            {
                "at-type": str,
                "atom-id": int,
                "x": float,
                "y": float,
                "z": float,
            }
        )
        with open(filename, "w") as grofile:
            grofile.write(
                f"{self.fstem} sheet {self.n_sheet}\n{sheet_n_atoms}\n"
            )
            for idx, entry in sheet_df.reset_index().iterrows():
                line: list = entry.to_list()
                grofile.write(
                    GRO_FMT.format(
                        *re.split(r"(\d+)", line[0], maxsplit=1)[1:], *line[1:]
                    )
                )
            grofile.write(f"{self.format_dimensions(self.dimensions / 10)}\n")
        add_resnum(crdin=filename, crdout=filename)
        uc_array = self.uc_array.copy()
        self.random_generator.shuffle(uc_array)
        uc_n_atoms: NDArray = (
            np.array([self.uc_data.n_atoms[uc_id] for uc_id in uc_array])
            .reshape(self.x_cells, self.y_cells)
            .astype(np.int32)
        )
        x_repeats: Callable = lambda n_atoms: self.__cells_shift(
            n_atoms=n_atoms, n_cells=self.x_cells
        )
        y_repeats: Callable = lambda n_atoms: self.__cells_shift(
            n_atoms=n_atoms, n_cells=self.y_cells
        )
        x_pos_shift: NDArray = np.ravel(
            np.apply_along_axis(x_repeats, arr=uc_n_atoms, axis=0), order="F"
        )
        y_pos_shift: NDArray = np.ravel(
            np.apply_along_axis(y_repeats, arr=uc_n_atoms, axis=1), order="F"
        )
        new_positions: NDArray = filename.universe.atoms.positions
        new_positions[:, 0] += self.uc_dimensions[0] * x_pos_shift
        new_positions[:, 1] += self.uc_dimensions[1] * y_pos_shift
        new_universe = filename.universe
        new_universe.atoms.positions = new_positions
        logger.finfo(f"Writing sheet {self.n_sheet} to {filename.name}")
        filename.universe = new_universe
        filename.write()
        self.__adjust_z_to_bbox()

    def __cells_shift(self, n_cells: int, n_atoms: int) -> NDArray:
        shift: NDArray = np.atleast_2d(np.arange(n_cells)).repeat(
            n_atoms, axis=1
        )
        return shift

    @staticmethod
    def format_dimensions(dimensions: NDArray) -> str:
        return "".join([f"{dimension:12.4f}" for dimension in dimensions])

    @cached_property
    def uc_dimensions(self) -> NDArray:
        return self.uc_data.dimensions

    @property
    def universe(self) -> Universe:
        return Universe(str(self.get_filename(suffix=".gro")))

    # TODO: add n_atoms and uc data to match data

    def backup(self, filename: Path) -> None:
        sheets_backup: Path = filename.with_suffix(f"{filename.suffix}.1")
        backups = filename.parent.glob(f"*.{filename.suffix}.*")
        for backup in reversed(list(backups)):
            n_backup: int = int(backup.suffices[-1].strip("."))
            new_backup: Path = backup.with_suffix(
                f"{filename.suffix}.{n_backup + 1}"
            )
            shutil.move(backup, new_backup)
        shutil.move(filename, sheets_backup)


class Solvent:
    solv_density = 1000e-27  # g/L 1L = 10E27 A^3
    mw_sol = 18

    @add_gmx_args
    def __init__(
        self,
        x_dim: Optional[Union[int, float]] = None,
        y_dim: Optional[Union[int, float]] = None,
        z_dim: Optional[Union[int, float]] = None,
        n_mols: Optional[Union[int]] = None,
        n_ions: Optional[Union[int]] = None,
        z_padding: float = 0.4,
        min_height: float = 1.5,
    ):
        self.x_dim = float(x_dim)
        self.y_dim = float(y_dim)
        self.min_height = float(min_height)
        if z_dim is None and n_mols is not None:
            self.n_mols = int(n_mols)
            self._z_dim = self.get_solvent_sheet_height(self.n_mols)
        elif n_mols is None and z_dim is not None:
            self._z_dim = float(z_dim)
            self.n_mols = self.get_sheet_solvent_mols(self._z_dim)
        else:
            raise ValueError(
                "No sheet height or number of molecules specified"
            )

        self._z_padding = 0
        self._z_padding_increment = z_padding

        if n_ions is None:
            self.n_ions = 0
        else:
            self.n_ions = n_ions
            self.n_mols += self.n_ions
        self.n_mols: int = int(self.n_mols)

    @property
    def z_dim(self) -> float:
        return self._z_dim + self._z_padding

    @property
    def universe(self) -> Universe:
        universe = getattr(self, "__universe", None)
        return universe

    @property
    def topology(self) -> TopologyConstructor:
        top = getattr(self, "__top", None)
        return top

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.n_mols} molecules, {self.x_dim:.2f} X {self.y_dim:.2f} X {self.z_dim:.2f} {ANGSTROM}))"

    def __str__(self) -> str:
        return self.__repr__()

    def get_solvent_sheet_height(self, mols_sol: int) -> float:
        z_dim = (self.mw_sol * mols_sol) / (
            constants["N_Avogadro"]
            * self.x_dim
            * self.y_dim
            * self.solv_density
        )
        return z_dim

    def get_sheet_solvent_mols(self, z_dim: Union[float, int]) -> int:
        mols_sol = (
            z_dim
            * constants["N_Avogadro"]
            * self.x_dim
            * self.y_dim
            * self.solv_density
        ) / (self.mw_sol)
        return round(mols_sol, 0)

    def top_str(self) -> str:
        return f"SOL\t{self.n_mols}\n"

    def write(
        self, spc_name: GROFile, topology: Optional[TopologyConstructor] = None
    ) -> None:
        """Write solvent sheet to GRO file
        :param spc_name: GROFile object or path to GRO file
        :param topology: TopologyConstructor object
        :return: None
        """
        if spc_name.__class__.__name__ != "GROFile":
            spc_gro: GROFile = GROFile(spc_name)
        else:
            spc_gro: GROFile = spc_name
        spc_top: TOPFile = spc_gro.top
        spc_gro.universe = Universe.empty(n_atoms=0)
        spc_gro.write(topology=topology)
        logger.finfo(f"Adding interlayer solvent:")
        while True:
            if self._z_padding > 5:
                raise Exception(
                    f"\nUnsuccessful solvation after expanding interlayer by {self._z_padding} {ANGSTROM}.\nSomething odd is going on..."
                )

            logger.finfo(
                f"\tAttempting solvation with interlayer height = {self.z_dim:.2f} {ANGSTROM}"
            )
            if self._z_dim < self.min_height:
                self._z_dim = self.min_height
            solv, out = self.gmx_commands.run_gmx_solvate(
                cs="spc216",
                maxsol=self.n_mols,
                o=spc_gro,
                p=spc_top,
                scale=0.57,
                v="",
                box=f"{self.x_dim / 10} {self.y_dim / 10} {(self.z_dim / 10)}",
            )

            # check if a sufficient number of water molecules has been added
            # if not, expand z-axis by 0.5 A and try again
            try:
                self.check_solvent_nummols(solv)
            except Exception as e:
                logger.finfo(kwd_str="\t\t", message=f"{e}")
                self._z_padding += self._z_padding_increment
                logger.finfo(
                    f"\t\tIncreasing box size by {self._z_padding} {ANGSTROM}"
                )
                continue
            else:
                break

        logger.debug(f"Saving solvent sheet as {spc_gro.stem!r}")
        self.__universe: Universe = spc_gro.universe
        self.__top: TopologyConstructor = topology

    def check_solvent_nummols(self, solvate_stderr: str) -> None:
        """Find number of inserted water molecules from GROMAX stderr output
        :param solvate_stderr: GROMACS solvate stderr output
        :type solvate_stderr: str
        :return: None"""
        added_wat: str = re.search(
            r"(?<=Number of solvent molecules:)\s+(\d+)", solvate_stderr
        ).group(1)
        if int(added_wat) < self.n_mols:
            raise ValueError(
                "With chosen box height, GROMACS was only able to "
                f"insert {added_wat} instead of {self.n_mols} water "
                f"molecules."
            )
