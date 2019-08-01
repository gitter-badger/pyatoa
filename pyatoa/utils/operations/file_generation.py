"""
For generation of input files for Specfem, or for any external files required
for codes that interact with Pyatoa
"""
import os
import glob
import json
import time
import numpy as np


def write_misfit_json(ds, model, step_count=0, fidout="./misfits.json"):
    """
    Write a .json file containing misfit information for a given dataset,
    model and step count. Sums misfit, number of windows, and number of
    adjoint sources for a given event, model and step.
    ---
    NOTE:
    Operates on a crude file lock system, which renames the .json file to keep
    other compute nodes from accessing a file being written.
    If this function crashes while writing, Pyatoa will get stuck in a loop,
    and Seisflows will need to be stopped and resumed.
    
    Before this, make sure /path/to/misfits.json_lock is removed or renamed.
    ---

    As per Tape (2010) Eq. 7, the total misfit function F^T is given as:
            F^T(m) = (1/S) * sum[s=1:S] (F^T_s(m))
    
    where S is the number of sources

    :type ds: pyasdf.ASDFDataSet
    :param ds: processed dataset, assumed to contain auxiliary_data.Statistics
    :type model: str
    :param model: model number, e.g. "m00"
    :type step_count: int
    :param step_count: line search step count
    :type fidout: str
    :param fidout: output file to write the misfit
    """
    # organize information to be written
    step = "s{:0>2}".format(step_count)
    stats = ds.auxiliary_data.Statistics[model][step].parameters
    misfit = ds.auxiliary_data.Statistics[model][step].data.value[0]
    windows = stats["number_misfit_windows"]
    adjsrcs = stats["number_adjoint_sources"]
    event_id = os.path.basename(ds.filename).split(".")[0]
   
    # build nested dictioanaries 
    event_dict = {"misfit": float(misfit), 
                  "windows": int(windows), 
                  "adjsrcs": int(adjsrcs)
                  }
    step_dict = {"{}".format(event_id): event_dict}
    model_dict = {"{}".format(step): step_dict}
    misfit_dict = {model: model_dict}
    
    # To allow multiple cpu's clean, simultaenous write capability, create a 
    # lock file that can only be accessed by one cpu at a time
    fidout_lock = fidout + "_lock"
    while True:
        # another process has control of the misfit file
        if os.path.exists(fidout_lock):
            # print("file is locked, waiting")
            time.sleep(5)
        # misfit file is available for writing
        elif os.path.exists(fidout) and not os.path.exists(fidout_lock):
            # print("file is available at {}".format(time.asctime()))
            os.rename(fidout, fidout_lock)
            with open(fidout_lock, "r") as f:
                misfit_dict = json.load(f)
                if model in misfit_dict.keys():
                    if step in misfit_dict[model].keys():
                        misfit_dict[model][step][event_id] = event_dict
                    else:
                        misfit_dict[model][step] = step_dict
                else:
                    misfit_dict[model] = model_dict
       
                # Parse misfit dict to give the total misfit
                misfits, windows_all, adjsrcs_all = [], [], []
                for key in misfit_dict[model][step].keys():
                    if key in ["misfit", "windows", "adjsrcs"]:
                        continue
                    misfits.append(misfit_dict[model][step][key]["misfit"])
                    windows_all.append(misfit_dict[model][step][key]["windows"])
                    adjsrcs_all.append(misfit_dict[model][step][key]["adjsrcs"])

                misfit_dict[model][step]["misfit"] = sum(misfits)/len(misfits)
                misfit_dict[model][step]["windows"] = sum(windows_all)
                misfit_dict[model][step]["adjsrcs"] = sum(adjsrcs_all)
                f.close()
    
            # rewrite new misfit into lock file, then rename when finished
            with open(fidout_lock, "w") as f:
                json.dump(misfit_dict, f, indent=4, separators=(',', ':'), 
                          sort_keys=True)
                f.close()
            os.rename(fidout_lock, fidout)   
            return
        # misfit file has not been written yet
        else:
            # print("file has not been written")
            with open(fidout, "w") as f:
                json.dump(misfit_dict, f, indent=4, separators=(',', ':'),
                          sort_keys=True)
            return

         
