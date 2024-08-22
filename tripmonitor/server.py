import json
import requests

from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import Request
from fastapi import Response
from lxml.etree import fromstring
from lxml.etree import XMLParser

from .isotime import timestamp
from .request import TriasRequest
from .request import StopEventRequest
from .response import StopEventResponse

class TripMonitorServer:

    def __init__(self, request_url: str, requestor_ref: str):
        self._request_url = request_url
        self._requestor_ref = requestor_ref

        self._fastapi = FastAPI()
        self._api_router = APIRouter()

        self._api_router.add_api_route('/', endpoint=self._index, methods=['GET'])
        self._api_router.add_api_route('/departures', endpoint=self._departures, methods=['GET'])
        self._api_router.add_api_route('/render', endpoint=self._render, methods=['GET'])

    def _index(self, request: Request) -> Response:
        pass

    def _departures(self, request: Request) -> Response:
        
        stop_point_ref = request.query_params['s'] if 's' in request.query_params else ''
        
        request = StopEventRequest(self._requestor_ref, stop_point_ref, timestamp())
        response = self._send_stop_event_request(request)

        results = [dict(d.__dict__) for d in response.departures]

        return Response(content=json.dumps(results), media_type='application/json')
    
    def _render(self, reqest: Request) -> Response:
        pass

    def _send_stop_event_request(self, trias_request: StopEventRequest):
        response = requests.post(self._request_url, headers={'Content-Type': 'application/xml'}, data=trias_request.xml())
        return StopEventResponse(response.content)

    def create(self) -> FastAPI:
        self._fastapi.include_router(self._api_router)

        return self._fastapi