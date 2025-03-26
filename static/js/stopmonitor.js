class StopMonitor {
    constructor(stopRef, numResults, orderType = 'estimated_time') {
        this.stopRef = stopRef;
        this.numResults = numResults;
        this.orderType = orderType;
		
		this.pageHidden = false;
		
		let t = this;
		window.addEventListener('focus', function() {
			t.pageHidden = false;
		}, false);
		
		window.addEventListener('blur', function() {
			t.pageHidden = true;
		}, false);
    }

	requestDepartureUpdates(departureTemplate, callback) {
		// create template
        this.departureTemplate = _.template(departureTemplate);
		
		// establish WebSocket connection to server
		try {
			this._connectDeparturesWebSocket(callback)			
		} catch (error) {
			callback(null, 0);
		}
	} 

	requestSituationUpdates(situationTemplate, callback) {
		this.situationTemplate = _.template(situationTemplate);

		// establish WebSocket connection to server
		try {
			this._connectSituationsWebSocket(callback)			
		} catch (error) {
			callback(null, 0);
		}
	}
	
	_connectDeparturesWebSocket(callback) {
		// obtain WebSocket connection parameters
		let protocol = 'ws:';
		let host = window.location.host
		if (window.location.protocol == 'https:') {
			protocol = 'wss:'
		}

		let t = this;

		// create WebSocket instance
		let socket = new WebSocket(`${protocol}//${host}/ws/departures/${this.orderType}/${this.numResults}/${this.stopRef}`);
		socket.onmessage = function (event) {
			let message = JSON.parse(event.data)

			let departuresHtml = null;
			if ('departures' in message) {
				departuresHtml = '';

				_.forEach(message.departures, function (departure, index) {
					departuresHtml += t.departureTemplate({
						planned_date: departure.planned_date,
						planned_time: departure.planned_time,
						estimated_date: departure.estimated_date,
						estimated_time: departure.estimated_time,
						realtime: departure.realtime,
						cancelled: departure.cancelled,
						planned_bay: departure.planned_bay,
						mode: departure.mode,
						sub_mode: departure.sub_mode,
						published_mode: departure.published_mode,
						line_name: departure.line_name,
						line_description: departure.line_description,
						origin_text: departure.origin_text,
						destination_text: departure.destination_text,
						is_last_element: index == message.departures.length - 1
					});
				});
			}

			callback(departuresHtml, message.departures.length);
		}

		socket.onclose = function(event) {
			callback(null, 0);
			setTimeout(function () {
				t._connectDeparturesWebSocket(callback)
			}, 30000);
		}

		window.onbeforeunload = function () {
			socket.close();
		}
	}

	_connectSituationsWebSocket(callback) {
		// obtain WebSocket connection parameters
		let protocol = 'ws:';
		let host = window.location.host
		if (window.location.protocol == 'https:') {
			protocol = 'wss:'
		}

		let t = this;

		// create WebSocket instance
		let socket = new WebSocket(`${protocol}//${host}/ws/situations/priority/${this.stopRef}`);
		socket.onmessage = function (event) {
			let message = JSON.parse(event.data)

			let situationsHtml = null;
			if ('situations' in message) {
				situationsHtml = '';

				_.forEach(message.situations, function (situation, index) {
					situationsHtml += t.situationTemplate({
						text: situation.text,
						is_last_element: index == message.situations.length - 1
					});
				});
			}

			callback(situationsHtml, message.situations.length);
		}

		socket.onclose = function(event) {
			callback(null, 0);
			setTimeout(function () {
				t._connectSituationsWebSocket(callback)
			}, 30000);
		}

		window.onbeforeunload = function () {
			socket.close();
		}
	}
}