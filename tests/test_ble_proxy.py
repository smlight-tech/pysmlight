import asyncio
from typing import Any
from unittest.mock import Mock, patch

import pytest

from pysmlight.ble_proxy import BleProxyClient, BleProxyProtocol
from pysmlight.const import BleProxyMode


class MockServerProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None
        self.received_packets: list[tuple[bytes, Any]] = []

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.received_packets.append((data, addr))
        if len(data) >= 4 and data[1] == 0:
            use_port = int.from_bytes(data[2:4], byteorder="little")
            ack_pkt = b"\x00\x02"
            if self.transport:
                self.transport.sendto(ack_pkt, (addr[0], use_port))


@pytest.mark.asyncio
async def test_ble_proxy_protocol_ack() -> None:
    """Test that datagram_received processes an ACK action and triggers the on_ack callback."""
    callback = Mock()
    on_ack = Mock()
    protocol = BleProxyProtocol(callback, on_ack)
    protocol.datagram_received(b"\x00\x02", ("127.0.0.1", 12345))
    on_ack.assert_called_once()
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_ble_proxy_protocol_invalid() -> None:
    """Test that datagram_received ignores invalid data."""
    callback = Mock()
    on_ack = Mock()
    protocol = BleProxyProtocol(callback, on_ack)
    protocol.datagram_received(b"\x01\x02", ("127.0.0.1", 12345))
    protocol.datagram_received(b"\x00", ("127.0.0.1", 12345))
    protocol.datagram_received(b"\x00\x03\x00\x00\x00\x00\x00", ("127.0.0.1", 12345))
    protocol.datagram_received(b"\x00\x05", ("127.0.0.1", 12345))
    mac_bytes = b"\x55\x44\x33\x22\x11\x00"
    incomplete_packet = (
        b"\x00\x03" + mac_bytes + b"\x01" + b"\xab" + b"\x0a" + b"\x02\x01\x06"
    )
    protocol.datagram_received(incomplete_packet, ("127.0.0.1", 12345))
    on_ack.assert_not_called()
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_ble_proxy_protocol_valid_data() -> None:
    """Test that datagram_received successfully parses valid data."""
    callback = Mock()
    on_ack = Mock()
    protocol = BleProxyProtocol(callback, on_ack)
    mac_bytes = b"\x55\x44\x33\x22\x11\x00"
    addr_type = b"\x01"
    rssi = b"\xab"
    payload = b"\x02\x01\x06"
    packet = b"\x00\x03" + mac_bytes + addr_type + rssi + b"\x03" + payload
    protocol.datagram_received(packet, ("127.0.0.1", 12345))
    callback.assert_called_once_with(mac_bytes, -85, 1, payload)
    on_ack.assert_not_called()


@pytest.mark.asyncio
async def test_ble_proxy_protocol_bundled_data() -> None:
    """Test that datagram_received successfully parses bundled advertisements."""
    callback = Mock()
    on_ack = Mock()
    protocol = BleProxyProtocol(callback, on_ack)
    mac_bytes_1 = b"\x55\x44\x33\x22\x11\x00"
    payload_1 = b"\x02\x01\x06"
    packet_1 = b"\x00\x03" + mac_bytes_1 + b"\x01" + b"\xab" + b"\x03" + payload_1

    mac_bytes_2 = b"\xaa\xbb\xcc\xdd\xee\xff"
    payload_2 = b"\x05\x09\x4d\x79\x44\x65\x76"
    packet_2 = b"\x00\x03" + mac_bytes_2 + b"\x00" + b"\xb0" + b"\x07" + payload_2

    packet = packet_1 + packet_2
    protocol.datagram_received(packet, ("127.0.0.1", 12345))

    assert callback.call_count == 2
    callback.assert_any_call(mac_bytes_1, -85, 1, payload_1)
    callback.assert_any_call(mac_bytes_2, -80, 0, payload_2)
    on_ack.assert_not_called()


@pytest.mark.asyncio
async def test_ble_proxy_protocol_exception() -> None:
    """Test that exceptions inside datagram_received are caught and do not propagate."""
    callback = Mock(side_effect=ValueError("Callback error"))
    on_ack = Mock()
    protocol = BleProxyProtocol(callback, on_ack)
    mac_bytes = b"\x55\x44\x33\x22\x11\x00"
    addr_type = b"\x01"
    rssi = b"\xab"
    payload = b"\x02\x01\x06"
    packet = b"\x00\x03" + mac_bytes + addr_type + rssi + b"\x03" + payload
    protocol.datagram_received(packet, ("127.0.0.1", 12345))
    callback.assert_called_once()


