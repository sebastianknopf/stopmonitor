from tripmonitor.server import TripMonitorServer

server = TripMonitorServer('https://projekte.kvv-efa.de/knopftrias/trias', 'VqkFJnKxw8fH')

app = server.create()