import asyncio
import json
import threading

from tornado import httputil, httpclient, websocket, gen, ioloop, escape

APPLICATION_JSON = 'application/json'
DEFAULT_CONNECT_TIMEOUT = 60
DEFAULT_REQUEST_TIMEOUT = 60


class websocket_client_base:
    """Base for web socket client.
    """
    def __init__(self, url, sid=None, connect_timeout=DEFAULT_CONNECT_TIMEOUT,
                 request_timeout=DEFAULT_REQUEST_TIMEOUT):
        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        self.loop = None
        self.thread = None
        self.url = url
        self.sid = sid
        self.recon_count = 0  # count of reconnection attempts

    def _connect(self):
        """Connect to the server using tornado's httpclient.
        :param url: server URL.
        :type url: str.
        """
        headers = httputil.HTTPHeaders({'Content-Type': APPLICATION_JSON})
        request = httpclient.HTTPRequest(url=self.url,
                                         connect_timeout=self.connect_timeout,
                                         request_timeout=self.request_timeout,
                                         headers=headers)

        ws_conn = websocket.websocket_connect(request.url)
        ws_conn.add_done_callback(self._connect_callback)

    def _send(self, data):
        """Send a message to the server.
        :param data: message.
        :type data: str.
        """
        if not self._ws_connection:
            raise RuntimeError('Web socket connection is closed.')

        self._ws_connection.write_message(escape.utf8(json.dumps(data)))

    def _close(self):
        """Close connection tot he server.
        Sends a stop message to the server.
        """
        if not self._ws_connection:
            raise RuntimeError('Web socket connection is already closed.')

        self._ws_connection.close()
        self._on_connection_close()

    def _connect_callback(self, future):
        """Callback once the connection is established.
        :param future: future of the connection.
        :type future: Future.
        """
        if future.exception() is None:
            self._ws_connection = future.result()
            self._on_connection_success()
            self._read_messages()
        else:
            self._on_connection_error(future.exception())

    @gen.coroutine
    def _read_messages(self):
        """Reads messages from the server asynchronously."""
        while True:
            msg = yield self._ws_connection.read_message()
            if msg is None:
                self._on_connection_close()
                break

            self._on_message(msg)

    def _on_message(self, msg):
        """This is called when new message is available from the server.
        :param str msg: server message.
        """
        raise NotImplementedError('Override _on_message in subclass.')

    def _on_connection_success(self):
        """This is called on successful connection ot the server.
        """
        raise NotImplementedError('Override _on_connection_success in subclass.')

    def _on_connection_close(self):
        """This is called when server closed the connection.
        """
        raise NotImplementedError('Override _on_connection_close in subclass.')

    def _on_connection_error(self, exception):
        """This is called in case if connection to the server could
        not established.
        :param exception: exception that occurred
        """
        raise NotImplementedError('Override _on_connection_error in subclass.')

    def stop(self):
        """Stops the connection and stops the io loop."""
        self._send('{\'feed_action\':\'stop\'}')
        # self.loop.instance().add_callback(self._close)
        self._close()

    def start(self):
        if self.loop:
            return

        self.loop = ioloop.IOLoop()

        print('starting client')

        self.thread = threading.Thread(target=self._client_loop)
        self.thread.daemon = True
        self.thread.start()

    def _client_loop(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self._connect()
        self.loop.instance().start()
