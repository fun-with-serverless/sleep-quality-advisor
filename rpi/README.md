# Sleep Quality Sensors (Raspberry Pi)

This project runs on a Raspberry Pi (Bookworm) to read BME680 data every 10s and POST it to your ingest endpoint. Warm-up readings are suppressed by default (300s).

## Prerequisites
- Raspberry Pi 3B+ (or similar) with Raspberry Pi OS Bookworm
- I2C enabled (raspi-config → Interface Options → I2C)
- Python managed via uv (install: curl -LsSf https://astral.sh/uv/install.sh | sh)
- Packages: sudo apt-get install -y i2c-tools libatlas-base-dev

## Setup
```bash
cd rpi
uv python install 3.14
uv sync
```

## Configuration
Create an environment file (do not commit secrets):
```bash
sudo tee /etc/sqs-bme680.env >/dev/null <<'EOF'
ENDPOINT_URL=https://your-api.example.com/ingest
POST_SECRET=...your-secret...
USER_AGENT=sleep-quality-sensors/1.0
SAMPLE_INTERVAL_SECS=10
WARMUP_DURATION_SECS=300
I2C_BUS=1
I2C_ADDRESS=0x76
LOG_LEVEL=INFO
EOF
```

## Run
```bash
cd rpi
uv run python -m sqa_rpi.main
```

## Systemd Service
Install the service (edit paths/user as needed in the template):
```bash
sudo cp systemd/sqa.service.template /etc/systemd/system/sqa.service
sudo systemctl daemon-reload
sudo systemctl enable sqa.service
sudo systemctl start sqa.service
```

## Development
- Lint/format/typecheck/tests:
```bash
cd rpi
uv run task check-fix
```

## Notes
- BME680 configuration (defaults in code):
  - Temperature OS=8x, Humidity OS=2x, Pressure OS=4x, IIR Filter Size=3
  - Gas heater: 320°C for 150ms (profile 0) and gas measurement enabled
- Warm-up suppression prevents unstable gas readings from being posted.
- Payload matches backend `EnvReadingModel` (`day`, `ts_min`, `temp_c`, `humidity_pct`, `pressure_hpa`, `iaq`, `noise_db`, `deviceId`).
