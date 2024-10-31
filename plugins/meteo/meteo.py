from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager
import os
from pyowm.owm import OWM
from pyowm.utils.config import get_default_config
import threading
import time
import requests
from dotenv import load_dotenv
load_dotenv()
from app import context_manager
import math

class Meteo(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        
    @hookimpl
    def startup(self):
        print ("METEO IS STARTING UP")
        self.settings = self.get_my_settings()
        print ("METEO settings", self.settings)
        self.geoloc = self.get_geoloc()
        print(f"GEOlOC",self.geoloc)
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
        api_key = self.settings.get("api_key")  # Ensure your API key is set in the environment variable
        owm = OWM(api_key, config_dict)
        mgr = owm.weather_manager()
        
        lat = self.geoloc.get('lat')
        lng = self.geoloc.get('lon')

        lat_home = float(self.geoloc.get('latHome'))
        lng_home = float(self.geoloc.get('lngHome'))
        is_home = self.is_home(lat,lng,lat_home,lng_home)
        context_manager.update_context("lieu_actuel", is_home)
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

        # print(f"mode = {mode}")

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
                # print(obj)
                context_manager.update_context("meteo", obj)
                return True
            except Exception as error:
                print("Error fetching weather data:", error)
                raise RuntimeError("Failed to fetch weather data.")
    
    def is_home(self, lat, lon, lat2, lon2):
        distanceFromHome = self.calculate_distance(lat, lon, lat2, lon2)
        print(f"distance from home {distanceFromHome}")
        if distanceFromHome <= 10:
            print("Vous etes à la maison")
            self.isHome = 1
        elif distanceFromHome <= 100:
            print("Vous etes à coté de la maison (entre 10 et 100 metres)")
            self.isHome = 0
        else:
            print("Vous n'etes pas à la maison")
            self.isHome = -1
        return self.isHome
    
    def get_geoloc(self):
        ip_geo = self.get_ip_geolocation()
        if ip_geo.get('status') == 'success':
            ip_geo['latHome'] = self.settings.get("lat_home")
            ip_geo['lngHome'] = self.settings.get("lng_home")
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
            # print(data)

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
    
    def calculate_distance(self,lat1, lon1, lat2, lon2):
        print ("Calculate distance: ",lat1,lon1,lat2,lon2)
        R = 6371e3  # meters

        φ1 = math.radians(lat1)
        φ2 = math.radians(lat2)
        Δφ = φ2 - φ1
        λ1 = math.radians(lon1)
        λ2 = math.radians(lon2)
        Δλ = λ2 - λ1

        a = (math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * (math.sin(Δλ / 2) ** 2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c
        return distance
    
    def force_update(self, var1,var2):
        print ("force update", var1, var2)