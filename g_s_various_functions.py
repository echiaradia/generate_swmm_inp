# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GenerateSwmmInp
                                 A QGIS plugin
 This plugin generates SWMM Input files
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-07-09
        copyright            : (C) 2022 by Jannik Schilling
        email                : jannik.schilling@posteo.de
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Jannik Schilling'
__date__ = '2022-04-28'
__copyright__ = '(C) 2022 by Jannik Schilling'


import numpy as np
import pandas as pd
from datetime import datetime
from qgis.core import QgsWkbTypes, QgsProcessingException, QgsEditorWidgetSetup

## geometry functions
def get_coords_from_geometry(df):
    """
    extracts coords from any gpd.geodataframe
    :param pd.DataFrame df
    """
    def extract_xy_from_simple_line(line_simple):
        """extracts x and y coordinates from a LineString"""
        xy_arr = np.dstack((p.x(),p.y()) for p in line_simple)[0]
        xy_df = pd.DataFrame(xy_arr.T,columns = ['x','y'])
        return xy_df
    def extract_xy_from_line(line_row):
        """extraxts xy from LineString or MultiLineString"""
        if QgsWkbTypes.displayString(line_row.wkbType()) == 'LineString':
            return extract_xy_from_simple_line(line_row.asPolyline())
        if QgsWkbTypes.displayString(line_row.wkbType()) == 'MultiLineString':
            xy_list = [extract_xy_from_simple_line(line_simple) for line_simple in line_row.asMultiPolyline()]
            return pd.concat(xy_list, ignore_index=True)
    if all(QgsWkbTypes.displayString(g_type.wkbType()) in ['Point'] for g_type in df.geometry):
        df['X_Coord'] = [str(df_row.asPoint().x()) for df_row in df['geometry']]
        df['Y_Coord'] = [str(df_row.asPoint().y()) for df_row in df['geometry']]
        return df['X_Coord'],df['Y_Coord']
    if all(QgsWkbTypes.displayString(g_type.wkbType()) in ['LineString', 'MultiLineString'] for g_type in df.geometry):
        return {na:extract_xy_from_line(geom) for geom,na in zip(df.geometry,df.Name)}
    if all(QgsWkbTypes.displayString(g_type.wkbType()) in ['Polygon', 'MultiPolygon'] for g_type in df.geometry):
        def extract_xy_from_area(geom_row):
            """extraxts xy from MultiPolygon or Polygon"""
            if QgsWkbTypes.displayString(geom_row.wkbType()) == 'MultiPolygon':
                xy_arr = np.dstack((v.x(),v.y()) for v in geom_row.vertices())[0]
                xy_df = pd.DataFrame(xy_arr.T,columns = ['x','y'])
                return xy_df
            if QgsWkbTypes.displayString(geom_row.wkbType()) == 'Polygon':
                xy_arr = np.dstack((v.x(),v.y()) for v in geom_row.vertices())[0]
                xy_df = pd.DataFrame(xy_arr.T,columns = ['x','y'])
                return xy_df
        return {na:extract_xy_from_area(ge) for ge,na in zip(df.geometry,df.Name)}

def get_point_from_x_y(sr):
    """
    converts x and y coordinates from a pd.Series to a QgsPoint geometry
    :param pd.Series sr
    """
    from qgis.core import QgsGeometry
    x_coord = sr['X_Coord']
    y_coord = sr['Y_Coord']
    geom = QgsGeometry.fromWkt('POINT('+str(x_coord)+' '+str(y_coord)+')')
    return [sr['Name'],geom]
    
    

    

## functions for data in tables
def get_curves_from_table(curves_raw, name_col):
    """
    generates curve data for the input file from tables (curve_raw)
    :param pd.DataFrame curve_raw
    :param str name_col
    """
    from .g_s_defaults import def_curve_types
    curve_dict = dict()
    for curve_type in def_curve_types:
        if curve_type in curves_raw.keys():
            curve_df = curves_raw[curve_type]
            if len(curve_df.columns) > 3:
                curve_df = curve_df[curve_df.columns[:3]]
            curve_df = curve_df[curve_df[name_col] != ";"]
            curve_df = curve_df[pd.notna(curve_df[name_col])]
            if curve_df.empty:
                pass
            else:
                curve_df.set_index(keys=[name_col], inplace=True)
                for i in curve_df.index.unique():
                    curve = curve_df[curve_df.index == i]
                    curve = curve.reset_index(drop=True)
                    curve_dict[i] = {'Name':i, 'Type':curve_type,'frame':curve}
    return(curve_dict)
    

