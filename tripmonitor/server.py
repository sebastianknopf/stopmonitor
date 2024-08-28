import json
import logging
import os
import requests
import yaml

from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import Request
from fastapi import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .isotime import timestamp
from .request import StopEventRequest
from .request import LocationInformationRequest
from .response import StopEventResponse
from .response import LocationInformationResponse

class TripMonitorServer:

    def __init__(self, config_filename: str):
        
        with open(config_filename, 'r') as config_file:
            self._config = yaml.safe_load(config_file) 
        
        self._request_url = self._config['app']['remote_server_endpoint']
        self._requestor_ref = self._config['app']['remote_server_requestor_ref']

        self._fastapi = FastAPI()
        self._fastapi.mount('/app/static', StaticFiles(directory='static'), name='static')
        self._fastapi.mount('/landing/static', StaticFiles(directory='landing'), name='landing')
        self._fastapi.mount('/templates', StaticFiles(directory='templates'), name='templates')

        self._api_router = APIRouter()
        
        # enable landing page if configured
        if self._config['app']['landing_enabled'] == True:
            self._api_router.add_api_route('/', endpoint=self._index, methods=['GET'])

        # enable admin page if configured
        if self._config['app']['admin_enabled'] == True:
            self._api_router.add_api_route('/admin', endpoint=self._admin, methods=['GET'])

        # enable required routes
        self._api_router.add_api_route('/view', endpoint=self._view, methods=['GET'], name='view-baseurl')
        self._api_router.add_api_route('/view/{template}', endpoint=self._view, methods=['GET'], name='view')
        
        self._api_router.add_api_route('/json/stops.json', endpoint=self._json_stopfinder, methods=['GET'])
        self._api_router.add_api_route('/json/{datatype}/{ordertype}/{stopref}/{numresults}.json', endpoint=self._json_datafinder, methods=['GET'])

        self._template_engine = Jinja2Templates(directory='templates')
        self._landing_engine = Jinja2Templates(directory='landing')

        # enable chaching if configured
        if self._config['app']['caching_enabled'] == True:
            import memcache

            self._cache = memcache.Client([self._config['caching']['caching_server_endpoint']], debug=0)
            self._cache_ttl = self._config['caching']['caching_server_ttl_seconds']
        else:
            self._cache = None

        self._logger = logging.getLogger('uvicorn')

    def _index(self, request: Request) -> Response:
        template = 'landing.html'

        ctx = dict()

        # set landing page parameters
        ctx['landing'] = dict()
        ctx['landing']['title'] = self._config['landing']['title']
        ctx['landing']['logo'] = self._config['landing']['logo']
        ctx['landing']['color'] = self._config['landing']['color']
        ctx['landing']['default_template'] = self._config['landing']['default_template']

        # set enabled / disabled flags for fields
        ctx['landing']['title_enabled'] = self._config['landing']['title_enabled']
        ctx['landing']['num_results_enabled'] = self._config['landing']['num_results_enabled']
        ctx['landing']['template_enabled'] = self._config['landing']['template_enabled']

        # add available templates
        ctx['landing']['templates'] = list()
        for directory in os.listdir('templates'):
            ctx['landing']['templates'].append(directory)                

        return self._landing_engine.TemplateResponse(request=request, name=template, context=ctx)
    
    def _admin(self, request: Request) -> Response:
        return 'admin enabled'

    def _view(self, template: str, request: Request) -> Response:
        template = f"{template}/{template}.html"

        ctx = dict()

        # set app general variables
        ctx['app'] = dict()
        ctx['app']['title'] = request.query_params['t'] if 't' in request.query_params else 'Abfahrten'
        ctx['app']['stop_ref'] = request.query_params['s'] if 's' in request.query_params else 'de:08231:11'
        ctx['app']['num_results'] = request.query_params['n'] if 'n' in request.query_params and request.query_params['n'].isdigit() else 10
        ctx['app']['mode_filter'] = request.query_params['m'] if 'm' in request.query_params and request.query_params['m'] else None
        ctx['app']['update_frequency'] = request.query_params['u'] if 'u' in request.query_params and request.query_params['u'].isdigit() else 30

        # append template specific variables
        ctx['template'] = dict()
        for qp_name, qp_value in request.query_params.items():
            if qp_name.startswith('tx'):
                key = qp_name.replace('tx', '')
                ctx['template'][key] = qp_value

        return self._template_engine.TemplateResponse(request=request, name=template, context=ctx)

    def _json_datafinder(self, datatype: str, stopref: str, ordertype: str, numresults: int, req: Request) -> Response:
        
        if self._cache is not None:
            json_cached = self._cache.get(req.url.path)
            if json_cached is not None:
                self._logger.info(f'Returning JSON response from cache for {req.url.path}')
                return Response(content=json_cached, media_type='application/json')

        if not datatype == 'departures' and not datatype == 'situations':
            datatype = 'departures'
        
        if stopref.strip() == '':
            return Response(status_code=400)
        
        if not ordertype == 'planned_time' and not ordertype == 'estimated_time':
            ordertype = 'estimated_time'
        
        if numresults > 50:
            numresults = 50

        try:
            if datatype == 'departures':                
                request = StopEventRequest(self._requestor_ref, stopref, timestamp(), numresults)
                response = self._send_stop_event_request(request, ordertype)

                result = dict()
                result['departures'] = response.departures

            elif datatype == 'situations':
                result = dict()
                result['situations'] = list()

            json_result = json.dumps(result)
            if self._cache is not None:
                self._cache.set(req.url.path, json_result, self._cache_ttl)

            self._logger.info(f'Returning JSON response from remote server for {req.url.path}')
            return Response(content=json_result, media_type='application/json')
        except Exception as ex:
            self._logger.error(str(ex))
            return Response(content=str(ex), status_code=500)
        
    def _json_stopfinder(self, req: Request) -> Response:

        if 'q' not in req.query_params or req.query_params['q'].strip() == '':
            return Response(status_code=400)

        try:
            request = LocationInformationRequest(self._requestor_ref, req.query_params['q'].strip())
            response = self._send_location_information_request(request)

            result = dict()
            result['stops'] = response.stops

            json_result = json.dumps(result)

            self._logger.info(f'Returning JSON response from remote server for {req.url.path}')
            return Response(content=json_result, media_type='application/json')
        except Exception as ex:
            self._logger.error(str(ex))
            return Response(content=str(ex), status_code=500)

    def _send_stop_event_request(self, trias_request: StopEventRequest, order_type: str) -> StopEventResponse:
        response = requests.post(self._request_url, headers={'Content-Type': 'application/xml'}, data=trias_request.xml())
        return StopEventResponse(response.content, order_type)
    
    def _send_location_information_request(self, trias_request: LocationInformationRequest) -> LocationInformationResponse:
        response = requests.post(self._request_url, headers={'Content-Type': 'application/xml'}, data=trias_request.xml())
        return LocationInformationResponse(response.content)

    def create(self) -> FastAPI:
        self._fastapi.include_router(self._api_router)

        return self._fastapi