def write_misfit_stats(ds, model, pathout="./", fidout=None):
    """
    A simpler alternative to write_misfit_json()

    This function simply writes a new text file for each event, which contains 
    the total misfit for that event.

    e.g. path/to/misfits/{model_number}/{event_id}
    
    These files will then need to be read by: seisflows.workflow.write_misfit()

    :type ds: pyasdf.ASDFDataSet
    :param ds: processed dataset, assumed to contain auxiliary_data.Statistics
    :type model: str
    :param model: model number, e.g. "m00"
    :type pathout: str
    :param pathout: output path to write the misfit. fid will be the event name
    :type fidout: str
    :param fidout: allow user defined filename, otherwise default to name of ds
        note: if given, var 'pathout' is not used, this must be a full path
    """
    from pyatoa.utils.asdf.extractions import sum_misfits

    # By default, name the file after the name of the asdf dataset
    if fidout is None:
        event_id = os.path.basename(ds.filename).split(".")[0]
        fidout = os.path.join(pathout, event_id)
    
    # calculate misfit 
    misfit = sum_misfits(ds, model)

    # save in the same format as seisflows 
    np.savetxt(fidout, [misfit], '%11.6e')

           
def create_srcrcv_vtk_single(ds, model, pathout, event_separate=False,
                             utm_zone=60):
    """
    It's useful to visualize source receiver locations in Paraview, alongside
    sensitivity kernels. VTK files are produced by Specfem, however they are for
    all receivers, and a source at depth which is sometimes confusing. 

    -This function will create source_receiver vtk files using the asdf h5 files
    with only those receiver that were used in the misfit analysis, and only
    an epicentral source location, such that the source is visible on a top
    down view from Paraview.
    -Useful for visualizing event kernels
    -Gives the option to create an event vtk file separate to receivers, for
    more flexibility in the visualization.
    
    :type ds: pyasdf.ASDFDataSet
    :param ds: pyasdf dataset outputted by pyatoa
    :type model: str
    :param model: model number, e.g. 'm00'
    :type pathout: str
    :param pathout: output path to save vtk file
    :type event_separate: str
    :param event_separate: if event vtk file to be made separately
    :type utm_zone: int
    :param utm_zone: the utm zone of the mesh, 60 for NZ
    """
    from pyatoa.utils.operations.source_receiver import lonlat_utm

    # Check that this can be run, if dataset contains adjoint sources
    if not bool(ds.auxiliary_data.AdjointSources):
        return

    # Some information that is used a few times
    vtk_header = ("# vtk DataFile Version 2.0\n"
                  "Source and Receiver VTK file from Pyatoa\n"
                  "ASCII\n"
                  "DATASET POLYDATA\n"
                  )

    # Get receiver location information in lat-lon,
    event_id = os.path.basename(ds.filename).split(".")[0]
    sta_x, sta_y, sta_elv, sta_ids = [], [], [], []

    for adjsrc in ds.auxiliary_data.AdjointSources[model].list():
        sta = ds.auxiliary_data.AdjointSources[model][adjsrc]

        # make sure no repeat stations
        if sta.parameters["station_id"] in sta_ids:
            continue

        # Convert lat lon to UTM
        x, y = lonlat_utm(lon_or_x=sta.parameters["longitude"],
                          lat_or_y=sta.parameters["latitude"],
                          utm_zone=utm_zone, inverse=False)
        sta_x.append(x)
        sta_y.append(y)
        sta_elv.append(sta.parameters["elevation_in_m"])
        sta_ids.append(sta.parameters["station_id"])

    # Get event location information in UTM
    ev_x, ev_y = lonlat_utm(lon_or_x=ds.events[0].preferred_origin().longitude,
                            lat_or_y=ds.events[0].preferred_origin().latitude,
                            utm_zone=utm_zone, inverse=False
                            )
    # set event epicentral depth to 100km to keep it above topography
    ev_elv = 100.

    # Write header for VTK file and then print values for source receivers
    fid_out = os.path.join(pathout, "{}_{}.vtk".format(event_id, model))
    with open(fid_out, "w") as f:
        f.write(vtk_header)
        # num points equal to number of stations plus 1 event
        f.write("POINTS\t{} float\n".format(len(sta_x)+1))
        f.write("{X:18.6E}{Y:18.6E}{E:18.6E}\n".format(
            X=ev_x, Y=ev_y, E=ev_elv)
        )
        for x, y, e in zip(sta_x, sta_y, sta_elv):
            f.write("{X:18.6E}{Y:18.6E}{E:18.6E}\n".format(X=x, Y=y, E=e))

    # Make a separate VTK file for the source
    if event_separate:
        event_fid_out = os.path.join(
                             pathout, "{}_{}_event.vtk".format(event_id, model))
        with open(event_fid_out, "w") as f:
            f.write(vtk_header)
            f.write("POINTS\t1 float\n")
            f.write("{X:18.6E}{Y:18.6E}{E:18.6E}\n".format(
                X=ev_x, Y=ev_y, E=ev_elv)
            )


