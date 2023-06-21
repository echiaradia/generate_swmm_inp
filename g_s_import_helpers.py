# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GenerateSwmmInp
                                 A QGIS plugin
 This plugin generates SWMM Input files
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-07-09
        copyright            : (C) 2023 by Jannik Schilling
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
__date__ = '2023-06-01'
__copyright__ = '(C) 2023 by Jannik Schilling'

import pandas as pd
import numpy as np
import copy
import os
from datetime import datetime
from qgis.core import (
    QgsProcessingException,
    QgsProcessingContext,
    QgsProject,
    QgsVectorLayer,
    NULL
)
from .g_s_defaults import (
    annotation_field_name,
    def_layer_names_dict,
    def_sections_dict,
    def_sections_geoms_dict,
    def_stylefile_dict,
    def_qgis_fields_dict,
    ImportDataStatus,
    st_files_path
)
from .g_s_nodes import (
    create_points_df,
    get_storages_from_inp,
    get_outfalls_from_inp,
    get_dividers_from_inp
)
from .g_s_subcatchments import (
    get_raingages_from_inp,
    create_polygons_df,
    prepare_infiltration_inp_lines,
    create_infiltr_df
)
from .g_s_links import (
    create_lines_for_section,
    adjust_xsection_df,
    adjust_outlets_list
)
from .g_s_read_write_data import (
    create_layer_from_df
)

