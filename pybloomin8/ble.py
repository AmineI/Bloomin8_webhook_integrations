"""Bluetooth Low Energy wake support."""
"""Reference : https://github.com/ARPOBOT-BLOOMIN8/eink_canvas_home_assistant_component/blob/main/custom_components/bloomin8_eink_canvas/ble_wake.py"""
import asyncio
import logging

from bleak import BleakClient, BleakScanner

from .constants import (
    BLE_WAKE_CHARACTERISTIC_UUID,
    BLE_WAKE_PAYLOAD_OFF,
    BLE_WAKE_PAYLOAD_ON,
    BLE_WAKE_PULSE_GAP_SECONDS,
)

log = logging.getLogger(__name__)


async def wake_device(mac_address: str, retries: int = 3) -> None:
    """Wake a frame with the official assert/release BLE pulse."""
    for attempt in range(1, retries + 1):
        try:
            # Step 1 – Discover the device over BLE
            log.info(
                "[BLE] Scanning for %s (attempt %d/%d)",
                mac_address,
                attempt,
                retries,
            )
            device = await BleakScanner.find_device_by_address(
                mac_address,
                timeout=25.0,
            )
            if device is None:
                raise RuntimeError(f"Device {mac_address} not found")

            # Step 2 – Connect and write the assert/release wake pulse
            async with BleakClient(device) as client:
                await client.write_gatt_char(
                    BLE_WAKE_CHARACTERISTIC_UUID,
                    BLE_WAKE_PAYLOAD_ON,
                    response=False,
                )
                await asyncio.sleep(BLE_WAKE_PULSE_GAP_SECONDS)
                await client.write_gatt_char(
                    BLE_WAKE_CHARACTERISTIC_UUID,
                    BLE_WAKE_PAYLOAD_OFF,
                    response=False,
                )

            log.info("[BLE] Wake pulse sent to %s", device.name or mac_address)
            return
        except Exception as exc:
            log.warning("[BLE] Attempt %d failed: %s", attempt, exc)
            if attempt == retries:
                raise
            await asyncio.sleep(2.0)