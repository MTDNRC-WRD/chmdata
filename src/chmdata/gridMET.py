"""
Module with functions to output netCDF and GeoTiff of averaged 1-year aggregate data (e.g. spei, spi)
or calculate yearly totals from daily data (e.g. pet, precip) and average yearly totals"""


import os

import matplotlib.pyplot as plt  # For optional visualization
import numpy as np
import xarray as xr
from tqdm import tqdm


def average_timeseries(
        opendap_url: str,
        start_year: int,
        end_year: int,
        variable_name: str = 'spei1y',
        output_dir: str = '.',
        bbox_west: float = -116.0,
        bbox_south: float = 44.0,
        bbox_east: float = -104.0,
        bbox_north: float = 49.5
):
    """
    Downloads SPEI data from Gridmet OPeNDAP for a specified time range,
    averages each pixel over that timeframe, and saves the result as a NetCDF raster.

    Args:
        opendap_url (str): The OPeNDAP URL for the Gridmet SPEI dataset (e.g., SPEI12).
        start_year (int): The starting year for the averaging period (inclusive).
        end_year (int): The ending year for the averaging period (inclusive).
        variable_name (str): The name of the SPEI variable in the dataset (e.g., 'spei').
        output_dir (str): Directory to save the output NetCDF file.
        bbox_west (float): Western longitude bound of the area of interest.
        bbox_south (float): Southern latitude bound.
        bbox_east (float): Eastern longitude bound.
        bbox_north (float): Northern latitude bound.
    """
    print(f"Starting averaging process for {start_year}-{end_year}...")
    print(f"OPeNDAP URL: {opendap_url}")
    print(f"Variable: {variable_name}")
    print(f"Bounding Box: W:{bbox_west}, S:{bbox_south}, E:{bbox_east}, N:{bbox_north}")

    output_base_name = f'avg_total_{variable_name}_{start_year}-{end_year}'
    output_netcdf_filename = f'{output_base_name}.nc'
    output_geotiff_filename = f'{output_base_name}.tif'

    # Define the full time range as strings for xarray slicing
    time_slice_start = f'{start_year}-01-01'
    time_slice_end = f'{end_year}-12-31'  # Include the last day of the end_year

    try:
        # 1. Open the remote dataset
        # chunks='auto' enables Dask for lazy loading, which is crucial for large datasets.
        # This only loads metadata initially, not the full data.
        ds = xr.open_dataset(opendap_url, chunks='auto')
        print("\nDataset opened successfully. Displaying dataset info (first few lines):")
        print(ds)

        # Ensure the variable exists
        if variable_name not in ds.data_vars:
            raise ValueError(
                f"Variable '{variable_name}' not found in the dataset. Available variables: {list(ds.data_vars.keys())}")

        # 2. Subset the data by time
        print(f"\nSubsetting data for time range: {time_slice_start} to {time_slice_end}")
        ds_time_subset = ds.sel(day=slice(time_slice_start, time_slice_end))
        print(ds_time_subset)

        # 3. Subset the data by spatial bounding box
        print(f"\nSubsetting data for spatial bounding box...")
        # Note: Gridmet uses positive longitudes for East and negative for West
        # Ensure 'lon' coordinate range matches your bbox (e.g., -180 to 180 or 0 to 360)
        # Gridmet usually uses -125 to -65 for CONUS.
        data_subset_spatial_temporal = ds_time_subset[variable_name].sel(
            lat=slice(bbox_north, bbox_south),
            lon=slice(bbox_west, bbox_east)
        )
        print("Subsetted DataArray (head):")
        print(data_subset_spatial_temporal)

        # 4. Calculate the mean over the time dimension
        # .mean() will compute the average for each (lat, lon) pixel over the selected time period.
        # skipna=True ensures that missing values (NaNs) are ignored in the average.
        print(f"\nCalculating the average of '{variable_name}' across the time dimension...")
        averaged_raster = data_subset_spatial_temporal.mean(dim='day', skipna=True)
        print("\nResulting averaged DataArray:")
        print(averaged_raster)

        # Force computation and loading into memory (if not already done by .mean())
        # This step actually downloads the data and performs the calculation.
        print("\nLoading computed average into memory...")
        final_raster_data = averaged_raster.compute()

        # 5. Save the result to a NetCDF file
        os.makedirs(output_dir, exist_ok=True)
        output_filepath = os.path.join(output_dir, output_netcdf_filename)
        print(f"\nSaving averaged raster to {output_filepath}")
        final_raster_data.to_netcdf(output_filepath)

        print(f"\nProcess completed. Averaged SPEI raster saved to: {output_filepath}")

        # 6. Save the result to a GeoTIFF file
        output_geotiff_filename = f'{output_geotiff_filename.split('.')[0]}.tif'
        output_geotiff_filepath = os.path.join(output_dir, output_geotiff_filename)
        print(f"\nSaving averaged raster to GeoTIFF: {output_geotiff_filepath}")

        nodata_value = np.nan
        if '_FillValue' in ds[variable_name].encoding:
            nodata_value = ds[variable_name].encoding['_FillValue']
            # Attempt to ensure nodata is of the correct dtype
            if not np.issubdtype(type(nodata_value), final_raster_data.dtype):
                try:
                    nodata_value = np.array(nodata_value).astype(final_raster_data.dtype).item()
                except (ValueError, TypeError):
                    print(
                        f"Warning: Could not cast _FillValue {ds[variable_name].encoding['_FillValue']} to {final_raster_data.dtype}. Using NaN.")
                    nodata_value = np.nan
            print(f"Using _FillValue from original dataset as nodata: {nodata_value}")
        else:
            print(f"No _FillValue found in original dataset encoding. Using NaN as nodata for GeoTIFF.")

        # Try saving the GeoTIFF
        try:
            final_raster_data.rio.write_crs('epsg:4326', inplace=True)
            final_raster_data.rio.to_raster(
                output_geotiff_filepath,
                dtype=final_raster_data.dtype,
                compress='LZW',
                nodata=nodata_value,
                # Additional rasterio options if needed, e.g., driver='GTiff' (default)
                # This could be helpful if you want to try a specific profile directly
                # profile=final_raster_data.rio.profile # Get profile from rioxarray
            )
            print(f"GeoTIFF save command executed for: {output_geotiff_filepath}")

            # Verify GeoTIFF creation
            if os.path.exists(output_geotiff_filepath) and os.path.getsize(output_geotiff_filepath) > 0:
                print(f"GeoTIFF file verified: size {os.path.getsize(output_geotiff_filepath)} bytes.")
                # Optional: try opening with rasterio to check integrity
                # import rasterio
                # with rasterio.open(output_geotiff_filepath) as src:
                #     print(f"Rasterio opened GeoTIFF successfully. Driver: {src.driver}, CRS: {src.crs}")
            else:
                print("ERROR: GeoTIFF file either not created or is empty (0 bytes)! This indicates a silent failure.")
                print("Possible causes: permissions, disk space, or internal rasterio/gdal issue with data.")

        except Exception as write_error:
            print(f"ERROR: An exception occurred during GeoTIFF writing: {write_error}")
            # This would catch errors that rioxarray's internal try/except might miss or re-raise.

        print(f"\nProcess completed. Files should be in: {output_dir}")
        return final_raster_data

    except ValueError as ve:
        print(f"Data processing error: {ve}")
        print("This likely indicates an issue with spatial subsetting, data dimensions, or coordinate order.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print("Please double-check the OPeNDAP URL, variable name, and spatial/temporal ranges.")
        print("Ensure you have an active internet connection.")
        return None


def calc_annual_data_and_average(
        opendap_url: str,
        variable_name: str,
        frequency: str, # 'day', 'month', 'year'
        start_year: int,
        end_year: int,
        output_dir: str,
        bbox_west: float,
        bbox_south: float,
        bbox_east: float,
        bbox_north: float
):
    """
    Calculates the average of yearly sums for a given variable of daily data over a specified period,
    and saves the result as NetCDF and GeoTIFF rasters.

    Args:
        opendap_url (str): The OPeNDAP URL for the Gridmet dataset.
        variable_name (str): The name of the variable to process (e.g., 'precipitation_amount').
        frequency: (str), Frequency of data inputs, accepts 'day', 'month', 'year'
        start_year (int): The starting year for the averaging period (inclusive).
        end_year (int): The ending year for the averaging period (inclusive).
        output_dir (str): Directory to save the output files.
        bbox_west (float): Western longitude bound of the area of interest.
        bbox_south (float): Southern latitude bound.
        bbox_east (float): Eastern longitude bound.
        bbox_north (float): Northern latitude bound.
    """
    print(f"\n--- Processing '{variable_name}' for average yearly totals ({start_year}-{end_year}) ---")
    print(f"OPeNDAP URL: {opendap_url}")
    print(f"Bounding Box: W:{bbox_west}, S:{bbox_south}, E:{bbox_east}, N:{bbox_north}")

    yearly_totals_list = []
    output_base_name = f'avg_total_{variable_name}_{start_year}-{end_year}'
    output_netcdf_filename = f'{output_base_name}.nc'
    output_geotiff_filename = f'{output_base_name}.tif'

    try:
        # Open the remote dataset once outside the loop for efficiency
        # Using decode_times=False for initial open if 'time' dimension has issues for slicing
        # and then re-decoding later if needed, but usually default is fine.
        ds = xr.open_dataset(opendap_url, chunks='auto')
        print(f"Dataset for '{variable_name}' opened. Available variables: {list(ds.data_vars.keys())}")

        if variable_name not in ds.data_vars:
            raise ValueError(
                f"Variable '{variable_name}' not found in the dataset. Available variables: {list(ds.data_vars.keys())}")

        # Determine 'lat' coordinate order for correct slicing
        lat_coords = ds['lat'].values
        lat_slice_start_val = bbox_south
        lat_slice_end_val = bbox_north
        if len(lat_coords) > 1 and np.diff(lat_coords).mean() < 0:
            lat_slice_start_val = bbox_north
            lat_slice_end_val = bbox_south
            print(f"Detected descending 'lat' coordinate. Slicing from {lat_slice_start_val} to {lat_slice_end_val}")
        else:
            print(f"Detected ascending 'lat' coordinate. Slicing from {lat_slice_start_val} to {lat_slice_end_val}")

        print(ds)

        print(f"\nCalculating yearly totals for '{variable_name}'...")
        for year in tqdm(range(start_year, end_year + 1), desc=f"Calculating {variable_name} by year"):
            time_slice_start = f'{year}-01-01'
            time_slice_end = f'{year}-12-31'


            # Select data for the current year
            if frequency == 'day':
                try:
                    yearly_daily_data = ds[variable_name].sel(
                        day=slice(time_slice_start, time_slice_end),
                        lat=slice(lat_slice_start_val, lat_slice_end_val),
                        lon=slice(bbox_west, bbox_east)
                    )

                    # Check if subset has valid spatial dimensions before computing sum
                    if 'lat' not in yearly_daily_data.dims or 'lon' not in yearly_daily_data.dims:
                        print(f"  Warning: No 'lat'/'lon' dims for {year}. Skipping.")
                        continue
                    if yearly_daily_data.sizes.get('lat', 0) < 2 or yearly_daily_data.sizes.get('lon', 0) < 2:
                        print(
                            f"  Warning: Spatial dimensions too small for {year} (lat={yearly_daily_data.sizes.get('lat', 0)}, lon={yearly_daily_data.sizes.get('lon', 0)}). Skipping.")
                        continue
                    if yearly_daily_data['day'].size == 0:
                        print(f"  Warning: No data for time slice {year}. Skipping.")
                        continue

                    # Sum daily data for the year, then compute to load into memory
                    yearly_total_raster = yearly_daily_data.sum(dim='day', skipna=True).compute()

                    # Add a 'year' coordinate to the yearly total raster
                    yearly_total_raster = yearly_total_raster.assign_coords(year=year).expand_dims('year')
                    yearly_totals_list.append(yearly_total_raster)

                except Exception as e:
                    print(f"  Error processing {variable_name} for year {year}: {e}. Skipping this year.")
                    continue

            elif frequency == 'month':
                try:
                    yearly_monthly_data = ds[variable_name].sel(
                        time=slice(time_slice_start, time_slice_end),
                        lat=slice(lat_slice_start_val, lat_slice_end_val),
                        lon=slice(bbox_west, bbox_east)
                    )

                    # Check if subset has valid spatial dimensions before computing sum
                    if 'lat' not in yearly_monthly_data.dims or 'lon' not in yearly_monthly_data.dims:
                        print(f"  Warning: No 'lat'/'lon' dims for {year}. Skipping.")
                        continue
                    if yearly_monthly_data.sizes.get('lat', 0) < 2 or yearly_monthly_data.sizes.get('lon', 0) < 2:
                        print(
                            f"  Warning: Spatial dimensions too small for {year} (lat={yearly_monthly_data.sizes.get('lat', 0)}, lon={yearly_monthly_data.sizes.get('lon', 0)}). Skipping.")
                        continue
                    if yearly_monthly_data['time'].size == 0:
                        print(f"  Warning: No data for time slice {year}. Skipping.")
                        continue

                    # Sum monthly data for the year, then compute to load into memory
                    yearly_total_raster = yearly_monthly_data.sum(dim='time', skipna=True).compute()

                    # Add a 'year' coordinate to the yearly total raster
                    yearly_total_raster = yearly_total_raster.assign_coords(year=year).expand_dims('year')
                    yearly_totals_list.append(yearly_total_raster)

                except Exception as e:
                    print(f"  Error processing {variable_name} for year {year}: {e}. Skipping this year.")
                    continue

            elif frequency == 'year':
                try:
                    yearly_data = ds[variable_name].sel(
                        year=slice(time_slice_start, time_slice_end),
                        lat=slice(lat_slice_start_val, lat_slice_end_val),
                        lon=slice(bbox_west, bbox_east)
                    )

                    # Check if subset has valid spatial dimensions before computing sum
                    if 'lat' not in yearly_data.dims or 'lon' not in yearly_data.dims:
                        print(f"  Warning: No 'lat'/'lon' dims for {year}. Skipping.")
                        continue
                    if yearly_data.sizes.get('lat', 0) < 2 or yearly_data.sizes.get('lon', 0) < 2:
                        print(
                            f"  Warning: Spatial dimensions too small for {year} (lat={yearly_data.sizes.get('lat', 0)}, lon={yearly_data.sizes.get('lon', 0)}). Skipping.")
                        continue
                    if yearly_data['year'].size == 0:
                        print(f"  Warning: No data for time slice {year}. Skipping.")
                        continue

                    # Sum daily data for the year, then compute to load into memory
                    yearly_total_raster = yearly_data

                    # Add a 'year' coordinate to the yearly total raster
                    yearly_total_raster = yearly_total_raster.assign_coords(year=year).expand_dims('year')
                    yearly_totals_list.append(yearly_total_raster)

                except Exception as e:
                    print(f"  Error processing {variable_name} for year {year}: {e}. Skipping this year.")
                    continue

        if not yearly_totals_list:
            raise ValueError(
                f"No valid yearly total rasters were generated for {variable_name} in the specified period.")

        print(f"\nConcatenating {len(yearly_totals_list)} yearly totals...")
        # Combine all yearly total DataArrays into a single DataArray with a 'year' dimension
        all_yearly_totals = xr.concat(yearly_totals_list, dim='year')
        print("Concatenated DataArray structure:")
        print(all_yearly_totals)

        print(f"\nCalculating the average of yearly totals for '{variable_name}' across the 'year' dimension...")
        final_average_total_raster = all_yearly_totals.mean(dim='year', skipna=True)

        # --- Rioxarray setup for GeoTIFF export ---
        print("\nApplying rioxarray configuration to final average raster...")
        # Ensure CRS is explicitly set. Gridmet is typically WGS84.
        if final_average_total_raster.rio.crs is None:
            final_average_total_raster = final_average_total_raster.rio.set_crs("EPSG:4326")
            print("Set CRS to EPSG:4326 (WGS84).")
        else:
            print(f"CRS already present: {final_average_total_raster.rio.crs}")

        # Explicitly tell rioxarray which dimensions are 'x' and 'y'.
        final_average_total_raster.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
        print(
            f"Spatial dimensions set: x='{final_average_total_raster.rio.x_dim}', y='{final_average_total_raster.rio.y_dim}'")

        # # Ensure coordinates are monotonic (sorted).
        # if not final_average_total_raster.rio.x_coords_are_monotonic:
        #     print(f"Warning: {final_average_total_raster.rio.x_dim} coordinates are not monotonic. Sorting...")
        #     final_average_total_raster = final_average_total_raster.sortby(final_average_total_raster.rio.x_dim)
        # if not final_average_total_raster.rio.y_coords_are_monotonic:
        #     print(f"Warning: {final_average_total_raster.rio.y_dim} coordinates are not monotonic. Sorting...")
        #     final_average_total_raster = final_average_total_raster.sortby(final_average_total_raster.rio.y_dim)

        # Final diagnostic print before writing
        print("\n--- Final Average Yearly Total DataArray state before saving ---")
        print(final_average_total_raster)
        print(f"DataArray CRS: {final_average_total_raster.rio.crs}")
        try:
            bounds = final_average_total_raster.rio.bounds()
            print(f"Calculated bounds: {bounds}")
        except Exception as e:
            raise ValueError(f"Still unable to determine bounds for GeoTIFF after setup: {e}")

        # Check for all NaN data in the final result
        num_nans = final_average_total_raster.isnull().sum().item()
        total_elements = final_average_total_raster.size
        print(f"Number of NaN values in final average raster: {num_nans} / {total_elements}")
        if num_nans == total_elements:
            print(
                "WARNING: The entire final average raster is composed of NaN values. GeoTIFF will likely be empty or nearly empty.")
            print("This indicates no valid data was found or all processed data points were NaN.")
            # Depending on your requirement, you might want to skip saving if completely NaN.

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        print(f"\nOutput directory '{output_dir}' checked/created.")

        # Save to NetCDF
        output_netcdf_filepath = os.path.join(output_dir, output_netcdf_filename)
        print(f"\nAttempting to save average total raster to NetCDF: {output_netcdf_filepath}")
        final_average_total_raster.to_netcdf(output_netcdf_filepath)
        print(f"NetCDF saved successfully: {output_netcdf_filepath}")
        if os.path.exists(output_netcdf_filepath) and os.path.getsize(output_netcdf_filepath) > 0:
            print(f"NetCDF file verified: size {os.path.getsize(output_netcdf_filepath)} bytes.")
        else:
            print("WARNING: NetCDF file either not created or is empty!")

        # Save to GeoTIFF
        output_geotiff_filepath = os.path.join(output_dir, output_geotiff_filename)
        print(f"\nAttempting to save average total raster to GeoTIFF: {output_geotiff_filepath}")

        # Determine nodata value from original dataset, if available for this variable
        nodata_value = np.nan
        if '_FillValue' in ds[variable_name].encoding:
            nodata_value = ds[variable_name].encoding['_FillValue']
            if not np.issubdtype(type(nodata_value), final_average_total_raster.dtype):
                try:
                    nodata_value = np.array(nodata_value).astype(final_average_total_raster.dtype).item()
                except (ValueError, TypeError):
                    print(
                        f"Warning: Could not cast _FillValue {ds[variable_name].encoding['_FillValue']} to {final_average_total_raster.dtype}. Using NaN.")
                    nodata_value = np.nan
            print(f"Using _FillValue from original dataset for '{variable_name}' as nodata: {nodata_value}")
        else:
            print(
                f"No _FillValue found for '{variable_name}' in original dataset encoding. Using NaN as nodata for GeoTIFF.")

        try:
            final_average_total_raster.rio.to_raster(
                output_geotiff_filepath,
                dtype=final_average_total_raster.dtype,
                compress='LZW',
                nodata=nodata_value
            )
            print(f"GeoTIFF save command executed for: {output_geotiff_filepath}")

            if os.path.exists(output_geotiff_filepath) and os.path.getsize(output_geotiff_filepath) > 0:
                print(f"GeoTIFF file verified: size {os.path.getsize(output_geotiff_filepath)} bytes.")
            else:
                print("ERROR: GeoTIFF file either not created or is empty (0 bytes)! Silent failure detected.")

        except Exception as write_error:
            print(f"ERROR: An exception occurred during GeoTIFF writing: {write_error}")

        print(f"\nProcess for '{variable_name}' completed. Files should be in: {output_dir}")
        return final_average_total_raster

    except ValueError as ve:
        print(f"Data processing error for '{variable_name}': {ve}")
        print("This likely indicates an issue with spatial/temporal subsetting or data dimensions.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred for '{variable_name}': {e}")
        print("Please double-check the OPeNDAP URL, variable name, and spatial/temporal ranges.")
        return None


def terra_seasonality_index():
    pass


if __name__ == "__main__":

    # Gets Precip and ETo from GRIDMet
    START_YEAR = 1994
    END_YEAR = 2023
    OUTPUT_FOLDER = 'gridmet_output'

    # lat longs of bounds
    BBOX = {
        'west': -118.0,
        'south': 42.0,
        'east': -100.0,
        'north': 55.0
    }
    # URL_VAR_NAME = 'pr'
    # OPENDAP_URL = f'http://thredds.northwestknowledge.net:8080/thredds/dodsC/agg_met_{URL_VAR_NAME}_1979_CurrentYear_CONUS.nc'
    # VARIABLE_NAME = 'precipitation_amount'
    # FREQ = 'day'
    #
    # avg_total_pet_data = calc_annual_data_and_average(
    #     opendap_url=OPENDAP_URL,
    #     start_year=START_YEAR,
    #     end_year=END_YEAR,
    #     variable_name=VARIABLE_NAME,
    #     frequency=FREQ,
    #     output_dir=OUTPUT_FOLDER,
    #     bbox_west=BBOX['west'],
    #     bbox_south=BBOX['south'],
    #     bbox_east=BBOX['east'],
    #     bbox_north=BBOX['north']
    # )

    URL_VAR_NAME = 'vp'
    OPENDAP_URL = f'http://thredds.northwestknowledge.net:8080/thredds/dodsC/agg_met_{URL_VAR_NAME}_1979_CurrentYear_CONUS.nc'
    VARIABLE_NAME = 'daily_minimum_temperature'
    FREQ = 'day'

    avg_timeseries = calc_annual_data_and_average(
        opendap_url=OPENDAP_URL,
        start_year=START_YEAR,
        end_year=END_YEAR,
        variable_name=VARIABLE_NAME,
        frequency=FREQ,
        output_dir=OUTPUT_FOLDER,
        bbox_west=BBOX['west'],
        bbox_south=BBOX['south'],
        bbox_east=BBOX['east'],
        bbox_north=BBOX['north']
    )


    # # Gets Precip and ETo from TerraClimate
    # START_YEAR = 1994
    # END_YEAR = 2023
    # OUTPUT_FOLDER = 'terraclimate_output'
    #
    # # lat longs of bounds
    # BBOX = {
    #     'west': -118.0,
    #     'south': 42.0,
    #     'east': -100.0,
    #     'north': 52.0
    # }
    # OPENDAP_URL = r'http://thredds.northwestknowledge.net:8080/thredds/dodsC/agg_terraclimate_ppt_1958_CurrentYear_GLOBE.nc'
    # VARIABLE_NAME = 'ppt'
    # FREQ = 'month'

    # avg_total_precip_data = calc_annual_data_and_average(
    #     opendap_url=OPENDAP_URL,
    #     start_year=START_YEAR,
    #     end_year=END_YEAR,
    #     variable_name=VARIABLE_NAME,
    #     frequency= FREQ,
    #     output_dir=OUTPUT_FOLDER,
    #     bbox_west=BBOX['west'],
    #     bbox_south=BBOX['south'],
    #     bbox_east=BBOX['east'],
    #     bbox_north=BBOX['north']
    # )
    #
    # OPENDAP_URL = r'http://thredds.northwestknowledge.net:8080/thredds/dodsC/agg_terraclimate_pet_1958_CurrentYear_GLOBE.nc'
    # VARIABLE_NAME = 'pet'
    # FREQ = 'month'
    #
    # avg_total_pet_data = calc_annual_data_and_average(
    #     opendap_url=OPENDAP_URL,
    #     start_year=START_YEAR,
    #     end_year=END_YEAR,
    #     variable_name=VARIABLE_NAME,
    #     frequency=FREQ,
    #     output_dir=OUTPUT_FOLDER,
    #     bbox_west=BBOX['west'],
    #     bbox_south=BBOX['south'],
    #     bbox_east=BBOX['east'],
    #     bbox_north=BBOX['north']
    # )
    #
    # # if avg_total_precip_data is not None:
    # #     try:
    # #         plt.figure(figsize=(12, 10))
    # #         avg_total_precip_data.plot(x='lon', y='lat', cmap='Blues',
    # #                                    cbar_kwargs={
    # #                                        'label': 'Average Annual Precipitation (mm)'})  # Gridmet 'pr' is usually in mm
    # #         plt.title(f'40-Year Average Annual Total Precipitation ({START_YEAR}-{END_YEAR})')
    # #         plt.xlabel('Longitude')
    # #         plt.ylabel('Latitude')
    # #         plt.grid(True)
    # #         plt.tight_layout()
    # #         plt.show()
    # #     except Exception as e:
    # #         print(f"Could not plot average total precipitation data: {e}")
    # #
    # # if avg_total_pet_data is not None:
    # #     try:
    # #         plt.figure(figsize=(12, 10))
    # #         avg_total_pet_data.plot(x='lon', y='lat', cmap='Greens',
    # #                                 cbar_kwargs={
    # #                                     'label': 'Average Annual Potential Evapotranspiration (mm)'})  # Gridmet 'pet' is usually in mm
    # #         plt.title(f'40-Year Average Annual Total Potential Evapotranspiration ({START_YEAR}-{END_YEAR})')
    # #         plt.xlabel('Longitude')
    # #         plt.ylabel('Latitude')
    # #         plt.grid(True)
    # #         plt.tight_layout()
    # #         plt.show()
    # #     except Exception as e:
    # #         print(f"Could not plot average total PET data: {e}")



    # SPEI from GRIDMet
    # OPENDAP_URL = 'http://thredds.northwestknowledge.net:8080/thredds/dodsC/agg_met_spei1y_1979_CurrentYear_CONUS.nc'
    # VARIABLE_NAME = 'spei'

    # OPENDAP_URL = 'http://thredds.northwestknowledge.net:8080/thredds/dodsC/agg_met_srad_1979_CurrentYear_CONUS.nc'
    # VARIABLE_NAME = 'daily_mean_shortwave_radiation_at_surface'
    #
    # averaged_spei_data = average_yearly_aggregates(
    #     opendap_url=OPENDAP_URL,
    #     start_year=START_YEAR,
    #     end_year=END_YEAR,
    #     variable_name=VARIABLE_NAME,
    #     output_dir=OUTPUT_FOLDER,
    #     bbox_west=BBOX['west'],
    #     bbox_south=BBOX['south'],
    #     bbox_east=BBOX['east'],
    #     bbox_north=BBOX['north']
    # )
    #
    # if averaged_spei_data is not None:
    #     print("\nSuccessfully generated averaged SPEI raster and GeoTIFF.")
    #
    #     # Optional: Basic Visualization (requires matplotlib)
    #     try:
    #         plt.figure(figsize=(10, 8))
    #         # Use rioxarray's plotting for proper labels/orientation if needed
    #         # averaged_spei_data.plot.imshow() or .plot() often works directly
    #         averaged_spei_data.plot(x='lon', y='lat', cmap='RdBu', center=0, cbar_kwargs={'label': 'Average SPEI'})
    #         plt.title(f'Average SPEI ({START_YEAR}-{END_YEAR})')
    #         plt.xlabel('Longitude')
    #         plt.ylabel('Latitude')
    #         plt.grid(True)
    #         plt.tight_layout()
    #         plt.show()
    #     except Exception as e:
    #         print(
    #             f"Could not plot the data. Ensure matplotlib is installed and display environment is set up. Error: {e}")