# main function
def sect_list_import_handler(
    section_name,
    dict_all_vals,
    out_type,
    feedback,
    import_parameters_dict=None
):
    """
    prepares raw data lists for every section
    :param str section_name
    :param dict dict_all_vals
    :param str out_type: geodata, table, data_join, geom_join
    :parama QgsProcessingFeedback feedback
    """
    if out_type in ['geom_join', 'data_join']:
        #create empty data if the section is not available
        if not section_name in dict_all_vals.keys():
            dict_all_vals[section_name]={}
            dict_all_vals[section_name]['data'] = []
            dict_all_vals[section_name]['n_objects'] = 0
            dict_all_vals[section_name]['status'] = ImportDataStatus.RAW
        data_dict = dict_all_vals[section_name]

        # skip if the section is already processed
        if data_dict['status'] == ImportDataStatus.PROCESSED:
            pass
        else:
            feedback.setProgressText('Preparing section \"'+section_name+'\"')

            # preparation
            if section_name == 'INFILTRATION':
                data_dict['data'] = [
                    prepare_infiltration_inp_lines(
                        inp_line,
                        **import_parameters_dict
                    ) for inp_line in data_dict['data']
                ]

            # build df
            df_join = build_df_sect_direct(section_name, data_dict)
            if out_type == 'geom_join':
                dict_all_vals[section_name]['data'] = create_points_df(df_join, feedback)
            if out_type == 'data_join':
                # adjustments
                if section_name == 'XSECTIONS':
                    df_join = adjust_xsection_df(df_join)
                if section_name == 'INFILTRATION':
                    df_join = df_join.apply(lambda x: create_infiltr_df(x, feedback), axis=1)
                df_join = df_join.applymap(replace_nan_null)
                data_dict['data'] = df_join.set_index('Name')
            dict_all_vals[section_name]['status'] = ImportDataStatus.PROCESSED
    else:
        if not section_name in dict_all_vals.keys():
            pass
        else:
            feedback.setProgressText('Preparing section \"'+section_name+'\"')
            data_dict = dict_all_vals[section_name]
            if out_type == 'geodata':
                # data preparation
                if section_name == 'RAINGAGES':
                    data_dict['data'] = [get_raingages_from_inp(inp_line, feedback) for inp_line in data_dict['data']]
                    diff_fields = list(def_qgis_fields_dict[section_name].keys())               
                if section_name == 'STORAGE':
                    data_dict['data'] = [get_storages_from_inp(inp_line, feedback) for inp_line in data_dict['data']]
                if section_name == 'OUTFALLS':
                    data_dict['data'] = [get_outfalls_from_inp(inp_line, feedback) for inp_line in data_dict['data']]
                if section_name == 'DIVIDERS':
                    data_dict['data'] = [get_dividers_from_inp(inp_line, feedback) for inp_line in data_dict['data']]
                if section_name == 'OUTLETS':
                    data_dict['data'] = [adjust_outlets_list(inp_line, feedback) for inp_line in data_dict['data']]
                if section_name == 'RAINGAGES':
                    df_processed = build_df_sect_direct(
                            section_name, 
                            data_dict,
                            with_annot=True,
                            diff_fields = diff_fields
                        )
                else:
                    df_processed = build_df_sect_direct(
                            section_name, 
                            data_dict,
                            with_annot=True,
                        )
                
                # join data
                if section_name in ['CONDUITS', 'WEIRS', 'ORIFICES']:
                    sect_list_import_handler('XSECTIONS', dict_all_vals, 'data_join', feedback)
                    xsects_df = dict_all_vals['XSECTIONS']['data']
                    df_processed = df_processed.join(xsects_df, on='Name')
                    if section_name == 'CONDUITS':
                        sect_list_import_handler('LOSSES', dict_all_vals, 'data_join', feedback)
                        losses_df = dict_all_vals['LOSSES']['data']
                        df_processed = df_processed.join(losses_df, on='Name')
                    # adjustments; ToDo: as functions
                    if section_name == 'WEIRS':
                        df_processed = df_processed.drop(
                            columns=['Shape', 'Geom4', 'Barrels', 'Culvert', 'Shp_Trnsct']
                        )
                        df_processed = df_processed.rename(
                            columns={
                                'Geom1': 'Height',
                                'Geom2': 'Length',
                                'Geom3': 'SideSlope'
                            }
                        )
                    if section_name == 'ORIFICES':
                        df_processed = df_processed.drop(
                            columns=['Geom3', 'Geom4', 'Barrels', 'Culvert', 'Shp_Trnsct']
                        )
                        df_processed = df_processed.rename(
                            columns={'Geom1': 'Height', 'Geom2': 'Width'}
                        )
                if section_name == 'SUBCATCHMENTS':
                    for sect_join in ['SUBAREAS', 'INFILTRATION']:
                        sect_list_import_handler(sect_join, dict_all_vals, 'data_join', feedback, import_parameters_dict)
                        df_for_join = dict_all_vals[sect_join]['data']
                        df_processed = df_processed.join(df_for_join, on='Name')
                    
                # get geometries          
                if def_sections_geoms_dict[section_name] == 'Point':
                    if section_name in ['JUNCTIONS', 'STORAGE', 'OUTFALLS', 'DIVIDERS']:
                        sect_list_import_handler('COORDINATES', dict_all_vals, 'geom_join', feedback)
                        ft_geoms = dict_all_vals['COORDINATES']['data']
                    if section_name == 'RAINGAGES':
                        sect_list_import_handler('SYMBOLS', dict_all_vals, 'geom_join', feedback)
                        ft_geoms = dict_all_vals['SYMBOLS']['data']
                if def_sections_geoms_dict[section_name] == 'LineString':
                    sect_list_import_handler('VERTICES', dict_all_vals, 'geom_join', feedback)
                    sect_list_import_handler('COORDINATES', dict_all_vals, 'geom_join', feedback)   
                    ft_geoms = create_lines_for_section(df_processed, dict_all_vals, feedback)
                if def_sections_geoms_dict[section_name] == 'Polygon':
                    sect_list_import_handler('POLYGONS', dict_all_vals, 'geom_join', feedback)
                    ft_geoms = create_polygons_df(df_processed, dict_all_vals, feedback)
                # join geometries        
                df_processed = df_processed.join(ft_geoms, on='Name')
                
                # write
                df_processed = df_processed.applymap(replace_nan_null)
                dict_all_vals[section_name]['data'] = df_processed
                dict_all_vals[section_name]['status'] = ImportDataStatus.GEOM_READY

            if out_type == 'table':
                pass


def build_df_sect_direct(section_name,
    data_dict,
    with_annot=False,
    diff_fields=None
):
    """
    builds dataframes for a section
    :param str section_name: Name of the SWMM section in the input file
    :param dict data_dict
    :param bool with_annot: indicates if an annotations column will be added
    :return: pd.DataFrame
    """
    if diff_fields is not None:
        col_names = diff_fields
        if with_annot:
            col_names = col_names + [annotation_field_name]
    else:
        if type(def_sections_dict[section_name]) == list:
            col_names = def_sections_dict[section_name]
            if with_annot:
                col_names = col_names + [annotation_field_name]
        if def_sections_dict[section_name] is None:
            col_names = None
    # empty df with correct columns
    if data_dict['n_objects'] == 0:
        df = pd.DataFrame(columns=col_names)
    else:
        df = build_df_from_vals_list(
            copy.deepcopy(data_dict['data']),
            col_names
        )
        if with_annot:
            section_annots = data_dict['annotations']
            df[annotation_field_name] = df['Name'].map(section_annots)
    return df
    

