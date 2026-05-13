from datetime import datetime
from forexconnect.lib import fxcorepy
from logging import Logger, getLogger
from typing import Optional


class Client:

    endpoint = "https://www.fxcorporate.com/Hosts.jsp"

    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or getLogger()
        # Session and status
        self._session = None
        self._status = None
        self._connected = False
        # Status listener
        self._status_listener = fxcorepy.AO2GSessionStatus()
        self._status_listener.on_session_status_changed = self._on_status_changed
        self._status_listener.on_login_failed = self._on_login_failed
        self._status_flag = False
        self._login_error = None

    def _on_status_changed(self, status: fxcorepy.AO2GSessionStatus.O2GSessionStatus):
        self.logger.debug("Session status: %s", status)
        self._status = str(status)
        if status == fxcorepy.AO2GSessionStatus.O2GSessionStatus.CONNECTED:
            self._connected = True
            self._status_flag = True
        elif status == fxcorepy.AO2GSessionStatus.O2GSessionStatus.DISCONNECTED:
            self._connected = False
            self._status_flag = True

    def _on_login_failed(self, err: str):
        self._login_error = err

    @property
    def status(self) -> str:
        return self._status

    @property
    def connected(self) -> bool:
        return self._connected

    @staticmethod
    def set_proxy(host: Optional[str] = None, port: int = 80):
        fxcorepy.O2GTransport.set_proxy(host, port)

    def connect(self, user_id: str, password: str, connection: str = "demo"):
        self._status_flag = False
        self._session = fxcorepy.O2GTransport.create_session()
        self._session.subscribe_session_status(self._status_listener)
        self._session.login(user_id, password, self.endpoint, connection)
        while not self._status_flag:
            pass
        if not self._connected:
            raise ConnectionError(self._login_error)

    def close(self):
        if self._connected:
            self._status_flag = False
            self._session.logout()
            while not self._status_flag:
                pass
            self._session.unsubscribe_session_status(self._status_listener)
            self._session = None

    def price_history(self,
            instrument: str,
            timeframe: str,
            date_from: Optional[datetime] = None,
            date_to: Optional[datetime] = None,
            quotes_count: int = -1,
    ):
        comm = fxcorepy.PriceHistoryCommunicatorFactory.create_communicator(self._session, "./cache")
        timeframe = comm.timeframe_factory.create(timeframe)
        if not timeframe:
            raise ValueError("Invalid timeframe.")
        while not comm.is_ready:
            pass
        comm.candle_open_price_mode = fxcorepy.O2GCandleOpenPriceMode.FIRST_TICK
        reader = comm.get_history(instrument, timeframe, date_from, date_to, quotes_count)
        if timeframe.unit == fxcorepy.O2GTimeFrameUnit.TICK:
            fields = ("date", "bid", "ask")
        else:
            fields = ("date", "bid_open", "bid_high", "bid_low", "bid_close",
                      "ask_open", "ask_high", "ask_low", "ask_close", "volume")
        return [{field: getattr(row, field) for field in fields} for row in reader]
