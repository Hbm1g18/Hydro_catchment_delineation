import matplotlib.pyplot as plt
from pysheds.grid import Grid
from matplotlib.colors import ListedColormap
import geopandas as gpd
import numpy as np
import matplotlib.colors
import seaborn as sns
import rasterio
import geopandas as gpd
from shapely.geometry import Polygon
import os

# Load DEM raster
raster = 'NY30sw_DTM_1m.tif'
raster = 'NY30sw_DTM_1m.tif'
with rasterio.open(raster) as src:
    crs = src.crs
print(crs)

grid = Grid.from_raster(raster)
dem = grid.read_raster(raster)

# Condition DEM
# ----------------------
# Fill pits in DEM
pit_filled_dem = grid.fill_pits(dem)

# Fill depressions in DEM
flooded_dem = grid.fill_depressions(pit_filled_dem)
    
# Resolve flats in DEM
inflated_dem = grid.resolve_flats(flooded_dem)

# Determine D8 flow directions from DEM
# ----------------------
# Specify directional mapping
dirmap = (64, 128, 1, 2, 4, 8, 16, 32)
    
# Compute flow directions
# -------------------------------------
fdir = grid.flowdir(inflated_dem, dirmap=dirmap)

# Compute accumulation
acc = grid.accumulation(fdir, dirmap=dirmap)

# Display accumulation map and let user select pour point
plt.figure(figsize=(8, 6))
plt.imshow(acc, cmap='viridis', extent=grid.extent, norm=matplotlib.colors.LogNorm(vmin=1, vmax=1e6))
plt.colorbar(label='Accumulation')
plt.title('Click to select pour point')

# Initialize variables to store clicked coordinates
clicked_x, clicked_y = None, None

def onclick(event):
    # Use the global variables to store the clicked coordinates
    global clicked_x, clicked_y
    
    # Check if the click is within the extent of the grid
    if event.xdata is not None and event.ydata is not None:
        # Store the clicked coordinates
        clicked_x, clicked_y = int(event.xdata), int(event.ydata)
        plt.close()

plt.gcf().canvas.mpl_connect('button_press_event', onclick)
plt.show()

# print("Clicked coordinates:", clicked_x, clicked_y)

# Delineate a catchment
# ---------------------

# Snap pour point to high accumulation cell
x_snap, y_snap = grid.snap_to_mask(acc > 1000, (clicked_x, clicked_y))

# Delineate the catchment
catch = grid.catchment(x=x_snap, y=y_snap, fdir=fdir, dirmap=dirmap, 
                       xytype='coordinate')

# Crop and plot the catchment
# ---------------------------
# Clip the bounding box to the catchment
grid.clip_to(catch)
clipped_catch = grid.view(catch)

shapes = grid.polygonize()

polygons = [Polygon(shape[0]['coordinates'][0]) for shape in shapes]

gdf = gpd.GeoDataFrame(geometry=polygons, crs=crs)

folder_name = 'CatchmentShapefile'
if not os.path.exists(folder_name):
    os.makedirs(folder_name)

shapefile_path = os.path.join(folder_name, 'catchment_shapefile.shp')
gdf.to_file(shapefile_path)


# Extract river network
# ---------------------
branches = grid.extract_river_network(fdir, acc > 1000, dirmap=dirmap)

sns.set_palette('husl')
fig, ax = plt.subplots(figsize=(6,4))

plt.xlim(grid.bbox[0], grid.bbox[2])
plt.ylim(grid.bbox[1], grid.bbox[3])
ax.set_aspect('equal')

for branch in branches['features']:
    line = np.asarray(branch['geometry']['coordinates'])
    plt.plot(line[:, 0], line[:, 1])
    
_ = plt.title('D8 channels', size=10)

plt.show()