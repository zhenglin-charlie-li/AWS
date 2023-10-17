# Python 3
import datetime
import http.server
import json
import logging
import subprocess

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

PORT = 56789  # port to expose
FILE_TO_RUN = "shadow_analysis.py"  # file to run when request come
URL_PATH = "/run_a1_shadow_analysis"
MONGODB_URI = ""  # todo: add mongodb uri here


def init_logger():
    # Create a logger
    logger = logging.getLogger("logger")
    logger.setLevel(logging.DEBUG)  # Set the desired log level

    # Create a file handler to write log messages to a file
    file_handler = logging.FileHandler("log.log")
    # Set the log level for the file handler
    file_handler.setLevel(logging.DEBUG)

    # Create a console handler to display log messages in the console
    console_handler = logging.StreamHandler()
    # Set the log level for the console handler
    console_handler.setLevel(logging.INFO)

    # Define a log format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global results
        time_now_utc = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        time_now_ct = (datetime.datetime.now() -
                       datetime.timedelta(hours=5)).strftime('%Y-%m-%d %H:%M')
        if self.path == URL_PATH:
            try:
                # run the desired file to perform shadow analysis
                logger.info("running shadow analysis.py")
                return_code = subprocess.call(
                    ["python3", FILE_TO_RUN, time_now_ct])
                if return_code != 0:
                    self.send_response(
                        503, "internal error occurred, request not processed")
                    return
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()

                # get run result from MongoDB
                logger.info("getting run result from MongoDB")
                uri = MONGODB_URI
                client = MongoClient(uri, server_api=ServerApi('1'))
                client.admin.command('ping')
                db = client["A1_Shadow_Analysis"]
                collection = db["A1_Shadow_Analysis"]
                query = {"TimeStamp": time_now_ct}
                results = collection.find_one(query)
                logger.info("get result from mongodb successfully!")

                # create json response
                # loaded_df = results['ShadowMatrix']
                VisualizedImages = results['VisualizedImages']
                response_data = {
                    "Message": "API run successfully!",
                    "Timestamp": time_now_ct,
                    "VisualizedImages": VisualizedImages
                }
                json_response = json.dumps(response_data)
                self.wfile.write(json_response.encode('utf-8'))
                logger.info("response done!")
            except Exception as e:
                logger.error(e)
                self.send_response(
                    503, "internal error occurred, request not processed!")
                return
        else:
            super().do_GET()


if __name__ == '__main__':
    logger = init_logger()
    try:
        # Listen on all available network interfaces on port
        server_address = ('', PORT)
        httpd = http.server.HTTPServer(server_address, Handler)
        logger.info('Server started on port: ' + str(PORT))
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('Server stopped at ', datetime.datetime.now())
