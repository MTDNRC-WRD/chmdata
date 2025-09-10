import ee
import geemap
import os

# https://developers.google.com/earth-engine/datasets/catalog/NASA_ORNL_DAYMET_V4#:~:text=Explore%20with%20Earth%20Engine&text=and%20Climatological%20Summaries-,Daymet%20V4%20provides%20gridded%20estimates%20of%20daily%20weather%20parameters%20for,and%20various%20supporting%20data%20sources.

DAYMET_EE = 'NASA/ORNL/DAYMET_V4'
SRTM_EE = 'USGS/SRTMGL1_003'
ERA5_EE = 'ECMWF/ERA5_LAND/DAILY_AGGR'

EE_PROJECT = 'ee-saba'
SCALE_METERS = 1000


def display_asset(asset_path, band_name, layer_name, vis_params=None, auto_min_max=True):
    """
       Initializes Earth Engine, creates a geemap, and displays a single-band image
       from an Earth Engine asset path.

       This version is simplified for single-band visualization and can optionally
       calculate the min and max pixel values for that band.

       Args:
           asset_path (str): The full path to the Earth Engine image asset.
                             Example: 'CGIAR/SRTM90_V4' (a digital elevation model)
           band_name (str): The name of the single band to display.
                            Example: 'elevation' for the SRTM data.
           vis_params (dict, optional): A dictionary of visualization parameters
                                        for the image. This can be partially
                                        specified, e.g., only providing a palette.
           layer_name (str, optional): The name of the layer to be displayed on the map.
           auto_min_max (bool, optional): If True, the function will calculate the
                                          min and max values for the specified band.
                                          This will override any 'min' or 'max'
                                          values provided in vis_params. Defaults to False.
       """
    try:
        # Initialize Earth Engine.
        # ee.Authenticate() # Uncomment this line if you haven't authenticated yet
        ee.Initialize()

        # Load the image and select the single band
        ee_image = ee.Image(asset_path).select(band_name)

        # Set a default visualization parameter if none is provided.
        if vis_params is None:
            vis_params = {}

        # If auto_min_max is enabled, we'll calculate the min and max for the band.
        if auto_min_max:
            print(f"Calculating min and max values for band: {band_name}...")

            # Use reduceRegion to get the min and max statistics for the band.
            # We use a default geometry of the image's footprint.
            stats = ee_image.reduceRegion(
                reducer=ee.Reducer.minMax(),
                geometry=ee_image.geometry(),
                scale=1000,  # Use a nominal scale, e.g., 90m for SRTM
                maxPixels=1e13
            ).getInfo()

            # Extract the single min and max values from the dictionary.
            min_val = stats[f'{band_name}_min']
            max_val = stats[f'{band_name}_max']

            # Update the visualization parameters with the calculated values.
            vis_params['min'] = min_val
            vis_params['max'] = max_val

            print(f"Calculated min value: {min_val}")
            print(f"Calculated max value: {max_val}")

        # If min/max are still not defined (and auto_min_max was not used),
        # apply a default stretch.
        elif 'min' not in vis_params or 'max' not in vis_params:
            print("No min/max values provided, using a default stretch of 0-4000.")
            vis_params['min'] = 0
            vis_params['max'] = 4000

        # Create a geemap instance
        m = geemap.Map()

        # Center the map on the image's geometry
        m.centerObject(ee_image, 10)

        # Add the image layer to the map
        m.add_layer(ee_image, vis_params, layer_name)

        # Display the map
        print(f"Displaying single-band image from asset: {asset_path}")
        return m

    except ee.EEException as e:
        print(f"An Earth Engine error occurred: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def export_daymet_images(asset_id,source_folder, bucket_name, destination_folder, sub_folder, scale):
    """exports single daymet immage to a Google Cloud Storage bucket.
    This function is optimized for a collection of images with a consistent
    geometry and scale.

    Args:
        asset_id (str): Name of the asset
        source_folder (str): The path to the Earth Engine asset folder (e.g., 'users/your-user-name/my_assets').
        bucket_name (str): The name of the Google Cloud Storage bucket.
        destination_folder (str): The folder path within the bucket to save the assets.
        scale (int): The resolution in meters per pixel for the image exports.
    """

    try:
        # The ee.Image() call will create a client-side object for the asset.
        image = ee.Image(f'{source_folder}/{asset_id}')
        file_name = asset_id

        # Create the export task.
        task = ee.batch.Export.image.toCloudStorage(
            image=image,
            description=f'Export {file_name}',
            bucket=bucket_name,
            fileNamePrefix=f'{destination_folder}/{sub_folder}/{file_name}',
            scale=scale,
            region=region  # Use the region from the first image for all exports.
        )
        task.start()
        print(
            f"Export task started: {task.id}. You can monitor its status in the GEE Code Editor Task Manager.")
    except Exception as e:
        print(f"An error occurred while trying to export asset {asset_id}: {e}")




def batch_export_daymet_images(source_folder, bucket_name, destination_folder, sub_folder, scale):
    """
    Lists all image assets in a given Earth Engine folder and exports them to a Google Cloud
    Storage bucket. This function is optimized for a collection of images with a consistent
    geometry and scale.

    Args:
        source_folder (str): The path to the Earth Engine asset folder (e.g., 'users/your-user-name/my_assets').
        bucket_name (str): The name of the Google Cloud Storage bucket.
        destination_folder (str): The folder path within the bucket to save the assets.
        scale (int): The resolution in meters per pixel for the image exports.
    """
    print(f"Listing image assets in folder: {source_folder}")
    assets = ee.data.listAssets({'parent': source_folder})

    if 'assets' not in assets or len(assets['assets']) == 0:
        print("No assets found in the specified folder or the folder does not exist.")
        return

    # Use the geometry of the first image to define the export region for all images.
    # This assumes all images have the same spatial extent.
    first_image_id = assets['assets'][0]['id']
    first_image = ee.Image(first_image_id)
    region = first_image.geometry()

    for asset_info in assets['assets']:
        asset_id = asset_info['id']
        asset_type = asset_info['type']

        # Get the asset name from the ID for the output file name.
        file_name = os.path.basename(asset_id)

        # Only export assets that are of type 'IMAGE'.
        if asset_type == 'IMAGE':
            print(f"\nFound asset: {asset_id}")

            try:
                # The ee.Image() call will create a client-side object for the asset.
                image = ee.Image(asset_id)

                # Create the export task.
                task = ee.batch.Export.image.toCloudStorage(
                    image=image,
                    description=f'Export {file_name}',
                    bucket=bucket_name,
                    fileNamePrefix=f'{destination_folder}/{sub_folder}/{file_name}',
                    scale=scale,
                    region=region  # Use the region from the first image for all exports.
                )
                task.start()
                print(
                    f"Export task started: {task.id}. You can monitor its status in the GEE Code Editor Task Manager.")
            except Exception as e:
                print(f"An error occurred while trying to export asset {asset_id}: {e}")
        else:
            print(f"Skipping asset {asset_id} of type {asset_type} as it is not an IMAGE.")



def return_day(day, area):
    daymet_collection = ee.ImageCollection(DAYMET_EE).filterBounds(area)
    daymet_image = daymet_collection.filterDate(day, ee.Date(day).advance(1, 'day')).first()
    return daymet_image


def return_elevation(area):
    elevation = ee.Image(SRTM_EE).clip(area)
    return elevation


def calc_winter_summer_prcp_ratio(start_day, end_day, area):
    """
        Calculates the ratio of cold season (Nov-Apr) to warm season (May-Oct)
        total precipitation over the specified period.

        Args:
            start_day (str): The start date for the calculation in 'YYYY-MM-DD' format.
            end_day (str): The end date for the calculation in 'YYYY-MM-DD' format.
            area (ee.Geometry.Rectangle or ee.Geometry.Polygon): The region of interest for the calculation.

        Returns:
            ee.Image: A single image representing the winter/summer precipitation ratio for the period.
        """
    daymet_collection = ee.ImageCollection(DAYMET_EE).filter(ee.Filter.date(start_day, end_day)).filterBounds(area)
    var = 'prcp'
    # Filter the collection for the "cold" season (November to April)
    # The calendar range is inclusive, so it will get all images from Nov, Dec, Jan, Feb, Mar, Apr.
    cold_season_collection = daymet_collection.filter(ee.Filter.calendarRange(11, 4, 'month'))
    # Filter the collection for the "warm" season (May to October)
    warm_season_collection = daymet_collection.filter(ee.Filter.calendarRange(5, 10, 'month'))

    # Calculate the total precipitation for each season over the entire period
    cold_prcp_sum = cold_season_collection.select(var).sum()
    warm_prcp_sum = warm_season_collection.select(var).sum()

    # --- Handle division by zero to prevent errors in arid regions ---
    # Create a mask for pixels where warm season precipitation is greater than a small tolerance value.
    mask = warm_prcp_sum.gt(0.001)
    # Divide the cold season sum by the warm season sum to get the ratio.
    # Update the mask to only show valid results.
    ratio = cold_prcp_sum.divide(warm_prcp_sum).updateMask(mask)
    return ratio

def calc_ave_annual_prcp(start_day, end_day, area, var='prcp'):
    """ Args:
            start_day (str): The start date for the calculation in 'YYYY-MM-DD' format.
            end_day (str): The end date for the calculation in 'YYYY-MM-DD' format.
            area (ee.Geometry.Rectangle or ee.Geometry.Polygon): The region of interest for the calculation.
            var (str): desired band from daymet image (defaults to prcp)

        Returns:
            ee.Image: A single image representing the average annual band, annual products are a sum of daily..
        """
    def calc_annual_prcp(year):
        start_date = ee.Date.fromYMD(year, 1, 1)
        end_date = start_date.advance(1, 'year')
        # Filter the collection for the current year
        year_collection = daymet_collection.filterDate(start_date, end_date)
        # Calculate the sum of band data for the year
        annual_data = year_collection.select(var).sum()
        # Set a property on the image to store the year, useful for later inspection
        return annual_data.set('year', year)

    # Load the Daymet V4 daily data
    daymet_collection = ee.ImageCollection(DAYMET_EE).filter(ee.Filter.date(start_day, end_day)).filterBounds(area)
    # Create a list of years from the start to end year
    years = ee.List.sequence(int(start_day.split('-')[0]), int(end_day.split('-')[0]))
    # Map the function over the list of years to create a collection of annual images
    annual_band_collection = ee.ImageCollection(years.map(calc_annual_prcp))
    # Reduce the ImageCollection to a single image by taking the mean over all years
    avg_annual_band = annual_band_collection.mean().rename(f'avg_annual_{var}')
    # Check the properties of the final image
    print("Final image properties:", avg_annual_band.getInfo())
    return avg_annual_band

def calc_ave_annual_srad(start_day, end_day, area, var='srad'):
    """ Args:
                start_day (str): The start date for the calculation in 'YYYY-MM-DD' format.
                end_day (str): The end date for the calculation in 'YYYY-MM-DD' format.
                area (ee.Geometry.Rectangle or ee.Geometry.Polygon): The region of interest for the calculation.
                var (str): desired band from daymet image (defaults to srad)

            Returns:
                ee.Image: A single image representing the average annual band, annual products are a mean of dailys.
            """
    def calc_annual_srad(year):
        start_date = ee.Date.fromYMD(year, 1, 1)
        end_date = start_date.advance(1, 'year')
        # Filter the collection for the current year
        year_collection = daymet_collection.filterDate(start_date, end_date)
        # Calculate the sum of band data for the year
        annual_data = year_collection.select(var).mean()
        # Set a property on the image to store the year, useful for later inspection
        return annual_data.set('year', year)

    # Load the Daymet V4 daily data
    daymet_collection = ee.ImageCollection(DAYMET_EE).filter(ee.Filter.date(start_day, end_day)).filterBounds(area)
    # Create a list of years from the start to end year
    years = ee.List.sequence(int(start_day.split('-')[0]), int(end_day.split('-')[0]))
    # Map the function over the list of years to create a collection of annual images
    annual_band_collection = ee.ImageCollection(years.map(calc_annual_srad))
    # Reduce the ImageCollection to a single image by taking the mean over all years
    avg_annual_band = annual_band_collection.mean().rename(f'avg_annual_{var}')
    # Check the properties of the final image
    print("Final image properties:", avg_annual_band.getInfo())
    return avg_annual_band


def calc_prcp_stdev(start_day, end_day, area, var='prcp'):
    def calc_annual_prcp(year):
        start_date = ee.Date.fromYMD(year, 1, 1)
        end_date = start_date.advance(1, 'year')
        # Filter the collection for the current year
        year_collection = daymet_collection.filterDate(start_date, end_date)
        # Calculate the sum of band data for the year
        annual_data = year_collection.select(var).sum()
        # Set a property on the image to store the year, useful for later inspection
        return annual_data.set('year', year)

    # Load the Daymet V4 daily data
    daymet_collection = ee.ImageCollection(DAYMET_EE).filter(ee.Filter.date(start_day, end_day)).filterBounds(area)
    # Create a list of years from the start to end year
    years = ee.List.sequence(int(start_day.split('-')[0]), int(end_day.split('-')[0]))
    # Map the function over the list of years to create a collection of annual images
    annual_band_collection = ee.ImageCollection(years.map(calc_annual_prcp))
    # Reduce the ImageCollection to a single image by taking the mean over all years
    avg_annual_band = annual_band_collection.reduce(ee.Reducer.stdDev()).rename(f'std_{var}')
    # Check the properties of the final image
    print("Final image properties:", avg_annual_band.getInfo())
    return avg_annual_band


def calc_ave_annual_temp(start_day, end_day, area, var):
    def calc_annual_temp(year):
        start_date = ee.Date.fromYMD(year, 1, 1)
        end_date = start_date.advance(1, 'year')
        # Filter the collection for the current year
        year_collection = daymet_collection.filterDate(start_date, end_date)
        # Calculate the mean of band data for the year
        annual_data = year_collection.select(var).mean()
        # Set a property on the image to store the year, useful for later inspection
        return annual_data.set('year', year)

    # Load the Daymet V4 daily data
    daymet_collection = ee.ImageCollection(DAYMET_EE).filter(ee.Filter.date(start_day, end_day)).filterBounds(area)
    # Create a list of years from the start to end year
    years = ee.List.sequence(int(start_day.split('-')[0]), int(end_day.split('-')[0]))
    # Map the function over the list of years to create a collection of annual images
    annual_band_collection = ee.ImageCollection(years.map(calc_annual_temp))
    # Reduce the ImageCollection to a single image by taking the mean over all years
    avg_annual_band = annual_band_collection.mean().rename(f'avg_annual_{var}')
    # Check the properties of the final image
    print("Final image properties:", avg_annual_band.getInfo())
    return avg_annual_band


def calc_month_tmean(start_day, end_day, area, month):
    """
        Calculates the average monthly mean temperature for a specified month over a period of years
        using Daymet V4 data.

        Args:
            start_year (int): The starting year for the calculation.
            end_year (int): The ending year for the calculation.
            month (int): The month (1-12) for which to calculate the average.
            area (ee.Geometry.Polygon): The area of interest for the calculation.

        Returns:
            ee.Image: An image with the average monthly mean temperature for the specified
                      month over the given time period.
        """
    # Load the Daymet V4 daily data
    daymet_collection = ee.ImageCollection(DAYMET_EE).filter(ee.Filter.date(start_day, end_day)).filterBounds(area)
    # Create a list of years from the start to end year
    years = ee.List.sequence(int(start_day.split('-')[0]), int(end_day.split('-')[0]))

    def monthly_mean(year):
        """
        Inner function to calculate the mean temperature for a specific month in a given year.
        This function is mapped over the list of years.
        """
        # Filter the Daymet collection for the specific month and year
        start_date = ee.Date.fromYMD(ee.Number(year), month, 1)
        end_date = start_date.advance(1, 'month')
        # Filter the collection by date and location
        month_data = daymet_collection.filterDate(start_date, end_date).filterBounds(area)
        # Calculate the mean of tmin and tmax for the month
        tmin = month_data.select('tmin').mean()
        tmax = month_data.select('tmax').mean()
        # Calculate the mean temperature and rename the band
        tmean = tmin.add(tmax).divide(2).rename('tmean')
        # Set a property on the image to store the year
        return tmean.set('year', year)

    # Map the function over the list of years to create a collection of yearly mean images
    yearly_means_collection = ee.ImageCollection(years.map(monthly_mean))
    # Reduce the collection to a single image by taking the mean over all years
    # Rename the final band for clarity
    avg_monthly_tmean = yearly_means_collection.mean().rename(f'avg_{month:02d}_tmean')
    return avg_monthly_tmean

def calc_tmean():
    #load the tmin and tmax assets
    tmin_asset = ee.Image(f'projects/{EE_PROJECT}/assets/30yr_annual_tmin')
    tmax_asset = ee.Image(f'projects/{EE_PROJECT}/assets/30yr_annual_tmax')
    tmean_immage = tmin_asset.add(tmax_asset).divide(2)
    return tmean_immage


def calc_PSI(start_day, end_day, area):
    """precipitation seasonality index 0 - 1.83
     Args:
            start_day (str): The start date for the calculation in 'YYYY-MM-DD' format.
            end_day (str): The end date for the calculation in 'YYYY-MM-DD' format.
            area (ee.Geometry.Rectangle or ee.Geometry.Polygon): The region of interest for the calculation.

        Returns:
            ee.Image: A single image representing the Precipitation seasonality index for the period
    """
    var = 'prcp'
    daymet_collection = ee.ImageCollection(DAYMET_EE).filter(ee.Filter.date(start_day, end_day)).filterBounds(area)
    # load the ave annual precip asset
    asset = f'projects/{EE_PROJECT}/assets/30yr_ave_annual_prcp'
    ave_annual_prcp = ee.Image(asset)

    # # Calculates average annual prcp
    # total_prcp_over_period = daymet_collection.select(var).sum()
    num_years = ee.Date(end_day).difference(ee.Date(start_day), 'year')
    # ave_annual_prcp = total_prcp_over_period.divide(num_years)

    # create an average precip per month asset
    twelfth_of_annual_prcp = ave_annual_prcp.divide(12)

    # Group the entire collection by month and calculate the mean for each month
    # This will result in an ImageCollection of 12 images (one for each month)
    def monthly_average_calc(month):
        # Filter the collection for the specified month across all years in the period
        monthly_images = daymet_collection.filter(ee.Filter.calendarRange(month, month, 'month'))
        # Use .sum() and then divide by the number of years to get a true average monthly value.
        total_prcp_for_month = monthly_images.select(var).sum()
        return total_prcp_for_month.divide(num_years).set('month', month)

    # Create an ImageCollection with 12 images, one for each month's average precipitation
    monthly_average_collection = ee.ImageCollection(ee.List.sequence(1, 12).map(monthly_average_calc))

    # Calculate the absolute difference for each month
    # This correctly subtracts the true average monthly precipitation from each month's image
    monthly_differences = monthly_average_collection.map(
        lambda monthly_image: monthly_image.subtract(twelfth_of_annual_prcp).abs()
    )

    # Sum the absolute differences from all 12 months
    monthly_sums = monthly_differences.sum()
    # Divide by the average annual precipitation to get the final PSI
    psi = monthly_sums.divide(ave_annual_prcp)

    return psi

def calc_PII(start_day, end_day, area):
    """
        Calculates the gridded Precipitation Intensity Index. This is defined as the
        ratio of the sum of precipitation from the three wettest days of the year
        to the total annual precipitation, averaged over the specified period.

        Args:
            start_day (str): The start date for the calculation in 'YYYY-MM-DD' format.
            end_day (str): The end date for the calculation in 'YYYY-MM-DD' format.
            area (ee.Geometry.Rectangle or ee.Geometry.Polygon): The region of interest for the calculation.

        Returns:
            ee.Image: A single image representing the average annual precipitation
                      intensity ratio for the period.
        """
    # Load the Daymet collection and filter by date and area
    daymet_collection = ee.ImageCollection(DAYMET_EE).filter(ee.Filter.date(start_day, end_day)).filterBounds(area)

    var = 'prcp'

    # Get a list of unique years in the collection.
    years = ee.List.sequence(ee.Date(start_day).get('year'), ee.Date(end_day).get('year'))

    def calc_annual_intensity(year):
        """
        A helper function to calculate the precipitation intensity for a single year.
        This function will be mapped over the list of years.
        """
        # Filter the collection for the current year
        annual_collection = daymet_collection.filter(ee.Filter.calendarRange(year, year, 'year'))

        # Get the three wettest days for each pixel.
        # 1. Convert the collection to a single multi-band image where each band is a day.
        prcp_array = annual_collection.select(var).toArray()
        # 2. Sort the array values for each pixel in ascending order.
        sorted_prcp = prcp_array.arraySort()
        # 3. Slice the last three elements (the highest values) from the sorted array.
        top3_prcp = sorted_prcp.arraySlice(0, -3)
        # 4. Sum the three values for each pixel.
        sum3_array = top3_prcp.arrayReduce(ee.Reducer.sum(), [0])
        # 5. Project the array to a single dimension and then get the scalar value.
        # This is the new, more robust fix.
        sum3 = sum3_array.arrayProject([0]).arrayGet(0)

        # Calculate the total annual precipitation.
        sum_annual = annual_collection.select(var).sum()

        # Perform the division to get the intensity ratio.
        intensity_ratio = sum3.divide(sum_annual)

        return ee.Image(intensity_ratio).rename('intensity').set('year', year)

    # Map the calculation function over the list of years.
    annual_intensity_collection = ee.ImageCollection(years.map(calc_annual_intensity))

    # Finally, calculate the average annual intensity over the entire period.
    ave_annual_intensity = annual_intensity_collection.mean()

    return ave_annual_intensity


def calc_PPS(start_day, end_day, area):
    """Percent Precipitation as Snow (30-year annual ave) 0-100%"""
    # load saymet data
    daymet_collection = ee.ImageCollection(DAYMET_EE).filter(ee.Filter.date(start_day, end_day)).filterBounds(area)

    def process_daymet_image(daymet_image):
        # calc daily mean temp from tmin and tmax add new band
        tmax = daymet_image.select('tmax')
        tmin = daymet_image.select('tmin')
        tmean = tmin.add(tmax).divide(2).rename('tmean')
        # get precip band
        prcp = daymet_image.select('prcp')
        # Get daily PS (snow fraction):
        # if T <= -2.5: PS = 1 , if T>=4: PS = 0, else PS =  Ps= -0.1667Tm + 0.6667
        ps_lowt = tmean.lt(-2.5).rename('ps_frac')
        ps_hight = tmean.gte(4).rename('ps_frac')
        ps_midt = tmean.multiply(-0.1667).add(0.6667).rename('ps_frac')
        ps_frac = ee.Image(0).where(ps_lowt, 1).where(ps_hight, 0).where(tmean.gte(-2.5).And(tmean.lt(4)), ps_midt)
        ps_frac = ps_frac.rename('ps_frac')
        # multiply PS x prcp save as new band snow
        snow = ps_frac.multiply(prcp).rename('snow')
        # Add all the new bands to the image
        return daymet_image.addBands([tmean, ps_frac, snow])

    processed_collection = daymet_collection.map(process_daymet_image)
    # calc total prcp and snow
    total_prcp = processed_collection.select('prcp').sum().rename('total_prcp')
    total_snow = processed_collection.select('snow').sum().rename('total_snow')
    # calc PPS
    pps = total_snow.divide(total_prcp).multiply(100).rename('pps')
    return pps


def calc_rs_rso(start_day, end_day, area):
    """
          Calculates the gridded average annual the fraction of solar radiation (Rs) to clear-sky solar radiation (Rso)
          is used to calculate the effect of cloud cover on net longwave radiation (Rn).
          The function returns a single image of the average annual fraction for the specified area and time period.

          Args:
              start_day (str): Start date in 'YYYY-MM-DD' format.
              end_day (str): End date in 'YYYY-MM-DD' format.
              area (ee.Geometry): A point, polygon, or other geometry to filter the collection.

          Returns:
              ee.Image: The average annual radiation fraction image.
          """
    # Filter the Daymet collection once at the beginning to get all daily images.
    daymet_collection = ee.ImageCollection(DAYMET_EE).filter(ee.Filter.date(start_day, end_day)).filterBounds(area)

    # Check if the collection is empty.
    collection_size = daymet_collection.size().getInfo()
    if collection_size == 0:
        print("Error: The filtered image collection is empty.")
        print("This could be due to the date range or the specified area being outside the DAYMET data coverage.")
        return None

    # Load a DEM to get elevation once for efficiency
    elevation = ee.Image(SRTM_EE).select('elevation').toFloat()

    def calculate_daily_frac(image):
        """
        Calculates daily frac for a single Daymet image, with error handling.
        This function returns only the frac band to optimize performance.
        """
        # Define a list of required bands.
        required_bands = ['tmax', 'tmin', 'srad', 'vp', 'dayl']

        # Check if all required bands exist on the image.
        has_required_bands = image.bandNames().containsAll(required_bands)

        def perform_calculation():
            # Get bands from the image and explicitly cast to float immediately.
            tmax = image.select('tmax').toFloat()
            tmin = image.select('tmin').toFloat()
            srad = image.select('srad').toFloat()
            vp = image.select('vp').toFloat()
            dayl = image.select('dayl').toFloat()

            # Get image date and location information
            date = image.date()
            day_of_year = ee.Image.constant(date.getRelative('day', 'year').add(1))

            # --- Physical Constants and Calculations ---
            t_mean = tmax.add(tmin).divide(2)
            # Atmospheric Pressure Calc
            p = elevation.expression('101.3 * ((293.0 - 0.0065 * elevation) / 293.0)**5.26',
                                     {'elevation': elevation})

            # Saturation vapor pressure
            es = tmax.expression('0.6108 * exp((17.27 * T) / (T + 237.3))', {'T': tmax}).add(
                tmin.expression('0.6108 * exp((17.27 * T) / (T + 237.3))', {'T': tmin})).divide(2)

            # Actual vapor pressure
            ea = vp.divide(1000)

            # Solar radiation
            srad_mj_per_day = srad.multiply(dayl).divide(ee.Number(1000000))

            # Net radiation
            albedo = 0.23
            rns = srad_mj_per_day.multiply(1 - albedo)

            # Extraterrestrial radiation (Ra)
            lat_rad = ee.Image.pixelLonLat().select('latitude').multiply(ee.Number(3.1415926535)).divide(180)
            dr = day_of_year.expression('1 + 0.033 * cos(2 * PI * day_of_year / 365)',
                                        {'PI': ee.Number(3.1415926535), 'day_of_year': day_of_year})
            delta_s = day_of_year.expression('0.409 * sin((2 * PI * day_of_year / 365) - 1.39)',
                                             {'PI': ee.Number(3.1415926535), 'day_of_year': day_of_year})
            ws = lat_rad.expression('acos(-tan(latitude) * tan(delta_s))',
                                    {'latitude': lat_rad, 'delta_s': delta_s}).min(
                ee.Image.constant(1.57079632679)).max(ee.Image.constant(0.0))
            ra = dr.expression(
                '24 * 60 / PI * 0.0820 * dr * (ws * sin(lat) * sin(delta_s) + cos(lat) * cos(delta_s) * sin(ws))', {
                    'PI': ee.Number(3.1415926535),
                    'dr': dr,
                    'ws': ws,
                    'lat': lat_rad,
                    'delta_s': delta_s,
                })

            # Clear-sky solar radiation
            rso = elevation.expression('(0.75 + 0.00002 * elevation) * ra', {'elevation': elevation, 'ra': ra})
            rs_rso = srad_mj_per_day.divide(rso).min(ee.Image.constant(1.0)).toFloat().rename('rs_rso')
            return rs_rso

        return ee.Algorithms.If(has_required_bands, perform_calculation(),
                                ee.Image.constant(-9999).toFloat().rename('rs_rso'))

    # Calculate annual frac for each year.
    years = ee.List.sequence(ee.Date(start_day).get('year'), ee.Date(end_day).get('year'))

    def calculate_annual_frac(year):
        """
        Calculates the total frac for a single year by filtering the original collection
        and then mapping the daily calculation function.
        """
        # Filter the original daymet collection for the specific year.
        annual_collection = daymet_collection.filter(ee.Filter.calendarRange(year, year, 'year'))

        # Map the daily ETo calculation over the annual collection.
        eto_daily_annual_collection = ee.ImageCollection(annual_collection.map(calculate_daily_frac))

        # Remove any images where the daily calculation returned the placeholder value.
        eto_daily_annual_collection = eto_daily_annual_collection.filter(ee.Filter.neq('rs_rso', -9999))

        # average rad frac.
        annual_sum = eto_daily_annual_collection.mean()

        # Set a property on the image to identify its year.
        return ee.Image(annual_sum).set('year', year)

    # Map the annual calculation function over the list of years to get a collection of annual totals.
    frac_collection_annual = ee.ImageCollection(years.map(calculate_annual_frac))

    # Finally, calculate the average annual ETo over the entire period.
    ave_annual_rad_frac = frac_collection_annual.mean().rename('average_annual_rad_frac')

    return ave_annual_rad_frac


def calc_ETo(start_day, end_day, area, wind_speed=False):
    """
       Calculates the gridded average annual ETo using the FAO-56 Penman-Monteith method.
       The function returns a single image of the average annual ETo for the specified area and time period.

       Args:
           start_day (str): Start date in 'YYYY-MM-DD' format.
           end_day (str): End date in 'YYYY-MM-DD' format.
           area (ee.Geometry): A point, polygon, or other geometry to filter the collection.
           wind_speed (bool, optional): True subsamples the ERA5-land dataset to compute ave daily surface wind.
                                        False assumes a constant wind speed of 2.0 m/s

       Returns:
           ee.Image: The average annual ETo image.
       """
    # Filter the Daymet collection once at the beginning to get all daily images.
    daymet_collection = ee.ImageCollection(DAYMET_EE).filter(ee.Filter.date(start_day, end_day)).filterBounds(area)
    if wind_speed:
        wind_collection = ee.ImageCollection(ERA5_EE).filter(ee.Filter.date(start_day, end_day)).filterBounds(area)

    # Check if the collection is empty.
    collection_size = daymet_collection.size().getInfo()
    if collection_size == 0:
        print("Error: The filtered image collection is empty.")
        print("This could be due to the date range or the specified area being outside the DAYMET data coverage.")
        return None

    # Load a DEM to get elevation once for efficiency
    elevation = ee.Image(SRTM_EE).select('elevation').toFloat()

    # # --- Verification Step ---
    # # You can check the elevation at a specific point within your area
    # sample_point = area.centroid()
    # elevation_at_point = elevation.sample(sample_point, 1).first().get('elevation').getInfo()
    #
    # # Print the result to confirm it's a valid number
    # if isinstance(elevation_at_point, (int, float)):
    #     print(f"Verification successful: Elevation data loaded. Sample value at centroid: {elevation_at_point} meters.")
    # else:
    #     print(
    #         "Verification failed: Could not retrieve a valid elevation value. Check your area and the SRTM data source.")
    #
    # # --- End Verification Step ---

    def calculate_daily_eto(image):
        """
        Calculates daily ETo for a single Daymet image, with error handling.
        This function returns only the ETo band to optimize performance.
        """
        # Define a list of required bands.
        required_bands = ['tmax', 'tmin', 'srad', 'vp', 'dayl']

        # Check if all required bands exist on the image.
        has_required_bands = image.bandNames().containsAll(required_bands)

        def perform_calculation():
            # Get bands from the image and explicitly cast to float immediately.
            tmax = image.select('tmax').toFloat()
            tmin = image.select('tmin').toFloat()
            srad = image.select('srad').toFloat()
            vp = image.select('vp').toFloat()
            dayl = image.select('dayl').toFloat()

            # Get image date and location information
            date = image.date()
            day_of_year = ee.Image.constant(date.getRelative('day', 'year').add(1))

            # --- Physical Constants and Calculations ---
            t_mean = tmax.add(tmin).divide(2)
            # Atmospheric Pressure Calc
            p = elevation.expression('101.3 * ((293.0 - 0.0065 * elevation) / 293.0)**5.26',
                                     {'elevation': elevation})
            gamma = p.multiply(0.000665)

            # Saturation vapor pressure
            es = tmax.expression('0.6108 * exp((17.27 * T) / (T + 237.3))', {'T': tmax}).add(
                tmin.expression('0.6108 * exp((17.27 * T) / (T + 237.3))', {'T': tmin})).divide(2)

            # Actual vapor pressure
            ea = vp.divide(1000)

            # Vapor pressure deficit
            es_minus_ea = es.subtract(ea)

            # Slope of saturation vapor pressure curve
            delta = t_mean.expression('4098.0 * es / pow(T_mean + 237.3, 2)', {'T_mean': t_mean, 'es': es})

            # Solar radiation
            srad_mj_per_day = srad.multiply(dayl).divide(ee.Number(1000000))

            # Net radiation
            albedo = 0.23
            rns = srad_mj_per_day.multiply(1 - albedo)
            # Stefan-Boltzmann constant
            sigma = 4.903e-9

            # Extraterrestrial radiation (Ra)
            lat_rad = ee.Image.pixelLonLat().select('latitude').multiply(ee.Number(3.1415926535)).divide(180)
            dr = day_of_year.expression('1 + 0.033 * cos(2 * PI * day_of_year / 365)',
                                        {'PI': ee.Number(3.1415926535), 'day_of_year': day_of_year})
            delta_s = day_of_year.expression('0.409 * sin((2 * PI * day_of_year / 365) - 1.39)',
                                             {'PI': ee.Number(3.1415926535), 'day_of_year': day_of_year})
            ws = lat_rad.expression('acos(-tan(latitude) * tan(delta_s))',
                                    {'latitude': lat_rad, 'delta_s': delta_s}).min(
                ee.Image.constant(1.57079632679)).max(ee.Image.constant(0.0))
            ra = dr.expression(
                '24 * 60 / PI * 0.0820 * dr * (ws * sin(lat) * sin(delta_s) + cos(lat) * cos(delta_s) * sin(ws))', {
                    'PI': ee.Number(3.1415926535),
                    'dr': dr,
                    'ws': ws,
                    'lat': lat_rad,
                    'delta_s': delta_s,
                })

            # Clear-sky solar radiation
            rso = elevation.expression('(0.75 + 0.00002 * elevation) * ra', {'elevation': elevation, 'ra': ra})
            rs_rso = srad_mj_per_day.divide(rso).min(ee.Image.constant(1.0))

            # Net longwave radiation
            tmax_k = tmax.add(273.15)
            tmin_k = tmin.add(273.15)
            rnl = tmax_k.expression(
                'sigma * ((TmaxK**4 + TminK**4) / 2) * (0.34 - 0.14 * sqrt(ea)) * (1.35 * rs_rso - 0.35)', {
                    'sigma': ee.Number(sigma),
                    'TmaxK': tmax_k,
                    'TminK': tmin_k,
                    'ea': ea,
                    'rs_rso': rs_rso
                })

            # Total net radiation
            rn = rns.subtract(rnl)

            if not wind_speed:
                # Wind speed is a constant, so make it an image for calculations.
                wind_speed_img = ee.Image.constant(2.0)
            else:
                # --- Fetch and calculate daily wind speed from ERA5 ---
                date = image.date()

                # Filter the wind collection for the specific day and select the wind bands
                wind_image = wind_collection.filterDate(date, date.advance(1, 'day')).first()
                u_wind = wind_image.select('u_component_of_wind_10m')
                v_wind = wind_image.select('v_component_of_wind_10m')

                # Calculate the wind speed magnitude at 10m
                wind_speed_10m = u_wind.pow(2).add(v_wind.pow(2)).sqrt()

                # Adjust to 2m wind speed by multiplying by 0.75
                wind_speed_img = wind_speed_10m.multiply(0.75)

            # --- Penman-Monteith equation ---

            # Numerator and denominator
            # Corrected: convert constants to images before operations
            numerator_energy = rn.multiply(0.408).multiply(delta)

            # Corrected: convert 900 to an image before division
            numerator_aero = gamma.multiply(ee.Image.constant(900).divide(t_mean.add(273))).multiply(
                wind_speed_img).multiply(es_minus_ea)

            # Corrected: convert 1 to an image before addition
            denominator = delta.add(gamma.multiply(ee.Image.constant(1).add(wind_speed_img.multiply(0.34))))

            # Final daily ETo
            eto_daily = numerator_energy.add(numerator_aero).divide(denominator).toFloat().rename('eto_daily')

            return eto_daily

        # If required bands are missing, return a constant image with the 'eto_daily' band to prevent errors.
        return ee.Algorithms.If(has_required_bands, perform_calculation(),
                                ee.Image.constant(-9999).toFloat().rename('eto_daily'))

    # Calculate annual ETo for each year.
    years = ee.List.sequence(ee.Date(start_day).get('year'), ee.Date(end_day).get('year'))

    def calculate_annual_eto(year):
        """
        Calculates the total ETo for a single year by filtering the original collection
        and then mapping the daily calculation function.
        """
        # Filter the original daymet collection for the specific year.
        annual_collection = daymet_collection.filter(ee.Filter.calendarRange(year, year, 'year'))

        # Map the daily ETo calculation over the annual collection.
        eto_daily_annual_collection = ee.ImageCollection(annual_collection.map(calculate_daily_eto))

        # Remove any images where the daily calculation returned the placeholder value.
        eto_daily_annual_collection = eto_daily_annual_collection.filter(ee.Filter.neq('eto_daily', -9999))

        # Sum the daily ETo for the year.
        annual_sum = eto_daily_annual_collection.sum()

        # Set a property on the image to identify its year.
        return ee.Image(annual_sum).set('year', year)

    # Map the annual calculation function over the list of years to get a collection of annual totals.
    eto_collection_annual = ee.ImageCollection(years.map(calculate_annual_eto))

    # Finally, calculate the average annual ETo over the entire period.
    ave_annual_eto = eto_collection_annual.mean().rename('average_annual_eto')

    return ave_annual_eto


if __name__ == "__main__":
    # Authentication should only need to be run once on a machine (maybe)
    # ee.Authenticate()
    ee.Initialize(project=EE_PROJECT)

    band = 'tmax'  # 'tmin', 'tmax', 'prcp', 'srad', 'vp', 'swe', 'dayl'
    start_date = '1994-01-01'
    end_date = '2023-12-31'
    # end_date = '1994-12-31'
    bbox = [-118, 42, -100, 52]  # {'west': -118.0, 'south': 42.0, 'east': -100.0, 'north': 52.0}
    # bbox = [-119, 40, -99, 52]  # big
    # bbox = [-112.1, 46.4, -111.9, 46.6]  # Helena
    region = ee.Geometry.Rectangle(bbox)
    export_folder = 'EarthEngine_Exports'
    export_file = '30yr_ave_July_tmean'
    asset_location = f'projects/{EE_PROJECT}/assets/{export_file}'

    # daymet_image = calc_CV()

    # daymet_image = calc_ETo(start_day=start_date, end_day=end_date, area=region, wind_speed=True)

    # daymet_image = return_elevation(area=region)

    daymet_image = calc_month_tmean(start_day=start_date, end_day=end_date, area=region, month=7)






    # daymet_image = calc_ETo_debugg(start_day=start_date, end_day=end_date, area=region)
    # export_file = 'ETo_debugg'

    # Set up the export task
    task = ee.batch.Export.image.toAsset(
        image=daymet_image,
        description=export_file,
        assetId=asset_location,
        region=region.getInfo()['coordinates'],  # region must be a GeoJSON-style object
        scale=SCALE_METERS,
        crs='EPSG:4326',  # Standard WGS84 CRS
        maxPixels=1e13
    )
    #
    # # task = ee.batch.Export.image.toDrive(
    # #     image=daymet_image,
    # #     description=export_file,
    # #     folder=export_folder,
    # #     fileNamePrefix=export_file,
    # #     region=region.getInfo()['coordinates'],  # region must be a GeoJSON-style object
    # #     scale=SCALE_METERS,
    # #     crs='EPSG:4326',  # Standard WGS84 CRS
    # #     maxPixels=1e13
    # # )

    # task.start()

    print(f"Task {export_file} Sent to Earth Engine")

    # batch_export_daymet_images(source_folder=f'projects/{EE_PROJECT}/assets',
    #                            bucket_name='wsb_gis_data',
    #                            destination_folder='basin_class',
    #                            sub_folder='daymet',
    #                            scale=1000)

    export_daymet_images(asset_id='30yr_ave_July_tmean',
                         source_folder=f'projects/{EE_PROJECT}/assets',
                         bucket_name='wsb_gis_data',
                         destination_folder='basin_class',
                         sub_folder='daymet',
                         scale=1000)
