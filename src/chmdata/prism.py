""" Module that downloads monthly PRISM 4kmx4km gridded surface weather day for CONUS 1981-present.
    Contains classes to produce raster of precipitation sesonality index (SI) &
    percent precipitation fallen as snow (PPS) """

import os

import matplotlib.pyplot as plt
import numpy as np
import pyPRISMClimate as ppc
import rasterio as rio
from rasterio.plot import show


class PRISM:
    """
        PRISM data downloader

         PRISM (Parameter-elevation Regressions on Independent Slopes Model) data downloader
         Utilizes the pyPRISMClimate package.

         Note: variables ppt & tmean required for Seasonality index and %precip as snow calc

         Args:
             start_year (int): daily data 1981 to present
             end_year (int): see above
             variable (str): options include 'tmean', 'tmin', 'tmax', 'ppt', 'vpdmon', 'vpdmax'
             root_directory (str): absolute filepath of directory where data is downloaded to
    """

    def __init__(self, start_year: int, end_year: int, variable: str, root_directory: str):
        self.years = list(range(start_year, end_year + 1))
        self.months = list(range(1, 12 + 1))
        self.variable = variable
        self.root_directory = root_directory
        # Ensure the output directory exists
        if not os.path.exists(root_directory):
            os.makedirs(root_directory)
        self.monthly_data()

    def monthly_data(self):
        """ gets averaged monthly 4km rasterized data for given time interval, saves in 'root_directory' """

        print(f"Downloading monthly {self.variable} data ...")
        v_directory = os.path.join(self.root_directory, self.variable)
        if not os.path.exists(v_directory):
            os.makedirs(v_directory)
        try:
            ppc.get_prism_monthlys(
                variable=self.variable,
                years=self.years,
                months=self.months,
                dest_path=v_directory,
                # keep_zip=False  # Crashing when set to True, need to delete zip folders manually
            )
            print("Download complete!")
            print(f"Files saved in: {v_directory}")

        except Exception as e:
            print(f"An error occurred: {e}")
            print(
                "Please ensure you have the pyPRISMClimate library installed and that your internet connection is stable.")
        print("Script finished.")


