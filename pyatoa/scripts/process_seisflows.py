"""
A plugin to seisflows solver.specfem3d_nz.eval_func() to use in evaluating the
misfit functional within the automated workflow, in the context of
requirements mandated by seisflows
"""
import os
import sys
import glob
import pyasdf
import pyatoa
import logging
import argparse
import traceback

from obspy import read_inventory

from pyatoa.utils.operations.pyasdf_editing import clean_ds
from pyatoa.utils.operations.formatting import write_adj_src_to_ascii
from pyatoa.utils.operations.file_generation import create_stations_adjoint


def initialize_parser():
    """
    Seisflows calls pyatoa via subprocess, so we use an argparser to provide
    Pyatoa with information that it requires
    :return:
    """
    parser = argparse.ArgumentParser(description="Inputs for Seisflows")
    parser.add_argument("-i", "--event_id")
    parser.add_argument("-m", "--model_number")
    parser.add_argument("-w", "--working_dir")
    parser.add_argument("-p", "--path_to_synthetics")
    parser.add_argument("-o", "--output_dir")
    parser.add_argument("-l", "--logging", default=True)

    return parser.parse_args()


def set_logging(set_bool=True):
    """
    Turn logging on or off for Pyatoa, lots of information is spit out so for
    fully automatic workflows, best to turn off
    :param set_bool:
    :return:
    """
    if set_bool:
        logger = logging.getLogger("pyatoa")
        logger.setLevel(logging.DEBUG)


def process_data(args):
    """
    Main workflow for Pyatoa to process data
    :param args:
    :return:
    """
    # initiate config using provided arguments
    model_number = args.model_number
    working_dir = args.working_dir
    event_id = args.event_id
    output_dir = args.output_dir

    # make a directory to store generated figures, make the output dir if needed
    fig_dir = os.path.join(output_dir, "figures", model_number, event_id)
    if not os.path.exists(fig_dir):
        os.makedirs(fig_dir)

    # set the pyatoa config object for misfit quantification
    config = pyatoa.Config(
        event_id=event_id, model_number=model_number, min_period=10,
        max_period=30, filter_corners=4, rotate_to_rtz=False,
        unit_output="DISP", pyflex_config="UAF",
        adj_src_type="multitaper_misfit",
        paths_to_synthetics=[os.path.join(os.getcwd(), "test_synthetics")],
        # paths_to_waveforms=[os.path.join(basepath, "primer", "seismic"],
        # paths_to_responses=[os.path.join(basepath, "primer", "seed", "RESPONSE"]
        )

    # initiate pyasdf dataset where all data will be saved
    ds = pyasdf.ASDFDataSet(os.path.join(
        working_dir, "data", "{}.h5".format(config.event_id))
    )
    clean_ds(ds)
    config.write_to_asdf(ds)

    # begin the Pyatoa Workflow, loop through all stations located in the inv.
    mgmt = pyatoa.Manager(config=config, ds=ds)
    master_inventory = read_inventory(os.path.join(
        basepath, "primer", "auxiliary_data", "stationxml",
        "master_inventory_slim.xml")
    )
    for net in master_inventory:
        for sta in net:
            if sta.is_active(time=mgmt.event.preferred_origin().time):
                try:
                    mgmt.gather_data(
                        station_code="{net}.{sta}.{loc}.{cha}".format(
                            net=net.code, sta=sta.code, loc="*", cha="HH?")
                    )
                    mgmt.preprocess()
                    mgmt.run_pyflex()
                    mgmt.run_pyadjoint()
                    mgmt.plot_wav(save=os.path.join(fig_dir, "wav_{sta}".format(
                        sta=sta.code)), show=False
                    )
                    mgmt.plot_map(save=os.path.join(fig_dir, "map_{sta}".format(
                        sta=sta.code)), show=False
                    )
                    mgmt.reset()
                except Exception as e:
                    print("\n")
                    traceback.print_exc()
                    mgmt.reset()
                    continue

    # save adjoint sources to the seisflows scratch directory
    sem_path = os.path.join(working_dir, "traces", "adj")
    write_adj_src_to_ascii(ds, model_number=model_number, filepath=sem_path)
    create_stations_adjoint(ds, model_number=model_number, filepath=sem_path)


if __name__ == "__main__":
    args = initialize_parser()
    set_logging(set=args.logging)
    process_data(args)



