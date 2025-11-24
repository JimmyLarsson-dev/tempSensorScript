#!/usr/bin/env python3
import glob
import time
import logging

import requests
import RPi.GPIO as GPIO

# ---------- CONFIGURATION ----------

# Path to the 1-Wire temperature sensor reading
SENSOR_GLOB = "/sys/bus/w1/devices/28-*/temperature"

# GPIO pin (BCM numbering)
GPIO_PIN = 17

# Temperature threshold (°C)
THRESHOLD_C = 10

# How often to read (seconds)
POLL_INTERVAL_SECONDS = 60

# API configuration
API_URL = "https://example.com/temperature"  # <-- change this to your API endpoint
API_TOKEN = None  # e.g. "your-secret-token" or leave as None if not used

# ---------- FUNCTIONS ----------

def read_temperature_c() -> float:
    """
    Reads the temperature in °C from the 1-Wire sensor.
    Assumes /sys/bus/w1/devices/28-*/temperature contains value in 1/1000 °C.
    """
    paths = glob.glob(SENSOR_GLOB)
    if not paths:
        raise FileNotFoundError(f"No sensor found matching {SENSOR_GLOB}")

    path = paths[0]  # use the first sensor found
    with open(path, "r") as f:
        raw = f.read().strip()

    try:
        milli_c = int(raw)
    except ValueError:
        raise ValueError(f"Could not parse temperature from '{raw}'")

    return milli_c / 1000.0


def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_PIN, GPIO.OUT, initial=GPIO.LOW)


def set_output_for_temp(temp_c: float) -> int:
    """
    Convert to whole degrees and set GPIO:
    - HIGH if temp < THRESHOLD_C
    - LOW  if temp >= THRESHOLD_C
    Returns the integer temperature used.
    """
    temp_int = int(round(temp_c))

    if temp_int < THRESHOLD_C:
        GPIO.output(GPIO_PIN, GPIO.HIGH)
        logging.info(
            "Temperature %d°C < %d°C -> GPIO %d HIGH",
            temp_int, THRESHOLD_C, GPIO_PIN
        )
    else:
        GPIO.output(GPIO_PIN, GPIO.LOW)
        logging.info(
            "Temperature %d°C >= %d°C -> GPIO %d LOW",
            temp_int, THRESHOLD_C, GPIO_PIN
        )

    return temp_int


def send_temperature(temp_c: float, temp_int: int):
    """
    Sends the temperature to the API as JSON via HTTP POST.
    Adjust the payload structure as needed to match your API.
    """
    headers = {"Content-Type": "application/json"}
    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"

    payload = {
        "temperature_c": temp_c,
        "temperature_int_c": temp_int,
        "unit": "C"
    }

    # try:
    #     resp = requests.post(API_URL, json=payload, headers=headers, timeout=5)
    #     resp.raise_for_status()
    #     logging.info(
    #         "Sent temperature to API: %.2f°C (int %d°C), status=%d",
    #         temp_c, temp_int, resp.status_code
    #     )
    # except Exception as e:
    #     logging.error("Failed to send temperature to API: %s", e)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    logging.info("Starting temperature monitor")
    setup_gpio()

    try:
        while True:
            try:
                temp_c = read_temperature_c()
                temp_int = set_output_for_temp(temp_c)
                send_temperature(temp_c, temp_int)
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