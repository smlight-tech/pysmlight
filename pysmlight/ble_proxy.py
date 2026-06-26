import asyncio
from collections.abc import Callable
from enum import IntEnum
import logging
import struct

_LOGGER = logging.getLogger(__name__)


class ProxyAction(IntEnum):
    PING = 0
    DISCONNECT = 1
    ACK = 2
    DATA = 3
    SET_SCAN_MODE = 4
    REQ_ACTIVE_WINDOW = 5


# Structure of the fixed portion of the BLE proxy ring packet:
# - api_version (uint8)
# - api_action (uint8)
# - address (6 bytes)
# - address_type (uint8)
# - rssi (int8)
# - adv_data_len (uint8)
BLE_PROXY_HEADER_STRUCT = struct.Struct("<BB6sBbB")


class BleProxyProtocol(asyncio.DatagramProtocol):
    """Protocol to handle incoming UDP packets from SLZB BLE Proxy server."""

    def __init__(
        self,
        callback: Callable[[str, int, int, bytes], None],
        on_ack: Callable[[], None],
    ) -> None:
        self.callback = callback
        self.on_ack = on_ack

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            offset = 0
            while offset < len(data):
                if len(data) - offset < 2:
                    break

                version = data[offset]
                if version > 0:
                    break

                action = data[offset + 1]
                if action == ProxyAction.ACK:
                    self.on_ack()
                    offset += 2
                    continue

                if action == ProxyAction.DATA:
                    if len(data) - offset < BLE_PROXY_HEADER_STRUCT.size:
                        break

                    (
                        _,
                        _,
                        mac_bytes,
                        address_type,
                        rssi,
                        adv_data_len,
                    ) = BLE_PROXY_HEADER_STRUCT.unpack_from(data, offset)

                    if len(data) - offset < BLE_PROXY_HEADER_STRUCT.size + adv_data_len:
                        break

                    raw_data = data[
                        offset + BLE_PROXY_HEADER_STRUCT.size : offset
                        + BLE_PROXY_HEADER_STRUCT.size
                        + adv_data_len
                    ]
                    device_mac = f"{mac_bytes[5]:02X}:{mac_bytes[4]:02X}:{mac_bytes[3]:02X}:{mac_bytes[2]:02X}:{mac_bytes[1]:02X}:{mac_bytes[0]:02X}"
                    self.callback(device_mac, rssi, address_type, raw_data)
                    offset += BLE_PROXY_HEADER_STRUCT.size + adv_data_len
                else:
                    break
        except Exception:
            _LOGGER.exception("Error parsing SLZB Bluetooth proxy packet from %s", addr)


class BleProxyClient:
    """Client to manage connection with SLZB BLE Proxy UDP server."""

    def __init__(
        self,
        esp32_ip: str,
        callback: Callable[[str, int, int, bytes], None],
        esp32_port: int = 5050,
    ) -> None:
        self.esp32_ip = esp32_ip
        self.esp32_port = esp32_port
        self.callback = callback
        self.transport: asyncio.DatagramTransport | None = None
        self.protocol: BleProxyProtocol | None = None
        self._connect_task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._connected_evt = asyncio.Event()
        self.running = False

    async def start(self) -> None:
        self.running = True
        self._connect_task = asyncio.create_task(self._connect_loop())

    async def _connect_loop(self) -> None:
        backoff = 2.0
        while self.running:
            try:
                loop = asyncio.get_running_loop()

                self.transport, self.protocol = await loop.create_datagram_endpoint(
                    lambda: BleProxyProtocol(self.callback, self._on_ack),
                    local_addr=("0.0.0.0", 0),
                )

                self.local_port = self.transport.get_extra_info("sockname")[1]
                self._send_ping()

                await asyncio.wait_for(self._connected_evt.wait(), timeout=2.0)
                self._ping_task = asyncio.create_task(self._ping_loop())
                break
            except (OSError, TimeoutError) as err:
                _LOGGER.warning(
                    "Connection to SLZB BLE Proxy failed, retrying in %.1fs: %s",
                    backoff,
                    err,
                )
                self.stop_transport()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    def _on_ack(self) -> None:
        self._connected_evt.set()

    def _send_ping(self) -> None:
        if self.transport and self.local_port != 0:
            ping_packet = struct.pack("<BBH", 0, ProxyAction.PING, self.local_port)
            self.transport.sendto(ping_packet, (self.esp32_ip, self.esp32_port))

    async def _ping_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(2.0)
                self._send_ping()
        except asyncio.CancelledError:
            pass

    def stop_transport(self) -> None:
        if self.transport:
            try:
                disconnect_packet = struct.pack("<BB", 0, ProxyAction.DISCONNECT)
                self.transport.sendto(
                    disconnect_packet, (self.esp32_ip, self.esp32_port)
                )
            except Exception:
                _LOGGER.exception("Error sending disconnect packet to SLZB BLE Proxy")
            finally:
                self.transport.close()
                self.transport = None
                self.protocol = None

    def stop(self) -> None:
        self.running = False
        if self._connect_task:
            self._connect_task.cancel()
            self._connect_task = None

        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None

        self.stop_transport()
        self._connected_evt.clear()
