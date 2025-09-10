from src.chmdata import prism

# get mean temp and pecip monthly averaged data, will create relative file path named "Downloads"
prism.PRISM(2013, 2023, 'tmean', 'Downloads')
prism.PRISM(2013, 2023, 'ppt', 'Downloads')

# First we need to calculate precip seasonality index, this will aggregate and save our precip data as raster
SI = prism.SI(2013, 2023, 'Downloads')
SI.calc_SI()

# We can now calculate percent annual precip fallen as snow and save as raster
PPS = prism.PPS(2013, 2023, 'Downloads')
PPS.calc_PPS()
