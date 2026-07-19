import logging
import sys

def get_logger():

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG) # Overall logger threshold

    # 2. Create a handler specifically for the Command Prompt
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO) # This handler can have its own level

    # 3. Create a formatter and add it to the handler
    log_format = logging.Formatter('%(name)s | %(levelname)s | %(message)s')
    console_handler.setFormatter(log_format)

    # 4. Add the handler to your logger
    logger.addHandler(console_handler)

    return logger