class SI:
    """
    Calculates Seasonality Index from downloaded monthly PRISM data.

    Calculation for precipitation seasonality index from Imteaz & Hossain 2022:
    https://link.springer.com/article/10.1007/s11269-022-03320-z

    Note: Requires monthly ppt rasters in root directory (see PRISM_data module)

    Args:
        start_year (int): daily data 1981 to present
        end_year (int): see above
        root_directory (str): absolute filepath of root directory where data is downloaded to
    """

    def __init__(self, start_year: int, end_year: int, root_directory: str):
        self.years = list(range(start_year, end_year + 1))
        self.months = list(range(1, 12 + 1))
        self.root_directory = root_directory
        # Ensure directories exist
        self.output_directory = os.path.join(root_directory, 'SI')
        self.precip_directory = os.path.join(root_directory, 'ppt')
        if not os.path.exists(self.output_directory):
            os.makedirs(root_directory)
        if not os.path.exists(self.precip_directory):
            print("No ppt directory")

    def create_file_lists(self) -> list:
        """Compiles list of daily averages from directory"""
        file_list = []
        for m in self.months:
            month_list = []
            for y in self.years:
                file_name = f'PRISM_ppt_stable_4kmM3_{str(y)}{str(m)}_bil.bil'
                month_list.append(file_name)
            file_list.append(month_list)
        print(file_list)
        return file_list

    def get_monthly_averages(self, raster_file_lists: list):
        """Uses output from def create_file_lists to generate monthly average ppt rasters."""
        for month_list in raster_file_lists:
            raster_arrays = []
            for raster_file in month_list:
                path = os.path.join(self.precip_directory, raster_file)
                with rio.open(path) as src:
                    raster_arrays.append(src.read(1).astype(np.float32))  # Read the first band, convert to float
                    profile = src.profile  # Store metadata for output
                summed_array = np.nansum(raster_arrays,
                                         axis=0)  # axis zero sums across arrays, axis 1 sums within array
                ave_array = summed_array / len(raster_arrays)
            print(f"Doing Maths for Month {self.months[raster_file_lists.index(month_list)]}...")

            filename = f'avePPT_month{self.months[raster_file_lists.index(month_list)]}.tif'
            out_path = os.path.join(self.output_directory, filename)
            profile.update(dtype=rio.float32, compress='lzw')
            with rio.open(out_path, 'w', **profile) as dst:
                dst.write(ave_array, 1)

    def get_annual_average(self):
        """Averages monthly ave ppt raster to produce average annual ppt raster."""
        raster_arrays = []
        for m in self.months:
            file = f'avePPT_month{m}.tif'
            path = os.path.join(self.output_directory, file)
            with rio.open(path) as src:
                raster_arrays.append(src.read(1).astype(np.float32))
                profile = src.profile
        summed_array = np.nansum(raster_arrays, axis=0)

        profile.update(dtype=rio.float32, compress='lzw')
        outpath = os.path.join(self.output_directory, 'annual_ppt.tif')
        with rio.open(outpath, 'w', **profile) as dst:
            dst.write(summed_array, 1)

        ave_array = summed_array / len(raster_arrays)
        profile.update(dtype=rio.float32, compress='lzw')
        outpath = os.path.join(self.output_directory, 'ave_month_ppt.tif')
        with rio.open(outpath, 'w', **profile) as dst:
            dst.write(ave_array, 1)

    def calc_seasonality_index(self):
        """Calculates SI from monthly average and annual average rasters, outputs data as raster."""
        month_arrays = []
        for m in self.months:
            file = f'avePPT_month{m}.tif'
            path = os.path.join(self.output_directory, file)
            with rio.open(path) as src:
                month_arrays.append(src.read(1).astype(np.float32))

        file = 'annual_ppt.tif'
        path = os.path.join(self.output_directory, file)
        with rio.open(path) as src:
            annual_array = src.read(1).astype(np.float32)
            profile = src.profile

        file = 'ave_month_ppt.tif'
        path = os.path.join(self.output_directory, file)
        with rio.open(path) as src:
            ave_month_array = src.read(1).astype(np.float32)

        abs_dev_arrays = []
        for a in month_arrays:
            dif = np.subtract(a, ave_month_array)
            abs_ = np.absolute(dif)
            abs_dev_arrays.append(abs_)
        sum_abs_dev_array = np.nansum(abs_dev_arrays, axis=0)
        si = sum_abs_dev_array / annual_array

        outpath = os.path.join(self.output_directory, 'SI.tif')
        with rio.open(outpath, 'w', **profile) as dst:
            dst.write(si, 1)

        return si

    def calc_SI(self):
        """Calculates precip seasonality index skipping intermediary steps, outputs data as raster."""
        raster_file_lists = self.create_file_lists()
        self.get_monthly_averages(raster_file_lists)
        self.get_annual_average()
        self.calc_seasonality_index()

        # # Open raster and plot
        raster_path = os.path.join(self.output_directory, 'SI.tif')
        with rio.open(raster_path) as src:
            raster_data = src.read(1)  # Read the first band
            raster_meta = src.meta
            omit_value = 0
            masked_data = np.where(raster_data == omit_value, np.nan, raster_data)
        fig, ax = plt.subplots()
        show(masked_data, transform=raster_meta['transform'], ax=ax, cmap='viridis')  # You can change the cmap
        ax.set_title('Seasonality Index')
        plt.show()


