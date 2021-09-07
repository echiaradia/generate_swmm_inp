# -*- coding: utf-8 -*-

"""
/***************************************************************************
 GenerateSwmmInp
                                 A QGIS plugin
 This plugin generates SWMM Input files
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-07-09
        copyright            : (C) 2021 by Jannik Schilling
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
__date__ = '2021-08-23'
__copyright__ = '(C) 2021 by Jannik Schilling'

from datetime import datetime
import numpy as np
import os
import pandas as pd
from qgis.core import (NULL,
                       QgsField,
                       QgsFeature,
                       QgsGeometry,
                       QgsProcessingAlgorithm,
                       QgsProcessingContext,
                       QgsProcessingException,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterCrs,
                       QgsProject,
                       QgsVectorLayer,
                       QgsVectorFileWriter)
from qgis.PyQt.QtCore import QVariant, QCoreApplication
import shutil
pluginPath = os.path.dirname(__file__)


class ImportInpFile (QgsProcessingAlgorithm):
    """
    generates shapefiles and tables from a swmm input file
    """
    INP_FILE = 'INP_FILE'
    SAVE_FOLDER = 'SAVE_FOLDER'
    DATA_CRS = 'DATA_CRS'
    
    def initAlgorithm(self, config):
        """
        inputs and outputs of the algorithm
        """

        self.addParameter(
            QgsProcessingParameterFile(
                name = self.INP_FILE,
                description = self.tr('SWMM input file to import'),
                extension = 'inp'
            )
        )
        
        self.addParameter(
            QgsProcessingParameterFolderDestination(
            self.SAVE_FOLDER,
            self.tr('Folder in which the imported data will be saved.')
            )
        )
        
        self.addParameter(
            QgsProcessingParameterCrs(
            self.DATA_CRS,
            self.tr('CRS of the SWMM input file'),
            defaultValue='epsg:25833'
            )
        )
    def name(self):
        return 'ImportInpFile'
        
    def shortHelpString(self):
        return self.tr(""" The tool imports a swmm inp file and saves the data in a folder selected by the user.\n 
        Choosing a folder name such as \"swmm_data\" is recommended.\n
        The layers (shapefiles) are added to the QGIS project.\n
        """)

    def displayName(self):
        return self.tr('3_ImportInpFile')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return ''

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return ImportInpFile()

    def processAlgorithm(self, parameters, context, feedback):
        folder_save = self.parameterAsString(parameters, self.SAVE_FOLDER, context)
        readfile = self.parameterAsString(parameters, self.INP_FILE, context)
        crs_result = self.parameterAsCrs(parameters, self.DATA_CRS, context)
        crs_result = str(crs_result.authid())
        default_data_path = os.path.join(pluginPath,'test_data','swmm_data')
        files_list = [f for f in os.listdir(default_data_path) if f.endswith('qml')]
        
        try:
            for f in files_list:
                f2 = os.path.join(default_data_path,f)
                shutil.copy(f2, folder_save)
            feedback.setProgressText(self.tr('style files saved to folder '+folder_save))
        except:
            raise QgsProcessingException(self.tr('Could not add default files to chosen folder'))

        """defaults for all sections"""
        from .g_s_defaults import def_sections_dict

        with open(readfile) as f:
            inp_text = f.readlines()

        inp_text = [x for x in inp_text if x != '\n']
        inp_text = [x for x in inp_text if x != '\s']
        inp_text = [x for x in inp_text if not x.startswith(';;')]
        inp_text = [x.replace('\n','') for x in inp_text]

        section_list_brackets = ['['+k+']' for k in def_sections_dict.keys()]
        section_list_brackets = [sect for sect in section_list_brackets if sect in inp_text] #remove section which are not available
        pos_start_list = [inp_text.index(sect) for sect in section_list_brackets] 

        # remove brackets
        section_list = [x.replace('[','') for x in section_list_brackets] 
        section_list = [x.replace(']','') for x in section_list]

        # sort section_list according to occurance of sections in inp_text
        section_list = [section_list[i] for i in np.argsort(pos_start_list).tolist()]  

        # sort startpoints of sections in inp_text
        pos_start_list = sorted(pos_start_list)

        # endpoints of sections in inp_text
        pos_end_list = pos_start_list[1:]+[len(inp_text)]

        # make a dict of sections to extract
        dict_search = {section_list[i]:[pos_start_list[i],pos_end_list[i]] for i in range(len(section_list))}


        def extract_section_vals_from_text(text_limits):
            '''extracts sections from inp_text'''
            section_text = inp_text[text_limits[0]+1:text_limits[1]]
            section_text = [x.strip() for x in section_text if not x.startswith(';')] #delete comments and "headers"
            section_vals = [x.split() for x in section_text]
            return section_vals

        dict_all_raw_vals = {k:extract_section_vals_from_text(dict_search[k]) for k in dict_search.keys()}

        def build_df_from_vals_list(section_vals, col_names):
            '''builds dataframes from list of lists of vals'''
            df = pd.DataFrame(section_vals)
            col_len = len(df.columns)
            if col_names == None:
                pass
            else:
                df.columns = col_names[0:col_len]
                if len(col_names) > col_len: #if missing vals in inp-data
                    for i in col_names[col_len:]:
                        df[i]=np.nan
            return df

        def build_df_for_section(section_name, dict_raw):
            '''builds dataframes for a section'''
            if type(def_sections_dict[section_name]) == list:
                col_names = def_sections_dict[section_name]
            if def_sections_dict[section_name] is None:
                col_names = None
            if type(def_sections_dict[section_name]) == dict:
                col_names = list(def_sections_dict[section_name].keys())
            if not section_name in dict_raw.keys():
                df = pd.DataFrame(columns = col_names)
            else:
                df = build_df_from_vals_list(dict_raw[section_name], col_names)
            return df


        def adjust_line_length(ts_line, pos, line_length , insert_val=np.nan):
            '''adds insert_val at pos in line lengt is not line length'''
            if len(ts_line) < line_length:
                ts_line[pos:pos] = insert_val
                return ts_line
            elif len(ts_line) == line_length:
                return ts_line

        def del_kw_from_list(data_list, kw, pos):
            '''deletes elem from list at pos if elem in kw or elem==kw'''
            if type(kw) == list:
                kw_upper = [k.upper() for k in kw]
                kw_list = kw + kw_upper
            else:
                kw_list = [kw, kw.upper()]
            if data_list[pos] in kw_list:
                    data_list.pop(pos)
            return data_list
                

        ### Excel files 
        def dict_to_excel(data_dict, save_name):
            '''writes an excel file from a data_dict'''
            with pd.ExcelWriter(os.path.join(folder_save, save_name)) as writer:
                for sheet_name, df in data_dict.items():
                    df.to_excel(writer, sheet_name=sheet_name,index = False)
                    

        def adjust_column_types(df, col_types):
            '''converts column types in df according to col_types'''
            def col_conversion (col):
                '''applies the type conversion'''
                col = col.replace('*',np.nan)
                if col_types[col.name] =='Double':
                    return [float(x) for x in col]
                if col_types[col.name] =='String': 
                    return [str(x) for x in col]
                if col_types[col.name] =='Int':
                    return [int(x) for x in col]
                if col_types[col.name] =='Bool': 
                    return [bool(x) for x in col]
                if col_types[col.name] =='Date': 
                    return  [datetime.strptime(x, '%m/%d/%Y').date() for x in col]
                if col_types[col.name] =='Time':
                    try:
                        return  [datetime.strptime(x, '%H:%M:%S').time() for x in col]
                    except:
                        return  [datetime.strptime(x, '%H:%M').time() for x in col]
            df = df.apply(col_conversion, axis = 0)
            return df

        # options    
        if 'OPTIONS' in dict_all_raw_vals.keys():
            from .g_s_various_functions import convert_options_format_for_import
            df_options = build_df_for_section('OPTIONS',dict_all_raw_vals)
            dict_options = {k:v for k,v in zip(df_options['Option'],df_options['Value'])}
            df_options_converted = convert_options_format_for_import(dict_options)
            dict_to_excel({'OPTIONS':df_options_converted},'gisswmm_options.xlsx')
            main_infiltration_method = df_options.loc[df_options['Option'] == 'INFILTRATION','Value'].values[0]
        else: 
            main_infiltration_method = 'HORTON' #assumption for main infiltration method if not in options
        
        # inflows
        if 'INFLOWS' in dict_all_raw_vals.keys():
            df_inflows = build_df_for_section('INFLOWS', dict_all_raw_vals)
        else:
            df_inflows = build_df_from_vals_list([], def_sections_dict['INFLOWS'])
        if 'DWF' in dict_all_raw_vals.keys():
            df_dry_weather = build_df_for_section('DWF', dict_all_raw_vals)
        else:
            df_dry_weather = build_df_from_vals_list([], def_sections_dict['DWF'])
        dict_inflows = {'Direct':df_inflows,
                        'Dry_Weather':df_dry_weather}
        dict_to_excel(dict_inflows,'gisswmm_inflows.xlsx')

        # patterns
        pattern_times={'HOURLY':['0:00','1:00','2:00','3:00',
                                 '4:00','5:00','6:00','7:00',
                                 '8:00','9:00','10:00','11:00',
                                 '12:00','13:00','14:00','15:00',
                                 '16:00','17:00','18:00','19:00',
                                 '20:00','21:00','22:00','23:00'],
         'DAILY':['So','Mo','Tu','We','Th','Fr','Sa'],
         'MONTHLY':['Jan','Feb','Mar','Apr','May','Jun',
                    'Jul','Aug','Sep','Oct','Nov','Dec'],
         'WEEKEND':['0:00','1:00','2:00','3:00','4:00',
                    '5:00','6:00','7:00','8:00','9:00',
                    '10:00','11:00','12:00','13:00','14:00',
                    '15:00','16:00','17:00','18:00','19:00',
                    '20:00','21:00','22:00','23:00']}
        pattern_cols={'HOURLY':['Name','Time','Factor'],
                      'DAILY':['Name','Day','Factor'],
                      'MONTHLY':['Name','Month','Factor'],
                      'WEEKEND':['Name','Time','Factor']}
                      
        if 'PATTERNS' in dict_all_raw_vals.keys():
            all_patterns = build_df_for_section('PATTERNS',dict_all_raw_vals)
            occuring_patterns_types = all_patterns.loc[all_patterns[1].isin(['HOURLY','DAILY','MONTHLY','WEEKEND']),[0,1]].set_index(0)
            occuring_patterns_types.columns = ["PatternType"]
            all_patterns = all_patterns.fillna(np.nan)
            all_patterns = all_patterns.replace({'HOURLY':np.nan,'DAILY':np.nan,'MONTHLY':np.nan,'WEEKEND':np.nan})
            def adjust_patterns_df(pattern_row):
                pattern_adjusted = [[pattern_row[0],i] for i in pattern_row[1:] if pd.notna(i)]
                return (pd.DataFrame(pattern_adjusted, columns = ['Name','Factor']))
            all_patterns = pd.concat([adjust_patterns_df(all_patterns.loc[i,:]) for i in all_patterns.index])
            all_patterns = all_patterns.join(occuring_patterns_types, on = 'Name')
            all_patterns = {k:v.iloc[:,:-1] for k, v in all_patterns.groupby("PatternType")}
        else:
            all_patterns = dict()
        def add_pattern_timesteps(pattern_type):
            count_patterns = int(len(all_patterns[pattern_type])/len(pattern_times[pattern_type]))
            new_col = pattern_times[pattern_type]*count_patterns
            return new_col
        for pattern_type in pattern_cols.keys():
            if pattern_type in all_patterns.keys():
                all_patterns[pattern_type]['Time'] = add_pattern_timesteps(pattern_type)
                all_patterns[pattern_type] = all_patterns[pattern_type][['Name','Time','Factor']]
                if pattern_type == 'DAILY':
                    all_patterns[pattern_type] = all_patterns[pattern_type].rename({'Time':'Day'})
                if pattern_type == 'MONTHLY':
                    all_patterns[pattern_type] = all_patterns[pattern_type].rename({'Time':'Month'})
                all_patterns[pattern_type]['Factor'] = [float(x) for x in all_patterns[pattern_type]['Factor']]
                all_patterns[pattern_type].columns = pattern_cols[pattern_type]
            else:
                all_patterns[pattern_type] = build_df_from_vals_list([], pattern_cols[pattern_type])
        dict_to_excel(all_patterns,'gisswmm_patterns.xlsx')


        # curves section
        curve_cols_dict = {'Pump1': ['Name','Volume','Flow'],
                           'Pump2': ['Name','Depth','Flow'],
                           'Pump3': ['Name','Head','Flow'],
                           'Pump4': ['Name','Depth','Flow'],
                           'Storage': ['Name','Depth','Area'],
                           'Rating': ['Name','Head/Depth','Outflow'],
                           'Tidal':['Name','Hour_of_Day','Stage'],
                           'Control':['Name','Value','Setting'],
                           'Diversion':['Name','Inflow','Outflow'],
                           'Shape':['Name','Depth', 'Width'],
                           'Weir': ['Name','Head','Coefficient']
                           }
        
        if 'CURVES' in dict_all_raw_vals.keys():
            curve_type_dict= {l[0]:l[1] for l in dict_all_raw_vals['CURVES'] if l[1] in curve_cols_dict.keys()}
            # if upper case:
            upper_keys = [i.upper() for i in curve_cols_dict.keys()]
            curve_type_dict_upper= {l[0]:l[1] for l in dict_all_raw_vals['CURVES'] if l[1] in upper_keys}
            curve_type_dict.update(curve_type_dict_upper)
            occuring_curve_types = list(set(curve_type_dict.values()))
            all_curves = [del_kw_from_list(l, occuring_curve_types, 1) for l in dict_all_raw_vals['CURVES'].copy()]
            all_curves = build_df_from_vals_list(all_curves, def_sections_dict['CURVES'])
            all_curves['CurveType'] = [curve_type_dict[i].capitalize() for i in all_curves['Name']] # capitalize as in curve_cols_dict
            all_curves['XVal'] = [float(x) for x in all_curves['XVal']]
            all_curves['YVal'] = [float(x) for x in all_curves['YVal']]
            all_curves = {k:v[['Name','XVal','YVal']] for k, v in all_curves.groupby('CurveType')}
        else:
            all_curves = dict()
        for curve_type in curve_cols_dict.keys():
            if curve_type in all_curves.keys():
                all_curves[curve_type].columns = curve_cols_dict[curve_type]
            else:
                all_curves[curve_type] = build_df_from_vals_list([], curve_cols_dict[curve_type])
            all_curves[curve_type]['Notes']=np.nan
        dict_to_excel(all_curves,'gisswmm_curves.xlsx')


        # quality
        quality_cols_dict = {k:def_sections_dict[k] for k in ['POLLUTANTS','LANDUSES','COVERAGES','LOADINGS','BUILDUP','WASHOFF']}
        all_quality = {k:build_df_for_section(k,dict_all_raw_vals) for k in quality_cols_dict.keys() if k in dict_all_raw_vals.keys()}
        missing_quality_data = {k:build_df_from_vals_list([],list(def_sections_dict[k].keys())) for k in quality_cols_dict.keys() if k not in dict_all_raw_vals.keys()}
        all_quality.update(missing_quality_data)
        all_quality = {k:adjust_column_types(v,def_sections_dict[k]) for k,v in all_quality.items()}
        if len(all_quality['BUILDUP']) == 0: #fill with np.nan in order to facilitate join below
            if len(all_quality['LANDUSES']) > 0:
                landuse_names = all_quality['LANDUSES']['Name']
                landuse_count = len(landuse_names)
                all_quality['BUILDUP'].loc[0:landuse_count,:] = np.nan 
                all_quality['BUILDUP']['Name'] = landuse_names
        landuses = all_quality['BUILDUP'].copy().join(all_quality['LANDUSES'].copy().set_index('Name'), on = 'Name')
        col_names = all_quality['LANDUSES'].columns.tolist()
        col_names.extend(all_quality['BUILDUP'].columns.tolist()[1:])
        landuses = landuses[col_names]
        landuses['join_name'] = landuses['Name']+landuses['Pollutant']
        all_quality['WASHOFF']['join_name'] = all_quality['WASHOFF']['Name'] +all_quality['WASHOFF']['Pollutant']
        all_quality['WASHOFF'] = all_quality['WASHOFF'].drop(columns=['Name', 'Pollutant'])
        landuses = landuses.join(all_quality['WASHOFF'].set_index('join_name'), on = 'join_name')
        landuses = landuses.drop(columns = ['join_name'])
        all_quality['LANDUSES'] = landuses
        del all_quality['BUILDUP']
        del all_quality['WASHOFF']
        dict_to_excel(all_quality,'gisswmm_quality.xlsx')


        # timeseries
        ts_cols_dict = {'Name':'String',
                        'Type':'String', 
                        'Date':'Date', 
                        'Time':'Time',
                        'Value':'Double', 
                        'Format':'String',
                        'Description':'String'}  
        if 'TIMESERIES' in dict_all_raw_vals.keys():
            all_time_series = [adjust_line_length(x,1,4) for x in dict_all_raw_vals['TIMESERIES'].copy()]
            all_time_series = build_df_from_vals_list(all_time_series,def_sections_dict['TIMESERIES'])
            all_time_series.insert(1,'Type',np.nan)
            all_time_series['Format'] = np.nan
            all_time_series['Description'] = np.nan
        else:
            all_time_series = build_df_from_vals_list([],list(ts_cols_dict.keys()))
        if 'RAINGAGES' in dict_all_raw_vals.keys():
            rain_gage = build_df_from_vals_list(dict_all_raw_vals['RAINGAGES'],def_sections_dict['RAINGAGES'])
            for i in rain_gage.index:
                if rain_gage.loc[i,'Source'] == 'TIMESERIES':
                    all_time_series.loc[all_time_series['Name'] == rain_gage.loc[i,'SourceName'],'Type'] = 'rain_gage'
                    all_time_series.loc[all_time_series['Name'] == rain_gage.loc[i,'SourceName'],'Format'] = rain_gage.loc[i,'Format']
                    all_time_series.loc[all_time_series['Name'] == rain_gage.loc[i,'SourceName'],'Description'] = rain_gage.loc[i,'Description']
        all_time_series = adjust_column_types(all_time_series, ts_cols_dict)
        dict_to_excel({'Table1':all_time_series},'gisswmm_timeseries.xlsx')
            
            
            
        ### shapefiles        
        def create_feature_from_df(df, pr):
            '''creates a QgsFeature from data in df'''
            f = QgsFeature()
            f.setGeometry(df.geometry)
            f.setAttributes(df.tolist()[:-1])
            pr.addFeature(f)

        def create_layer_from_table(data_df,section_name,geom_type,layer_name, layer_fields = 'not_set'):
            '''creates a QgsVectorLayer from data in data_df'''
            vector_layer = QgsVectorLayer(geom_type,layer_name,'memory')
            v_l_crs = vector_layer.crs()
            v_l_crs.createFromUserInput(crs_result)
            vector_layer.setCrs(v_l_crs)
            pr = vector_layer.dataProvider()
            field_types_dict = {'Double':QVariant.Double,
                                'String':QVariant.String,
                                'Int':QVariant.Int,
                                'Bool': QVariant.Bool}
            if layer_fields == 'not_set':
                layer_fields = def_sections_dict[section_name]
            for col in layer_fields:
                field_type_string = layer_fields[col]
                field_type = field_types_dict[field_type_string]
                pr.addAttributes([QgsField(col, field_type)])
            vector_layer.updateFields()
            data_df.apply(lambda x: create_feature_from_df(x, pr), axis =1)
            vector_layer.updateExtents() 
            QgsVectorFileWriter.writeAsVectorFormat(vector_layer,
                                                    os.path.join(folder_save,layer_name+'.shp'),
                                                    'utf-8',
                                                    vector_layer.crs(),
                                                    driverName='ESRI Shapefile')
            return vector_layer

        def replace_nan_null(data):
            '''replaces np.nan with NULL'''
            if pd.isna(data):
                return NULL
            elif data == '*':
                return NULL
            else:
                return data
                
        def insert_nan_after_kw(df_line, kw_position, kw, insert_position):
            '''adds np.nan after keyword (kw)'''
            if df_line[kw_position] == kw:
                df_line.insert(insert_position,np.nan)
            return df_line
        
        def add_layer_on_completion(folder_save, layer_name, style_file):
            '''adds the current layer on completen to canvas'''
            layer_filename = layer_name+'.shp'
            vlayer = QgsVectorLayer(os.path.join(folder_save, layer_filename), layer_name, "ogr")
            vlayer.loadNamedStyle(os.path.join(folder_save,style_file))
            context.temporaryLayerStore().addMapLayer(vlayer)
            context.addLayerToLoadOnCompletion(vlayer.id(), QgsProcessingContext.LayerDetails("", QgsProject.instance(), ""))
            
        ##POINTS
        coords = build_df_for_section('COORDINATES',dict_all_raw_vals)
        from .g_s_various_functions import get_point_from_x_y

        # create Layer
        all_geoms = [get_point_from_x_y(coords.loc[i,:]) for i in coords.index]
        all_geoms = pd.DataFrame(all_geoms, columns = ['Name', 'geometry']).set_index('Name')

        #junctions
        if 'JUNCTIONS' in dict_all_raw_vals.keys():
            all_junctions = build_df_for_section('JUNCTIONS',dict_all_raw_vals)
            all_junctions = all_junctions.join(all_geoms, on = 'Name')
            all_junctions = all_junctions.applymap(replace_nan_null)
            junctions_layer = create_layer_from_table(all_junctions,'JUNCTIONS','Point','SWMM_junctions')
            add_layer_on_completion(folder_save, 'SWMM_junctions', 'style_junctions.qml')
            
        #storages
        if 'STORAGE' in dict_all_raw_vals.keys():
            all_storages = build_df_for_section('STORAGE',dict_all_raw_vals)
            all_storages = all_storages.join(all_geoms, on = 'Name')
            all_storages = all_storages.applymap(replace_nan_null)
            storages_layer = create_layer_from_table(all_storages,'STORAGE','Point','SWMM_storages')
            add_layer_on_completion(folder_save, 'SWMM_storages', 'style_storages.qml')
        
        #outfalls
        if 'OUTFALLS' in dict_all_raw_vals.keys():
            dict_all_raw_vals['OUTFALLS'] = [insert_nan_after_kw(x,2,'FREE',3) for x in dict_all_raw_vals['OUTFALLS'].copy()]
            all_outfalls = build_df_for_section('OUTFALLS',dict_all_raw_vals)
            all_outfalls = all_outfalls.join(all_geoms, on = 'Name')
            all_outfalls = all_outfalls.applymap(replace_nan_null)
            outfalls_layer = create_layer_from_table(all_outfalls,'OUTFALLS','Point','SWMM_outfalls')
            add_layer_on_completion(folder_save, 'SWMM_outfalls', 'style_outfalls.qml')


        ##LINES
        if 'VERTICES' in dict_all_raw_vals.keys(): # vertices section seems to be always available
            all_vertices = build_df_for_section('VERTICES',dict_all_raw_vals)
        else:
            all_vertices = build_df_from_vals_list([],list(def_sections_dict['VERTICES']))
        def get_line_geometry(section_df):
            def get_line_from_points(line_name):
            # From vertices section
                verts = all_vertices.copy()[all_vertices['Name']==line_name]
                if len(verts) > 0:
                    l_verts = verts.reset_index(drop=True)
                    l_verts_points = [get_point_from_x_y(l_verts.loc[i,:])[1] for i in l_verts.index]
                    l_verts_points = [x.asPoint() for x in l_verts_points]
                else:
                    l_verts_points = []
                # From all geoms
                from_node = section_df.loc[section_df['Name']==line_name, 'FromNode']
                from_geom = all_geoms.loc[from_node,'geometry'].values[0]
                from_point = from_geom.asPoint()
                to_node = section_df.loc[section_df['Name']==line_name, 'ToNode']
                to_geom = all_geoms.loc[to_node,'geometry'].values[0]
                to_point = to_geom.asPoint()
                l_all_verts = [from_point]+l_verts_points+[to_point]
                line_geom = QgsGeometry.fromPolylineXY(l_all_verts)
                return [line_name, line_geom]
            lines_created = [get_line_from_points(x) for x in section_df['Name']]
            lines_created = pd.DataFrame(lines_created, columns = ['Name', 'geometry']).set_index('Name')
            return lines_created 
            
        #conduits
        if 'CONDUITS' in dict_all_raw_vals.keys():
            #cross sections
            all_xsections = build_df_for_section('XSECTIONS', dict_all_raw_vals)
            all_xsections = all_xsections.applymap(replace_nan_null)
            
            #losses
            if 'LOSSES' in dict_all_raw_vals.keys():
                all_losses = build_df_for_section('LOSSES', dict_all_raw_vals)
                all_losses = all_losses.applymap(replace_nan_null)
            else: 
                all_losses = build_df_from_vals_list([],list(def_sections_dict['LOSSES'].keys()))
            
            all_conduits = build_df_for_section('CONDUITS', dict_all_raw_vals)
            all_conduits = all_conduits.join(all_xsections.set_index('Name'), on = 'Name')
            all_conduits = all_conduits.join(all_losses.set_index('Name'), on = 'Name')
            all_conduits['FlapGate'] = all_conduits['FlapGate'].fillna('NO')
            conduits_geoms = get_line_geometry(all_conduits)
            all_conduits = all_conduits.join(conduits_geoms, on = 'Name')
            all_conduits_fields = def_sections_dict['CONDUITS'].copy()
            all_conduits_fields.update(def_sections_dict['XSECTIONS'])
            all_conduits_fields.update(def_sections_dict['LOSSES'])
            all_conduits = all_conduits.applymap(replace_nan_null)
            conduits_layer = create_layer_from_table(all_conduits,
                                                     'CONDUITS',
                                                     'LineString',
                                                     'SWMM_conduits',
                                                     layer_fields = all_conduits_fields)
            add_layer_on_completion(folder_save, 'SWMM_conduits', 'style_conduits.qml')
        
        
            # transects in hec2 format
            transects_columns = ['TransectName',
                                 'RoughnessLeftBank',
                                 'RoughnessRightBank',
                                 'RoughnessChannel',
                                 'BankStationLeft',
                                 'BankStationRight',
                                 'ModifierMeander',
                                 'ModifierStations',
                                 'ModifierElevations']
            if 'TRANSECTS' in dict_all_raw_vals.keys():
                all_transects_data_df = dict()
                transects_list = dict_all_raw_vals['TRANSECTS'].copy()
                tr_startp = [i for i, x in enumerate(transects_list) if x[0] == 'NC']
                tr_endp = tr_startp[1:]+[len(transects_list)]
                #tr_dict = {transects_list[x+1][1]:get_transects_data(transects_list[x:y]) for x,y in zip(tr_startp,tr_endp)}
                def get_transects_data(tr_i):
                    tr_roughness = tr_i[0][1:]
                    tr_name = tr_i[1][1]
                    tr_count = tr_i[1][2]
                    tr_bankstat_left = tr_i[1][3]
                    tr_bankstat_right = tr_i[1][4]
                    tr_modifier = tr_i[1][7:10]
                    tr_data = [tr_name]+tr_roughness+[tr_bankstat_left]+[tr_bankstat_right]+tr_modifier
                    return tr_data
                    
                    
                def get_transects_vals(tr_i):
                    tr_name = tr_i[1][1]
                    tr_count = tr_i[1][2]
                    tr_values = [del_kw_from_list(x, 'GR', 0) for x in tr_i[2:]]
                    tr_values = [x for sublist in tr_values for x in sublist]
                    tr_values_splitted = [[tr_values[x*2],tr_values[(x*2)+1]] for x in range(int(tr_count))] #split into list of lists of len 2
                    tr_values_splitted = [[tr_name] + x for x in tr_values_splitted]
                    return tr_values_splitted
               
                all_tr_vals = [get_transects_vals(transects_list[x:y]) for x,y in zip(tr_startp,tr_endp)]
                all_tr_vals = [x for sublist in all_tr_vals for x in sublist]
                all_tr_dats = [get_transects_data(transects_list[x:y]) for x,y in zip(tr_startp,tr_endp)]
                
                all_tr_vals_df = build_df_from_vals_list(all_tr_vals, ['TransectName', 'Elevation', 'Station'])
                all_tr_vals_df = all_tr_vals_df[['TransectName',
                                                 'Station',
                                                 'Elevation']] # order of columns according to swmm interface
                all_tr_dats_df = build_df_from_vals_list(all_tr_dats, transects_columns)
                all_tr_dats_df = all_tr_dats_df[['TransectName',
                                 'RoughnessLeftBank',
                                 'RoughnessRightBank',
                                 'RoughnessChannel',
                                 'BankStationLeft',
                                 'BankStationRight',
                                 'ModifierStations',
                                 'ModifierElevations',
                                 'ModifierMeander']]# order of columns according to swmm interface
                transects_dict = {'Data':all_tr_dats_df, 'XSections':all_tr_vals_df}
                dict_to_excel(transects_dict,'gisswmm_transects.xlsx')

        #outlets
        def adjust_outlets_list(outl_list_i):
            if outl_list_i[4].startswith('TABULAR'):
                curve_name = outl_list_i[5]
                flap_gate = outl_list_i[6]
                outl_list_i[:5]
                return outl_list_i[:5]+[np.nan,np.nan]+[flap_gate, curve_name]
            else:
                return outl_list_i+[np.nan]
        if 'OUTLETS' in dict_all_raw_vals.keys():
            dict_all_raw_vals['OUTLETS'] = [adjust_outlets_list(i) for i in dict_all_raw_vals['OUTLETS']]
            all_outlets = build_df_for_section('OUTLETS', dict_all_raw_vals)
            all_outlets = all_outlets.applymap(replace_nan_null)
            outlets_geoms = get_line_geometry(all_outlets)
            all_outlets = all_outlets.join(outlets_geoms, on = 'Name')
            outlets_layer = create_layer_from_table(all_outlets,'OUTLETS','LineString','SWMM_outlets')
            add_layer_on_completion(folder_save, 'SWMM_outlets', 'style_regulators.qml')

        #pumps
        if 'PUMPS' in dict_all_raw_vals.keys():
            all_pumps = build_df_for_section('PUMPS', dict_all_raw_vals)
            all_pumps = all_pumps.applymap(replace_nan_null)
            pumps_geoms = get_line_geometry(all_pumps)
            all_pumps = all_pumps.join(pumps_geoms, on = 'Name')
            pumps_layer = create_layer_from_table(all_pumps,'PUMPS','LineString','SWMM_pumps')
            add_layer_on_completion(folder_save, 'SWMM_pumps','style_pumps.qml')

        #weirs
        if 'WEIRS' in dict_all_raw_vals.keys():
            all_weirs= build_df_for_section('WEIRS', dict_all_raw_vals)
            all_weirs = all_weirs.join(all_xsections.set_index('Name'), on = 'Name')
            all_weirs = all_weirs.drop(columns=['Shape', 'Geom4', 'Barrels', 'Culvert'])
            all_weirs = all_weirs.rename(columns = {'Geom1':'Height','Geom2':'Length', 'Geom3':'SideSlope'})
            all_weirs = all_weirs.applymap(replace_nan_null) 
            weirs_geoms = get_line_geometry(all_weirs)
            all_weirs = all_weirs.join(weirs_geoms, on = 'Name')
            all_weirs_fields = def_sections_dict['WEIRS'].copy()
            all_weirs_fields.update({'Height':'Double','Length':'Double', 'SideSlope':'Double'})
            weirs_layer = create_layer_from_table(all_weirs,'WEIRS','LineString','SWMM_weirs',all_weirs_fields)
            add_layer_on_completion(folder_save, 'SWMM_weirs', 'style_regulators.qml')

        ## POLYGONS 
        if 'Polygons' in dict_all_raw_vals.keys():
            all_polygons = build_df_for_section('Polygons',dict_all_raw_vals)
            all_polygons = all_polygons.applymap(replace_nan_null)
            def get_polygon_from_verts(polyg_name):
                    verts = all_polygons.copy()[all_polygons['Name']==polyg_name]
                    verts = verts.reset_index(drop=True)
                    verts_points = [get_point_from_x_y(verts.loc[i,:])[1] for i in verts.index]
                    verts_points = [x.asPoint() for x in verts_points]
                    if len (verts_points) < 3: #only 1 or 2 vertices
                        polyg_geom = QgsGeometry.fromPointXY(verts_points[0]).buffer(5, 5) #set geometry to buffer around first vertice
                    else:
                        polyg_geom = QgsGeometry.fromPolygonXY([verts_points])
                    return [polyg_name, polyg_geom]

        #subcatchments        
        if 'SUBCATCHMENTS' in dict_all_raw_vals.keys():
            from .g_s_subcatchments import create_subcatchm_attributes_from_inp_df
            all_subcatchments = build_df_for_section('SUBCATCHMENTS',dict_all_raw_vals)
            all_subareas = build_df_for_section('SUBAREAS',dict_all_raw_vals)
            all_infiltr = [adjust_line_length(x,4,6,[np.nan,np.nan] ) for x in dict_all_raw_vals['INFILTRATION'].copy()]
            all_infiltr = build_df_from_vals_list(all_infiltr, list(def_sections_dict['INFILTRATION'].keys()))
            all_subcatchments, infiltr_dtypes = create_subcatchm_attributes_from_inp_df(all_subcatchments,
                                                                                        all_subareas, 
                                                                                        all_infiltr, 
                                                                                        main_infiltration_method)
            polyg_geoms = [get_polygon_from_verts(x) for x in all_subcatchments['Name']]
            polyg_geoms = pd.DataFrame(polyg_geoms, columns = ['Name', 'geometry']).set_index('Name')
            all_subcatchments = all_subcatchments.join(polyg_geoms, on = 'Name')
            all_subcatchments = all_subcatchments.applymap(replace_nan_null)
            all_subcatchments_fields = def_sections_dict['SUBCATCHMENTS']
            all_subcatchments_fields.update(def_sections_dict['SUBAREAS'])
            all_subcatchments_fields.update(infiltr_dtypes)
            subcatchments_layer = create_layer_from_table(all_subcatchments,'SUBCATCHMENTS','Polygon','SWMM_subcatchments', all_subcatchments_fields)
            add_layer_on_completion(folder_save, 'SWMM_subcatchments', 'style_catchments.qml')
        return {}