def build_df_from_vals_list(section_vals, col_names):
    """
    builds a dataframe for a section; 
    missing vals at the end are set as np.nan
    :param list section_vals
    :param list col_names
    :return: pd.DataFrame
    """
    df = pd.DataFrame(section_vals)
    col_len = len(df.columns)
    if col_names is None:
        pass
    else:
        df.columns = col_names[0:col_len]
        if len(col_names) > col_len:  # if missing vals in inp-data
            for i in col_names[col_len:]:
                df[i] = np.nan
    return df


def concat_quoted_vals(text_line):
    """
    finds quoted text and cocatenates text strings if
    they have been separated by whitespace or other separators
    """
    if any([x.startswith('"') for x in text_line]):  # any quoted elements
        text_line_new = []
        i = 0
        quoted_elem = 0  # set not quoted
        for t_l in text_line:
            if quoted_elem == 0:  # is not quoted
                text_line_new = text_line_new + [[t_l]]
                if t_l.startswith('"'):
                    quoted_elem = 1  # set quoted
                    # t_l is not '"' and fully quoted (e.g. '"test"')
                    if len(t_l) > 1 and t_l.endswith('"'):  
                        quoted_elem = 0  # set not quoted again
                        i += 1
                else:
                    i += 1
            else:  # is quoted and has been separated
                text_line_new[i] = text_line_new[i]+[t_l]
                if t_l.endswith('"'):
                    quoted_elem = 0  # set not quoted again
                    i += 1
                else:
                    pass  # keep quoted and i
        text_line_new = [' '.join(x) for x in text_line_new]  # concatenate strings
    else:
        text_line_new = text_line
    return text_line_new 

def replace_nan_null(data):
    """replaces np.nan or asterisk with NULL"""
    if pd.isna(data):
        return NULL
    elif data == '*':
        return NULL
    else:
        return data
    

def get_annotations(
    section_text,
    startpoint,
    endpoint,
    section_len
):
    """
    concats annotations for a feature
    :param list section text
    :param int startpoint
    :param int endpoint
    :param in section_len
    """
    annot_text_list = [x[1:] for x in section_text[startpoint:(endpoint+1)]]
    annot_text = ' '.join(annot_text_list)
    if endpoint+1 != section_len:
        feature_name = section_text[endpoint+1].split()[0]
        return [feature_name, annot_text]


def extract_sections_from_text(
    inp_text,
    text_limits,
    section_key
):
    """
    extracts sections from inp_text
    :param dict text_limits: line numbers at beginning and end sections
    :param str section_key 
    :return: dict
    """
    section_text = inp_text[text_limits[0]+1:text_limits[1]]
    # find descriptions
    section_len = len(section_text)
    annotations_list = [i for i, x in enumerate(section_text) if x.startswith(';')]
    annot_starts = [i for i in annotations_list if i-1 not in annotations_list]
    annot_ends = [i for i in annotations_list if i+1 not in annotations_list]
    annot_result_list = [get_annotations(section_text, s, e, section_len) for s, e in zip(annot_starts, annot_ends)]
    annot_dict = {i[0]: i[1] for i in annot_result_list if i is not None}
    # exclude empty comments
    annot_dict = {k: v for k, v in annot_dict.items() if len(v) > 0}
    section_text = [x for x in section_text if not x.startswith(';')]  # delete annotations / descriptions
    section_vals = [x.split() for x in section_text]
    section_vals_clean = [concat_quoted_vals(x) for x in section_vals]
    inp_extracted = {
        'data': section_vals_clean,
        'status': ImportDataStatus.RAW,
        'annotations': annot_dict,
        'n_objects': len(section_vals_clean)
    }
    return inp_extracted
    
def build_df_for_section(section_name, dict_all_raw_vals, with_annot=False):
    """
    builds dataframes for a section
    :param str section_name: Name of the SWMM section in the input file
    :param list dict_all_raw_vals
    :param bool with_annot: indicates if an annotations column will be added
    :return: pd.DataFrame
    """
    if type(def_sections_dict[section_name]) == list:
        col_names = def_sections_dict[section_name]
        if with_annot:
            col_names = col_names + [annotation_field_name]
    if def_sections_dict[section_name] is None:
        col_names = None
    # empty df with correct columns
    if (
        section_name not in dict_all_raw_vals.keys() 
        or len(dict_all_raw_vals[section_name]['data']) == 0
    ):
        df = pd.DataFrame(columns=col_names)
    else:
        df = build_df_from_vals_list(
            dict_all_raw_vals[section_name]['data'],
            col_names
        )
        if with_annot:
            section_annots = dict_all_raw_vals[section_name]['annotations']
            df[annotation_field_name] = df['Name'].map(section_annots)
    return df

