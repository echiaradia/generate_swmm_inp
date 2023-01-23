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


# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import os
import pandas as pd
import numpy as np
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterVectorLayer
)
from .g_s_various_functions import check_columns, get_coords_from_geometry
from .g_s_defaults import (
    annotation_field_name,
    def_qgis_fields_dict,
    def_curve_types,
    def_sections_dict
)
from .g_s_read_write_data import (
    read_data_from_table_direct,
    read_layers_direct
)


class GenerateSwmmInpFile(QgsProcessingAlgorithm):
    """
    generates a swmm input file from geodata and tables
    """
    QGIS_OUT_INP_FILE = 'QGIS_OUT_INP_FILE'
    FILE_RAINGAGES = 'FILE_RAINGAGES'
    FILE_CONDUITS = 'FILE_CONDUITS'
    FILE_JUNCTIONS = 'FILE_JUNCTIONS'
    FILE_DIVIDERS = 'FILE_DIVIDERS'
    FILE_ORIFICES = 'FILE_ORIFICES'
    FILE_OUTFALLS = 'FILE_OUTFALLS'
    FILE_OUTLETS = 'FILE_OUTLETS'
    FILE_STORAGES = 'FILE_STORAGES'
    FILE_PUMPS = 'FILE_PUMPS'
    FILE_SUBCATCHMENTS = 'FILE_SUBCATCHMENTS'
    FILE_WEIRS = 'FILE_WEIRS'
    FILE_CURVES = 'FILE_CURVES'
    FILE_PATTERNS = 'FILE_PATTERNS'
    FILE_OPTIONS = 'FILE_OPTIONS'
    FILE_TIMESERIES = 'FILE_TIMESERIES'
    FILE_INFLOWS = 'FILE_INFLOWS'
    FILE_QUALITY = 'FILE_QUALITY'
    FILE_TRANSECTS = 'FILE_TRANSECTS'
    FILE_STREETS = 'FILE_STREETS'

    def initAlgorithm(self, config):
        """
        inputs and output of the algorithm
        """
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.QGIS_OUT_INP_FILE,
                self.tr('Where should the inp file be saved?'),
                'INP files (*.inp)',
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.FILE_RAINGAGES,
                self.tr('Rain gages Layer'),
                types=[QgsProcessing.SourceType.TypeVectorPoint],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.FILE_JUNCTIONS,
                self.tr('Junctions Layer'),
                types=[QgsProcessing.SourceType.TypeVectorPoint],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.FILE_CONDUITS,
                self.tr('Conduits Layer'),
                types=[QgsProcessing.SourceType.TypeVectorLine],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.FILE_SUBCATCHMENTS,
                self.tr('Subcatchments Layer'),
                types=[QgsProcessing.SourceType.TypeVectorAnyGeometry],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.FILE_STORAGES,
                self.tr('Storages Layer'),
                types=[QgsProcessing.SourceType.TypeVectorPoint],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.FILE_OUTFALLS,
                self.tr('Outfalls Layer'),
                types=[QgsProcessing.SourceType.TypeVectorPoint],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.FILE_DIVIDERS,
                self.tr('Dividers Layer'),
                types=[QgsProcessing.SourceType.TypeVectorPoint],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.FILE_PUMPS,
                self.tr('Pumps Layer'),
                types=[QgsProcessing.SourceType.TypeVectorLine],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.FILE_WEIRS,
                self.tr('Weirs Layer'),
                types=[QgsProcessing.SourceType.TypeVectorLine],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.FILE_ORIFICES,
                self.tr('Orifices Layer'),
                types=[QgsProcessing.SourceType.TypeVectorLine],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.FILE_OUTLETS,
                self.tr('Outlets Layer'),
                types=[QgsProcessing.SourceType.TypeVectorLine],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.FILE_OPTIONS,
                self.tr('Options table file'),
                QgsProcessingParameterFile.File,
                optional=True,
                fileFilter='Tables (*.xlsx *.xls *.odf)'
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.FILE_CURVES,
                self.tr('Curves table file'),
                QgsProcessingParameterFile.File,
                optional=True,
                fileFilter='Tables (*.xlsx *.xls *.odf)'
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.FILE_PATTERNS,
                self.tr('Patterns table file'),
                QgsProcessingParameterFile.File,
                optional=True,
                fileFilter='Tables (*.xlsx *.xls *.odf)'
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.FILE_TIMESERIES,
                self.tr('Timeseries table file'),
                QgsProcessingParameterFile.File,
                optional=True,
                fileFilter='Tables (*.xlsx *.xls *.odf)'
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.FILE_INFLOWS,
                self.tr('Inflows table file'),
                QgsProcessingParameterFile.File,
                optional=True,
                fileFilter='Tables (*.xlsx *.xls *.odf)'
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.FILE_QUALITY,
                self.tr('Quality table file'),
                QgsProcessingParameterFile.File,
                optional=True,
                fileFilter='Tables (*.xlsx *.xls *.odf)'
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.FILE_TRANSECTS,
                self.tr('Transects table file'),
                QgsProcessingParameterFile.File,
                optional=True,
                fileFilter='Tables (*.xlsx *.xls *.odf)'
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.FILE_STREETS,
                self.tr('Streets and Inlets table file'),
                QgsProcessingParameterFile.File,
                optional=True,
                fileFilter='Tables (*.xlsx *.xls *.odf)'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        main process algorithm of this tool
        """
        # input file name and path"
        inp_file_path = self.parameterAsString(parameters, self.QGIS_OUT_INP_FILE, context)
        inp_file_name = os.path.basename(inp_file_path)
        project_dir = os.path.dirname(inp_file_path)

        # initializing the input dictionary
        """
        SECTION: {
            'data': pd.df,
            'annotations': {
                'object_name1': 'annotation_string'
                'object_name2': 'annotation_string'
            }
        }
        COORDINATES:
        Polygons:
        VERTICES:{}
        """
        inp_dict = dict()
        inp_dict['TITLE'] = {'data': pd.DataFrame(['test'])}
        inp_dict['XSECTIONS'] = {
            'data': pd.DataFrame(),
            'annotations': {}
        } 
        inp_dict['COORDINATES'] = {'data': pd.DataFrame()}
        inp_dict['VERTICES'] = {'data': dict()}

        # reading geodata
        feedback.setProgressText(self.tr('Reading shapfiles'))
        feedback.setProgress(1)
        file_raingages = self.parameterAsVectorLayer(parameters, self.FILE_RAINGAGES, context)
        file_outfalls = self.parameterAsVectorLayer(parameters, self.FILE_OUTFALLS, context)
        file_storages = self.parameterAsVectorLayer(parameters, self.FILE_STORAGES, context)
        file_subcatchments = self.parameterAsVectorLayer(parameters, self.FILE_SUBCATCHMENTS, context)
        file_conduits = self.parameterAsVectorLayer(parameters, self.FILE_CONDUITS, context)
        file_junctions = self.parameterAsVectorLayer(parameters, self.FILE_JUNCTIONS, context)
        file_pumps = self.parameterAsVectorLayer(parameters, self.FILE_PUMPS, context)
        file_weirs = self.parameterAsVectorLayer(parameters, self.FILE_WEIRS, context)
        file_orifices = self.parameterAsVectorLayer(parameters, self.FILE_ORIFICES, context)
        file_outlets = self.parameterAsVectorLayer(parameters, self.FILE_OUTLETS, context)
        file_dividers = self.parameterAsVectorLayer(parameters, self.FILE_DIVIDERS, context)
        raw_layers_dict = {
            'raingages_raw': file_raingages,
            'outfalls_raw': file_outfalls,
            'storages_raw': file_storages,
            'subcatchments_raw': file_subcatchments,
            'conduits_raw': file_conduits,
            'junctions_raw': file_junctions,
            'pumps_raw': file_pumps,
            'weirs_raw': file_weirs,
            'orifices_raw': file_orifices,
            'outlets_raw': file_outlets,
            'dividers_raw': file_dividers
        }
        raw_layers_crs_list = [
            v.crs().authid() for v in raw_layers_dict.values() if v is not None
        ]
        unique_crs = np.unique(raw_layers_crs_list)
        if len(unique_crs) > 1:
            feedback.pushWarning(
                'Warning: different CRS in the selected layers.'
                + 'This may lead to unexpected locations in SWMM')
        raw_data_dict = read_layers_direct(raw_layers_dict)
        feedback.setProgressText(self.tr('done \n'))
        feedback.setProgress(12)

        # reading data in tables (curves, patterns, inflows ...)
        feedback.setProgressText(self.tr('Reading tables'))
        file_curves = self.parameterAsString(parameters, self.FILE_CURVES, context)
        file_patterns = self.parameterAsString(parameters, self.FILE_PATTERNS, context)
        file_options = self.parameterAsString(parameters, self.FILE_OPTIONS, context)
        file_timeseries = self.parameterAsString(parameters, self.FILE_TIMESERIES, context)
        file_inflows = self.parameterAsString(parameters, self.FILE_INFLOWS, context)
        file_quality = self.parameterAsString(parameters, self.FILE_QUALITY, context)
        file_transects = self.parameterAsString(parameters, self.FILE_TRANSECTS, context)
        file_streets = self.parameterAsString(parameters, self.FILE_STREETS, context)

        # options table
        if file_options != '':
            raw_data_dict['options_df'] = read_data_from_table_direct(
                file_options,
                sheet='OPTIONS'
            )
        # curves table
        if file_curves != '':
            raw_data_dict['curves'] = {}
            for curve_type in def_curve_types:
                curve_df = read_data_from_table_direct(
                    file_curves,
                    sheet=curve_type
                )
                if len(curve_df) > 0:
                    raw_data_dict['curves'][curve_type] = curve_df
        # patterns table
        if file_patterns != '':
            raw_data_dict['patterns'] = {}
            for pattern_type in ['HOURLY', 'DAILY', 'MONTHLY', 'WEEKEND']:
                raw_data_dict['patterns'][pattern_type] = read_data_from_table_direct(
                    file_patterns,
                    sheet=pattern_type
                )
        # inflows table
        if file_inflows != '':
            raw_data_dict['inflows'] = {}
            for inflow_type in ['Direct', 'Dry_Weather']:
                raw_data_dict['inflows'][inflow_type] = read_data_from_table_direct(
                    file_inflows,
                    sheet=inflow_type
                )
        # timeseries table
        if file_timeseries != '':
            raw_data_dict['timeseries'] = read_data_from_table_direct(
                file_timeseries
            )
        # quality table
        if file_quality != '':
            raw_data_dict['quality'] = {}
            for quality_param in ['POLLUTANTS', 'LANDUSES', 'COVERAGES', 'LOADINGS']:
                raw_data_dict['quality'][quality_param] = read_data_from_table_direct(
                    file_quality,
                    sheet=quality_param
                )
        # transects table
        if file_transects != '':
            raw_data_dict['transects'] = {}
            for transects_param in ['Data', 'XSections']:
                raw_data_dict['transects'][transects_param] = read_data_from_table_direct(
                    file_transects,
                    sheet=transects_param
                )
        # streets table
        if file_streets != '':
            raw_data_dict['streets'] = {}
            for streets_param in ['STREETS', 'INLETS', 'INLET_USAGE']:
                raw_data_dict['streets'][streets_param] = read_data_from_table_direct(
                    file_streets,
                    sheet=streets_param
                )
        feedback.setProgressText(self.tr('done \n'))
        feedback.setProgress(20)
        feedback.setProgressText(self.tr('preparing data for input file:'))
        
        # function for annotations / descriptions
        def get_annotations_from_raw_df(df_raw):
            if annotation_field_name in df_raw.columns:
                annot_dict = {k: v for k, v in zip(df_raw['Name'], df_raw[annotation_field_name])}
                annot_dict = {k: v for k, v in annot_dict.items() if pd.notna(v)}
                annot_dict = {k: v for k, v in annot_dict.items() if len(v) > 0}
            else:
                annot_dict = {}
            return annot_dict

        # options
        main_infiltration_method = None
        if 'options_df' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[OPTIONS] section'))
            from .g_s_options import get_options_from_table
            options_df, main_infiltration_method = get_options_from_table(raw_data_dict['options_df'].copy())
            inp_dict['OPTIONS'] = {'data': options_df}

        # subcatchments
        if 'subcatchments_raw' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[SUBCATCHMENTS] section'))
            from .g_s_subcatchments import get_subcatchments_from_layer
            subcatchments_df, subareas_df, infiltration_df = get_subcatchments_from_layer(
                raw_data_dict['subcatchments_raw'].copy(),
                main_infiltration_method
            )
            inp_dict['Polygons'] = {'data':
                get_coords_from_geometry(raw_data_dict['subcatchments_raw'])
            }
            subcatchments_annot = get_annotations_from_raw_df(
                raw_data_dict['subcatchments_raw'].copy()
            )
            inp_dict['SUBCATCHMENTS'] = {
                'data': subcatchments_df,
                'annotations': subcatchments_annot
            }
            inp_dict['SUBAREAS'] = {'data': subareas_df}
            inp_dict['INFILTRATION'] = {'data': infiltration_df}

        # conduits
        if 'conduits_raw' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[CONDUITS] section'))
            from .g_s_links import get_conduits_from_shapefile, del_first_last_vt
            conduits_df, xsections_df, losses_df = get_conduits_from_shapefile(raw_data_dict['conduits_raw'].copy())
            conduits_verts = get_coords_from_geometry(raw_data_dict['conduits_raw'].copy())
            conduits_verts = {k: del_first_last_vt(v) for k, v in conduits_verts.items() if len(v) > 2}  # first and last vertices are in nodes coordinates anyway
            inp_dict['VERTICES']['data'].update(conduits_verts)
            conduits_annot = get_annotations_from_raw_df(
                raw_data_dict['conduits_raw'].copy()
            )
            inp_dict['CONDUITS'] = {
                'data': conduits_df,
                'annotations': conduits_annot
            }
            inp_dict['XSECTIONS'] = {'data': xsections_df}
            inp_dict['LOSSES'] = {'data': losses_df}

        # pumps
        if 'pumps_raw' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[PUMPS] section'))
            from .g_s_links import get_pumps_from_shapefile, del_first_last_vt
            pumps_df = get_pumps_from_shapefile(raw_data_dict['pumps_raw'].copy())
            pumps_annot = get_annotations_from_raw_df(
                raw_data_dict['pumps_raw'].copy()
            )
            pumps_verts = get_coords_from_geometry(raw_data_dict['pumps_raw'].copy())
            pumps_verts = {k: del_first_last_vt(v) for k, v in pumps_verts.items() if len(v) > 2}
            pumps_inp_cols = def_sections_dict['PUMPS']
            inp_dict['VERTICES']['data'].update(pumps_verts)
            inp_dict['PUMPS'] = {
                'data': pumps_df[pumps_inp_cols],
                'annotations': pumps_annot
            }

        # weirs
        if 'weirs_raw' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[WEIRS] section'))
            from .g_s_links import get_weirs_from_shapefile, del_first_last_vt
            weirs_df, xsections_df = get_weirs_from_shapefile(raw_data_dict['weirs_raw'])
            weirs_annot = get_annotations_from_raw_df(
                raw_data_dict['weirs_raw'].copy()
            )
            weirs_verts = get_coords_from_geometry(raw_data_dict['weirs_raw'].copy())
            weirs_verts = {k: del_first_last_vt(v) for k, v in weirs_verts.items() if len(v) > 2}  # first and last vertices are in nodes coordinates anyway
            inp_dict['VERTICES']['data'].update(weirs_verts)
            inp_dict['XSECTIONS']['data'] = inp_dict['XSECTIONS']['data'].append(xsections_df)
            inp_dict['XSECTIONS']['data'] = inp_dict['XSECTIONS']['data'].reset_index(drop=True)
            inp_dict['WEIRS'] = {
                'data': weirs_df,
                'annotations': weirs_annot
            }

        # outlets
        if 'outlets_raw' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[OUTLETS] section'))
            from .g_s_links import get_outlets_from_shapefile, del_first_last_vt
            outlets_annot = get_annotations_from_raw_df(
                raw_data_dict['outlets_raw'].copy()
            )            
            inp_dict['OUTLETS'] = {
                'data': get_outlets_from_shapefile(raw_data_dict['outlets_raw']),
                'annotations': outlets_annot
            }
            outlets_verts = get_coords_from_geometry(raw_data_dict['outlets_raw'].copy())
            outlets_verts = {k: del_first_last_vt(v) for k, v in outlets_verts.items() if len(v) > 2}
            inp_dict['VERTICES']['data'].update(outlets_verts)

        # optional: transects for conduits or weirs
        if 'conduits_raw' in raw_data_dict.keys() or 'weirs_raw' in raw_data_dict.keys():
            if 'transects' in raw_data_dict.keys():
                feedback.setProgressText(self.tr('[TRANSECTS] section'))
                from .g_s_links import get_transects_from_table
                transects_string_list = get_transects_from_table(raw_data_dict['transects'].copy())
                inp_dict['TRANSECTS'] = {'data': transects_string_list}

        # orifices
        if 'orifices_raw' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[ORIFICES] section'))
            from .g_s_links import get_orifices_from_shapefile, del_first_last_vt
            orifices_df, xsections_df = get_orifices_from_shapefile(raw_data_dict['orifices_raw'])
            orifices_annot = get_annotations_from_raw_df(
                raw_data_dict['orifices_raw'].copy()
            )
            orifices_verts = get_coords_from_geometry(raw_data_dict['orifices_raw'].copy())
            orifices_verts = {k: del_first_last_vt(v) for k, v in orifices_verts.items() if len(v) > 2}  # first and last vertices are in nodes coordinates anyway
            inp_dict['VERTICES']['data'].update(orifices_verts)
            inp_dict['XSECTIONS']['data'] = inp_dict['XSECTIONS']['data'].append(xsections_df)
            inp_dict['XSECTIONS']['data'] = inp_dict['XSECTIONS']['data'].reset_index(drop=True)
            inp_dict['ORIFICES'] = {
                'data': orifices_df,
                'annotations': orifices_annot
            }

        feedback.setProgress(40)

        # nodes (junctions, outfalls, orifices)
        all_nodes = list()
        if 'junctions_raw' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[JUNCTIONS] section'))
            # check columns
            junctions_cols = list(def_qgis_fields_dict['JUNCTIONS'].keys())
            junctions_layer_name = 'Junctions Layer'
            check_columns(
                junctions_layer_name,
                junctions_cols,
                raw_data_dict['junctions_raw'].keys()
            )
            junctions_df = raw_data_dict['junctions_raw'].copy()
            junctions_df['MaxDepth'] = junctions_df['MaxDepth'].fillna(0)
            junctions_df['InitDepth'] = junctions_df['InitDepth'].fillna(0)
            junctions_df['SurDepth'] = junctions_df['SurDepth'].fillna(0)
            junctions_df['Aponded'] = junctions_df['Aponded'].fillna(0)
            junctions_annot = get_annotations_from_raw_df(
                raw_data_dict['junctions_raw'].copy()
            )
            junctions_df['X_Coord'], junctions_df['Y_Coord'] = get_coords_from_geometry(junctions_df)
            junctions_coords = junctions_df[['Name', 'X_Coord', 'Y_Coord']]
            junctions_inp_cols = def_sections_dict['JUNCTIONS']
            inp_dict['JUNCTIONS'] = {
                'data': junctions_df[junctions_inp_cols],
                'annotations': junctions_annot
            }
            inp_dict['COORDINATES']['data'] = inp_dict['COORDINATES']['data'].append(junctions_coords)
            all_nodes = all_nodes+junctions_df['Name'].tolist()
        if 'outfalls_raw' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[OUTFALLS] section'))
            outfalls_cols = list(def_qgis_fields_dict['OUTFALLS'].keys())
            outfalls_layer_name = 'Outfalls Layer'
            check_columns(
                outfalls_layer_name,
                outfalls_cols,
                raw_data_dict['outfalls_raw'].keys()
            )
            from .g_s_nodes import get_outfalls_from_shapefile
            outfalls_df = get_outfalls_from_shapefile(raw_data_dict['outfalls_raw'].copy())
            outfalls_df['X_Coord'], outfalls_df['Y_Coord'] = get_coords_from_geometry(outfalls_df)
            outfalls_coords = outfalls_df[['Name', 'X_Coord', 'Y_Coord']]
            outfalls_annot = get_annotations_from_raw_df(
                raw_data_dict['outfalls_raw'].copy()
            )
            inp_dict['OUTFALLS'] = {
                'data': outfalls_df,
                'annotations': outfalls_annot
            }
            inp_dict['COORDINATES']['data'] = inp_dict['COORDINATES']['data'].append(outfalls_coords)
            all_nodes = all_nodes+outfalls_df['Name'].tolist()
        if 'storages_raw' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[STORAGES] section'))
            # check columns is performed within get_storages_from_geodata for different storage types
            from .g_s_nodes import get_storages_from_geodata
            storage_df = get_storages_from_geodata(raw_data_dict['storages_raw'].copy())
            storage_annot = get_annotations_from_raw_df(
                raw_data_dict['storages_raw'].copy()
            )
            storage_coords = storage_df[['Name', 'X_Coord', 'Y_Coord']]
            storage_inp_cols = [
                'Name', 'Elevation', 'MaxDepth','InitDepth','Type',
                'Shape1','Shape2','Shape3','SurDepth','Fevap','Psi',
                'Ksat','IMD'
            ]
            storage_df = storage_df[storage_inp_cols]
            inp_dict['COORDINATES']['data'] = inp_dict['COORDINATES']['data'].append(storage_coords)
            inp_dict['STORAGE'] = {
                'data': storage_df,
                'annotations': storage_annot
            }
            all_nodes = all_nodes+storage_df['Name'].tolist()
        if 'dividers_raw' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[DIVIDERS] section'))
            dividers_df = raw_data_dict['dividers_raw'].copy()
            dividers_df['X_Coord'], dividers_df['Y_Coord'] = get_coords_from_geometry(dividers_df)
            # check columns
            dividers_cols = list(def_qgis_fields_dict['DIVIDERS'].keys())
            dividers_layer_name = 'Dividers Layer'
            check_columns(dividers_layer_name,
                          dividers_cols,
                          dividers_df.keys())
            dividers_df['CutoffFlow'] = dividers_df['CutoffFlow'].fillna('')
            dividers_df['Curve'] = dividers_df['Curve'].fillna('')
            dividers_df['WeirMinFlo'] = dividers_df['WeirMinFlo'].fillna('')
            dividers_df['WeirMaxDep'] = dividers_df['WeirMaxDep'].fillna('')
            dividers_df['WeirCoeff'] = dividers_df['WeirCoeff'].fillna('')
            dividers_annot = get_annotations_from_raw_df(
                raw_data_dict['dividers_raw'].copy()
            )
            dividers_coords = dividers_df[['Name', 'X_Coord', 'Y_Coord']]
            inp_dict['DIVIDERS'] = {
                'data': dividers_df,
                'annotations': dividers_annot
            }
            inp_dict['COORDINATES']['data'] = inp_dict['COORDINATES']['data'].append(dividers_coords)
            all_nodes = all_nodes+dividers_df['Name'].tolist()
        feedback.setProgress(50)

        # inflows
        if len(all_nodes) > 0:
            if 'inflows' in raw_data_dict.keys():
                feedback.setProgressText(self.tr('[INFLOWS] section'))
                from .g_s_nodes import get_inflows_from_table
                dwf_dict, inflow_dict = get_inflows_from_table(
                    raw_data_dict['inflows'],
                    all_nodes
                )
                if len(inflow_dict) > 0:
                    inp_dict['INFLOWS'] = {'data': inflow_dict}
                if len(dwf_dict) > 0:
                    inp_dict['DWF'] = {'data': dwf_dict}
        feedback.setProgress(55)

        # Streets and inlets
        if 'streets' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[STREETS] and [INLETS] section'))
            from .g_s_links import get_street_from_tables
            streets_df, inlets_df, inlet_usage_df = get_street_from_tables(
                raw_data_dict['streets']
            )
            if len(streets_df) > 0:
                inp_dict['STREETS'] = {'data': streets_df}
            if len(inlets_df) > 0:
                inp_dict['INLETS'] = {'data': inlets_df}
            if len(inlet_usage_df) > 0:
                inp_dict['INLET_USAGE'] = {'data': inlet_usage_df}

        # Curves
        if 'curves' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[CURVES] section'))
            from .g_s_various_functions import get_curves_from_table
            inp_dict['CURVES'] = {
                'data': get_curves_from_table(
                    raw_data_dict['curves'],
                    name_col='Name'
                )
            }
        feedback.setProgress(60)

        # patterns
        if 'patterns' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[PATTERNS] section'))
            from .g_s_various_functions import get_patterns_from_table
            inp_dict['PATTERNS'] = {
                'data': get_patterns_from_table(
                    raw_data_dict['patterns'],
                    name_col='Name'
                )
            }
        feedback.setProgress(65)

        # time series
        if 'timeseries' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[TIMESERIES] section'))
            from .g_s_various_functions import get_timeseries_from_table
            inp_dict['TIMESERIES'] = {
                'data': get_timeseries_from_table(
                    raw_data_dict['timeseries'],
                    name_col='Name',
                    feedback=feedback
                )
            }
        feedback.setProgress(70)

        # rain gages
        from .g_s_subcatchments import get_raingage_from_qgis_row
        if 'raingages_raw' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[RAINGAGES] section'))
            rg_cols = list(def_qgis_fields_dict['RAINGAGES'].keys())
            rg_features_df = raw_data_dict['raingages_raw']
            check_columns(
                file_raingages,
                rg_cols,
                rg_features_df.columns
            )
            raingages_annot = get_annotations_from_raw_df(
                rg_features_df
            )
            rg_features_df = rg_features_df.apply(
                lambda x: get_raingage_from_qgis_row(x),
                axis=1
            )
            rg_features_df['X_Coord'], rg_features_df['Y_Coord'] = get_coords_from_geometry(rg_features_df)
            rg_symbols_df = rg_features_df[['Name', 'X_Coord', 'Y_Coord']]
            rg_inp_cols = def_sections_dict['RAINGAGES']
            rg_features_df = rg_features_df[rg_inp_cols]
            inp_dict['RAINGAGES'] = {
                'data': rg_features_df,
                'annotations': raingages_annot
            }
            inp_dict['SYMBOLS'] = {'data': rg_symbols_df}

        # quality
        if 'quality' in raw_data_dict.keys():
            feedback.setProgressText(self.tr('[POLLUTANTS] and [LANDUSES] section'))
            from .g_s_quality import get_quality_params_from_table
            if 'SUBCATCHMENTS' in inp_dict.keys():
                inp_dict['QUALITY'] = {
                    'data': get_quality_params_from_table(
                        raw_data_dict['quality'],
                        inp_dict['SUBCATCHMENTS']['data'].copy()
                    )
                }
            else:
                inp_dict['QUALITY'] = {
                    'data': get_quality_params_from_table(
                        raw_data_dict['quality']
                    )
                }
        feedback.setProgressText(self.tr('done \n'))
        feedback.setProgress(80)

        # writing inp file
        feedback.setProgressText(self.tr('Creating inp file:'))
        inp_dict = {k: v for k, v in inp_dict.items() if len(v['data']) > 0}  # remove empty sections
        from .g_s_write_inp import write_inp
        write_inp(inp_file_name,
                  project_dir,
                  inp_dict,
                  feedback)
        feedback.setProgress(98)
        feedback.setProgressText(
            self.tr(
                'input file saved in ' + str(os.path.join(
                    project_dir,
                    inp_file_name)
                )
            )
        )
        return {}

    def shortHelpString(self):
        return self.tr(""" With this tool you can write a swmm input file based on QGIS layers (and supplementary data in .xslx files).\n
        The column names within attribute tables have to be the same as in the default data set.
        Proposed workflow:\n
        1) load default data with the first tool.\n
        2) copy all files to a new folder and edit the data set.\n
        3) select the edited layers / files to create the input file (.inp)\n
        4) run the input file in swmm
        """)

    def name(self):
        return 'GenerateSwmmInpFile'

    def displayName(self):
        return self.tr('2_GenerateSwmmInpFile')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return ''

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return GenerateSwmmInpFile()
