import datetime
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
from lxml.etree import fromstring
from lxml.etree import tostring

from .isotime import timestamp
from .request import StopEventRequest
from .request import LocationInformationRequest
from .response import StopEventResponse
from .response import LocationInformationResponse

class StopMonitorServer:

    def __init__(self, config_filename: str):
    
        # load config and set default values
        with open(config_filename, 'r') as config_file:
            self._config = yaml.safe_load(config_file)

        self._config = self._default_config(self._config)
        
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
        self._api_router.add_api_route('/json/{datatype}/{ordertype}/{stopref}/{numresults}.json', endpoint=self._json_departurefinder, methods=['GET'])

        self._template_engine = Jinja2Templates(directory='templates')
        self._landing_engine = Jinja2Templates(directory='landing')

        # enable chaching if configured
        if 'caching_enabled' in self._config['app'] and self._config['app']['caching_enabled'] == True:
            import memcache

            self._cache = memcache.Client([self._config['caching']['caching_server_endpoint']], debug=0)
            self._cache_ttl = self._config['caching']['caching_server_ttl_seconds']
        else:
            self._cache = None

        # enable data logging if configured
        if 'datalog_enabled' in self._config['app'] and self._config['app']['datalog_enabled'] == True: 
            if not os.path.exists('./datalog'):
                os.makedirs('./datalog')

            self._datalog = './datalog'
        else:
            self._datalog = None

        self._logger = logging.getLogger('uvicorn')

    async def _index(self, request: Request) -> Response:
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
    
    async def _admin(self, request: Request) -> Response:
        return 'admin enabled'

    async def _view(self, template: str, request: Request) -> Response:
        template = f"{template}/{template}.html"

        ctx = dict()

        # set app general variables
        ctx['view'] = dict()
        ctx['view']['title'] = request.query_params['t'] if 't' in request.query_params else 'Abfahrten'
        ctx['view']['stop_ref'] = request.query_params['s'] if 's' in request.query_params else 'de:08231:11'
        ctx['view']['num_results'] = request.query_params['n'] if 'n' in request.query_params and request.query_params['n'].isdigit() else 10
        ctx['view']['update_frequency'] = request.query_params['u'] if 'u' in request.query_params and request.query_params['u'].isdigit() else 30

        # append template specific variables
        ctx['template'] = dict()
        for qp_name, qp_value in request.query_params.items():
            if qp_name.startswith('tx'):
                key = qp_name.replace('tx', '')
                ctx['template'][key] = qp_value

        return self._template_engine.TemplateResponse(request=request, name=template, context=ctx)

    async def _json_departurefinder(self, datatype: str, stopref: str, ordertype: str, numresults: int, req: Request) -> Response:
        
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
                response = await self._send_stop_event_request(request, ordertype)

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
        
    async def _json_stopfinder(self, req: Request) -> Response:

        if 'q' not in req.query_params or req.query_params['q'].strip() == '':
            return Response(status_code=400)

        try:
            request = LocationInformationRequest(self._requestor_ref, req.query_params['q'].strip())
            response = await self._send_location_information_request(request)

            result = dict()
            result['stops'] = response.stops

            json_result = json.dumps(result)

            self._logger.info(f'Returning JSON response from remote server for {req.url.path}')
            return Response(content=json_result, media_type='application/json')
        except Exception as ex:
            self._logger.error(str(ex))
            return Response(content=str(ex), status_code=500)

    async def _send_stop_event_request(self, trias_request: StopEventRequest, order_type: str) -> StopEventResponse:

        await self._create_datalog('StopEventRequest', trias_request.xml())
        response = requests.post(self._request_url, headers={'Content-Type': 'application/xml', 'User-Agent': 'TripMonitorServer/1'}, data=trias_request.xml())
        
        await self._create_datalog('StopEventResponse', response.content)
        return StopEventResponse(response.content, order_type)
    
    async def _send_location_information_request(self, trias_request: LocationInformationRequest) -> LocationInformationResponse:
        
        await self._create_datalog('LocationInformationRequest', trias_request.xml())
        response = requests.post(self._request_url, headers={'Content-Type': 'application/xml', 'User-Agent': 'TripMonitorServer/1'}, data=trias_request.xml())

        await self._create_datalog('LocationInformationResponse', response.content)
        return LocationInformationResponse(response.content)
    
    async def _create_datalog(self, datatype: str, xml: str) -> None:
        if self._datalog is not None:

            # look for old datalog files and remove them
            # for speed up, check for the filename not beginning with today instead of ressource consuming difference calculation
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            for datalog_file in os.listdir(self._datalog):

                # proceed only if the datalogfile is not from today
                if not datalog_file.startswith(today):
                    datalog_timestamp = datalog_file.split('_')[0]
                    datalog_timestamp = datetime.datetime.strptime(datalog_timestamp, '%Y-%m-%d-%H.%M.%S-%f')

                    difference = (datetime.datetime.now() - datalog_timestamp).total_seconds()
                    if difference > 60 * 60 * 24:
                        datalog_file = os.path.join(self._datalog, datalog_file)
                        os.remove(datalog_file)

            # generate new datalog file
            datalog_timestamp = datetime.datetime.now().strftime('%Y-%m-%d-%H.%M.%S-%f')
            datalog_filename = f"{datalog_timestamp}_{datatype}.xml"

            with open(os.path.join(self._datalog, datalog_filename), 'wb') as datalog_file:
                try:
                    xml = tostring(fromstring(xml), pretty_print=True)
                except Exception as ex:
                    self._logger.error(str(ex))
                finally:
                    datalog_file.write(xml)
                    datalog_file.close()

    def _default_config(self, config):
        default_config = {
            'app': {
                'adapter': {
                    'type': 'vdv431',
                    'endpoint': '[YourRemoteServerEndpoint]',
                    'api_key': '[YourRemoteServerApiKey]'
                },
                'landing_enabled': True,
                'admin_enabled': False,
                'caching_enabled': False,
                'datalog_enabled': False
            },
            'landing': {
                'title': 'DemoStopMonitorInstance',
                'logo': '/static/default/logo.svg',
                'color': '#21a635',
                'default_template': 'default',
                'title_enabled': True,
                'num_results_enabled': False,
                'template_enabled': False
            },
            'admin': {
                'something': 'ComesHereSoon'
            },
            'caching': {
                'caching_server_endpoint': '[YourCachingServerEndpoint]',
                'caching_server_ttl_seconds': 30
            }
        }

        return self._merge_config(default_config, config)

    def _merge_config(self, defaults, actual):
        if isinstance(defaults, dict) and isinstance(actual, dict):
            return {k: self._merge_config(defaults.get(k, {}), actual.get(k, {})) for k in set(defaults) | set(actual)}
        return actual if actual else defaults

    def create(self) -> FastAPI:
        self._fastapi.include_router(self._api_router)

        return self._fastapi