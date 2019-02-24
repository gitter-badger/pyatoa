#!/usr/bin/env python3
"""
Map making functionalities

Produces a basemap of target region with beachball representing event,
all available stations with data for the given origin time, relevant station
highlighted, connecting line between station and event, and important
information annotated (e.g. misift information, distance, BAz etc.)
"""
import warnings
import pkg_resources

import numpy as np
import matplotlib as mpl
import matplotlib.cm as cm
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap
from obspy import read_inventory
from obspy.imaging.beachball import beach

from pyatoa.utils.gathering.grab_auxiliaries import hardcode_paths
from pyatoa.utils.operations.source_receiver import gcd_and_baz, parse_inventory
from pyatoa.utils.operations.calculations import myround


mpl.rcParams['font.size'] = 12
mpl.rcParams['lines.linewidth'] = 1.25
mpl.rcParams['lines.markersize'] = 10
mpl.rcParams['axes.linewidth'] = 2


def legend():
    leg = plt.legend(loc="lower right")
    leg.get_frame().set_edgecolor('k')
    leg.get_frame().set_linewidth(1)


def standalone_colorbar(bounds, steps):
    """
    generate a colorbar as a new figure
    TO DO: clean this up and potentially add it into basemap
    """
    fig = plt.figure(figsize=(0.5, 8))
    mpl.rcParams['font.size'] = 25
    mpl.rcParams['axes.linewidth'] = 4

    ax = fig.add_axes([0.2,0.05,0.4,0.75])
    # bounds = range(0,90,10)
    cmap = mpl.cm.get_cmap('jet_r')
    norm = mpl.colors.BoundaryNorm(bounds, cmap.N)
    cb = mpl.colorbar.ColorbarBase(ax, cmap=cmap, norm=norm, extend='max',
                                   orientation='vertical')
    cb.set_label("Event Depth (km)")
    cb.ax.invert_yaxis()
    plt.show()


def place_scalebar(m, map_corners, loc="upper-right"):
    """
    Put the scale bar in the corner at a reasonable distance from each edge
    handy reminder:
        latitude is up down
        longitude is right left

    :type m: Basemap
    :param m: basemap object
    :type map_corners: list of floats
    :param map_corners: [lat_bot,lat_top,lon_left,lon_right]
    """
    if loc == "upper-right":
        latscale = map_corners[0] + (map_corners[1] - map_corners[0]) * 0.94
        lonscale = map_corners[2] + (map_corners[3] - map_corners[2]) * 0.875
    if loc == "lower-right":
        latscale = map_corners[0] + (map_corners[1] - map_corners[0]) * 0.24
        lonscale = map_corners[2] + (map_corners[3] - map_corners[2]) * 0.9
    m.drawmapscale(lonscale, latscale, lonscale, latscale, 100,
                   yoffset=0.01 * (m.ymax-m.ymin), zorder=5000, linewidth=2,
                   fontsize=13
                   )


def build_colormap(array):
    """
    Build a custom range colormap, hardcoded colormap. Round values before.

    :type array: numpy.array
    :param array: array to build colormap from
    :rtype colormap: matplotlib.cm.ScalarMappable
    :return colormap: custom colormap
    """
    vmax = myround(np.nanmax(array), base=1, choice='up')
    vmin = myround(np.nanmin(array), base=1, choice='down')
    norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
    cmap = cm.jet_r
    colormap = cm.ScalarMappable(norm=norm, cmap=cmap)

    return colormap


def scale_magnitude(magitude):
    """
    Short function to standardize magnitude scaling on plots
    :param magitude: float
    :return:
    """
    return

