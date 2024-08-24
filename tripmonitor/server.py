import json
import logging
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
        self._api_router.add_api_route('/json/{datatype}/{ordertype}/{stopref}/{numresults}.json', endpoint=self._json, methods=['GET'])

        self._templates = Jinja2Templates(directory='templates')

        self._cache = None

        self._logger = logging.getLogger('uvicorn')

    def _index(self, request: Request) -> Response:
        pass

    def _view(self, template: str, request: Request) -> Response:
        template = f"{template}/{template}.html"

        ctx = dict()
        ctx['app_title'] = request.query_params['t'] if 't' in request.query_params else 'Abfahrten'
        ctx['app_stop_ref'] = request.query_params['s'] if 's' in request.query_params else 'de:08231:11'
        ctx['app_num_results'] = request.query_params['n'] if 'n' in request.query_params and request.query_params['n'].isdigit() else 10
        ctx['app_mode_filter'] = request.query_params['m'] if 'm' in request.query_params and request.query_params['m'] else None
        ctx['app_update_frequency'] = request.query_params['u'] if 'u' in request.query_params and request.query_params['u'].isdigit() else 30

        return self._templates.TemplateResponse(request=request, name=template, context=ctx)

    def _json(self, datatype: str, stopref: str, ordertype: str, numresults: int, req: Request) -> Response:
        
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
            return Response(content=str(ex), status_code=500)

    def _send_stop_event_request(self, trias_request: StopEventRequest, order_type: str):
        response = requests.post(self._request_url, headers={'Content-Type': 'application/xml'}, data=trias_request.xml())
        return StopEventResponse(response.content, order_type)

    def create(self) -> FastAPI:
        self._fastapi.include_router(self._api_router)

        return self._fastapi
    
    def cache(self, host: str, port: int, ttl: int) -> None:
        import memcache

        self._cache = memcache.Client([f"{host}:{port}"], debug=0)
        self._cache_ttl = ttl