from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window
from pyproj import Transformer


class DEMDataset:
    def __init__(self, path):
        self.path = path
        self.ds = rasterio.open(path)
        self.transformer = Transformer.from_crs(
            "EPSG:4326",
            self.ds.crs,
            always_xy=True
        )

    def contains(self, lat, lon):
        x, y = self.transformer.transform(lon, lat)

        return (
            self.ds.bounds.left <= x <= self.ds.bounds.right
            and
            self.ds.bounds.bottom <= y <= self.ds.bounds.top
        )

    def elevation(self, lat, lon):
        x, y = self.transformer.transform(lon, lat)

        row, col = self.ds.index(x, y)

        if (
            0 <= row < self.ds.height
            and
            0 <= col < self.ds.width
        ):
            value = self.ds.read(1, window=Window(col, row, 1, 1))
            z = float(value[0, 0])
            return np.nan if z == self.ds.nodata else z

        return np.nan


class DEMManager:
    def __init__(self):
        self.high_res = []
        self.low_res = []

        self.load_directory("dem_13", self.high_res)
        self.load_directory("dem_1", self.low_res)

    def load_directory(self, dirname, dataset_list):
        path = Path(dirname)

        if not path.exists():
            return

        for tif in path.glob("*.tif"):
            dataset_list.append(DEMDataset(tif))

    def elevation_at(
        self,
        lat,
        lon,
        distance_m,
        local_radius_m=30000
    ):
        for dem in self.high_res:
            if dem.contains(lat, lon):
                z = dem.elevation(lat, lon)
                if not np.isnan(z):
                    return z

        for dem in self.low_res:
            if dem.contains(lat, lon):
                z = dem.elevation(lat, lon)
                if not np.isnan(z):
                    return z

        return np.nan