@pytest.mark.asyncio
async def test_ble_proxy_client_success() -> None:
    """Test that BleProxyClient successfully starts, connects, pings, and stops cleanly."""
    loop = asyncio.get_running_loop()
    server_transport, server_protocol = await loop.create_datagram_endpoint(
        MockServerProtocol,
        local_addr=("127.0.0.1", 0),
    )
    server_port = server_transport.get_extra_info("sockname")[1]

    callback = Mock()
    client = BleProxyClient(
        esp32_ip="127.0.0.1",
        callback=callback,
        esp32_port=server_port,
    )

    original_sleep = asyncio.sleep

    async def mock_sleep(delay):
        if delay == 2.0:  # Backoff sleep or ping loop sleep
            await original_sleep(0.001)
        else:
            await original_sleep(delay)

    with patch("asyncio.sleep", side_effect=mock_sleep):
        await client.start()
        await original_sleep(0.001)
        assert client.transport is not None
        assert client.protocol is not None
        for _ in range(5):
            await original_sleep(0.01)
        client.stop()
        await asyncio.sleep(0.01)

    server_transport.close()
    assert len(server_protocol.received_packets) >= 2
    handshake_data, _ = server_protocol.received_packets[0]
    assert handshake_data[0] == 0
    assert handshake_data[1] == 0

    disconnect_found = False
    for data, _ in server_protocol.received_packets:
        if len(data) >= 2 and data[1] == 1:
            disconnect_found = True
            break
    assert disconnect_found


@pytest.mark.asyncio
async def test_ble_proxy_client_disconnect_exception() -> None:
    """Test that an exception during sending disconnect_packet in stop() is caught and ignored"""
    client = BleProxyClient(
        esp32_ip="127.0.0.1",
        callback=Mock(),
        esp32_port=5050,
    )
    mock_transport = Mock()
    mock_transport.sendto.side_effect = OSError("Transmit error")
    client.transport = mock_transport
    client.stop()
    mock_transport.close.assert_called_once()


@pytest.mark.asyncio
async def test_ble_proxy_client_timeout() -> None:
    """Test that BleProxyClient handles connection timeouts and executes proper exponential backoff retries."""
    callback = Mock()
    client = BleProxyClient(
        esp32_ip="127.0.0.1",
        callback=callback,
        esp32_port=1,
    )

    original_sleep = asyncio.sleep
    sleep_calls: list[float] = []

    async def mock_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        await original_sleep(0.0001)

    async def mock_wait_for(fut: Any, timeout: float | None) -> Any:
        if asyncio.iscoroutine(fut):
            fut.close()
        raise TimeoutError()

    with (
        patch("asyncio.sleep", side_effect=mock_sleep),
        patch("asyncio.wait_for", side_effect=mock_wait_for),
        patch("pysmlight.ble_proxy._LOGGER") as mock_logger,
    ):
        await client.start()

        for _ in range(100):
            if len(sleep_calls) >= 2:
                break
            await original_sleep(0.001)

        client.stop()

    assert len(sleep_calls) >= 2
    assert sleep_calls[0] == 2.0
    assert sleep_calls[1] == 4.0
    mock_logger.warning.assert_called()


@pytest.mark.asyncio
async def test_ble_proxy_client_api_methods() -> None:
    """Test BleProxyClient's API methods set_scan_mode and set_active_window."""
    client = BleProxyClient(
        esp32_ip="127.0.0.1",
        callback=Mock(),
        esp32_port=5050,
    )
    mock_transport = Mock()
    client.transport = mock_transport

    client.set_scan_mode(BleProxyMode.BLE_PROXY_MODE_ACTIVE)
    mock_transport.sendto.assert_called_with(
        b"\x00\x04\x01",
        ("127.0.0.1", 5050),
    )

    client.set_scan_mode(BleProxyMode.BLE_PROXY_MODE_PASSIVE)
    mock_transport.sendto.assert_called_with(
        b"\x00\x04\x00",
        ("127.0.0.1", 5050),
    )

    client.set_active_window(timeout=120)
    mock_transport.sendto.assert_called_with(
        b"\x00\x05\x78\x00",
        ("127.0.0.1", 5050),
    )


@pytest.mark.asyncio
async def test_ble_proxy_client_api_methods_exceptions() -> None:
    """Test BleProxyClient's API methods raise SmlightConnectionError on socket failure."""
    from pysmlight.exceptions import SmlightConnectionError

    client = BleProxyClient(
        esp32_ip="127.0.0.1",
        callback=Mock(),
        esp32_port=5050,
    )
    mock_transport = Mock()
    mock_transport.sendto.side_effect = OSError("Socket error")
    client.transport = mock_transport

    with pytest.raises(SmlightConnectionError):
        client.set_scan_mode(BleProxyMode.BLE_PROXY_MODE_ACTIVE)

    with pytest.raises(SmlightConnectionError):
        client.set_active_window(timeout=120)
