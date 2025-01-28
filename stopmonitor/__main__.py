import click
import uvicorn

from .server import StopMonitorServer

@click.group()
def cli():
    pass

@cli.command()
@click.argument('config')
@click.option('--host', '-h', default='0.0.0.0', help='Hostname for the server to listen')
@click.option('--port', '-p', default='8080', help='Port for the server to listen')
def run(config, host, port):
    server = StopMonitorServer(config)
    uvicorn.run(app=server.create(), host=host, port=int(port))


if __name__ == '__main__':
    cli()