def plot_hikurangi_trench(m):
    """
    Trace the hikurangi trench from a coordinate file

    :type m: Basemap
    :param m: basemap object
    :type path_: str
    :param path_: pathway to hikurangi trench coordinates
    """
    trenchcoords = np.load(
        pkg_resources.resource_filename(
            __name__, "fault_coordinates/hikurangi_trench.npz"))
    lats = trenchcoords['LAT']
    lons = trenchcoords['LON']
    x, y = m(lons, lats)

    # interpolate points to make a smoother curve
    xprime = np.flip(x, axis=0)
    yprime = np.flip(y, axis=0)
    xprimenew = np.linspace(x.min(), x.max(), 100)
    yprimenew = np.interp(xprimenew, xprime, yprime)

    m.plot(xprimenew, yprimenew, ':', linewidth=2.25, color='k', alpha=0.5,
           zorder=2)


def plot_active_faults(m):
    """
    Plot onshore and offshore fault coordinate files taken from GeoNet

    :type m: Basemap
    :param m: basemap object
    :type path_: str
    :param path_: pathway to hikurangi trench coordinates
    """
    int_fid = "fault_coordinates/north_island_550_641_{}.npz"
    for tag in ["onshore", "offshore"]:
        fid = pkg_resources.resource_filename(__name__, int_fid.format(tag))
        active_faults = np.load(fid)
        lats = active_faults['LAT']
        lons = active_faults['LON']
        faults = active_faults['FAULT']

        for i in range(faults.min(), faults.max()+1, 1):
            indices = np.where(faults == i)
            x, y = m(lons[indices], lats[indices])
            m.plot(x, y, '-.', linewidth=1, color='k', zorder=2, alpha=0.25)


def event_beachball(m, event, type="focal_mechanism", **kwargs):
    """
    Plot event beachball for a given geonet moment tensor list,
    read in the from the GeoNet moment tensor csv file.

    :type m: Basemap
    :param m: basemap object
    :type event: obspy.core.event.Event
    :param event: event object which should contain focal mechanism
    """
    width = kwargs.get("width", 2.6E4)
    facecolor = kwargs.get("facecolor", 'r')

    eventx, eventy = m(event.preferred_origin().longitude,
                       event.preferred_origin().latitude
                       )
    if type == "focal_mechanism":
        beach_input = [
            event.focal_mechanisms[0].moment_tensor.tensor['m_rr'],
            event.focal_mechanisms[0].moment_tensor.tensor['m_tt'],
            event.focal_mechanisms[0].moment_tensor.tensor['m_pp'],
            event.focal_mechanisms[0].moment_tensor.tensor['m_rt'],
            event.focal_mechanisms[0].moment_tensor.tensor['m_rp'],
            event.focal_mechanisms[0].moment_tensor.tensor['m_tp']
        ]
    elif type == "strike_dip_rake":
        beach_input = [
            event.focal_mechanisms[0].nodal_planes.nodal_plane_1.strike,
            event.focal_mechanisms[0].nodal_planes.nodal_plane_1.dip,
            event.focal_mechanisms[0].nodal_planes.nodal_plane_1.rake
        ]
    b = beach(beach_input, xy=(eventx, eventy), width=width, linewidth=1,
              facecolor=facecolor)
    b.set_zorder(1000)
    ax = plt.gca()
    ax.add_collection(b)


