#########################
# Author: Lukas Gust    #
# Company: SynopticLabs #
# Date: 2018-06-28      #
#########################
# TODO README
# TODO add api path for past latencies
# TODO finish Index page
# TODO restore session i.e. metadata and data

import asyncio
import functools
import json
import threading
import time
import calendar

import numpy as np
import pandas as pd
from pandas.io.json import json_normalize
from tornado import gen
from tornado import ioloop
from tornado import web
from tornado.options import options, define

from websocket_client_base import websocket_client_base


class LatencyStatServer:
    """
    The LatencyStatServer is responsible for processing HTTP GET requests. It reports various combinations of data from
    the SynopticPushClient. It runs on a separate dameon thread. Contains various handlers for different GET requests.
    """

    class IndexHandler(web.RequestHandler):
        """
        Handles the index page. Renders a simple html file explaining what to do in order to use the service. Inherits
        tornado.web.RequestHandler.
        """
        @gen.coroutine
        def get(self):
            print('index handler')
            self.render('index.html')

    class MonitorLandingHandler(web.RequestHandler):
        """
        Handles the landing of the monitor service root. Writes all relevant statistics from SynopticPushClient as JSON.
        """
        @gen.coroutine
        def get(self, arg):
            """
            Writes StreamStats to the connection.
            """
            self.write(SynopticPushClient.stats.get_message_dict())

    class MetadataLandingHandler(web.RequestHandler):
        """
        Handles the landing of the metadata service root. Writes all relevant metadata from SynopticPushClient as JSON.
        """
        @gen.coroutine
        def get(self, arg):
            """
            Writes Metadata to the connection.
            """
            self.write(SynopticPushClient.meta.get_message_dict())

    class CountsLandingHandler(web.RequestHandler):
        """
        Handles the landing of the count data. Writes all relevant count data from SynopticPushClient as JSON.
        """
        @gen.coroutine
        def get(self, arg):
            message = None
            if not arg:
                temp = dict()
                temp['network_ob_count'] = SynopticPushClient.stats.network_ob_count
                temp['station_ob_count'] = SynopticPushClient.stats.station_ob_count
                message = temp
            elif arg == 'network':
                network = self.get_argument('network', default=None)
                print(network.split(','))
                if not network:
                    message = {'network_ob_count': SynopticPushClient.stats.network_ob_count}
                else:
                    if network in SynopticPushClient.stats.network_ob_count:
                        message = {'network_ob_count': {network: SynopticPushClient.stats.network_ob_count[network]}}
                    else:
                        message = {'network_ob_count': dict()}
            elif arg == 'station':
                stid = self.get_argument('stid', default=None)
                if not stid:
                    message = {'station_ob_count': SynopticPushClient.stats.station_ob_count}
                else:
                    print(stid.split(','))
                    if stid in SynopticPushClient.stats.station_ob_count:
                        message = {'station_ob_count': {stid: SynopticPushClient.stats.station_ob_count[str(stid).upper()]}}
                    else:
                        message = {'station_ob_count': dict()}
            else:
                raise web.HTTPError(404)
            if message:
                self.write(message)

    def __init__(self, url):
        """
        Initialize LatencyStatServer. Creates a SynopticPushClient.
        :param url: url for the SynopticPushClient to connect to.
        """
        self.app = web.Application([(r'/', self.IndexHandler),
                                    (r'/monitor/?(?P<arg>[A-z]*)?', self.MonitorLandingHandler),
                                    (r'/metadata/?(?P<arg>[A-z]*)?', self.MetadataLandingHandler),
                                    (r'/counts/?(?P<arg>[A-z]*)?', self.CountsLandingHandler)])
        self.loop = None
        self.thread = None
        try:
            with open('session.txt') as fp:
                self.sid = fp.readline()
                url += '/' + str(self.sid)
        except FileNotFoundError:
            self.sid = None
        if self.sid:
            self.client = SynopticPushClient(url, sid=self.sid)
        else:
            self.client = SynopticPushClient(url)
        self.birth_time = time.time()

    def _server_loop(self):
        """
        Begin server loop and begin communication with any clients.
        """
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.app.listen(options.port)
        self.loop.instance().start()
        print('Server started successfully on port {0}. thread: {1}'.format(options.port, threading.current_thread()))

    def start(self):
        """
        Starts the thread for the server to run on and initializes its tornado.ioloop.IOLoop. The thread is a dameon
        thread so it will not keep the application from exiting.
        """
        if self.loop:
            return

        self.loop = ioloop.IOLoop()

        print('Starting server on {0}'.format(options.port))

        self.thread = threading.Thread(target=self._server_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        """
        Stops the tornado.ioloop
        """
        self.client.stop()
        # self.loop.instance().stop()


class Metadata:
    """
    Wraps up metadata from SynopticData Push Service into dictionaries
    """

    def __init__(self, fp=None):
        self.stations = dict()
        self.network_stations = dict()
        self.station_count_per_net = dict()
        if fp:
            _dict = json.load(fp)
            assert (list(_dict.keys()) == ['stations', 'station_count_per_net', 'network_stations'])
            self.stations = _dict['stations']
            self.network_stations = {network: set(_list) for network, _list in _dict['network_stations'].items()}
            print(self.stations.keys())
            self.station_count_per_net = _dict['station_count_per_net']

    def __str__(self):
        """
        Produces string representation Metadata.
        :return: string representation of Metadata
        """
        return '{\"stations\": ' + json.dumps(self.stations) + \
               ', \"station_count_per_net\":' + json.dumps(self.station_count_per_net) + \
               ', \"network_stations\": ' + json.dumps({network: list(_set)
                                                        for network, _set in self.network_stations.items()}) + '}'

    def get_message_dict(self):
        """
        Produces dictionary object of Metadata
        :return: dictionary of __str__
        """
        return json.loads(str(self))


class StreamStats:
    """
    Wraps up latency stats data into dictionaries
    """

    def __init__(self, fp=None):
        self.total_avg_latency = 0
        self.station_latency = dict()
        self.max_latency = dict()
        self.max_station_latency = dict()
        self.max_network_latency = dict()
        self.network_ob_count = dict()
        self.station_ob_count = dict()
        if fp:
            _dict = json.load(fp)
            assert (list(_dict.keys()) == list(['station_latency', 'total_avg_latency', 'max_latency',
                                                'max_station_latency', 'max_network_latency', 'network_ob_count',
                                                'station_ob_count']))
            self.total_avg_latency = _dict['total_avg_latency']
            self.station_latency = _dict['station_latency']
            self.max_latency = _dict['max_latency']
            self.max_station_latency = _dict['max_station_latency']
            self.max_network_latency = _dict['max_network_latency']
            self.network_ob_count = _dict['network_ob_count']
            self.station_ob_count = _dict['station_ob_count']

            assert (len(self.station_latency) == len(self.max_station_latency))

    def __str__(self):
        """
        Produces string representation of StreamStats
        :return: string representation of StreamStats
        """
        return '{\"station_latency\": ' + json.dumps(self.station_latency) + \
               ', \"total_avg_latency\": ' + json.dumps(self.total_avg_latency) + \
               ', \"max_latency\": ' + json.dumps(self.max_latency) + \
               ', \"max_station_latency\": ' + json.dumps(self.max_station_latency) + \
               ', \"max_network_latency\": ' + json.dumps(self.max_network_latency) + \
               ', \"network_ob_count\": ' + json.dumps(self.network_ob_count) + \
               ', \"station_ob_count\": ' + json.dumps(self.station_ob_count) + '}'

    def get_message_dict(self):
        """
        Produces dictionary object of StreamStats
        :return:
        """
        return json.loads(str(self))


class SynopticPushClient(websocket_client_base):
    """
    Websocket client for the SynopticData Push Service. Collects various statistics about the observations being pushed.
    """
    meta = Metadata()
    stats = StreamStats()

    def _on_message(self, msg):
        """
        Checks the type of message from the push service and adds a callback to deal with the incoming data
        appropriately.
        :param msg: message coming from the websocket.
        :return: None
        """
        msg_dict = json.loads(msg)
        rtype = msg_dict['type']
        print('Received', rtype, 'message.')
        if not self.sid:
            if rtype == 'auth' and msg_dict['code'] == 'success':
                self.sid = msg_dict['session']
                print('Session ID:', self.sid)
                self.save_session_id()
        if rtype == 'metadata':
            ioloop.IOLoop.instance().add_callback(callback=functools.partial(self.add_metadata, msg_dict))
        if rtype == 'data':
            ioloop.IOLoop.instance().add_callback(callback=functools.partial(self.add_stats, msg_dict))

    @gen.coroutine
    def add_metadata(self, message_dict):
        """
        Adds meta data to the Metadata structure.
        :param message_dict: dictionary object loaded from the JSON sent to the websocket
        """
        for station in message_dict['stations']:
            stid = station['stid']
            network = str(station['network'])
            self.meta.stations[stid] = station
            if network in self.meta.network_stations:
                self.meta.network_stations[network].add(stid)
            else:
                self.meta.network_stations[network] = {stid}
        self.meta.station_count_per_net = {key: len(val) for key, val in self.meta.network_stations.items()}
        print(len(self.meta.stations), sum(self.meta.station_count_per_net.values()))
        assert (len(self.meta.stations) == sum(self.meta.station_count_per_net.values()))

        print('Processed metadata\n')

    @gen.coroutine
    def add_stats(self, message_dict):
        """
        Adds latency data to the StreamStats structure.
        :param message_dict: dictionary object loaded from the JSON sent to the websocket
        """
        df = pd.DataFrame()
        latency = np.zeros(len(message_dict['data']))

        _max = self.stats.max_latency['latency'] if len(self.stats.max_latency) != 0 else 0

        for i, ob in enumerate(message_dict['data']):
            # Initialization
            df = df.append(json_normalize(ob))
            laten = time.time() - calendar.timegm(time.strptime(ob['date'], '%Y-%m-%d %H:%M:%S'))
            latency[i] = laten
            stid = ob['stid']
            network = self.meta.stations[stid]['network']
            # ------------------------- #
            # Station observation count
            if stid in self.stats.station_ob_count:
                self.stats.station_ob_count[stid] += 1
            else:
                self.stats.station_ob_count[stid] = 1
            # ------------------------- #
            # Network observation count
            if network in self.stats.network_ob_count:
                self.stats.network_ob_count[network] += 1
            else:
                self.stats.network_ob_count[network] = 1
            # ------------------------- #
            # Max latency
            if laten > _max:
                _max = laten
                self.stats.max_latency = {'stid': stid, 'network': network, 'latency': _max}
            # ------------------------- #
            # Max station latency
            if stid in self.stats.max_station_latency:
                self.stats.max_station_latency[stid] = laten if laten > self.stats.max_station_latency[stid] \
                    else self.stats.max_station_latency[stid]
            else:
                self.stats.max_station_latency[stid] = laten
            # ------------------------- #
            # Max network latency
            if network in self.stats.max_network_latency:
                self.stats.max_network_latency[network] = laten if laten > self.stats.max_network_latency[network] \
                    else self.stats.max_network_latency[network]
            else:
                self.stats.max_network_latency[network] = laten
            # ------------------------- #

        df.drop(labels=['match', 'qc', 'sensor', 'set', 'value'], axis=1, inplace=True)
        df.set_index('stid', inplace=True)
        df['latency'] = latency
        stid_group = df.groupby('stid')
        avg_latency = stid_group['latency'].mean()

        # Average latencies
        self.stats.total_avg_latency = avg_latency.mean()
        for stid, lat in avg_latency.iteritems():
                self.stats.station_latency[stid] = {'network': self.meta.stations[stid]['network'], 'latency': lat}

        # print(len(self.stats.station_latency), len(self.stats.max_station_latency))
        assert(len(self.stats.station_latency) == len(self.stats.max_station_latency))

        print('Processed data.\n')

    def _on_connection_success(self):
        """Connection made successfully"""
        print('Connected!')
        self.recon_count = 0
        if self.sid:
            self.load_previous_session()
        # TODO cahnge to timeout for specific time
        ioloop.PeriodicCallback(self.dump_data, 900000).start()
        self._send(str(int(time.time())))

    # TODO
    def load_previous_session(self):

        today = str(time.strftime('%Y-%m-%d', time.gmtime(time.time())))
        print('Loading previous session for {0}.'.format(today))
        try:
            with open('dump/meta_dump' + today + '.json', 'r') as fp:
                self.meta = Metadata(fp=fp)
            with open('dump/stat_dump' + today + '.json', 'r') as fp:
                self.stats = StreamStats(fp=fp)
        except FileNotFoundError:
            self.meta = Metadata()
            self.stats = StreamStats()

    def dump_data(self):
        """
        Dump the current data to a json file for later observation through the Latency API service. Resets StreamStats
        """
        with open('dump/stat_dump' + str(time.strftime('%Y-%m-%d', time.gmtime(time.time()))) + '.json',
                  'w') as fp:
            json.dump(self.stats.get_message_dict(), fp)

        with open('dump/meta_dump' + str(time.strftime('%Y-%m-%d', time.gmtime(time.time()))) + '.json',
                  'w') as fp:
            json.dump(self.meta.get_message_dict(), fp)

        print('DUMP', str(time.strftime('%Y-%m-%d', time.gmtime(time.time()))))
        # TODO Reset timeout callback
        self.stats = StreamStats()

    def _on_connection_close(self):
        print('Connection closed!')
        self.loop.instance().add_callback(self.dump_data)
        return

    def _on_connection_error(self, exception):
        self.recon_count += 1
        print('Connection error: %s', exception)
        self.url += '/' + str(self.sid)
        ioloop.IOLoop.instance().add_timeout(time.time()+5, self.reconnect)

    def reconnect(self):
        if self.recon_count == 4:
            print('Attempting to reconnect...')
            self._connect()
        else:
            print('Tried to reconnect %s times', self.recon_count)

    def save_session_id(self):
        with open('session.txt', 'w') as fp:
            fp.write(self.sid)

## TODO Add a valid token below
URL = 'wss://push.synopticlabs.org/feed/<your token here>'

define("port", default=8888, help='Run on given port', type=int)


if __name__ == '__main__':
    options.parse_command_line()
    server = LatencyStatServer(URL)
    server.client.start()
    server.start()

    ev = threading.Event()
    ev.clear()
    try:
        while input() != 'quit':
            ev.wait(1)
    except KeyboardInterrupt:
        print("Keyboard interrupt.")
    finally:
        server.stop()
        server.thread.join(15)