def get_patterns_from_table(patterns_raw, name_col):
    """
    generates a pattern dict for the input file from tables (patterns_raw)
    :param pd.DataFrame patterns_raw
    :param str name_col
    """
    pattern_types = ['HOURLY','DAILY','MONTHLY','WEEKEND']
    pattern_dict = {}
    for pattern_type in pattern_types:
        pattern_df = patterns_raw[pattern_type]
        pattern_df = pattern_df[pattern_df[name_col] != ";"]
        pattern_df = pattern_df[pd.notna(pattern_df[name_col])]
        if pattern_df.empty:
            pass
        else:
            pattern_df.set_index(keys=[name_col], inplace=True)
            for i in pattern_df.index.unique():
                pattern = pattern_df[pattern_df.index == i]
                pattern = pattern.drop(columns = pattern.columns[0])
                pattern = pattern.reset_index(drop=True)
                pattern_dict[i] = {'Name':i, 'Type':pattern_type,'Factors':pattern}
    return(pattern_dict)
    
    
def get_timeseries_from_table(ts_raw, name_col, feedback):
    """
    enerates a timeseries dict for the input file from tables (ts_raw)
    :param pd.DataFrame ts_raw
    :param str name_col
    :param QgsProcessingFeedback feedback
    """
    ts_dict = dict()
    ts_raw = ts_raw[ts_raw[name_col] != ";"]
    if not 'File_Name' in ts_raw.columns:
        feedback.setProgressText('No external file is used in time series')
    if ts_raw.empty:
        pass
    else:
        for i in ts_raw[name_col].unique():
            ts_df = ts_raw[ts_raw[name_col] == i]
            if 'File_Name' in ts_raw.columns and not all(pd.isna(ts_df['File_Name'])): # external time series
                    ts_df['Date'] = 'FILE'
                    ts_df['Time'] = ts_df['File_Name']
                    ts_df['Value'] = ''
            else:
                try:
                    ts_df['Date']= [t.strftime('%m/%d/%Y') for t in ts_df['Date']]
                except:
                    ts_df['Date'] = [str(t) for t in ts_df['Date']]
                try:
                    ts_df['Time'] = [t.strftime('%H:%M') for t in ts_df['Time']]
                except:
                    # if string or numeric
                    str_formats = ['%H:%M:%S', '%H:%M', '%H']
                    for st in str_formats:
                        try:
                            ts_df['Time'] = [datetime.strptime(str(t),st) for t in ts_df['Time']]
                            ts_df['Time'] = [t.strftime('%H:%M') for t in ts_df['Time']]
                        except:
                            ts_df['Time'] = [str(t) for t in ts_df['Time']]
                        else:
                            break
            ts_description= ts_df['Description'].fillna('').unique()[0]
            ts_format= ts_df['Format'].fillna('').unique()[0]
            ts_type = ts_df['Type'].unique()[0]
            ts_dict[i] = {'Name':i,
                   'Type':ts_type,
                   'TimeSeries':ts_df[['Name','Date','Time','Value']], 
                   'Description':ts_description,
                   'Format':ts_format}
    return(ts_dict)
    
    




## errors and feedback


def check_columns(swmm_data_file, cols_expected, cols_in_df):
    """
    checks if all columns are in a dataframe
    :param str swmm_data_file
    :param list cols_expected
    :param list cols_in_df
    """
    missing_cols = [x for x in cols_expected if x not in cols_in_df]
    if len(missing_cols) == 0:
        pass
    else:
        err_message = 'Missing columns in '+swmm_data_file+': '+', '.join(missing_cols)
        err_message = err_message+'. For further advice regarding columns, read the documentation file in the plugin folder.'
        raise QgsProcessingException(err_message)
        
        
# input widgets
def field_to_value_map(layer, field, list_values):
    """
    creates a drop down menue in QGIS layers
    :param str layer 
    :param str field
    :param list list_values
    """
    config = {'map' : list_values}
    widget_setup = QgsEditorWidgetSetup('ValueMap',config)
    field_idx = layer.fields().indexFromName(field)
    layer.setEditorWidgetSetup(field_idx, widget_setup)