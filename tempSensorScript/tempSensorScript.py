#!/usr/bin/env python3
import glob
import time
import logging
from datetime import datetime, timezone
import requests
import RPi.GPIO as GPIO

# ---------- CONFIGURATION ----------

# Path to the 1-Wire temperature sensor reading
SENSOR_GLOB = "/sys/bus/w1/devices/28-*/temperature"

# GPIO pin (BCM numbering)
GPIO_PIN = 17

THRESHOLD_C = 10
POLL_INTERVAL_SECONDS = 60
API_URL = "http://192.168.1.24:8080/temperatures/report"
API_TOKEN = None

# ---------- FUNCTIONS ----------

def read_all_temperatures_c() -> dict:
    """
       Reads all DS18B20 sensors and returns a dict:
           { "28-xxxxxxxxxxxx": temp_c, ... }
       Temperatures are in °C.
       """
    temps= {}
    paths = glob.glob(SENSOR_GLOB)
    if not paths:
        raise FileNotFoundError(f"No sensors found matching {SENSOR_GLOB}")

    for path in paths:
        sensor_dir = path.split("/")[-2]  # e.g. '28-3c01d075c5ff'
        with open(path, "r") as f:
            raw = f.read().strip()

        try:
            milli_c = int(raw)
        except ValueError:
            raise ValueError(f"Could not parse temperature from '{raw}' for {sensor_dir}")

        temps[sensor_dir] = milli_c / 1000.0

    return temps


def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_PIN, GPIO.OUT, initial=GPIO.LOW)


def set_output_based_on_temps(temps_c: dict) -> float:
    min_temp = min(temps_c.values())
    enabled = min_temp < THRESHOLD_C

    GPIO.output(GPIO_PIN, GPIO.HIGH if enabled else GPIO.LOW)

    logging.info(
        "Min temperature %.3f°C -> GPIO %d %s",
        min_temp,
        GPIO_PIN,
        "HIGH" if enabled else "LOW",
    )
    return min_temp

def send_temperatures(temps_c: dict) -> None:
    sensor_ids = sorted(temps_c)

    if len(sensor_ids) != 2:
        logging.error(
            "Expected 2 sensors, found %d. Report not sent.",
            len(sensor_ids),
        )
        return

    payload = {
        "temperature1": int(round(temps_c[sensor_ids[0]])),
        "temperature2": int(round(temps_c[sensor_ids[1]])),
        "timeStamp": datetime.now(timezone.utc).isoformat(),
    }

    headers = {}
    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"

    try:
        resp = requests.post(
            API_URL,
            json=payload,
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        logging.info("Sent temperature report: %s", payload)
    except requests.exceptions.RequestException as e:
        logging.error("Failed to send temperatures to API: %s", e)

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    logging.info("Starting temperature monitor (multi-sensor)")
    setup_gpio()

    try:
        while True:
            try:
                temps_c = read_all_temperatures_c()
                temps_int = {sid: int(round(temp)) for sid, temp in temps_c.items()}
                logging.info("Temperatures: %s", temps_int)
                min_temp_c = set_output_based_on_temps(temps_c)
                send_temperatures(temps_c)
                # min_temp_int = set_output_based_on_temps(temps_int)
                # send_temperatures(temps_c, temps_int, min_temp_int)
            except Exception as e:
                logging.error("Error in main loop: %s", e)

            time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logging.info("Stopping due to KeyboardInterrupt")

    finally:
        GPIO.cleanup()
        logging.info("GPIO cleaned up")


if __name__ == "__main__":
    main()