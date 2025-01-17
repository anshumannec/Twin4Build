
# import necessay modules
import os 
import sys
import time
import pytz
import schedule
import json
import requests
import pandas as pd
from datetime import datetime , timedelta

###Only for testing before distributing package
if __name__ == '__main__':
    # Define a function to move up in the directory hierarchy
    uppath = lambda _path, n: os.sep.join(_path.split(os.sep)[:-n])
    # Calculate the file path using the uppath function
    file_path = uppath(os.path.abspath(__file__), 5)
    # Append the calculated file path to the system path
    sys.path.append(file_path)

#importing custom modules
from twin4build.logger.Logging import Logging

# Initialize the logger
logger = Logging.get_logger('API_logfile')

class RequestTimer:
    def __init__(self,request_class_obj) -> None:
        '''
            This class runs the simulation of history and forecast 
            according to the given time intervals.
        '''
        logger.info("[request_timer_class]: Entered initialise function")
        # Get the current time in the Denmark time zone
        self.denmark_timezone = pytz.timezone('Europe/Copenhagen')

        # minutes ,  seconds to be eiliminated , for update as well , history and forecast
        # 4:00:00 - H/M/S
        self.time_format = '%Y-%m-%d %H:%M:%S%z'
       
        self.simulation_count = 1

        # creating the object for the request simluation class
        self.request_obj  = request_class_obj

        # configuration function called of the request class
        self.config = self.request_obj.get_configuration()

        # reading the values from the config file
        self.simulation_duration = int(self.config["simulation_variables"]["simulation_duration"])
        self.forecast_simulation_duration = int(self.config["forecast_simulation_variables"]["forecast_simulation_duration"])
        
        self.warmup_time = int(self.config["simulation_variables"]["warmup_time"])
        self.forecast_warmup_time = int(self.config["forecast_simulation_variables"]["warmup_time"])

        self.simulation_frequency = int(self.config["forecast_simulation_variables"]["simulation_frequency"])

        logger.info("[request_timer_class]: Exited initialise function")

        
    def get_history_date(self):
        '''
            This function calculates the start , end and warmup time for history simulations
        '''

        # end = current time - 3
        # start = end - simulation_duration(1)
        # start time new = start - warmpup (12)

        # end time = current -3 


        self.current_time_denmark = datetime.now(self.denmark_timezone).replace(minute=0, second=0, microsecond=0) #### replace m =00 , s= 00
        
        # Log the rounded time
        logger.info("request_time:simulation ran last time at : %s", str(self.current_time_denmark))
        
        end_time = self.current_time_denmark - timedelta(hours=3)

        #start time = end time - simulation time ( 1 hour ) 
        start_time = end_time - timedelta(hours=self.simulation_duration)

        # total time (warmp up time start - 12 which will be the start for the input dict) = start time - warmup time
        total_start_time = start_time - timedelta(hours=self.warmup_time)

        # formatted total start (warmup) time to '%Y-%m-%d %H:%M:%S' format
        formatted_total_start_time = total_start_time.strftime(self.time_format)
        ## formatted end time to '%Y-%m-%d %H:%M:%S' format
        formatted_endtime = end_time.strftime(self.time_format)
        # formatted start time to '%Y-%m-%d %H:%M:%S' format
        formatted_startime = start_time.strftime(self.time_format)

        logger.info("[request_timer]: Calculated History Date")

        return formatted_startime,formatted_endtime,formatted_total_start_time
        
    def get_forecast_date(self):
        '''
            This function calculates the start , end and warmup time for forecast simulations
        '''
        self.current_time_denmark = datetime.now(self.denmark_timezone).replace(minute=0, second=0, microsecond=0)

        # Log the rounded time
        logger.info("request_time:simulation ran last time at : %s", str(self.current_time_denmark))
        
        # end time - 3 = start without warmup 
        start_time = self.current_time_denmark - timedelta(hours=3)
        # start time now + 24 hours = 3 , 30
        end_time = start_time + timedelta(hours=self.forecast_simulation_duration) # simulation_duration = 24
        # start time - 12 hours = warm up  3 28
        total_start_time = start_time - timedelta(hours=self.forecast_warmup_time)

        #  # formatted start , end  time to '%Y-%m-%d %H:%M:%S' format 
        forecast_total_start_time = total_start_time.strftime(self.time_format)
        forecast_endtime = end_time.strftime(self.time_format)
        forecast_startime = start_time.strftime(self.time_format)
        
        logger.info("[request_timer]: Calculated Forecast Date")
        
        return forecast_startime,forecast_endtime,forecast_total_start_time
    
    def request_for_forcasting_simulations(self):
        '''
        function to run simulation api for forecast
        '''
        # make changes as per forcasting times 
        start_time, end_time,warmup_time = self.get_forecast_date()
    
        logger.info("[request_to_api:main]:start and end time is")
        self.request_obj.request_to_simulator_api(start_time, end_time,warmup_time,forecast=True)
        logger.info("[request_timer]: Running Forecast Simulations")

    def request_for_history_simulations(self):
        '''
            function to run simulation api for forecast
        '''
        start_time, end_time,warmup_time = self.get_history_date()

        logger.info("[request_to_api:main]:start and end time is")
        self.request_obj.request_to_simulator_api(start_time, end_time,warmup_time,forecast=False)
        logger.info("[request_timer]: Running Forecast Simulations")

    def request_simulator(self):
        '''
        scheduled function for simulation api call for forcast and history with respect to the counter
        '''
        if self.simulation_count == 1:
            self.request_for_history_simulations()
            self.request_for_forcasting_simulations()

            #counter that adds up with 1 every hour
            self.simulation_count += 1
            self.simulation_last_time = datetime.now(self.denmark_timezone).replace(minute=0, second=0, microsecond=0)
            
            logger.info("request_time:simulation ran last time at : %s",str(self.simulation_last_time))

        else:
            # if the simulation running task is no inital then it runs the forecast function acccording to the counter 
            
            time_now = datetime.now(self.denmark_timezone).replace(minute=0, second=0, microsecond=0)
            self.time_difference  = time_now - self.simulation_last_time

            self.simulation_count += 1
            self.simulation_last_time =  datetime.now(self.denmark_timezone).replace(minute=0, second=0, microsecond=0)

            #from config we are getting the simulation frequency and running the forecast for every simulation_frequency interval
            # we are running forecasted simulation after 3 hours 

            config_time_diff = self.simulation_frequency*60*60

            #config_time_diff = 3 * 60 * 60
            
            if self.time_difference.seconds >= (config_time_diff) or self.simulation_count % self.simulation_frequency == 0:
                self.request_for_forcasting_simulations()
                logger.info("request_time:running forecast simulation for  : %s time",str(self.simulation_count))
                self.simulation_count = 0