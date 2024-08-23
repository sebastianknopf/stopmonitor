from abc import ABC
from lxml.etree import tostring
from lxml.etree import register_namespace
from lxml.etree import Element
from lxml.etree import SubElement
from lxml.etree import QName

from .isotime import timestamp

class TriasRequest(ABC):

    def __init__(self):
        nsmap = {None: 'http://www.vdv.de/trias', 'siri': 'http://www.siri.org.uk/siri'}
        self.trias = Element('Trias', nsmap=nsmap, version='1.1')

    def xml(self) -> str:
        return tostring(self.trias, xml_declaration=True, encoding='UTF-8')

class ServiceRequest(TriasRequest):

    def __init__(self, requestor_ref: str) -> None:
        super().__init__()

        service_request = SubElement(self.trias, 'ServiceRequest')
        SubElement(service_request, QName('http://www.siri.org.uk/siri', 'RequestTimestamp')).text = timestamp()
        SubElement(service_request, QName('http://www.siri.org.uk/siri', 'RequestorRef')).text = requestor_ref

class StopEventRequest(ServiceRequest):

    def __init__(self, requestor_ref: str, stop_point_ref: str, dep_arr_time: str, num_results: int = 20) -> None:
        super().__init__(requestor_ref)

        service_request = self.trias.find('.//ServiceRequest')

        request_payload = SubElement(service_request, 'RequestPayload')
        stop_event_request = SubElement(request_payload, 'StopEventRequest')
        location = SubElement(stop_event_request, 'Location')
        location_ref = SubElement(location, 'LocationRef')
        SubElement(location_ref, 'StopPointRef').text = stop_point_ref
        SubElement(stop_event_request, 'DepArrTime').text = dep_arr_time

        params = SubElement(stop_event_request, 'Params')
        SubElement(params, 'NumberOfResults').text = str(num_results)
        SubElement(params, 'StopEventType').text = 'departure'
        SubElement(params, 'IncludeRealtimeData').text = str(True).lower()

