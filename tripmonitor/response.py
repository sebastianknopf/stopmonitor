from abc import ABC
from lxml.etree import fromstring

from .model import Departure

class TriasResponse(ABC):
    def __init__(self, xml_data: str):
        self.nsmap = {None: 'http://www.vdv.de/trias', 'siri': 'http://www.siri.org.uk/siri'}
        self.root = fromstring(xml_data)

class StopEventResponse(TriasResponse):
    def __init__(self, xml_data: str):
        super().__init__(xml_data)

        self.departures = list()

        for stop_event_result in self.root.findall('.//StopEventResponse/StopEventResult', self.nsmap):
            stop_event = stop_event_result.find('.//StopEvent', self.nsmap)
            
            departure = Departure()
            departure.planned_departure_time = stop_event.find('.//ThisCall/CallAtStop/ServiceDeparture/TimetabledTime', self.nsmap).text
            departure.line_name = stop_event.find('.//Service/PublishedLineName/Text', self.nsmap).text
            
            if stop_event.find('.//ThisCall/CallAtStop/PlannedBay/Text', self.nsmap) is not None:
                departure.planned_bay = stop_event.find('.//ThisCall/CallAtStop/PlannedBay/Text', self.nsmap).text
            else:
                departure.planned_bay = None


            self.departures.append(departure)
