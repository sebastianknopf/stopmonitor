import asyncio
import json
import logging
import os
import yaml

from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import Request
from fastapi import Response
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

class StopMonitorServer:

    def __init__(self, config_filename: str):
    
        # load config and set default values
        with open(config_filename, 'r') as config_file:
            self._config = yaml.safe_load(config_file)

        self._config = self._default_config(self._config)

        # create adapter according to settings
        if self._config['app']['adapter']['type'] == 'vdv431':
            from .adapter.vdv431.api import Vdv431Adapter

            self._adapter = Vdv431Adapter(
                self._config['app']['adapter']['endpoint'],
                self._config['app']['adapter']['api_key'],
                './datalog' if self._config['app']['datalog_enabled'] else None
            )
        else:
            raise ValueError(f"unknown adapter type {self._config['app']['adapter']['type']}")

        # create API instance
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
        
        self._api_router.add_api_route('/json/stops.json', endpoint=self._json_stoprequest, methods=['GET'])

        self._api_router.add_api_websocket_route('/ws/{ordertype}/{numresults}/{stopref}', endpoint=self._websocket)

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

        # create logger instance
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
        
    async def _json_stoprequest(self, req: Request) -> Response:

        # handle value constraints
        if 'q' in req.query_params:
            lookup_name = req.query_params['q'].strip()
            if lookup_name == '':
                return Response(status_code=400)
        else:
            return Response(status_code=400)

        # run requests
        try:
            # load stops from adapter
            result = await self._adapter.find_stops(lookup_name)

            # create JSON result
            json_result = json.dumps(result)

            self._logger.info(f'Returning JSON response from remote server for {req.url.path}')
            return Response(content=json_result, media_type='application/json')
        except Exception as ex:
            self._logger.error(str(ex))
            return Response(content=str(ex), status_code=500)
        
    async def _websocket(self, ordertype: str, numresults: int, stopref: str, ws: WebSocket):
        # handle value constraints
        if not ordertype == 'planned_time' and not ordertype == 'estimated_time':
            ordertype = 'estimated_time'

        if numresults > 50:
            numresults = 50
        
        if stopref.strip() == '':
            return Response(status_code=400)

        # accept WebSocket connection
        await ws.accept()

        try:
            while True:
                # load departures from adapter
                result = await self._adapter.find_departures(
                    stopref.strip(),
                    numresults,
                    ordertype
                )

                # send results to monitor
                await ws.send_json(result)

                # wait for the next update interval
                await asyncio.sleep(30)
        except WebSocketDisconnect:
            pass

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
                'logo': '/img/demo-icon-white.svg',
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