from tripmonitor.server import TripMonitorServer

server = TripMonitorServer('https://projekte.kvv-efa.de/knopftrias/trias', 'VqkFJnKxw8fH')
server.cache('127.0.0.1', 11211, 30)

app = server.create()