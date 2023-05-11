import twin4build.saref4bldg.physical_object.building_object.building_device.distribution_device.distribution_flow_device.flow_controller.flow_controller as flow_controller
from typing import Union

from twin4build.logger.Logging import Logging

logger = Logging.get_logger("ai_logfile")

class FlowMeter(flow_controller.FlowController):
    def __init__(self,
                readOutType: Union[str, None] = None,
                remoteReading: Union[bool, None] = None,
                **kwargs):
        
        logger.info("[FlowMeter] : Entered in Initialise Fuction")

        super().__init__(**kwargs)
        assert isinstance(readOutType, str) or readOutType is None, "Attribute \"readOutType\" is of type \"" + str(type(readOutType)) + "\" but must be of type \"" + str(str) + "\""
        assert isinstance(remoteReading, bool) or remoteReading is None, "Attribute \"remoteReading\" is of type \"" + str(type(remoteReading)) + "\" but must be of type \"" + str(bool) + "\""
        self.readOutType = readOutType
        self.remoteReading = remoteReading

        logger.info("[FlowMeter] : Exited from Initialise Fuction")