class PPS:
    """
        Calculates percent precip as snow from downloaded monthly PRISM data.

        Calculation for percent precipitation as snow from McGabe and Wolock 2009:
        https://journals.ametsoc.org/view/journals/eint/13/12/2009ei283.1.xml

        Percent snowfall for values between Train and Tsnow follow a linear gradient,
        default values are provided with the ability to change if desired.

        Note: Seasonality index module must be run prior to running PPS to aggregate precip data

        Args:
            start_year (int): daily data 1981 to present
            end_year (int): see above
            root_directory (str): absolute filepath of root directory where data is downloaded to
            train (int): Temp, in Celsius, at which % precip is 0% snow (default value is 3)
            tsnow (int): Temp, in Celsius, at which % precip is 100% snow (default value is -1)
    """

    def __init__(self, start_year: int, end_year: int, root_directory: str, train: int = 3, tsnow: int = -1):
        self.years = list(range(start_year, end_year + 1))
        self.months = list(range(1, 12 + 1))
        self.root_directory = root_directory
        self.train = train
        self.tsnow = tsnow
        # Ensure directories exist
        self.output_directory = os.path.join(root_directory, 'PPS')
        self.precip_directory = os.path.join(root_directory, 'ppt')
        self.tmean_directory = os.path.join(root_directory, 'tmean')
        if not os.path.exists(self.output_directory):
            os.makedirs(root_directory)
        if not os.path.exists(self.precip_directory):
            print("No ppt directory")
        if not os.path.exists(self.tmean_directory):
            print("No tmean directory")

    def create_file_lists(self) -> list:
        """Compiles list of daily averages (mean temp) from directory"""
        file_list = []
        for m in self.months:
            month_list = []
            for y in self.years:
                file_name = f'PRISM_tmean_stable_4kmM3_{str(y)}{str(m)}_bil.bil'
                month_list.append(file_name)
            file_list.append(month_list)
        print(file_list)
        return file_list

    def get_monthly_averages(self, raster_file_lists: list):
        """Uses output from def create_file_lists to generate monthly average temp rasters."""
        for month_list in raster_file_lists:
            raster_arrays = []
            for raster_file in month_list:
                path = os.path.join(self.tmean_directory, raster_file)
                with rio.open(path) as src:
                    raster_arrays.append(src.read(1).astype(np.float32))  # Read the first band, convert to float
                    profile = src.profile  # Store metadata for output
                summed_array = np.nansum(raster_arrays,
                                         axis=0)  # axis zero sums across arrays, axis 1 sums within array
                ave_array = summed_array / len(raster_arrays)
            print(f"Doing Maths for Month {self.months[raster_file_lists.index(month_list)]}...")

            filename = f'tmean_month{self.months[raster_file_lists.index(month_list)]}.tif'
            out_path = os.path.join(self.output_directory, filename)
            profile.update(dtype=rio.float32, compress='lzw')
            with rio.open(out_path, 'w', **profile) as dst:
                dst.write(ave_array, 1)

    def calc_percent_snow(self):
        """Calculates pps from tmean and ppt raster data, outputs data as raster."""
        month_temp_arrays = []
        for m in self.months:
            file = f'tmean_month{m}.tif'
            path = os.path.join(self.output_directory, file)
            with rio.open(path) as src:
                month_temp_arrays.append(src.read(1).astype(np.float32))

        month_ppt_arrays = []
        for m in self.months:
            file = f'avePPT_month{m}.tif'
            path = os.path.join(self.precip_directory, file)
            with rio.open(path) as src:
                month_ppt_arrays.append(src.read(1).astype(np.float32))

        file = 'annual_ppt.tif'
        path = os.path.join(self.precip_directory, file)
        with rio.open(path) as src:
            annual_ppt = src.read(1).astype(np.float32)
            profile = src.profile

        snow_ratio_arrays = []
        for t in month_temp_arrays:
            ratio = np.copy(t).astype(float)
            ratio = np.where((t > self.tsnow) & (t < self.train), ((self.train - t) / (self.train - self.tsnow)), ratio)
            ratio = np.where(t >= 3, 0, ratio)
            ratio = np.where(t <= -1, 1, ratio)
            snow_ratio_arrays.append(ratio)

        precip_as_snow_arrays = [a * b for a, b in zip(snow_ratio_arrays, month_ppt_arrays)]
        total_snow = np.nansum(precip_as_snow_arrays, axis=0)
        percent_snow = (total_snow / annual_ppt) * 100

        outpath = os.path.join(self.output_directory, 'percent_snow.tif')
        with rio.open(outpath, 'w', **profile) as dst:
            dst.write(percent_snow, 1)

        return percent_snow

    def calc_PPS(self):
        """""Calculates percent precip as snow skipping intermediary steps, outputs data as raster."""

        raster_file_lists = self.create_file_lists()
        self.get_monthly_averages(raster_file_lists)
        self.calc_percent_snow()

        # # Open raster and plot
        raster_path = os.path.join(self.output_directory, 'percent_snow.tif')
        with rio.open(raster_path) as src:
            raster_data = src.read(1)  # Read the first band
            raster_meta = src.meta
            omit_value = 100
            masked_data = np.where(raster_data == omit_value, np.nan, raster_data)
        fig, ax = plt.subplots()
        show(masked_data, transform=raster_meta['transform'], ax=ax, cmap='viridis')
        ax.set_title('% Precip as Snow')

        plt.show()
