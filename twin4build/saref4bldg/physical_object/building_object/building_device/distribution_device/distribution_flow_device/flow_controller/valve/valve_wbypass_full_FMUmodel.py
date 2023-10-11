from .valve import Valve
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


class ValveModel(FMUComponent, Valve):
    def __init__(self,
                 mFlowValve_nominal=None,
                 mFlowPump_nominal=None,
                 dpCheckValve_nominal=None,
                 dpCoil_nominal=None,
                 dpPump=None,
                 dpValve_nominal=None,
                 dpSystem=None,
                **kwargs):
        Valve.__init__(self, **kwargs)
        self.start_time = 0
        fmu_filename = "valve_0wbypass_0full_0FMUmodel.fmu"
        self.fmu_filename = os.path.join(uppath(os.path.abspath(__file__), 1), fmu_filename)

        self.mFlowValve_nominal = mFlowValve_nominal
        self.mFlowPump_nominal = mFlowPump_nominal
        self.dpCheckValve_nominal = dpCheckValve_nominal
        self.dpCoil_nominal = dpCoil_nominal

        self.dpPump = dpPump
        self.dpValve_nominal = dpValve_nominal
        self.dpSystem = dpSystem



        self.input = {"valvePosition": None}
        self.output = {"waterFlowRate": None,
                       "valvePosition": None}
        
        #Used in finite difference jacobian approximation for uncertainty analysis.
        self.inputLowerBounds = {"valvePosition": 0}
        self.inputUpperBounds = {"valvePosition": 1}

        self.FMUinputMap = {"valvePosition": "u"}
        self.FMUoutputMap = {"waterFlowRate": "m_flow"}
        self.FMUparameterMap = {"mFlowValve_nominal": "mFlowValve_nominal",
                                "flowCoefficient.hasValue": "Kv",
                                "mFlowPump_nominal": "mFlowPump_nominal",
                                "dpCheckValve_nominal": "dpCheckValve_nominal",
                                "dpCoil_nominal": "dpCoil_nominal",
                                "dpPump": "dpPump",
                                "dpValve_nominal": "dpValve_nominal",
                                "dpSystem": "dpSystem"}
        
        self.input_unit_conversion = {"valvePosition": do_nothing}
        self.output_unit_conversion = {"waterFlowRate": do_nothing,
                                       "valvePosition": do_nothing}

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
            FMUComponent.__init__(self, start_time=self.start_time, fmu_filename=self.fmu_filename)
            # Set self.INITIALIZED to True to call self.reset() for future calls to initialize().
            # This currently does not work with some FMUs, because the self.fmu.reset() function fails in some cases.
            self.INITIALIZED = True
