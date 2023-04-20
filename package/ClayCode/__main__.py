#!/usr/bin/env python3
import sys

from ClayCode import logger
from ClayCode.core.parsing import parser, ArgsFactory, BuildArgs
from ClayCode.core.utils import get_header, get_subheader

__all__ = ['run']

def run():
    args = parser.parse_args(
        sys.argv[1:]
    )
    logger.setLevel(args.DEBUG)
    args_factory = ArgsFactory()
    args = args_factory.init_subclass(args)
    if isinstance(args, BuildArgs):
        from ClayCode.builder import Builder

        clay_builder = Builder(args)
        clay_builder.write_sheet_crds()
        if args.il_solv is False and args.match_charge["tot"] == 0:
            pass
        elif args.il_solv is True or args.match_charge["tot"] != 0:
            clay_builder.solvate_clay_sheets()
        if args.match_charge["tot"] != 0:
            clay_builder.add_il_ions()
            if args.il_solv is False:
                clay_builder.remove_il_solv()
            else:
                clay_builder.rename_il_solv()
        clay_builder.stack_sheets()
        clay_builder.extend_box()
        completed = False
        while completed is False:
            if args.bulk_solv is True:
                clay_builder.solvate_box()
            if not args.bulk_ion_conc == 0.0:
                clay_builder.add_bulk_ions()
            clay_builder.center_clay_in_box()
            completed = clay_builder.run_em()
            if completed is None:
                if clay_builder.extended_box is True:
                    repeat = None
                    while repeat not in ["y", "n"]:
                        repeat = input("Repeat solvation setup? [y/n]\n")
                    if repeat == "y":
                        completed = False
                        logger.info(get_subheader('Repeating solvation'))
            elif completed is False:
                logger.info("\nRepeating solvation setup.\n")
            else:
                logger.info(completed)
        clay_builder.conclude()


    # if PRMS.build:
    #     from package.builder.builder import ModelBuilder
    #     ModelBuilder().run()
    #
    # if PRMS.siminp:
    #     from package.siminp.siminp import SiminpWriter
    #     SiminpWriter().run()
    #
    # # builder = BuildParams()
    # # if builder.builder == "new":
    # #     if not builder.hasattr("uc_dict"):
    # #         ions_ff = ForceField(builder.FF['ions'])
    # #         clay_ff = ForceField(builder.FF['clay'])
    # #         exp = ExpComposition(builder._target_comp,
    # #                              ions_ff)
    # #         ratios = ElementRatios(
    # #             builder._target_comp,
    # #             builder.clay_type,
    # #             builder.x_cells,
    # #             builder.y_cells,
    # #             builder.outpath,
    # #             builder.sysname,
    # #         )

if __name__ == "__main__":
    run()