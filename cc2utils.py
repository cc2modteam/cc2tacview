import logging
logging.basicConfig()
logger = logging.getLogger("cc2tacview")
logger.setLevel(logging.INFO)


def m2deg(m: float) -> float:
    """meters to degrees north"""
    nm = m / 1852.0
    deg = nm / 60.0
    return deg
