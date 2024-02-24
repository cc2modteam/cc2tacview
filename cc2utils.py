
class TextLogger:
    def msg(self, msg: str, **kwargs):
        print(msg, **kwargs)

    def info(self, msg: str):
        self.msg(f"INFO {msg}")

    def debug(self, msg: str):
        self.msg(f"DEBUG: {msg}")


logger = TextLogger()


def m2deg(m: float) -> float:
    """meters to degrees north"""
    nm = m / 1852.0
    deg = nm / 60.0
    return deg
