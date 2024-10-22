from plugin_manager import hookimpl 
import os
from pyowm.owm import OWM
from pyowm.utils.config import get_default_config
import threading
import time
import requests
import json
from dotenv import load_dotenv
load_dotenv()

class Meteo:
    @hookimpl
    def get_frontend_components(self):
        print("loading geo frontend")
        return [
            {
                "vue": "meteo_component.vue"
            }
        ]

    @hookimpl
    def startup(self):
        print("Meteo is starting up!")
        self.geoloc = self.get_geoloc()
        self.get_meteo()
        self.schedule_meteo_updates()
        # Plugin-specific initialization logic
        
    def schedule_meteo_updates(self):
        # Use a daemon thread to periodically call get_meteo
        def meteo_updater():
            while True:
                self.get_meteo()
                time.sleep(600)  # 600 seconds = 10 minutes
        
        updater_thread = threading.Thread(target=meteo_updater)
        updater_thread.daemon = True  # This allows the program to exit even if the thread is running
        updater_thread.start()    
        
    def get_meteo(self):
        """
        Retrieve weather information based on the given geolocation data.

        Parameters:
        geoloc (dict): A dictionary containing geolocation data with keys:
            - lat: Latitude of the location.
            - lng: Longitude of the location.
            - latHome: Latitude of the home location.
            - lngHome: Longitude of the home location.
            - city: Name of the city.

        Returns:
        dict: Weather information from OpenWeatherMap.
        """

        # Configure language
        config_dict = get_default_config()
        config_dict['language'] = os.getenv("METEO_LANG")  # 'fr' for French language

        # Initialize the OWM object with your API key
        api_key = os.getenv('METEO_API_KEY')  # Ensure your API key is set in the environment variable
        owm = OWM(api_key, config_dict)
        mgr = owm.weather_manager()
        
        lat = self.geoloc.get('lat')
        lng = self.geoloc.get('lng')
        lat_home = float(self.geoloc.get('latHome'))
        lng_home = float(self.geoloc.get('lngHome'))
        city = self.geoloc.get('city')

        # Determine mode and coordinates
        if lat is not None and lng is not None:
            mode = 'coord'
        elif lat_home is not None and lng_home is not None:
            mode = 'coordHome'
            lat = lat_home
            lng = lng_home
        elif city is not None:
            mode = 'city'
        else:
            raise ValueError("No lat lng or home or city provided. Cannot retrieve weather infos.")

        print(f"mode = {mode}")

        if mode == 'city':
            raise NotImplementedError("City mode is not yet implemented.")
        else:  # 'coord' or 'coordHome'
            try:
                observation = mgr.weather_at_coords(lat, lng)
                weather = observation.weather
                obj = {
                    'status': weather.status,
                    'detailed_status': weather.detailed_status,
                    'temperature': weather.temperature('celsius'),
                    'humidity': weather.humidity,
                    'wind': weather.wind(),
                    'rain': weather.rain,
                    'snow': weather.snow,
                    'clouds': weather.clouds
                }
                print(obj)
                return obj
            except Exception as error:
                print("Error fetching weather data:", error)
                raise RuntimeError("Failed to fetch weather data.")
            
    def get_geoloc(self):
        ip_geo = self.get_ip_geolocation()
        if ip_geo.get('status') == 'success':
            ip_geo['latHome'] = os.getenv("IGOOR_LAT_HOME")
            ip_geo['lngHome'] = os.getenv("IGOOR_LNG_HOME")
            return ip_geo
        else:
            return {}

    def get_ip_geolocation(self):
        """
        Fetches latitude and longitude using a free IP geolocation API.

        Returns:
            A dictionary containing latitude and longitude or None if unsuccessful.
        """
        # Replace with your preferred free IP geolocation API endpoint
        try:
            url = "http://ip-api.com/json/"  # Free tier uses plain HTTP

            # Make the API request
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for unsuccessful requests (check status code)

            # Free tier response is JSON
            data = response.json()
            print(data)

            # Extract latitude and longitude (check if keys exist)
            latitude = data.get("lat")
            longitude = data.get("lon")

            if latitude and longitude:
                return data
            else:
                return None
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching geolocation: {e}")
            return None