def plot_stations(m, inv, event=None, **kwargs):
    """
    Fill map with stations based on station availability and network
    TO DO: fix this up and comment it nicely

    :type m: Basemap
    :param m: basemap object
    :type inv: obspy.core.inventory.Inventory
    :param inv: inventory containing relevant network and stations
    :type annotate_names: bool
    :param annotate_names: whether or not station names should placed nearby
    :type color_by_network: bool
    :param color_by_network: decided the coloring of different networks
    """
    annotate_names = kwargs.get("annotate_names", False)
    color_by_network = kwargs.get("color_by_network", False)
    network_codes, station_codes, latitudes, longitudes = parse_inventory(
        inv, event)

    x, y = m(longitudes, latitudes)

    if color_by_network:
        colors, markers = [], []
        color_dict = {"NZ": "red", "XX": "orange", "X1": "green",
                      "X2": "blue", "YH": "m"}
        marker_dict = {"NZ": "^", "XX": "v", "X1": "*",
                      "X2": "d", "YH": "s"}
        label_dict = {"NZ": "NZ (GeoNet)", "XX":"XX (BEACON)",
                      "X1": "X1", "X2": "X2 (SAHKE)", "YH": "YH (HOBITSS)"}
        # for the legend
        for net in color_dict.keys():
            m.scatter(0, 0, marker='v', color=color_dict[net], linestyle='-',
                      s=80, linewidth=1.25, zorder=1, label=label_dict[net]
                      )
        # for the station plot, so we can scatter all at once
        for net in network_codes:
            colors.append(color_dict[net])
        m.scatter(x, y, marker='v', color=colors, edgecolor='k',
                  linestyle='-', s=80, linewidth=1.25, zorder=1001
                  )
    else:
        m.scatter(x, y, marker='v', color='None', edgecolor='k', linestyle='-',
                  s=60, zorder=1001
                  )
    if annotate_names:
        for n_, x_, y_ in zip(station_codes, x, y):
            plt.annotate(n_, xy=(x_, y_), xytext=(x_, y_), zorder=6, fontsize=7,
                         bbox=dict(
                             facecolor='w', edgecolor='k', boxstyle='round')
                         )


def annotate_srcrcv_information(m, event, inv, config):
    """
    Annotate event receiver information into hard coded map area

    :type m: Basemap
    :param m: basemap object
    :type event: obspy.core.event.Event
    :param event: event object
    :type inv: obspy.core.inventory.Inventory
    :param inv: inventory containing relevant network and stations
    :type config: pyatoa.core.config.Config
    :param config: configuration object to steal information from
    """
    event.origins[0].time.precision = 0
    gcdist, baz = gcd_and_baz(event, inv)

    plt.annotate(s=("{id} / {net}.{sta}\n"
                    "{date}\n"
                    "{type}={mag:.2f}\n"
                    "Depth(km)={depth:.2f}\n"
                    "Dist(km)={dist:.2f}\n"
                    "BAz(deg)={baz:.2f}").format(
        id=config.event_id, net=inv[0].code, sta=inv[0][0].code,
        date=event.preferred_origin().time,
        depth=event.preferred_origin().depth*1E-3,
        type=event.preferred_magnitude().magnitude_type,
        mag=event.preferred_magnitude().mag, dist=gcdist, baz=baz
    ),
        xy=(m.xmin + (m.xmax-m.xmin) * 0.675,
            m.ymin + (m.ymax-m.ymin) * 0.035),
        multialignment='right', fontsize=10)


def connect_source_receiver(m, event, sta, **kwargs):
    """
    draw a dashed line connecting the station and receiver, highlight station

    :type m: Basemap
    :param m: basemap object
    :type event: obspy.core.event.Event
    :param event: event object
    :type sta: obspy.core.inventory.Inventory
    :param sta: inventory containing relevant network and stations
    """
    linestyle = kwargs.get("linestyle", "--")
    linewidth = kwargs.get("linewidth", 1.1)
    linecolor = kwargs.get("color", "k")
    marker = kwargs.get("marker", "v")
    markercolor = kwargs.get("markercolor", "r")
    zorder = kwargs.get("zorder", 100)

    event_x, event_y = m(event.preferred_origin().longitude,
                         event.preferred_origin().latitude)
    station_x, station_y = m(sta.longitude, sta.latitude)
    m.plot([event_x, station_x], [event_y, station_y], linestyle, linewidth,
           c=linecolor, zorder=998)
    m.scatter(station_x, station_y, marker=marker, color=markercolor,
              edgecolor='k', linestyle='-', s=75, zorder=zorder)
    m.scatter(event_x, event_y, marker="o", color=markercolor, edgecolor="k",
              s=75, zorder=zorder)


