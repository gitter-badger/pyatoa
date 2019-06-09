"""
Convenience function for editing Pyasdf ASDFDataSet objects. All functions
work with the dataset as an input and act in-place on the dataset so no returns
"""


def clean_ds(ds, model=None):
    """
    Removes synthetic waveforms and auxiliary data so that only observation
    data remains for new model runs. If no model nmber is given, will wipe
    all non-observation data and all auxiliary data
    
    :type ds: pyasdf.ASDFDataSet
    :param ds: dataset to be cleaned
    :type model: str
    :param model: model number, e.g. "m00"
    """
    del_synthetic_waveforms(ds=ds, model=model)
    del_auxiliary_data(ds=ds, model=model)


def del_synthetic_waveforms(ds, model=None):
    """
    Remove "synthetic_{model}" tagged waveforms from an asdf dataset.
    If no model number given, wipes all synthetic data from dataset.   
 
    :type ds: pyasdf.ASDFDataSet
    :param ds: dataset to be cleaned
    :type model: str
    :param model: model number, e.g. "m00"
    """
    for sta in ds.waveforms.list():
        for stream in ds.waveforms[sta].list():
            if "synthetic" in stream:
                if (model is not None) and model in stream:
                    del ds.waveforms[sta][stream]
                elif model is None:
                    del ds.waveforms[sta][stream]


def del_auxiliary_data(ds, model=None):
    """
    Delete all items in auxiliary data for a given model, if model not given,
    wipes all auxiliary data.
    
    :type ds: pyasdf.ASDFDataSet
    :param ds: dataset to be cleaned
    :type model: str
    :param model: model number, e.g. "m00"
    """
    
    for aux in ds.auxiliary_data.list():
        if model:
            try: 
                del ds.auxiliary_data[aux][model]
            except KeyError:
                pass
        else:    
            del ds.auxiliary_data[aux]


def del_adjoint_sources(ds, model=None):
    """
    Delete adjoint sources from auxiliary data by model. Wipe all if no model
    
    :type ds: pyasdf.ASDFDataSet
    :param ds: dataset to be cleaned
    :type model: str
    :param model: model number, e.g. "m00"
    """
    if model:
        for comp in ds.auxiliary_data.AdjointSources[model].list():
            del ds.auxiliary_data.AdjointSources[model][comp]
    else:
        for model in ds.auxiliary.data.AdjointSources.list():
            for comp in ds.auxiliary_data.AdjointSources[model].list():
                del ds.auxiliary_data.AdjointSources[model][comp]


def del_misfit_windows(ds, model=None):
    """
    Delete misfit windows from auxiliary data by model. Wipe all if no model
    
    :type ds: pyasdf.ASDFDataSet
    :param ds: dataset to be cleaned
    :type model: str
    :param model: model number, e.g. "m00"
    """
    if model:
        for comp in ds.auxiliary_data.MisfitWindows[model].list():
            del ds.auxiliary_data.MisfitWindows[model][comp]
    else:
        for model in ds.auxiliary.data.MisfitWindows.list():
            for comp in ds.auxiliary_data.MisfitWindows[model].list():
                del ds.auxiliary_data.MisfitWindows[model][comp]


def del_configs(ds, model=None):
    """
    Delete configs from auxiliary data by model. Wipe all if no model
    
    :type ds: pyasdf.ASDFDataSet
    :param ds: dataset to be cleaned
    :type model: str
    :param model: model number, e.g. "m00"
    """
    if model:
        for comp in ds.auxiliary_data.Configs[model].list():
            del ds.auxiliary_data.Configs[model][comp]
    else:
        for model in ds.auxiliary.data.Configs.list():
            for comp in ds.auxiliary_data.Configs[model].list():
                del ds.auxiliary_data.Configs[model][comp]



