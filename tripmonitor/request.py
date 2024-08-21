from abc import ABC
from lxml.etree import cleanup_namespaces
from lxml.etree import tostring
from lxml.etree import register_namespace
from lxml.objectify import deannotate
from lxml.objectify import Element
from lxml.objectify import DataElement

from .isotime import timestamp

class TriasRequest(ABC):

    def __init__(self):

        register_namespace('siri', 'http://www.siri.org.uk/siri')

        self.Trias = Element('Trias', version='1.1')

    def xml(self) -> str:
        deannotate(self.Trias)
        # cleanup_namespaces(self.Trias)

        return tostring(self.Trias, pretty_print=True, xml_declaration=True, encoding='UTF-8')    

class ServiceRequest(TriasRequest):

    def __init__(self, requestor_ref: str) -> None:
        super().__init__()

        self.Trias.ServiceRequest = Element('ServiceRequest')
        self.Trias.ServiceRequest.RequestTimestamp = DataElement(timestamp())
        self.Trias.ServiceRequest.RequestorRef = DataElement(requestor_ref)

class StopEventRequest(ServiceRequest):

    def __init__(self, requestor_ref: str, stop_point_ref: str, dep_arr_time: str) -> None:
        super().__init__(requestor_ref)

        self.Trias.ServiceRequest.RequestPayload = Element('RequestPayload')
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest = Element('StopEventRequest')
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Location = Element('Location')
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Location.LocationRef = Element('LocationRef')
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Location.LocationRef.StopPointRef = stop_point_ref
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.DepArrTime = dep_arr_time

        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Params = Element('Params')
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Params.NumberOfResults = 20
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Params.StopEventType = 'departure'
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Params.IncludeRealtimeData = True
