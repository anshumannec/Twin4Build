from .coil import Coil
from typing import Union
import twin4build.saref.measurement.measurement as measurement
from twin4build.utils.fmu.fmu_component import FMUComponent
from twin4build.utils.constants import Constants
from twin4build.utils.uppath import uppath
from scipy.optimize import least_squares
import numpy as np
import os
import sys
from twin4build.saref.property_.temperature.temperature import Temperature
from twin4build.saref.property_.flow.flow import Flow
from twin4build.utils.fmu.unit_converters.functions import to_degC_from_degK, to_degK_from_degC, do_nothing


class CoilSystem(FMUComponent, Coil):
    def __init__(self,
                m1_flow_nominal=None,
                m2_flow_nominal=None,
                tau1=None,
                tau2=None,
                tau_m=None,
                mFlowValve_nominal=None,
                mFlowPump_nominal=None,
                dpCheckValve_nominal=None,
                dp1_nominal=None,
                dpPump=None,
                dpValve_nominal=None,
                dpSystem=None,
                **kwargs):
        Coil.__init__(self, **kwargs)
        self.start_time = 0
        fmu_filename = "coil_0wbypass_0FMUmodel.fmu"
        self.fmu_path = os.path.join(uppath(os.path.abspath(__file__), 1), fmu_filename)

        self.m1_flow_nominal = m1_flow_nominal
        self.m2_flow_nominal = m2_flow_nominal
        self.tau1 = tau1
        self.tau2 = tau2
        self.tau_m = tau_m
        self.mFlowValve_nominal = mFlowValve_nominal
        self.mFlowPump_nominal = mFlowPump_nominal
        self.dpCheckValve_nominal = dpCheckValve_nominal
        self.dp1_nominal = dp1_nominal
        self.dpPump = dpPump
        self.dpValve_nominal = dpValve_nominal
        self.dpSystem = dpSystem

        self.input = {"valvePosition": None,
                      "airFlowRate": None,
                      "supplyWaterTemperature": None,
                      "inletAirTemperature": None}
        
        self.output = {"outletWaterTemperature": None, 
                       "outletAirTemperature": None}
        
        
        self.FMUinputMap = {"valvePosition": "u",
                            "airFlowRate": "inlet2.m_flow",
                            "supplyWaterTemperature": "supplyWaterTemperature",
                            "inletAirTemperature": "inlet2.forward.T"}
        
        self.FMUoutputMap = {"outletWaterTemperature": "outletWaterTemperature", 
                            "outletAirTemperature": "outlet2.forward.T"}
        
        self.FMUparameterMap = {"m1_flow_nominal": "m1_flow_nominal",
                                "m2_flow_nominal": "m2_flow_nominal",
                                "tau1": "tau1",
                                "tau2": "tau2",
                                "tau_m": "tau_m",
                                "nominalUa.hasValue": "UA_nominal",
                                "mFlowValve_nominal": "mFlowValve_nominal",
                                "flowCoefficient.hasValue": "Kv",
                                "mFlowPump_nominal": "mFlowPump_nominal",
                                "dpCheckValve_nominal": "dpCheckValve_nominal",
                                "dp1_nominal": "dp1_nominal",
                                "dpPump": "dpPump",
                                "dpValve_nominal": "dpValve_nominal",
                                "dpSystem": "dpSystem"}
        
        self.input_unit_conversion = {"valvePosition": do_nothing,
                                      "airFlowRate": do_nothing,
                                      "supplyWaterTemperature": to_degK_from_degC,
                                      "inletAirTemperature": to_degK_from_degC}
        
        self.output_unit_conversion = {"outletWaterTemperature": to_degC_from_degK,
                                      "outletAirTemperature": to_degC_from_degK}

        self.INITIALIZED = False

        
    def initialize(self,
                    startPeriod=None,
                    endPeriod=None,
                    stepSize=None):
        '''
            This function initializes the FMU component by setting the start_time and fmu_filename attributes, 
            and then sets the parameters for the FMU model.
        '''
        if self.INITIALIZED:
            self.reset()
        else:
            FMUComponent.__init__(self, start_time=self.start_time, fmu_path=self.fmu_path)
            # Set self.INITIALIZED to True to call self.reset() for future calls to initialize().
            # This currently does not work with some FMUs, because the self.fmu.reset() function fails in some cases.
            self.INITIALIZED = True


        