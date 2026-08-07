import time
import random
from config.settings import get_settings


def polite_sleep():
    runtime_cfg = get_settings()["runtime"]
    delay = random.uniform(runtime_cfg["request_delay_min"], runtime_cfg["request_delay_max"])
    time.sleep(delay)