def create_srcrcv_vtk_multiple(pathin, pathout, model, utm_zone=60):
    """
    Same as create_srcrcv_vtk_single, except instead of taking an asdf
    dataset input, takes a path, reads in datasets and creates one
    large vtk file containing all stations and all events.

    -Useful for visualizations of misfit kernels and gradients.
    -Automatically creates a separate event vtk file.

    :type pathin: str
    :param pathin: path containing .h5 files, will loop through all
        available h5 files in the folder
    :type model: str
    :param model: model number, e.g. 'm00'
    :type pathout: str
    :param pathout: output path to save vtk file
    :type utm_zone: int
    :param utm_zone: the utm zone of the mesh, 60 for NZ
    """
    import pyasdf
    from pyatoa.utils.operations.source_receiver import lonlat_utm

    vtk_header = ("# vtk DataFile Version 2.0\n"
                  "Source and Receiver VTK file from Pyatoa\n"
                  "ASCII\n"
                  "DATASET POLYDATA\n"
                  "POINTS\t{} float\n""
                  )
    vtk_line = "{X:18.6E}{Y:18.6E}{E:18.6E}\n"

    # Loop through available datasets
    datasets = glob.glob(os.path.join(pathin, '*.h5'))
    if not datasets:
        return

    event_ids, sta_ids = [], []
    ev_x, ev_y, sta_x, sta_y, sta_elv = [], [], [], [], []
    for fid in datasets:
        with pyasdf.ASDFDataSet(fid) as ds:
            # Check if dataset contains adjoint sources
            if not bool(ds.auxiliary_data.AdjointSources):
                continue
            
            # Loop through stations with adjoint sources
            if hasattr(ds.auxiliary_data.AdjointSources, model):
                for adjsrc in ds.auxiliary_data.AdjointSources[model].list():
                    sta = ds.auxiliary_data.AdjointSources[model][adjsrc]

                    # make sure no repeat stations
                    if sta.parameters["station_id"] in sta_ids:
                        continue

                    # Convert lat lon to UTM
                    sx, sy = lonlat_utm(lon_or_x=sta.parameters["longitude"],
                                        lat_or_y=sta.parameters["latitude"],
                                        utm_zone=utm_zone, inverse=False
                                        )
                    sta_x.append(sx)
                    sta_y.append(sy)
                    sta_elv.append(sta.parameters["elevation_in_m"])
                    sta_ids.append(sta.parameters["station_id"])
            else:
                continue

            # Get event location information in UTM
            event_id = os.path.basename(ds.filename).split(".")[0]
            ex, ey = lonlat_utm(
                lon_or_x=ds.events[0].preferred_origin().longitude,
                lat_or_y=ds.events[0].preferred_origin().latitude,
                utm_zone=utm_zone, inverse=False
            )
            event_ids.append(event_id)
            ev_x.append(ex)
            ev_y.append(ey)

    # set event epicentral depth to 100km to keep it above topography
    ev_elv = 100.

    # Write header for VTK file and then print values for source receivers
    fid_out = os.path.join(pathout, "rcvs_{}.vtk".format(model))
    with open(fid_out, "w") as f:
        f.write(vtk_header.format(len(sta_x) + len(ev_x)))
        # Loop through events
        for ex, ey in zip(ev_x, ev_y):
            f.write(vtk_line.format(X=ex, Y=ey, E=ev_elv))
        # Loop through stations
        for sx, sy, se in zip(sta_x, sta_y, sta_elv):
            f.write(vtk_line.format(X=sx, Y=sy, E=se))

    # Make a separate VTK file for all events so they can be formatted different
    event_fid_out = os.path.join(pathout, "srcs.vtk")
    if not os.path.exists(event_fid_out):
        with open(event_fid_out, "w") as f:
            f.write(vtk_header.format(len(ev_x)))
            for ex, ey in zip(ev_x, ev_y):
                f.write(vtk_line.format(X=ex, Y=ey, E=ev_elv))

    # Make a separate VTK file for each event.
    # This only needs to be run once so just skip over if the files exist
    for event_id, ex, ey in zip(event_ids, ev_x, ev_y):
        event_fid_out = os.path.join(pathout, "{}.vtk".format(event_id))
        if os.path.exists(event_fid_out):
            continue
        with open(event_fid_out, "w") as f:
            f.write(vtk_header.format(len(ev_x)))
            f.write(vtk_line.format(X=ex, Y=ey, E=ev_elv))



