from dataclasses import dataclass

import bme680
import smbus2
from bme680 import constants


@dataclass
class BME680Sample:
    temperature_c: float | None
    humidity_pct: float | None
    pressure_hpa: float | None
    gas_ohms: float | None
    gas_heat_stable: bool


class BME680Reader:
    def __init__(self, i2c_bus: int, i2c_address: int) -> None:
        self._sensor = bme680.BME680(i2c_addr=i2c_address, i2c_device=smbus2.SMBus(i2c_bus))

        self._sensor.set_humidity_oversample(constants.OS_2X)
        self._sensor.set_pressure_oversample(constants.OS_4X)
        self._sensor.set_temperature_oversample(constants.OS_8X)
        self._sensor.set_filter(constants.FILTER_SIZE_3)

        self._sensor.set_gas_status(constants.ENABLE_GAS_MEAS)
        self._sensor.set_gas_heater_temperature(320)
        self._sensor.set_gas_heater_duration(150)
        self._sensor.select_gas_heater_profile(0)

    def read(self) -> BME680Sample:
        if not self._sensor.get_sensor_data():
            return BME680Sample(None, None, None, None, False)

        data = self._sensor.data
        temp = float(data.temperature) if data.temperature is not None else None
        hum = float(data.humidity) if data.humidity is not None else None
        pres_hpa = float(data.pressure) if data.pressure is not None else None

        gas_ok = bool(data.heat_stable)
        gas_val = float(data.gas_resistance) if gas_ok and data.gas_resistance is not None else None

        return BME680Sample(
            temperature_c=temp,
            humidity_pct=hum,
            pressure_hpa=pres_hpa,
            gas_ohms=gas_val,
            gas_heat_stable=gas_ok,
        )
