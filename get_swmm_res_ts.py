import os
import pandas as pd
from qgis.utils import iface
from qgis.PyQt import (
    QtWidgets,
    uic
)
from PyQt5.QtWidgets import (
    QComboBox,
    QRadioButton,
    QDialog,
    QWidget ,
    QDialogButtonBox,
    QVBoxLayout,
    QLabel
)
from qgis.gui import QgsFileWidget
from pyswmm import Output
from swmm.toolkit.shared_enum import (
    LinkAttribute,
    NodeAttribute,
    SubcatchAttribute,
    SystemAttribute
)
import matplotlib.pyplot as plt


layer = QgsProject.instance().mapLayer('[% @layer_id %]')
layer_field_name = layer.fields().indexFromName("Name")
swmm_obj_requested = layer.getFeature([% $id %])
obj_name = swmm_obj_requested.attributes()[layer_field_name]


swmm_obj_types = {
    #'RAINGAGE': 'SYSTEM',
    'SUBCATCHMENTS': 'SUBCATCH',
    'JUNCTIONS': 'NODE',
    'OUTFALLS': 'NODE',
    'DIVIDERS': 'NODE',
    'STORAGE': 'NODE',
    'CONDUITS': 'LINK',
    'PUMPS': 'LINK',
    'ORIFICES': 'LINK',
    'WEIRS': 'LINK',
    'OUTLETS': 'LINK'
}

result_aggregates = {
    0: 'sum',
    1: 'mean',
    2: 'median',
    3: 'max',
    4: 'min'
}

print_flow_units = {
    'LPS': 'L/s',
    'CMS': 'm³/s',
    'MLD': '',
    'CFS': 'ft³/s',
    'GPM': '',
    'MGD': ''
}

print_swmm_units = {
    'q': print_flow_units,  # -> Flow; see print_flow_units
    'vel': ['ft/s', 'm/s'],  # -> Velocity
    'vol': ['ft³', 'm³'],  # -> Volume
    'd': ['ft', 'm'],  # -> Depth / Elevation
    'q_d': ['in/d', 'mm/d'],
    'q_hr': ['in/hr', 'mm/hr'] # -> Evaporation / Precipitation
}

print_swmm_units_system = {
    'US': 0,
    'SI': 1
}

nodes_attrs = {
    0: [NodeAttribute.FLOODING_LOSSES, 'q'],
    1: [NodeAttribute.HYDRAULIC_HEAD, 'd'],
    2: [NodeAttribute.INVERT_DEPTH, 'd'],
    3: [NodeAttribute.LATERAL_INFLOW, 'q'],
    4: [NodeAttribute.POLLUT_CONC_0, None],
    5: [NodeAttribute.PONDED_VOLUME, 'vol'],
    6: [NodeAttribute.TOTAL_INFLOW, 'q']
}
link_attrs = {
    0: [LinkAttribute.FLOW_RATE, 'q'],
    1: [LinkAttribute.FLOW_DEPTH, 'd'],
    2: [LinkAttribute.FLOW_VELOCITY,'vel'],
    3: [LinkAttribute.FLOW_VOLUME,'vol'],
    4: [LinkAttribute.CAPACITY, None],
    5: [LinkAttribute.POLLUT_CONC_0, None]
}
subcatch_attrs = {
    0: [SubcatchAttribute.EVAP_LOSS, 'q_d'],
    1: [SubcatchAttribute.GW_OUTFLOW_RATE, 'q'],
    2: [SubcatchAttribute.GW_TABLE_ELEV, 'd'],
    3: [SubcatchAttribute.INFIL_LOSS, 'q_hr'],
    4: [SubcatchAttribute.POLLUT_CONC_0, None],
    5: [SubcatchAttribute.RAINFALL, 'q_hr'],
    6: [SubcatchAttribute.RUNOFF_RATE, 'q'],
    7: [SubcatchAttribute.SNOW_DEPTH, 'd'],
    8: [SubcatchAttribute.SOIL_MOISTURE, None]
}