def create_stations_adjoint(ds, model, specfem_station_file, pathout=None):
    """
    Generate an adjoint stations file for Specfem input by reading in the master
    station list and checking which adjoint sources are available in the
    pyasdf dataset
    
    :type ds: pyasdf.ASDFDataSet
    :param ds: dataset containing AdjointSources auxiliary data
    :type model: str
    :param model: model number, e.g. "m00"
    :type specfem_station_file: str
    :param specfem_station_file: path/to/specfem/DATA/STATIONS
    :type pathout: str
    :param pathout: path to save file 'STATIONS_ADJOINT'
    """
    event_id = os.path.basename(ds.filename).split('.')[0]

    # Check which stations have adjoint sources
    stas_with_adjsrcs = []
    for code in ds.auxiliary_data.AdjointSources[model].list():
        stas_with_adjsrcs.append(code.split('_')[1])
    stas_with_adjsrcs = set(stas_with_adjsrcs)

    # Figure out which stations were simulated
    with open(specfem_station_file, "r") as f:
        lines = f.readlines()

    # if no output path is specified, save into current working directory with
    # an event_id tag to avoid confusion with other files, else normal naming
    if pathout is None:
        write_out = "./STATIONS_ADJOINT_{}".format(event_id)
    else:
        write_out = os.path.join(pathout, "STATIONS_ADJOINT")

    # Rewrite the Station file but only with stations that contain adjoint srcs
    with open(write_out, "w") as f:
        for line in lines:
            if line.split()[0] in stas_with_adjsrcs:
                    f.write(line)


def write_adj_src_to_ascii(ds, model, pathout=None, comp_list=["N", "E", "Z"]):
    """
    Take AdjointSource auxiliary data from a pyasdf dataset and write out
    the adjoint sources into ascii files with proper formatting, for input
    into PyASDF

    Note: Specfem dictates that if a station is given as an adjoint source,
        all components must be present, even if some components don't have
        any misfit windows. This function writes blank adjoint sources (0's)
        to satisfy this requirement.

    :type ds: pyasdf.ASDFDataSet
    :param ds: dataset containing adjoint sources
    :type model: str
    :param model: model number, e.g. "m00"
    :type pathout: str
    :param pathout: path to write the adjoint sources to
    :type comp_list: list of str
    :param comp_list: component list to check when writing blank adjoint sources
        defaults to N, E, Z, but can also be e.g. R, T, Z
    """
    import numpy as np

    def write_to_ascii(f, array):
        """
        Function used to write the ascii in the correct format

        :type f: _io.TextIO
        :param f: the open file to write to
        :type array: numpy.ndarray
        :param array: array of data from obspy stream
        """
        for dt, amp in array:
            if dt == 0. and amp != 0.:
                dt = 0
                adj_formatter = "{dt:>14}{amp:18.6f}\n"
            elif dt != 0. and amp == 0.:
                amp = 0
                adj_formatter = "{dt:14.6f}{amp:>18}\n"
            else:
                adj_formatter = "{dt:14.6f}{amp:18.6f}\n"

            f.write(adj_formatter.format(dt=dt, amp=amp))

    # Shortcuts
    adjsrcs = ds.auxiliary_data.AdjointSources[model]
    event_id = ds.filename.split('/')[-1].split('.')[0]

    # Set the path to write the data to.
    # If no path is given, default to current working directory
    if pathout is None:
        pathout = os.path.join("./", event_id)
    if not os.path.exists(pathout):
        os.makedirs(pathout)

    # Loop through adjoint sources and write out ascii files
    already_written = []
    for adj_src in adjsrcs.list():
        station = adj_src.replace('_', '.')
        fid = os.path.join(pathout, "{}.adj".format(station))
        with open(fid, "w") as f:
            write_to_ascii(f, adjsrcs[adj_src].data.value)

        # Write blank adjoint sources for components with no misfit windows
        for comp in comp_list:
            station_blank = (adj_src[:-1] + comp).replace('_', '.')
            if station_blank.replace('.', '_') not in adjsrcs.list() and \
                    station_blank not in already_written:
                # Use the same adjoint source, but set the data to zeros
                blank_adj_src = adjsrcs[adj_src].data.value
                blank_adj_src[:, 1] = np.zeros(len(blank_adj_src[:, 1]))

                # Write out the blank adjoint source
                fid_blank = os.path.join(
                    pathout, "{}.adj".format(station_blank)
                )
                with open(fid_blank, "w") as b:
                    write_to_ascii(b, blank_adj_src)

                # Append to a list to make sure we don't write doubles
                already_written.append(station_blank)

