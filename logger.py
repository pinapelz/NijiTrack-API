import time
from datetime import datetime
import pytz

def _get_datetime_string():
    utc_now = datetime.now(pytz.timezone('UTC'))
    pst_now = utc_now.astimezone(pytz.timezone('US/Pacific'))
    return pst_now.strftime('%Y-%m-%d %H:%M:%S')

def track_task_time(message: str):
    def decorator(func):
        def wrapper(*args, **kwargs):
            print(f"[{_get_datetime_string()}] TASK STARTED: " + message)
            start = time.time()
            result = func(*args, **kwargs)
            end = time.time()
            print(f"[{_get_datetime_string()}] TASK COMPLETED: {message} {round(end - start, 3)} seconds")
            return result
        return wrapper
    return decorator

class Logger:
    def __init__(self, path: str = "logs.txt", max_size_bytes: int = 1000000):
        self.max_size_bytes = max_size_bytes
        self.path = path
    
    def create_log_file(self):
        with open(self.path, "w") as file:
            file.write("")
    
    def log(self, message: str):
        with open(self.path, "a") as file:
            file.write(f"[{_get_datetime_string()}] {message}\n")