def get_node_ts(obj_name, out, req_attr):
    if obj_name in out.nodes.keys():
        result_ts = out.node_series(
            obj_name, 
            req_attr
        )
        return result_ts
    else:
        return None
        
def get_link_ts(obj_name, out, req_attr):
    if obj_name in out.links.keys():
        result_ts = out.link_series(
            obj_name, 
            req_attr
        )
        return result_ts
    else:
        return None

def get_subc_ts(obj_name, out, req_attr):
    if obj_name in out.subcatchments.keys():
        result_ts = out.subcatch_series(
            obj_name, 
            req_attr
        )
        return result_ts
    else:
        return None

def get_results(out_request):
    with Output(out_request['outfile']) as out:
        swmm_units = out.units
        swmm_units_flow = swmm_units['flow']
        swmm_units_system = swmm_units['system']
        swmm_units_pollutants = swmm_units['pollutant']
        req_swmm_type = swmm_obj_types[out_request['layer']]
        if req_swmm_type == 'NODE':
            req_attr = nodes_attrs[out_request['attr']][0]
            req_unit_type = nodes_attrs[out_request['attr']][1]
            result_ts = get_node_ts(out_request['obj_name'], out, req_attr)
        elif req_swmm_type == 'LINK':
            req_attr = link_attrs[out_request['attr']][0]
            req_unit_type = link_attrs[out_request['attr']][1]
            result_ts = get_link_ts(out_request['obj_name'], out, req_attr)
        elif req_swmm_type == 'SUBCATCH':
            req_attr = subcatch_attrs[out_request['attr']][0]
            req_unit_type = subcatch_attrs[out_request['attr']][1]
            result_ts = get_subc_ts(out_request['obj_name'], out, req_attr)
        #elif req_swmm_type == 'SYSTEM':
        #    req_attr = SystemAttribute.RAINFALL
        else:
            result_ts = None
            raise BaseException('Unbekannter SWMM-Objekttyp')
        res_dict = {
            'ts': result_ts,
            'unit_type': req_unit_type,
            'units_flow': swmm_units_flow,
            'units_system': swmm_units_system,
            'units_pollutants': swmm_units_pollutants,
            'req_attr': req_attr
        }
        return res_dict



