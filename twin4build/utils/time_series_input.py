from twin4build.saref4syst.system import System
import numpy as np
from twin4build.utils.data_loaders.load_spreadsheet import load_spreadsheet
from twin4build.utils.preprocessing.data_collection import DataCollection
from twin4build.logger.Logging import Logging
from twin4build.utils.get_main_dir import get_main_dir
logger = Logging.get_logger("ai_logfile")

class TimeSeriesInputSystem(System):
    """
    This component models a generic dynamic input based on prescribed time series data.
    It extracts and samples the second column of a csv file given by "filename".
    """
    def __init__(self,
                filename=None,
                **kwargs):
        super().__init__(**kwargs)
        self.filename = filename
        logger.info("[Time Series Input] : Entered in Initialise Function")
        self.cached_initialize_arguments = None
        self.cache_root = get_main_dir()

    def cache(self,
            startTime=None,
            endTime=None,
            stepSize=None):
        pass

    def initialize(self,
                    startTime=None,
                    endTime=None,
                    stepSize=None):
        if self.cached_initialize_arguments!=(startTime, endTime, stepSize):
            df = load_spreadsheet(filename=self.filename, stepSize=stepSize, start_time=startTime, end_time=endTime, dt_limit=1200, cache_root=self.cache_root)
            print(self.filename)
            print(self.id)
            print(df)
            data_collection = DataCollection(name=self.id, df=df, nan_interpolation_gap_limit=99999)
            data_collection.interpolate_nans()
            df = data_collection.get_dataframe()
            self.physicalSystemReadings = df.iloc[:,1]

            nan_dates = data_collection.time[np.isnan(self.physicalSystemReadings)]
            if nan_dates.size>0:
                message = f"data for TimeSeriesInputSystem object {self.id} contains NaN values at date {nan_dates[0].strftime('%m/%d/%Y')}."
                raise Exception(message)
            
        self.stepIndex = 0
        self.cached_initialize_arguments = (startTime, endTime, stepSize)
        logger.info("[Time Series Input] : Exited from Initialise Function")
        
    def do_step(self, secondTime=None, dateTime=None, stepSize=None):
        key = list(self.output.keys())[0]
        self.output[key] = self.physicalSystemReadings[self.stepIndex]
        self.stepIndex += 1
        
        