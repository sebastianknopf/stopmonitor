from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import Request
from fastapi import Response

from .isotime import timestamp
from .request import StopEventRequest

class TripMonitorServer:

    def __init__(self):
        self._fastapi = FastAPI()
        self._api_router = APIRouter()

        self._api_router.add_api_route('/', endpoint=self._index, methods=['GET'])
        self._api_router.add_api_route('/departures', endpoint=self._departures, methods=['GET'])

    def _index(self, request: Request) -> Response:
        pass

    def _departures(self, request: Request) -> Response:
        
        stop_point_ref = request.query_params['s']
        
        request = StopEventRequest('VqkFJnKxw8fH', stop_point_ref, timestamp())

        return Response(content=request.xml(), media_type='application/xml')

    def create(self) -> FastAPI:
        self._fastapi.include_router(self._api_router)

        return self._fastapi