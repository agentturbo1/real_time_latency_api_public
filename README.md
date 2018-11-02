# real_time_latency_api
*Written by: Lukas Gust*<br>
*Last updated: 09/19/18*<br>
## Overview
This web application utilizes the [Synoptic Push service](https://alert.synopticlabs.org/) to compute and distribute network/station latency
and observation count information. Latency being defined as the difference between NOW and when the observation was observed, typically in seconds.
This information is distributed using a simple RESTful request service much like the Synoptic API to retrieve this information.

### The Basics
In order to run the application on your local machine or on a server make sure that your system has Python 3.6.6. To develop this application
I have used the latest Anaconda3 distribution of python and Jet Brains PyCharm 2018. The application uses several libraries including, 
but not limited to: tornado, pandas, and numpy. Please make sure these are up to date. To run the application simply type into the command line:
``python real_time_latency_api.py``. There is an option to specify a specific port ``python real_time_latency_api.py --port 8080``. You may also type 
``python real_time_latency_api.py --help`` to see an exhaustive overview.<br>

The base URL: ``\<hostname>:\<port#>`` if it is run locally you need to include the port number e.g. ``localhost:8888``, otherwise 
it will just use the public facing hostname of the server.

## Resources
This API has 3 resources so far which can be queried by http GET requests. The root of the API simply points you to static landing page 
explaining much of what is explained here. Trailing slashes may be included or not on the resource names. the following resources can be accessed 
by appending the resource name to the end of the root address.

| Resource Name | Purpose |
| --- | --- |
| ``/metadata`` | Get metadata for all stations and networks that have reported since the start of the application |
| ``/latency`` | Get all latency statistics |
| ``/counts`` | Get observation count statistics |

Again the root address is going to depend whether you are looking at the data locally or remotely. For testing it is easiest to use it locally.
The remote address is dependent upon the server configuration. 

## ``/metadata``
This service provides all the metadata for every station that has reported since the start of the application.
Here is an example:
```json
{
  "stations": {
    "PAOO": {
      "elevation": 59.0,
      "network": 1, 
      "stid": "PAOO", 
      "longitude": "-165.11430", 
      "latitude": "60.53352", 
      "name": "Toksook Bay"
    }, 
    "PAHN": {
      "elevation": 49.0, 
      "network": 1, 
      "stid": "PAHN", 
      "longitude": "-135.51140", 
      "latitude": "59.24290", 
      "name": "Haines - Haines Airport"
    }
  }, 
    "station_count_per_net": {
      "1": 6
    }, 
    "network_stations": {
      "1": [
        "PAHN",
        "PAOO"
      ]
    }
}
```
**Summary of keys:**
- `stations`: dictionary of station id's and their meta data including elevation, network, stid, longitude, latitude, 
and name.
- `station_count_per_net`: the number of stations per network.
- `network_Stations`: the list of stations per network.
## ``/latency``
This service provides several types of latency statistics on the stations that have reported. The latency is defined to 
be the difference of the observation time and the now time in seconds. i.e. `now - observation time`. Here is an example:
```json
{
  "station_latency": {
    "PAHN": {
      "network": 1, 
      "latency": 732.620143532753
    },
    "PAOO": {
      "network": 1, 
      "latency": 732.607148706913
    }
  }, 
  "total_avg_latency": 732.611897101005, 
  "max_latency": {
    "stid": "PAHN",
    "network": 1, 
    "latency": 732.620143532753
  }, 
  "max_station_latency": {
    "PAOO": 732.6191442012787, "PAHN": 732.6241409778595
  }, 
  "max_network_latency": {
    "1": 732.6281385421753
  }
} 
``` 
**Summary of keys:**
- `station_latency`: average latency of all sensor types per station. e.g. wind_speed, air_temp.
- `total_avg_latency`: average latency over all station latencies.
- `max_latency`: maximum latency of all stations.
- `max_station_latency`: maximum latency observed for each station.
- `max_network_latency`: maximum latency observed for each network.
## ``/counts``
This service provides observation count statistics. Counts do not consider each sensor type as a single count, 
instead it counts *one* observation for all the sensor types in a single message from the push service. This may cause 
over-counting if, for example, only `air_temp` is sent in one message and only `wind_speed` in another several minutes 
later. This has the effect of "counting the same observation multiple times", but the benefits of a compact data 
structure outweigh the inaccuracies of the counts. Here is an example:

```json
{
  "network_ob_count": {
    "1": 14
  }, 
  "station_ob_count": {
    "PAOO": 4, "PAHN": 2
  }
}
```
**Summary of keys:**
- `network_ob_count`: observation count per network.
- `station_ob_count`: observation count per station.