class getSwmmResDialog(QDialog):
    def __init__(self, parent=None):
        """Constructor."""
        super(getSwmmResDialog, self).__init__(parent)
        self.setWindowTitle('Get SWMM time series for '+str(obj_name))
        
        self.label_out_file = QLabel('SWMM Output File')
        self.out_file = QgsFileWidget()
        self.out_file.setFilter("SWMM output files (*.out *.OUT)")
        
        self.label_SWMM_type = QLabel('SWMM object type')
        self.layer_sel_box = QComboBox()
        self.layer_sel_box.addItems(list(swmm_obj_types.keys()))
        
        self.label_Attribute = QLabel('SWMM attribute')
        self.attr_select_box = QComboBox()
        
        self.layer_sel_box.setCurrentIndex(1)
        self.layer_sel_box.currentIndexChanged.connect(self.update_attrs)
        self.layer_sel_box.setCurrentIndex(0)
        
        self.radioButton_saveCsv = QRadioButton('save timeseries as csv')
        self.radioButton_saveCsv.toggled.connect(self.add_csv_path_field)
        
        self.label_csv = QLabel('where should the resulting csv file be saved?')
        self.save_csvfile = QgsFileWidget()
        self.save_csvfile.setStorageMode(3)
        self.save_csvfile.setFilter("CSV files (*.csv *.CSV)")
        self.save_csvfile.setDisabled(True)
        self.label_csv.setDisabled(True)
        
        btn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        self.buttonBox = QDialogButtonBox(btn)
        self.buttonBox.accepted.connect(self.run_get_res)
        self.buttonBox.rejected.connect(self.close)
        self.buttonBox.clicked.connect(self.close)
        
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.label_out_file)
        self.layout.addWidget(self.out_file)
        self.layout.addWidget(self.label_SWMM_type)
        self.layout.addWidget(self.layer_sel_box)
        self.layout.addWidget(self.label_Attribute)
        self.layout.addWidget(self.attr_select_box)
        self.layout.addWidget(self.radioButton_saveCsv)
        self.layout.addWidget(self.label_csv)
        self.layout.addWidget(self.save_csvfile)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)
        
    def update_attrs(self):
        self.attr_select_box.clear()
        d_type = swmm_obj_types[self.layer_sel_box.currentText()]
        #if d_type == 'SYSTEM':
        #    self.attr_select_box.addItems(['a'])
        if d_type == 'SUBCATCH':
            val_list = [x[0].name for x in subcatch_attrs.values()]
            self.attr_select_box.addItems(val_list)
        if d_type == 'NODE':
            val_list = [x[0].name for x in nodes_attrs.values()]
            self.attr_select_box.addItems(val_list)
        if d_type == 'LINK':
            val_list = [x[0].name for x in link_attrs.values()]
            self.attr_select_box.addItems(val_list)
            
    def add_csv_path_field(self):
        if self.radioButton_saveCsv.isChecked()==True:
            self.save_csvfile.setEnabled(True)
            self.label_csv.setEnabled(True)
        else:
            self.save_csvfile.setDisabled(True)
            self.label_csv.setDisabled(True)
    
    def closeIt(self):
        self.close
        
    def run_get_res(self):
        self.out_request = {
                'outfile': self.out_file.filePath(),
                'layer': self.layer_sel_box.currentText(),
                'obj_name': obj_name,
                'attr': self.attr_select_box.currentIndex(),
                }
        if self.out_request['outfile'] == '':
            iface.messageBar().pushMessage("Error", 'No Output File selected!', level=Qgis.Critical)
            #raise ValueError('No Output File selected!')
        else:
            self.res_dict = get_results(self.out_request)
            self.ts = self.res_dict['ts']
            if self.ts is None:
                iface.messageBar().pushMessage(
                    "Error",
                    'Object '+ obj_name +' not in selected output file or wrong SWMM object type',
                    level=Qgis.Critical
                )
            else:
                self.df = pd.DataFrame(self.ts.items())
                if self.res_dict['unit_type'] == 'q':  # flow
                    self.print_units = print_flow_units[self.res_dict['units_flow']]
                else:
                    self.us_si = print_swmm_units_system[self.res_dict['units_system']]  # 0, 1
                    self.print_units = print_swmm_units[self.res_dict['unit_type']][self.us_si]
                self.req_swmm_type_str = self.out_request['layer'].capitalize()
                self.title_list = self.res_dict['req_attr'].name.split('_')
                self.title_text = ' '.join(self.title_list).lower()
                plt.plot(self.df[0],self.df[1])
                plt.title(
                    self.req_swmm_type_str + ': ' + str(obj_name) + ' ' + self.title_text,
                    fontsize=10
                    )
                plt.xlabel("Time")
                plt.ylabel(self.print_units)
                plt.show()
                if self.radioButton_saveCsv.isChecked()==True:
                    if self.save_csvfile.filePath() != '':
                        self.csvpth = self.save_csvfile.filePath()
                        try:
                            self.df = self.df.rename(columns={0: 'Time',1: self.res_dict['req_attr'].name})
                            self.df.to_csv(self.csvpth, index = False)
                            iface.messageBar().pushMessage(
                                "Info",
                                'Time series saved to '+ self.csvpth,
                                level=Qgis.Success
                            )
                            del self.out_request
                            self.closeIt
                        except BaseException:
                            iface.messageBar().pushMessage(
                                "Error",
                                ('Could not save time series to the selected '
                                +'file. (This can happen if the file is already '
                                +'opened in another program.)'),
                                level=Qgis.Critical
                            )
                            self.closeIt
                    else: 
                        iface.messageBar().pushMessage(
                            "Error",
                            'No csv file to save',
                            level=Qgis.Critical
                        )
                        self.closeIt()
                else:
                    del self.out_request
                    self.closeIt()
w = getSwmmResDialog()
w.show()