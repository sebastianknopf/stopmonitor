import json
import requests

from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import Request
from fastapi import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .isotime import timestamp
from .request import StopEventRequest
from .response import StopEventResponse

class TripMonitorServer:

    def __init__(self, request_url: str, requestor_ref: str):
        self._request_url = request_url
        self._requestor_ref = requestor_ref

        self._fastapi = FastAPI()
        self._fastapi.mount('/app/static', StaticFiles(directory='static'), name='static')
        self._fastapi.mount('/templates', StaticFiles(directory='templates'), name='templates')

        self._api_router = APIRouter()
        
        self._api_router.add_api_route('/', endpoint=self._index, methods=['GET'])

        self._api_router.add_api_route('/view/{template}', endpoint=self._view, methods=['GET'])
        
        self._api_router.add_api_route('/json', endpoint=self._json, methods=['GET'])

        self._templates = Jinja2Templates(directory='templates')

    def _index(self, request: Request) -> Response:
        pass

    def _view(self, template: str, request: Request) -> Response:
        template = f"{template}/{template}.html"

        ctx = dict()
        ctx['app_title'] = request.query_params['t'] if 't' in request.query_params else 'Abfahrten'
        ctx['app_stop_ref'] = request.query_params['s'] if 's' in request.query_params else 'de:08231:11'
        ctx['app_num_results'] = request.query_params['n'] if 'n' in request.query_params and request.query_params['n'].isdigit() else 10
        ctx['app_update_frequency'] = request.query_params['u'] if 'u' in request.query_params and request.query_params['u'].isdigit() else 30

        return self._templates.TemplateResponse(request=request, name=template, context=ctx)

    def _json(self, request: Request) -> Response:
        
        if not 's' in request.query_params:
            return Response(status_code=400)
        
        if 'd' in request.query_params:
            data_type = request.query_params['d']
        else:
            data_type = 'departures'

        if 'o' in request.query_params:
            order_type = request.query_params['o']
        else:
            order_type = 'estimated_time'

        if 'n' in request.query_params and not request.query_params['n'].isdigit():
            return Response(status_code=400)
        
        try:
            
            if data_type == 'departures':
                stop_point_ref = request.query_params['s'] if 's' in request.query_params else ''
                num_results = int(request.query_params['n']) if 'n' in request.query_params else 1
                
                request = StopEventRequest(self._requestor_ref, stop_point_ref, timestamp(), num_results)
                response = self._send_stop_event_request(request, order_type)

                result = dict()
                result['departures'] = response.departures

            elif data_type == 'situations':
                result = dict()
                result['situations'] = list()

            return Response(content=json.dumps(result), media_type='application/json')
        except Exception as ex:
            return Response(content=str(ex), status_code=500)

    def _send_stop_event_request(self, trias_request: StopEventRequest, order_type: str):
        response = requests.post(self._request_url, headers={'Content-Type': 'application/xml'}, data=trias_request.xml())
        return StopEventResponse(response.content, order_type)

    def create(self) -> FastAPI:
        self._fastapi.include_router(self._api_router)

        return self._fastapi