from abc import ABC
from lxml.etree import fromstring
from lxml.etree import Element
from operator import itemgetter

from .isotime import localtime

class TriasResponse(ABC):
    def __init__(self, xml_data: str):
        self.nsmap = {None: 'http://www.vdv.de/trias', 'siri': 'http://www.siri.org.uk/siri'}
        self.root = fromstring(xml_data)

    def _extract(self, xml_object: Element, tag_path: str, default: any = None) -> any:
        xml_result = xml_object.find(tag_path, self.nsmap)
        if xml_result is not None:
            if default is not None:
                t = type(default)
                return t(xml_result.text)
            
            return xml_result.text
        else:
            return default

class StopEventResponse(TriasResponse):

    def __init__(self, xml_data: str, order_type: str = 'estimated_time'):
        super().__init__(xml_data)

        self.departures = list()
        self.situations = list()

        departure_results = list()
        for stop_event_result in self.root.findall('.//StopEventResponse/StopEventResult', self.nsmap):
            stop_event = stop_event_result.find('.//StopEvent', self.nsmap)
            
            departure = dict()

            # extract planned and estimated departure time and several other departure information
            planned_time = localtime(self._extract(stop_event, './/ThisCall/CallAtStop/ServiceDeparture/TimetabledTime', None))
            estimated_time = localtime(self._extract(stop_event, './/ThisCall/CallAtStop/ServiceDeparture/EstimatedTime', None))

            departure['planned_date'] = planned_time.strftime('%Y-%m-%d') 
            departure['planned_time'] = planned_time.strftime('%H:%M:%S')
            departure['estimated_date'] = estimated_time.strftime('%Y-%m-%d') if estimated_time is not None else None
            departure['estimated_time'] = estimated_time.strftime('%H:%M:%S') if estimated_time is not None else None
            departure['planned_bay'] = self._extract(stop_event, './/ThisCall/CallAtStop/PlannedBay/Text', None)
            departure['estimated_bay'] = self._extract(stop_event, './/ThisCall/CallAtStop/EstimatedBay/Text', None)

            departure['sort_time'] = estimated_time if estimated_time is not None else planned_time

            # extract cancellation info
            trip_cancelled = self._extract(stop_event, './/Service/Cancelled', False)
            stop_cancelled = self._extract(stop_event, './/ThisCall/CallAtStop/StopCallStatus/NotServicedStop', False)

            departure['cancelled'] = trip_cancelled or stop_cancelled

            # set flag whether there're any realtime data available
            departure['realtime'] = departure['estimated_time'] is not None or departure['cancelled']

            # extract mode and submode
            departure['mode'] = self._extract(stop_event, './/Service/Mode/PtMode', None)

            # extract submode
            if departure['mode'] is not None:
                if departure['mode'] == 'air':
                    departure['sub_mode'] = self._extract(stop_event, './/Service/Mode/AirSubmode', None)
                elif departure['mode'] == 'bus':
                    departure['sub_mode'] = self._extract(stop_event, './/Service/Mode/BusSubmode', None)
                elif departure['mode'] == 'trolleyBus':
                    departure['sub_mode'] = self._extract(stop_event, './/Service/Mode/BusSubmode', None)
                elif departure['mode'] == 'tram':
                    departure['sub_mode'] = self._extract(stop_event, './/Service/Mode/TramSubmode', None)
                elif departure['mode'] == 'coach':
                    departure['sub_mode'] = self._extract(stop_event, './/Service/Mode/CoachSubmode', None)
                elif departure['mode'] == 'rail':
                    departure['sub_mode'] = self._extract(stop_event, './/Service/Mode/RailSubmode', None)
                elif departure['mode'] == 'intercityRail':
                    departure['sub_mode'] = self._extract(stop_event, './/Service/Mode/RailSubmode', None)
                elif departure['mode'] == 'urbanRail':
                    departure['sub_mode'] = self._extract(stop_event, './/Service/Mode/RailSubmode', None)
                elif departure['mode'] == 'metro':
                    departure['sub_mode'] = self._extract(stop_event, './/Service/Mode/MetroSubmode', None)
                elif departure['mode'] == 'water':
                    departure['sub_mode'] = self._extract(stop_event, './/Service/Mode/WaterSubmode', None)
                elif departure['mode'] == 'funicular':
                    departure['sub_mode'] = self._extract(stop_event, './/Service/Mode/FunicularSubmode', None)
                else:
                    departure['sub_mode'] = None
            else:
                departure['sub_mode'] = None

            departure['published_mode'] = self._extract(stop_event, './/Service/Mode/Name/Text', None)

            # extract line name and published line name
            published_line_name = self._extract(stop_event, './/Service/PublishedLineName/Text', None)
            if departure['published_mode'] is not None:
                departure['line_name'] = published_line_name.replace(departure['published_mode'], '').strip()
            else:
                departure['line_name'] = published_line_name

            departure['line_description'] = self._extract(stop_event, './/Service/RouteDescription/Text', None)

            # extract additional trip parameters
            departure['origin_text'] = self._extract(stop_event, './/Service/OriginText/Text', None)
            departure['destination_text'] = self._extract(stop_event, './/Service/DestinationText/Text', None)

            departure_results.append(departure)

        # sort by estimated departure time (estimated_time if available, else planned_time)
        # data are sorted by planned time by default, so we do not need to change anything here in this other case
        if order_type == 'estimated_time':
            sorted_results = sorted(departure_results, key=itemgetter('sort_time'))

        # remove real_departure_time field
        self.departures = [{k: v for k, v in d.items() if k != 'sort_time'} for d in sorted_results]

        situation_results = list()
        for pt_situation in self.root.findall('.//StopEventResponse//StopEventResponseContext//Situations//PtSituation', self.nsmap):
            
            situation = dict()

            situation['text'] = self._extract(pt_situation, './/{http://www.siri.org.uk/siri}Detail', None)
            situation['priority'] = self._extract(pt_situation, './/{http://www.siri.org.uk/siri}Priority', 3)
            
            situation['affects'] = list()
            for affected_stop_place in pt_situation.findall('.//{http://www.siri.org.uk/siri}Affects//{http://www.siri.org.uk/siri}StopPoints//{http://www.siri.org.uk/siri}AffectedStopPoint'):
                situation['affects'].append({
                    'type': 'stop',
                    'id': self._extract(affected_stop_place, './/{http://www.siri.org.uk/siri}StopPointRef')
                })

            for affected_line in pt_situation.findall('.//{http://www.siri.org.uk/siri}Affects//{http://www.siri.org.uk/siri}VehicleJourneys//{http://www.siri.org.uk/siri}AffectedVehicleJourney'):
                situation['affects'].append({
                    'type': 'line',
                    'id': self._extract(affected_line, './/{http://www.siri.org.uk/siri}LineRef')
                })

            situation_results.append(situation)

        self.situations = situation_results

class LocationInformationResponse(TriasResponse):
    
    def __init__(self, xml_data: str):
        super().__init__(xml_data)

        self.stops = list()

        results = list()
        for location in self.root.findall('.//LocationInformationResponse/Location', self.nsmap):            
            departure = dict()
            departure['id'] = self._extract(location, './/Location/StopPoint/StopPointRef', None)

            stop_name = self._extract(location, './/Location/StopPoint/StopPointName/Text', None)
            location_name = self._extract(location, './/Location/LocationName/Text', None)

            if location_name is not None and stop_name != location_name:
                departure['name'] = f"{location_name} {stop_name}"
            else:
                departure['name'] = stop_name

            results.append(departure)

        # set results
        self.stops = results
