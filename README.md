# StopMonitor
A simple departure monitor based on public available interfaces.

## Basic Idea
There're many public transport departure interfaces out there. E.g. the well-known TRIAS (VDV431) interface, the EFA-JSON API and OpenTripPlanner. The intent of this project is to provide a simple, light-weight application for running
digital departure monitors placed at bus stops. To keep the entire application as light-weight as possible, the UI is based on minimal CSS and JavaScript frameworks by using [w3.css](https://www.w3schools.com/w3css/w3css_downloads.asp), [underscore.js](https://github.com/jashkenas/underscore) and [moment.js](https://github.com/moment/moment). Other huge frameworks like Angular, React ... *are not used intentionally*.

The application starts a server delivering a landing page where users can select a station and several other parameters. By clicking 'Open', a departure monitor for the particular bus stop is opened in a new tab. The URL can be used to feed a digital sinage solution or any other public display out there. Behind the scenes, a server instance acts as a proxy between the client and the real endpoint. This enables you to use secret credentials and a caching mechanism under the hood. Finally, the architecture is constructed to use different connectors, first of all TRIAS.

_Note: Common displays at bus stops use another protocol (VDV453-DFI) typically which uses a publish/subscribe mechanism similar to MQTT. Due to the complexity of this protocol, it is not implemented here. Several tests have shown, that a departure monitor works fine even without using this protocol._

The application was initially developed for Verkehrsverbund Pforzheim-Enzkreis GmbH and is further developed. Ideas, issues and other contributions are highly welcome.

## Installation
There're different options to use the stop monitor. You can use it by cloning this repository and install it into your virtual environment directly:
```
git clone https://github.com/sebastianknopf/stopmonitor.git
cd stopmonitor

pip install .
```
and run it by using
```
python -m stopmonitor run ./config/your-config.yaml -h 127.0.0.1 -p 8080
```
This is especially good for development. 

If you simply want to run a stopmonitor on your server (e.g. behind a reverse-proxy), you also can use docker:
```
docker run --rm -v ./host/config.yaml:/app/config/config.yaml -p 8080:8080 sebastianknopf/stopmonitor:latest
```
Please note, that you're required to mount a configuration file with your specific configuration into the docker container to make the application running. 

Additionally, you can specify a certain hostname for the underlaying uvicorn server to listen to by using ENV variables with option `-e` (e.g. `-e PORT=80`, `-e HOST=127.0.0.1`).

### Running behind a Reverse Proxy
In production environments, you might want to run the stopmonitor behind a reverse proxy. Please note, that the uvicorn server running as ASGI requires the header `X-Forwared-Proto` set to `https`, if you want to the stopmonitor in a HTTPS environment. Otherwise, the URLs in the templates won't be rendered correctly. Please also note the proxy redirection for the websocket route. See the following apache2 configuration for reference:

```
ProxyPreserveHost On

# set request header to force https in template URLs
RequestHeader set X-Forwarded-Proto "https"

# reverse proxy route for landing page and layouts
ProxyPass / http://127.0.0.1:8080/

# reverse proxy route for websocket connections
RewriteEngine on
RewriteCond %{HTTP:Upgrade} websocket [NC]
RewriteCond %{HTTP:Connection} upgrade [NC]
RewriteRule ^/?(.*) "ws://127.0.0.1:8080/$1" [P,L]
```

### Configuration
The configuration YAML file enables you to customize the stopmonitor instance for your needs. See [config/default.yaml](./config/default.yaml) for further assistance.

You can configure different adapters for departure (and stop lookup) as well as situations. If you want to disable displaying situations, set the property `app.adapters.situations` to `null` explicitly.

## Templating
The application is designed to be as flexible as possible by using templates. There're two types of templates: The *layout templates* describe the layout of the departure monitor (including heading, footer, images, colors, ...). Layout templates are rendered using Jinja2 as template engine. The *departure templates* describe one row for one departure item (with different handling of route colors, displaying realtime information, cancellations, ...). Departure templates are rendered using underscore.js as template engine.

Each custom template needs to be placed in [./templates/](./templates/) folder and must contain at least one html file with the same name as the directory. Other resources (CSS, JS, ...) can be packaged with each template.

### Layout Template Variables & Files
Each layout template can use `url_for` (see Jinja2 docs for more information) to load static files. Additionally, following template variables are available in each layout template:
- `view.title`: The title for the departure monitor, taken from query parameter `t`
- `view.stop_ref`: The stop ID of a particular stop to be displayed, taken from query parameter `s`
- `view.num_results`: The number of results to be displayed, taken from query parameter `n`, default is 10 items
- `view.update_frequency`: The update frequency seconds, taken from query parameter `u`, default is 30s

If your template requires custom variables, you can pass them as query parameters by prepending `tx` before your varibale name. The `tx` is replaced by the server instance and the variable is added as `template.[variable]` into your layout template. You can see some examples that way:

- Try to add the parameter txplatform=0 - This makes the `default` and `vpe` layouts suppressing the 'Steig' column
- Try to add the parameter txdark=1 - This makes the `default` and `vpe` layouts appear in dark mode

_However, please note that working with these template variables always depends on the template you use._

### Departure Template Variables
Departure templates are a kind of sub-templates within a layout template. See [default.html](./templates/default/default.html) for reference. Each departure template has a set of variables to work with. 

These variables are:
- `planned_date`: The planned departure date
- `planned_time`: The planned departure time
- `estimated_date`: The estimated (realtime) departure date
- `estimated_time`: The estimated (realtime) departure time
- `planned_bay`: The planned bay of departure
- `realtime`: Whether the departure has realtime data available
- `cancelled`: Whether the departure is marked as cancelled
- `mode`: The transport mode of the departure
- `sub_mode`: The detailled sub-mode of the departure
- `published_mode`: The published mode name of the departure to be displayed in customer apps
- `line_name`: The line name of the departure
- `line_description`: The supplementary line description of the departure
- `origin_text`: The origin stop name of the trip
- `destination_text`: The destination stop name of the trip
- `is_last_element`: Indicates whether this is the last element of the departures collection

You can use these variables inside your departure template in order to display one departure item.

### Departure Template Variables
Situation templates are a kind of sub-templates within a layout template. See [default.html](./templates/default/default.html) for reference. Each situation template has a set of variables to work with.

These variables are:
- `text`: The situation detail text
- `is_last_element`: Indicates whether this is the last element of the situations collection

You can use these variables inside your situation template in order to display one situation item.

## License
This project is licensed under the Apache License. See [LICENSE.md](LICENSE.md) for more information.