def initiate_basemap(map_corners, scalebar=True, **kwargs):
    """
    set up the basemap object in the same way each time

    :type map_corners: list of floats
    :param map_corners: [lat_bot,lat_top,lon_left,lon_right]
    :rtype m: Basemap
    :return m: basemap object
    """
    continent_color = kwargs.get("contininent_color", "w")
    lake_color = kwargs.get("lake_color", "w")
    coastline_zorder = kwargs.get("coastline_zorder", 5)
    coastline_linewidth = kwargs.get("coastline_linewidth", 1.0)

    # initiate map
    m = Basemap(projection='stere', resolution='h', rsphere=6371200,
                lat_0=np.mean(map_corners[:2]), lon_0=np.mean(map_corners[2:]),
                llcrnrlat=map_corners[0], llcrnrlon=map_corners[2],
                urcrnrlat=map_corners[1], urcrnrlon=map_corners[3],
                )
    m.drawcoastlines(linewidth=coastline_linewidth, zorder=coastline_zorder)
    m.fillcontinents(color=continent_color, lake_color=lake_color)
    m.drawparallels(np.arange(int(map_corners[0]), int(map_corners[1]), 1),
                    labels=[1, 0, 0, 0], linewidth=0.0)
    m.drawmeridians(np.arange(int(map_corners[2]), int(map_corners[3])+1, 1),
                    labels=[0, 0, 0, 1], linewidth=0.0)
    if scalebar:
        place_scalebar(m, map_corners)

    return m


def generate_map(config, event_or_cat, inv=None,
                 map_corners=[-42.5007, -36.9488, 172.9998, 179.5077],
                 **kwargs):
    """
    TODO: change map corners to reflect the new mesh created in August
    TODO: make map_corners a dictionary to keep it less ambiguous?


    initiate and populate a basemap object for New Zealands north island.
    Functionality to manually ignore stations based on user quality control
    Takes station coordinates and coloring from npz files
    Choice to annotate two stations which correspond to waveforms
    Calls beachball and trench tracer to populate basemap

    :type config: pyatoa.core.config.Config
    :param config: configuration object that contains necessary parameters
        to run through the Pyatoa workflow
    :type event: obspy.core.event.Event
    :param event: event object
    :type inv: obspy.core.inventory.Inventory
    :param inv: inventory containing relevant network and stations
    :type map_corners: list of floats
    :param map_corners: [lat_bot,lat_top,lon_left,lon_right]
    :type show: bool
    :param show: show the plot once generated, defaults to False
    :type save: str
    :param save: absolute filepath and filename if figure should be saved
    :type show_faults: bool
    :param show_faults: whether or not to plot faults on map, plotting takes
        extra time compared to no faults
    :rtype f: matplotlib figure
    :return f: figure object
    :rtype m: Basemap
    :return m: basemap object
    """

    figsize = kwargs.get("figsize", (10, 9.4))
    dpi = kwargs.get("dpi", 100)
    show = kwargs.get("show", True)
    save = kwargs.get("save", None)
    annotate_names = kwargs.get("annotate_names", False)
    show_faults = kwargs.get("show_faults", False)
    color_by_network = kwargs.get("color_by_network", False)

    f = plt.figure(figsize=figsize, dpi=dpi)
    m = initiate_basemap(map_corners=map_corners, scalebar=True)

    # next section contains hardcoded paths
    background_inv = read_inventory(hardcode_paths()['stations'])
    if show_faults:
        warnings.warn("Plotting active faults takes some time, "
                      "please be patient", UserWarning)
        plot_hikurangi_trench(m)
        plot_active_faults(m)

    # TO FIX: I messed up all the stuff around here trying to plot a catalog
    # need to fix it up and make sure this mapper can handle both cleanly
    # plot_stations(m, inv=background_inv, event=None,
    #               annotate_names=annotate_names,
    #               color_by_network=color_by_network
    #               )
    # event_beachball(m, event_or_cat)
    plot_catalog(m)

    legend()

    if inv:
        connect_source_receiver(m, event_or_cat, inv[0][0])
        annotate_srcrcv_information(m, event_or_cat, inv[0][0], config)
    if save:
        plt.savefig(save, figsize=figsize, dpi=dpi)
    if show:
        plt.show()

    plt.close()
    return f, m


