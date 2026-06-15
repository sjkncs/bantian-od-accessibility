# -*- coding: utf-8 -*-
"""
在ArcGIS Desktop (ArcMap) 中运行此脚本以生成MXD文件
使用方法: 在ArcMap中打开Python窗口，粘贴运行
或在ArcGIS Pro的Python环境中运行

注意: 所有数据路径使用相对路径
"""
import arcpy
import os

# 设置工作目录（相对于本脚本所在位置）
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# 设置相对路径（关键！不使用绝对路径）
arcpy.env.workspace = "."
mxd_path = os.path.join(".", "坂田秋港花园交通网络分析.mxd")

# 创建MXD
mxd = arcpy.mapping.MapDocument("EMPTY")
df = arcpy.mapping.ListDataFrames(mxd)[0]
df.name = "交通网络分析"

# 设置投影坐标系
sr = arcpy.SpatialReference(4547)  # CGCS2000 3度带38带
df.spatialReference = sr

# 添加图层（相对路径）
shp_dir = os.path.join(".", "shapefiles_cgcs2000")

# 道路
road_layer = arcpy.mapping.Layer(os.path.join(shp_dir, "bantian_roads.shp"))
road_layer.name = "道路"
arcpy.mapping.AddLayer(df, road_layer, "BOTTOM")

# 网络边
edge_layer = arcpy.mapping.Layer(os.path.join(shp_dir, "network_edges.shp"))
edge_layer.name = "交通网络边"
arcpy.mapping.AddLayer(df, edge_layer, "AUTO_ARRANGE")

# 住宅小区
comm_layer = arcpy.mapping.Layer(os.path.join(shp_dir, "communities.shp"))
comm_layer.name = "住宅小区"
arcpy.mapping.AddLayer(df, comm_layer, "AUTO_ARRANGE")

# 医院
hosp_layer = arcpy.mapping.Layer(os.path.join(shp_dir, "hospitals.shp"))
hosp_layer.name = "综合医院"
arcpy.mapping.AddLayer(df, hosp_layer, "TOP")

# 缩放到全图
df.extent = road_layer.getExtent()

# 保存MXD（相对路径）
mxd.saveACopy(mxd_path)
print(f"MXD已保存: {mxd_path}")

# 导出JPG
jpg_path = os.path.join(".", "figures", "arcpy_network_map.jpg")
arcpy.mapping.ExportToJPEG(mxd, jpg_path, df, resolution=200)
print(f"JPG已导出: {jpg_path}")

del mxd
print("完成！")
