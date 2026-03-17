import logging
import collections

# Circular buffer to store logs in memory
log_buffer = collections.deque(maxlen=1000)

class BufferHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        log_buffer.append(log_entry)

# Setup logging
logger = logging.getLogger("wcag_auditor")
logger.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Add buffer handler
buffer_handler = BufferHandler()
buffer_handler.setFormatter(formatter)
logger.addHandler(buffer_handler)

# Also log to console
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def get_logs():
    return list(log_buffer)
