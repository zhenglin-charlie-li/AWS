#!/usr/bin/env python
# coding: utf-8
from pymongo.server_api import ServerApi
from pymongo.mongo_client import MongoClient
from io import BytesIO
import base64
import logging
import sys
import random

import matplotlib.pyplot as plt

from shadowingfunction_wallheight_13 import shadowingfunction_wallheight_13
from solarposition import *


# dsm is a map that represents elevation information
dsm = np.load('./dsm_local_array.npy')
dsm = np.nan_to_num(dsm, nan=0)

# Sun position
# https://github.com/pvlib/pvlib-python

lon = -95.30052
lat = 29.73463

utc_offset = -4

formatted_time = sys.argv[1]
# Create a date range from 6:00 to 20:00 with a 10-minute interval
timestamps = pd.date_range(formatted_time, formatted_time, freq='30T')

# Create a DataFrame using the timestamps as a column
df_solar_data = pd.DataFrame({'TimeStamp': timestamps})

# UTC time
df_solar_data['TimeStamp'] = pd.DatetimeIndex(
    df_solar_data['TimeStamp']) - pd.DateOffset(hours=utc_offset)

# To_Datetime
df_solar_data["TimeStamp"] = df_solar_data["TimeStamp"].apply(pd.to_datetime)
df_solar_data.set_index("TimeStamp", inplace=True)

# Add time index
df_solar_data["TimeStamp"] = df_solar_data.index

df_solar_data.head()

# Get_sun's position df
df_solar = get_solarposition(df_solar_data.index, lat, lon)

# Add time index
df_solar['TimeStamp'] = pd.DatetimeIndex(
    df_solar.index) + pd.DateOffset(hours=utc_offset)

df_solar = df_solar[['TimeStamp', 'apparent_zenith', 'zenith', 'apparent_elevation', 'elevation',
                     'azimuth', 'equation_of_time']]

# To_Datetime
df_solar["TimeStamp"] = df_solar["TimeStamp"].apply(pd.to_datetime)
df_solar.set_index("TimeStamp", inplace=True)

df_solar.head()

df_solar["TimeStamp"] = df_solar.index
df_solar = df_solar[['TimeStamp', 'elevation', 'zenith', 'azimuth']]

df_solar = df_solar.rename(
    columns={"elevation": "Elevation", "azimuth": "Azimuth", "zenith": "Zenith"})

df_solar.head()

# # Walls and Height

# Temporally !
scale = 1
walls = np.zeros((dsm.shape[0], dsm.shape[1]))
dirwalls = np.zeros((dsm.shape[0], dsm.shape[1]))

walls.shape

# # Shadow


i = 0

altitude = df_solar['Elevation'][i]
azimuth = df_solar['Azimuth'][i]

hour = df_solar.index[i].hour
minute = df_solar.index[i].minute

# Create a logger
logger = logging.getLogger("logger")
logger.setLevel(logging.DEBUG)  # Set the desired log level

# Create a file handler to write log messages to a file
file_handler = logging.FileHandler("log.log")
file_handler.setLevel(logging.DEBUG)  # Set the log level for the file handler

# Create a console handler to display log messages in the console
console_handler = logging.StreamHandler()
# Set the log level for the console handler
console_handler.setLevel(logging.INFO)

# Define a log format
formatter = logging.Formatter(
    "%(asctime)s - [%(lineno)d] - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("shadow analysis start")

logger.info("generating shallow matrix of time: " + formatted_time)

sh, wallsh, wallsun, facesh, facesun = shadowingfunction_wallheight_13(dsm, azimuth, altitude, scale, walls,
                                                                       dirwalls * np.pi / 180.)

plt.imshow(sh, cmap='viridis')

plt.title("%2s" % str(hour).zfill(2) + ":%2s" % str(minute).zfill(2),
          pad=10, fontsize=15, color="black", weight='bold')

df = pd.DataFrame(sh)

df.head()

data_dict = sh.tolist()

logger.info("shadow analysis complete")
logger.info("visualization start")


# Define a list of colormaps
colormaps = [
    'viridis', 'plasma', 'inferno', 'magma', 'cividis',
    'gray', 'jet', 'rainbow', 'cool', 'hot', 'nipy_spectral',
    'autumn', 'coolwarm', 'copper'
]

# Define a list of interpolation methods
interpolations = ['antialiased', 'none', 'nearest', 'bilinear', 'bicubic', 'spline16', 'spline36', 'hanning', 'hamming',
                  'hermite', 'kaiser', 'quadric', 'catrom', 'gaussian', 'bessel', 'mitchell', 'sinc', 'lanczos',
                  'blackman']

# Create subplots for each colormap
# plt.figure(figsize=(60, 60))
num_cols = 4
num_rows = int(np.ceil(len(colormaps) / num_cols))
VisualizedImages = []
# Create a single BytesIO object outside the loop
img_bytesio = BytesIO()

for i, cmap in enumerate(colormaps):
    interpolation = random.choice(interpolations)

    # Create the figure and axis
    fig, ax = plt.subplots()

    # Create the image
    im = ax.imshow(df, interpolation=interpolation, cmap=cmap)

    # Customize the plot
    ax.axis("off")
    ax.set_title(
        f"Shadow Matrix Visualization\nTime (CT): {formatted_time}\nColormap: {cmap}\nInterpolation: {interpolation}")

    # Save the plot to the BytesIO object (reset it first)
    img_bytesio.seek(0)
    img_bytesio.truncate()
    fig.savefig(img_bytesio, format='png')

    # Convert the image in the BytesIO object to a Base64 string
    img_base64 = base64.b64encode(img_bytesio.getvalue()).decode()

    # Now, img_base64 contains the Base64-encoded image
    VisualizedImages.append(img_base64)

# Close the BytesIO object outside the loop
img_bytesio.close()

# data_to_insert = {
#     "TimeStamp": formatted_time,
#     "ShadowMatrix": data_dict,
#     "VisualizedImages": VisualizedImages
# }
#
logger.info("visualization complete")

logger.info("persist result to MongoDB start")

data_to_insert = {
    "TimeStamp": formatted_time,
    "VisualizedImages": VisualizedImages
}


uri = ""  # todo: add mongodb uri here

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    db = client["A1_Shadow_Analysis"]
    collection = db["A1_Shadow_Analysis"]
    result = collection.insert_one(data_to_insert)
    logger.info(
        "insert data into mongodb A1_Shadow_Analysis.A1_Shadow_Analysis successfully!")
except Exception as e:
    print(e)
