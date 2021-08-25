#!/usr/bin/python3

import geopandas
import json
import multiprocessing
import subprocess
import os
from shapely.geometry import Point, Polygon, mapping, MultiPolygon
from geographiclib.geodesic import Geodesic
from sqlalchemy import Column, Integer, String, TIMESTAMP, create_engine, BigInteger, dialects, inspect
from sqlalchemy.dialects.postgresql import insert
from geoalchemy2 import WKTElement, Geometry
import sys
import shapely
from pyproj import CRS
import fiona

unique_id = 'id'
engine=create_engine(
    "postgresql://openindoor-db-admin:admin123@openindoor-db:5432/openindoor-db")
# lambert_93 = "EPSG:27561"
# lambert_93 = "EPSG:2154"

def _to_2d(x, y, z = None):
    return tuple(filter(None, [x, y]))

def to_geojson(pool, lock, floor_gdf):

    data_gdf = geopandas.read_postgis(
        "SELECT geometry AS geom, layer, paperspace, subclasses, linetype, entityhandle, text, level, geom_type, plan, index FROM bim2",
        con = engine
    )
    if "layer:room" in floor_gdf.iloc[0]:
        data_gdf[
            data_gdf["layer"]==floor_gdf["layer:room"][0]
            ].to_file(
                os.path.splitext(floor_gdf["raw_geojson"][0])[0] + "_room.geojson",
                driver='GeoJSON',
                encoding='utf-8'
            )
    if "layer:corridor" in floor_gdf.iloc[0]:
        data_gdf[
            data_gdf["layer"]==floor_gdf["layer:corridor"][0]
            ].to_file(
                os.path.splitext(floor_gdf["raw_geojson"][0])[0] + "_corridor.geojson",
                driver='GeoJSON',
                encoding='utf-8'
            )
    if "layer:room_name" in floor_gdf.iloc[0]:
        data_gdf[
            data_gdf["layer"]==floor_gdf["layer:room_name"][0]
            ].to_file(
                os.path.splitext(floor_gdf["raw_geojson"][0])[0] + "_room_name.geojson",
                driver='GeoJSON',
                encoding='utf-8'
            )
   

def dxf_to_postgis(pool, lock, floor_gdf):
    # Read AutoCAD file
    print("Read AutoCAD file:", floor_gdf["dxf"][0], flush=True)
    lambert_93 = floor_gdf["crs"][0]
    autocad_plan_gdf = geopandas.read_file(floor_gdf["dxf"][0], crs = lambert_93, encoding='utf-8', env = fiona.Env(DXF_ENCODING="UTF-8"))
    # autocad_gps_gdf = autocad_plan_gdf.set_crs(lambert_93, allow_override=True).to_crs('EPSG:4326')

    cmd = f"""ogr2ogr \
            -f 'GeoJSON' \
            /data/{floor_gdf["raw_geojson"][0]} \
            /data/{floor_gdf["dxf"][0]} \
            -t_srs EPSG:4326 \
            -s_srs {lambert_93}"""

# export DXF_ENCODING="UTF-8"
# ogr2ogr \
#     -f 'GeoJSON' /data/ISIMA/floor_000/ISIMA_RDC_geo.geojson \
#     /data/ISIMA/floor_000/ISIMA_RDC.dxf \
#     -t_srs EPSG:4326 \
#     -s_srs EPSG:27561
    my_env = os.environ.copy()
    my_env["DXF_ENCODING"] = "UTF-8"

    print("cmd:", flush=True)
    print(cmd, flush=True)
    subprocess.run(cmd, shell=True, env=my_env)

    autocad_gps_gdf = geopandas.read_file(floor_gdf["raw_geojson"][0], crs = 'EPSG:4326', encoding='utf-8')



    autocad_gps_gdf['geometry']=autocad_gps_gdf.geometry.apply(
        lambda shap: shapely.ops.transform(_to_2d, shap)
    )    

    autocad_gps_gdf['plan'] = floor_gdf["dwg"][0]
    autocad_gps_gdf['level'] = floor_gdf["level"][0]    
    autocad_gps_gdf['geom_type'] = autocad_gps_gdf.geometry.apply(
        lambda shap: shap.geom_type
    )
    
    autocad_gps_gdf.to_file(floor_gdf["raw_geojson"][0], driver='GeoJSON', encoding='utf-8')



    minx, miny, maxx, maxy = autocad_plan_gdf[autocad_plan_gdf["Layer"]==floor_gdf["layer:bound"][0]].total_bounds
    autocad_gcp_ungeoref_gdf = geopandas.GeoDataFrame.from_features(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [minx, miny],
                            [minx, maxy],
                            [maxx, miny]         
                        ]
                    }
                },
            ]
        },
        crs=floor_gdf["crs"][0]
    )
    autocad_gcp_ungeoref_gps_gdf = autocad_gcp_ungeoref_gdf.to_crs('EPSG:4326')
    (ungeoref_x, ungeoref_y) = autocad_gcp_ungeoref_gps_gdf["geometry"][0].coords.xy
    (georef_x, georef_y) = floor_gdf["geometry"][0].coords.xy

    # update geojson

        # -f 'GeoJSON' /data/ISIMA/floor_000/ISIMA_RDC.geojson \
    cmd = f"""ogr2ogr \
            -progress \
            -append \
            -f PostgreSQL PG:"dbname=openindoor-db host=openindoor-db port=5432 user=openindoor-db-admin password=admin123" \
            /data/{floor_gdf["raw_geojson"][0]} \
            --config OGR_TRUNCATE YES \
            -lco GEOMETRY_NAME=geometry \
            -lco FID=index \
            -nln bim2 \
            -gcp {ungeoref_x[0]} {ungeoref_y[0]}  {georef_x[0]} {georef_y[0]} \
            -gcp {ungeoref_x[1]} {ungeoref_y[1]}  {georef_x[1]} {georef_y[1]} \
            -gcp {ungeoref_x[2]} {ungeoref_y[2]}  {georef_x[2]} {georef_y[2]}"""

    print("cmd:", flush=True)
    # print(cmd, flush=True)
    subprocess.run(cmd, shell=True)


def main():
    print("Starting process...")

    os.chdir('/data/')
    with open("BIM.geojson") as bim:
        floors = json.load(bim)

    # with Pool(multiprocessing.cpu_count() - 1) as pool:
    with multiprocessing.Pool() as pool:
        manager = multiprocessing.Manager()
        lock = manager.Lock()


        for feature in floors["features"]:
            gdf = geopandas.GeoDataFrame.from_features(
                {
                    "type": "FeatureCollection",
                    "features": [feature]
                },
                crs="EPSG:4326"
            )
            print(gdf.iloc[0], flush=True)
            # dxf_to_postgis(pool, lock, gdf)
            to_geojson(pool, lock, gdf)

if __name__ == "__main__":
    main()
