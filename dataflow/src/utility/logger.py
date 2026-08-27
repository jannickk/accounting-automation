
import logging

def get_logger():
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    logger = logging.getLogger(__name__)

    logger.addHandler(logging.StreamHandler(sys.stdout)) # defaults to sys.stderr

    logging.getLogger("azure.identity").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("azure.core").setLevel(logging.WARNING)
    logging.getLogger("msal").setLevel(logging.WARNING)
