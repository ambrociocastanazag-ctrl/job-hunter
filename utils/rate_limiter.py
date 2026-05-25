import time
import random
from config.settings import REQUEST_DELAY_MIN, REQUEST_DELAY_MAX


def polite_sleep():
    delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
    time.sleep(delay)
