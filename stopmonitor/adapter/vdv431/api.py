import datetime
import os
import requests

from .isotime import timestamp
from .request import StopEventRequest
from .request import LocationInformationRequest
from .response import StopEventResponse
from .response import LocationInformationResponse

from stopmonitor.adapter.base import AdapterInterface

from lxml.etree import fromstring
from lxml.etree import tostring

class Vdv431Adapter(AdapterInterface):

    def __init__(self, request_url, requestor_ref, datalog_directory = None):
        self._request_url = request_url
        self._requestor_ref = requestor_ref
        self._datalog_directory = datalog_directory

    async def find_stops(self, lookup_name: str) -> dict:
        request = LocationInformationRequest(self._requestor_ref, lookup_name)
        response = await self._send_location_information_request(request)

        return {
            'stops': response.stops
        }
    
    async def find_departures(self, stop_id: str, num_results: int, order_type:str = 'estimated_time', offset_seconds:int = 0) -> dict:
        request = StopEventRequest(self._requestor_ref, stop_id, timestamp(offset_seconds), num_results)
        response = await self._send_stop_event_request(request, order_type)

        return {
            'departures': response.departures
        }
    
    async def find_situations(self, stop_id:str, order_type:str = 'priority', offset_seconds:int = 0) -> dict:
        request = StopEventRequest(self._requestor_ref, stop_id, timestamp(offset_seconds), 100)
        response = await self._send_stop_event_request(request, order_type)

        situations = list()
        for situation in response.situations:
            situation_match = True
            for affect in situation['affects']:
                if affect['type'] == 'stop' and affect['id'] != stop_id:
                    situation_match = False
                    break

            if situation_match:
                situations.append(situation)

        return {
            'situations': situations
        }

    async def _send_stop_event_request(self, trias_request: StopEventRequest, order_type: str) -> StopEventResponse:

        await self._create_datalog('StopEventRequest', trias_request.xml())
        response = requests.post(self._request_url, headers={'Content-Type': 'application/xml', 'User-Agent': 'StopMonitorServer/1'}, data=trias_request.xml())
        
        await self._create_datalog('StopEventResponse', response.content)
        return StopEventResponse(response.content, order_type)
    
    async def _send_location_information_request(self, trias_request: LocationInformationRequest) -> LocationInformationResponse:
        
        await self._create_datalog('LocationInformationRequest', trias_request.xml())
        response = requests.post(self._request_url, headers={'Content-Type': 'application/xml', 'User-Agent': 'StopMonitorServer/1'}, data=trias_request.xml())

        await self._create_datalog('LocationInformationResponse', response.content)
        return LocationInformationResponse(response.content)
    
    async def _create_datalog(self, datatype: str, xml: str) -> None:
        if self._datalog_directory is not None:

            # look for old datalog files and remove them
            # for speed up, check for the filename not beginning with today instead of ressource consuming difference calculation
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            for datalog_file in os.listdir(self._datalog_directory):

                # proceed only if the datalogfile is not from today
                if not datalog_file.startswith(today):
                    datalog_timestamp = datalog_file.split('_')[0]
                    datalog_timestamp = datetime.datetime.strptime(datalog_timestamp, '%Y-%m-%d-%H.%M.%S-%f')

                    difference = (datetime.datetime.now() - datalog_timestamp).total_seconds()
                    if difference > 60 * 60 * 24:
                        datalog_file = os.path.join(self._datalog_directory, datalog_file)
                        os.remove(datalog_file)

            # generate new datalog file
            datalog_timestamp = datetime.datetime.now().strftime('%Y-%m-%d-%H.%M.%S-%f')
            datalog_filename = f"{datalog_timestamp}_Vdv431Adapter-{datatype}.xml"

            with open(os.path.join(self._datalog_directory, datalog_filename), 'wb') as datalog_file:
                try:
                    xml = tostring(fromstring(xml), pretty_print=True)
                except Exception:
                    pass
                finally:
                    datalog_file.write(xml)
                    datalog_file.close()