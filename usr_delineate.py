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
import argparse
from osgeo import ogr
import json

# Initialize variables to store clicked coordinates
clicked_x, clicked_y = None, None

def onclick(event):
    # Use the global variables to store the clicked coordinates
    global clicked_x, clicked_y
    
    # Check if the click is within the extent of the grid
    if event.xdata is not None and event.ydata is not None:
        # Store the clicked coordinates
        clicked_x, clicked_y = int(event.xdata), int(event.ydata)
        print(clicked_x, clicked_y)
        plt.close()

thresholds = [50, 100, 500, 1000, 1500, 2000]


def main():
    parser = argparse.ArgumentParser(description="Generates an exif CSV for GPS data from a folder")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-a', '--all', action='store_true', help='Process all items')
    group.add_argument('-t', '--threshold', type=int, help='Specify a threshold value')

    parser.add_argument('-r', help="Input raster", required=True)

    args = parser.parse_args()

    if not (args.all or args.threshold):
        parser.error('Specify either -a for all or -t for a threshold')


    raster = args.r

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

    plt.gcf().canvas.mpl_connect('button_press_event', onclick)
    plt.show()

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
    parent_folder = "Network_Branches"
    os.makedirs(parent_folder, exist_ok=True)

    if args.all:
        # Iterate over thresholds
        for threshold in thresholds:
            # Extract river network with the current threshold
            branches = grid.extract_river_network(fdir, acc > threshold, dirmap=dirmap)
            branches_geojson = branches

            geojson_str = json.dumps(branches_geojson)
            geojson_mem_ds = ogr.Open(geojson_str)

            folder_name = os.path.join(parent_folder, f"Network_Branches_{threshold}")
            os.makedirs(folder_name, exist_ok=True)

            output_shapefile = os.path.join(folder_name, f"Network_Branches_{threshold}.shp")
            driver = ogr.GetDriverByName("ESRI Shapefile")
            shapefile_ds = driver.CreateDataSource(output_shapefile)

            for layer_index in range(geojson_mem_ds.GetLayerCount()):
                layer = geojson_mem_ds.GetLayerByIndex(layer_index)
                shapefile_layer = shapefile_ds.CreateLayer(
                    layer.GetName(), geom_type=layer.GetGeomType()
                )

                layer_defn = layer.GetLayerDefn()
                for i in range(layer_defn.GetFieldCount()):
                    field_defn = layer_defn.GetFieldDefn(i)
                    shapefile_layer.CreateField(field_defn)

                # Copy features
                for feature in layer:
                    shapefile_layer.CreateFeature(feature)

            # Close datasets
            geojson_mem_ds = None
            shapefile_ds = None

    elif args.threshold is not None:
        branches = grid.extract_river_network(fdir, acc > args.threshold, dirmap=dirmap)
        branches_geojson = branches

        geojson_str = json.dumps(branches_geojson)
        geojson_mem_ds = ogr.Open(geojson_str)

        output_shapefile = os.path.join(parent_folder, f"Network_Branches_{args.threshold}.shp")
        driver = ogr.GetDriverByName("ESRI Shapefile")
        shapefile_ds = driver.CreateDataSource(output_shapefile)

        for layer_index in range(geojson_mem_ds.GetLayerCount()):
            layer = geojson_mem_ds.GetLayerByIndex(layer_index)
            shapefile_layer = shapefile_ds.CreateLayer(
                layer.GetName(), geom_type=layer.GetGeomType()
            )

            layer_defn = layer.GetLayerDefn()
            for i in range(layer_defn.GetFieldCount()):
                field_defn = layer_defn.GetFieldDefn(i)
                shapefile_layer.CreateField(field_defn)

            for feature in layer:
                shapefile_layer.CreateFeature(feature)
                
        geojson_mem_ds = None
        shapefile_ds = None


if __name__ == '__main__':
    main()