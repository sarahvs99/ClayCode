#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r""":mod:`ClayCode.core.consts` --- Constants
============================================
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict

import yaml
from caseless_dictionary import CaselessDict
from importlib_resources import files

__all__ = [
    "exec_time",
    "exec_date",
    "AA",
    "FF",
    "MDP",
    "CLAYS",
    "IONS",
    "SOL",
    "SOL_DENSITY",
    "UCS",
    "FILE_SEARCHSTR_LIST",
    "DATA",
    "USER_MDP",
    "USER_DATA",
    "USER_FF",
    "USER_UCS",
    "USER_CLAYS",
    "MDP_DEFAULTS",
    "ITP_KWDS",
    "LINE_LENGTH",
    "CLAYFF_AT_TYPES",
    "CLAYFF_AT_CHARGES",
    "TABSIZE",
    "ANGSTROM",
]

DATA = files("ClayCode.data.data")
AA = DATA.joinpath("AA")
FF = DATA.joinpath("FF")
MDP = DATA.joinpath("MDP")
CLAYS = DATA.joinpath("CLAYS")
UCS = DATA.joinpath("UCS")

USER_DATA = files("ClayCode.data.user")
USER_MDP = USER_DATA.joinpath("MDP")
USER_FF = USER_DATA.joinpath("FF")
USER_UCS = USER_DATA.joinpath("UCS")
USER_CLAYS = USER_DATA.joinpath("CLAYS")

IONS = ["Cl", "Na", "Ca", "K", "Mg", "Cs"]
SOL_DENSITY = 1000  # g L-1
SOL = "SOL"
GRO_FMT = "{:>5s}{:<5s}{:5s}{:5d}{:8.3f}{:8.3f}{:8.3f}\n"

shandler = logging.StreamHandler()
shandler.setLevel(logging.INFO)

exec_datetime = datetime.now(timezone.utc).strftime("%y%m%d%H%M")
exec_date = datetime.now(timezone.utc).strftime("%y/%m/%d")
exec_time = datetime.now(timezone.utc).strftime("%H:%M")


FILE_SEARCHSTR_LIST = [""]

ITP_KWDS = TOP_KWDS = {
    "defaults": ["nbfunc", "comb-rule", "gen-pairs", "fudgeLJ", "fudgeQQ"],
    "atomtypes": [
        "at-type",
        "at-number",
        "mass",
        "charge",
        "ptype",
        "sigma",
        "epsilon",
    ],
    "bondtypes": ["ai", "aj", "func", "b0", "kb"],
    "pairtypes": ["ai", "aj", "V", "W"],
    "angletypes": ["ai", "aj", "ak", "theta0", "ktheta"],
    "dihedraltypes": ["ai", "aj", "ak", "al", "phi0", "phitheta"],
    "constrainttypes": ["ai", "aj", "b0"],
    "nonbond_params": ["ai", "aj", "V", "W"],
    "moleculetype": ["res-name", "n-excl"],
    "atoms": [
        "id",
        "at-type",
        "res-number",
        "res-name",
        "at-name",
        "charge-nr",
        "charge",
        "mass",
    ],
    "bonds": ["ai", "aj", "funct", "b0", "kb"],
    "pairs": ["ai", "aj", "funct", "theta0", "ktheta"],
    "angles": ["ai", "aj", "ak"],
    "dihedrals": ["ai", "aj", "ak", "al"],
    "system": ["sys-name"],
    "molecules": ["res-name", "mol-number"],
    "settles": ["at-type", "func", "doh", "dhh"],
    "exclusions": ["ai", "aj", "ak"],
    "position_restraints": ["i", "funct", "fcx", "fcy", "fcz"],
}
DTYPES = {
    "at-type": "str",
    "at-number": "int32",
    "ptype": "str",
    "sigma": "float64",
    "epsilon": "float64",
    "id": "int32",
    "res-number": "int32",
    "res-name": "str",
    "at-name": "str",
    "charge-nr": "int32",
    "charge": "float64",
    "mass": "float64",
    "FF": "str",
    "itp": "str",
    "ai": "int16",
    "aj": "int16",
    "ak": "int16",
    "al": "int16",
    "k0": "float64",
    "b0": "float64",
    "kb": "float64",
    "theta0": "float64",
    "ktheta": "float64",
    "phi0": "float64",
    "phitheta": "float64",
    "V": "str",
    "W": "str",
    "nbfunc": "int16",
    "func": "int16",
    "comb-rule": "int16",
    "gen-pairs": "str",
    "fudgeLJ": "float32",
    "fudgeQQ": "float32",
    "n-excl": "int16",
    "doh": "float32",
    "dhh": "float32",
    "funct": "int16",
    "sys-name": "str",
    "mol-number": "int32",
    "fcx": "int32",
    "fcy": "int32",
    "fcz": "int32",
    "i": "int32",
}

GRO_KWDS = {}
MDP_KWDS = {}
TOP_KWDS = ITP_KWDS


def set_globals() -> Dict[str, Dict[str, Any]]:
    """
    Combine '*._KWD' dictionaries and add datatype mapping
    :return: Combined keyword dictionary
    :rtype: Dict[str, Dict[str, str]]
    """
    import re

    combined_dict = {}

    def global_dict(global_key: str) -> Dict[str, Any]:
        return globals()[global_key]

    def del_global(global_key: str):
        globals().__delitem__(global_key)

    kwds = sorted(
        re.findall(r"[A-Z]+_KWDS", " ".join(globals().keys())), reverse=True
    )
    for kwd_dict in kwds:
        kwd = kwd_dict.split("_")[0]
        new_dict = {}
        for key, vals in global_dict(kwd_dict).items():
            new_dict[key] = {}
            for val in vals:
                new_dict[key][val] = global_dict("DTYPES")[val]
        combined_dict[f".{kwd.lower()}"] = new_dict
    del_global("DTYPES")
    return combined_dict


KWD_DICT = set_globals()

with open(MDP / "defaults.yaml", "r+") as yaml_file:
    MDP_DEFAULTS = yaml.safe_load(yaml_file)
    for k, v in MDP_DEFAULTS.items():
        MDP_DEFAULTS[k] = CaselessDict({ki: vi for ki, vi in v.items()})

LINE_LENGTH: int = 100

CLAYFF_AT_TYPES = UCS / "clay_at_types.yaml"
CLAYFF_AT_CHARGES = UCS / "clay_charges.yaml"


TABSIZE = 4

ANGSTROM = "\u212B"