# adjustments in data
def del_kw_from_list(data_list, kw, pos):
    """
    deletes elem from list at pos if elem in kw or elem==kw
    :param list data_list
    :param str kw: Keyword which shall be deleted
    :param int pos: expected position of keyword
    :return: list
    """
    if type(kw) == list:
        kw_upper = [k.upper() for k in kw]
        kw_list = kw + kw_upper
    else:
        kw_list = [kw, kw.upper()]
    if data_list[pos] in kw_list:
        data_list.pop(pos)
    return data_list

def adjust_line_length(
    ts_line,
    pos,
    line_length,
    insert_val=[np.nan]
):
    """
    adds insert_val at pos in line lengt is not line length
    :param list ts_line
    :param int pos: position in the list for the fill
    :param int line_length: expected line length
    :param list insert_val: values to insert at pos if the list is too short
    :return: list
    """
    if len(ts_line) < line_length:
        ts_line[pos:pos] = insert_val
        return ts_line
    else:
        return ts_line

def insert_nan_after_kw(df_line, kw_position, kw, insert_positions):
    """
    adds np.nan after keyword (kw)
    :param list df_line
    :param int kw_position: expected position of keyword
    :param str kw: Keyword
    :param list insert_positions: position at which np.nan should be insertet
    :return: list
    """
    if df_line[kw_position] == kw:
        for i_p in insert_positions:
            df_line.insert(i_p, np.nan)
    return df_line
    
def adjust_column_types(df, col_types):
    """
    converts column types in df according to col_types
    :param pd.DataFrame df
    :param dict col_types: colum data types of a section
    :return pd.DataFrame
    """
    def col_conversion(col):
        """applies the type conversion on a column"""
        col = col.replace('*', np.nan)

        def val_conversion(x):
            if pd.isna(x):
                return np.nan
            else:
                if col_types[col.name] == 'Double':
                    return float(x)
                if col_types[col.name] == 'String':
                    return str(x)
                if col_types[col.name] == 'Int':
                    return int(x)
                if col_types[col.name] == 'Bool':
                    return bool(x)
        if col_types[col.name] in ['Double', 'String', 'Int', 'Bool']:
            return [val_conversion(x) for x in col]
        if col_types[col.name] == 'Date':
            def date_conversion(x):
                if pd.isna(x):
                    return ''
                else:
                    return datetime.strptime(x, '%m/%d/%Y').date()
            return [date_conversion(x) for x in col]
        if col_types[col.name] == 'Time':
            def time_conversion(x):
                if pd.isna(x):
                    return x
                else:
                    try:
                        return datetime.strptime(str(x), '%H:%M:%S').time()
                    except BaseException:
                        try:
                            return datetime.strptime(str(x), '%H:%M').time()
                        except BaseException:
                            try:
                                return datetime.strptime(str(x), '%H').time()
                            except BaseException:
                                return x  # when over 48 h
            return [time_conversion(x) for x in col]
    df = df.apply(col_conversion, axis=0)
    return df
    
def add_layer_on_completion(
    layer_name,
    style_file,
    geodata_driver_extension,
    folder_save,
    pluginPath,
    context,
    **kwargs
):
    """
    adds the current layer to canvas
    :param str layer_name
    :param str style_file: file name of the qml file
    :param str geodata_driver_extension
    :param str folder_save
    :param str pluginPath
    """
    layer_filename = layer_name+'.'+geodata_driver_extension
    file_path = os.path.join(folder_save, layer_filename)
    if os.path.isfile(file_path):
        vlayer = QgsVectorLayer(
            file_path,
            layer_name,
            "ogr"
        )
        qml_file_path = os.path.join(
            pluginPath,
            st_files_path,
            style_file
        )
        vlayer.loadNamedStyle(qml_file_path)
        context.temporaryLayerStore().addMapLayer(vlayer)
        context.addLayerToLoadOnCompletion(vlayer.id(), QgsProcessingContext.LayerDetails("", QgsProject.instance(), ""))
    else:
        raise QgsProcessingException(
                'File '
                + file_path
                + ' could not be loaded to the project.' 
            )
