from __future__ import annotations

import json
from typing import Any, Literal, Self

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectionError

from .const import FW_URL, SEL_FW_CHANNEL, Devices
from .exceptions import SmlightConnectionError
from .models import Firmware

FwChannel = Literal["any", "release", "dev"]
FwMode = Literal["esp32", "zigbee"]


class FirmwareCatalog:
    """Firmware catalog for SMLIGHT devices."""

    def __init__(
        self,
        session: ClientSession | None = None,
        base_url: str = FW_URL,
    ) -> None:
        self.session = session
        self.base_url = base_url
        self.close_session = False

    async def __aenter__(self) -> Self:
        if self.session is None:
            self.session = ClientSession()
            self.close_session = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self.session is not None and self.close_session:
            await self.session.close()
            self.session = None
            self.close_session = False

    @classmethod
    def determine_firmware_type(
        cls, mode: FwMode, device: str | None = None, u_device: bool | None = None
    ) -> str:
        if mode == "zigbee":
            return "ZB"
        if u_device is None and device:
            u_device = device.endswith(("U", "u")) or "ultima" in device.lower()
        return "ESPs3" if u_device else "ESP"

    @staticmethod
    def format_release_notes(firmware: Firmware) -> str | None:
        """Format release notes for firmware."""
        if firmware.notes:
            items = (
                firmware.notes.splitlines()
                if firmware.mode == "ESP"
                else [firmware.notes]
            )
            notes = ""
            for i, v in enumerate(items):
                if i and v and not v.startswith("-"):
                    notes += f"* {v}\n"
                else:
                    notes += f"{v}\n\n"

            if firmware.dev and firmware.mode == "ZB":
                notes = "Dev firmware.\n\n" + notes
            return notes
        return None

    def parse_firmware(
        self,
        firmware_data: list[dict[str, Any]],
        fw_type: str,
        channel: FwChannel | None,
        zb_type: int | None,
    ) -> list[Firmware]:
        """Parse and format firmware items returned by the updates server."""
        client_filter = channel if fw_type != "ZB" else None
        fw: list[Firmware] = []
        for d in firmware_data:
            item = Firmware.from_dict(d)
            item.set_mode(fw_type)
            if client_filter == "release" and item.dev:
                continue
            if client_filter == "dev" and not item.dev:
                continue
            if zb_type is not None and item.type != zb_type:
                continue
            if item.notes:
                item.notes = self.format_release_notes(item)
            fw.append(item)
        return fw

    async def get_firmware_version(
        self,
        channel: FwChannel | None,
        *,
        device: str | None = None,
        mode: FwMode = "esp32",
        zb_type: int | None = None,
        idx: int = 0,
        hw: int | None = None,
        u_device: bool | None = None,
    ) -> list[Firmware]:
        """Get firmware versions for a device and mode."""
        self._check_channel(channel)
        fw_type = self.determine_firmware_type(mode, device, u_device)
        if mode == "zigbee":
            params = self._zigbee_params(channel, device, idx, hw)
        else:
            params = {"type": fw_type}

        data = await self._fetch(params)

        if mode == "zigbee":
            if not isinstance(data, list):
                raise SmlightConnectionError("Unexpected firmware manifest response")
            firmware_data = data
        else:
            if not isinstance(data, dict) or not isinstance(data.get("fw"), list):
                raise SmlightConnectionError("Unexpected firmware manifest response")
            firmware_data = data["fw"]

        return self.parse_firmware(firmware_data, fw_type, channel, zb_type)

    @staticmethod
    def _check_channel(channel: FwChannel | None) -> None:
        if channel is not None and channel not in SEL_FW_CHANNEL.values():
            raise ValueError(f"Unsupported firmware channel: {channel}")

    @staticmethod
    def _zigbee_params(
        channel: FwChannel | None, device: str | None, idx: int, hw: int | None
    ) -> dict[str, str]:
        if device is None:
            raise ValueError("Zigbee firmware query requires a device model")
        if device not in Devices:
            raise ValueError(f"Unknown device model: {device}")
        params = {
            "type": "ZB",
            "format": "slzb",
            "device": str(Devices[device]),
            "idx": str(idx),
        }
        if hw is not None:
            params["hw"] = str(hw)
        if channel == "release":
            params["ch"] = "0"
        elif channel == "dev":
            params["ch"] = "1"
        return params

    async def _fetch(self, params: dict[str, str]) -> Any:
        assert self.session is not None, "Session not created"
        try:
            async with self.session.get(self.base_url, params=params) as resp:
                if resp.status != 200:
                    raise SmlightConnectionError(f"HTTP error {resp.status}")
                text = await resp.text(encoding="utf-8")
        except (ClientConnectionError, TimeoutError) as err:
            raise SmlightConnectionError("Connection failed") from err

        try:
            return json.loads(text)
        except json.JSONDecodeError as err:
            raise SmlightConnectionError(
                "Invalid JSON received from firmware catalog"
            ) from err
