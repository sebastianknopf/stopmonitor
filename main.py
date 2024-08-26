from tripmonitor.server import TripMonitorServer

server = TripMonitorServer('./config/demo.yaml')
app = server.create()