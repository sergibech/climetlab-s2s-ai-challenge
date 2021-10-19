# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#
import climetlab as cml
import pandas as pd
from climetlab.normalize import DateListNormaliser, EnumListNormaliser

from . import (  # ALIAS_MARSORIGIN,
    ALIAS_FCTYPE,
    ALIAS_ORIGIN,
    DATA,
    DATA_VERSION,
    PATTERN_GRIB,
    PATTERN_NCDF,
    PATTERN_ZARR,
    URL,
    S2sDataset,
)
from .extra import cf_conventions
from .info import Info
from .s2s_mergers import S2sMerger


class FieldS2sDataset(S2sDataset):

    dataset = None

    # @normalize_args(parameter='variable-list(cf)')
    def __init__(self, origin, fctype, parameter, format, dev, version=DATA_VERSION, date=None):
        self._development_dataset = dev
        parameter = cf_conventions(parameter)
        self.origin = ALIAS_ORIGIN[origin.lower()]
        self.fctype = ALIAS_FCTYPE[fctype.lower()]
        self.version = version
        self.default_datelist = self.get_all_reference_dates()
        self.format = {
            "grib": Grib(),
            "netcdf": Netcdf(),
            "zarr": Zarr(),
        }[format]
        self.date = self.parse_date(date)
        parameter = self.parse_parameter(parameter)

        sources = []
        for p in parameter:
            request = self._make_request(p)
            sources.append(self.format._load(request))
        self.source = cml.load_source("multi", sources, merger="merge()")

    @classmethod
    def cls_get_all_reference_dates(cls, origin, fctype):
        return cls._info()._get_config("alldates", origin=origin, fctype=fctype)

    def get_all_reference_dates(self):
        return self._info()._get_config("alldates", origin=self.origin, fctype=self.fctype)

    @classmethod
    def _info(cls):
        return Info(cls.dataset)

    def parse_parameter(self, param):
        parameter_list = self._info().get_param_list(
            origin=self.origin,
            fctype=self.fctype,
        )
        return EnumListNormaliser(parameter_list)(param)

    def parse_date(self, date):
        if date is None:
            date = self.default_datelist
        date = DateListNormaliser("%Y%m%d")(date)
        for d in date:
            pd_date = pd.to_datetime(d)
            if pd_date not in self.default_datelist:
                raise ValueError(f"{d} is not in the available list of dates {self.default_datelist}")
        return date

    def _make_request(self, p):
        dataset = self.dataset
        if self._development_dataset:
            dataset = dataset + '-dev'
        request = dict(
            url=URL,
            data=DATA,
            dataset=dataset,
            origin=self.origin,
            version=self.version,
            parameter=p,
            fctype=self.fctype,
            date=self.date,
        )
        return request


class Grib:
    def _load(self, request):
        options = {
            "chunks": {"time": 1, "latitude": None, "longitude": None, "number": 1, "step": 1},
            "backend_kwargs": {
                "squeeze": False,
                "time_dims": ["time", "step"],  # this is the default in cfgrib
            },
        }

        return cml.load_source("url-pattern", PATTERN_GRIB, request, merger=S2sMerger(engine="cfgrib", options=options))


class Netcdf:
    def _load(self, request):
        return cml.load_source("url-pattern", PATTERN_NCDF, request, merger=S2sMerger(engine="netcdf4"))


class Zarr:
    def _load(self, request, *args, **kwargs):

        from climetlab.utils.patterns import Pattern

        request.pop("date")

        urls = Pattern(PATTERN_ZARR).substitute(request)

        return cml.load_source("zarr-s3", urls)


class TrainingInput(FieldS2sDataset):
    dataset = "training-input"

    def __init__(self, origin="ecmwf", format="netcdf", fctype="hindcast", dev=False, **kwargs):
        super().__init__(format=format, origin=origin, fctype=fctype, dev=dev, **kwargs)


class TestInput(FieldS2sDataset):
    dataset = "test-input"

    def __init__(self, origin="ecmwf", format="netcdf", fctype="forecast", dev=False, **kwargs):
        super().__init__(format=format, origin=origin, fctype=fctype, dev=dev, **kwargs)