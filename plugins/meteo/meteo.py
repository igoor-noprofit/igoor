from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager
import os
from pyowm.owm import OWM
from pyowm.utils.config import get_default_config
import threading
import time,asyncio
import requests
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
load_dotenv()
from context_manager import context_manager
import math
# openstreetmap for automatic address to
# from geopy.geocoders import Nominatim

class Meteo(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        self.router = None
        self.updater_thread = None  # Track the weather updater thread
        self.weather_fetching_initialized = False  # Track if weather fetching has been initialized
        super().__init__(plugin_name,pm)

    def _ensure_router(self):
        """Initialize FastAPI router for plugin endpoints"""
        if self.router is not None:
            return
        self.router = APIRouter(prefix="/api/plugins/meteo", tags=["meteo"])

        @self.router.get("/validate_api_key")
        async def validate_api_key(api_key: str):
            """Validate OpenWeatherMap API key and save to settings if valid"""
            if not api_key or not api_key.strip():
                raise HTTPException(status_code=400, detail="API key is required")

            try:
                # Try to fetch weather data for Paris as a validation test
                config_dict = get_default_config()
                owm = OWM(api_key.strip(), config_dict)
                mgr = owm.weather_manager()

                # Test the API key by fetching weather for Paris coordinates
                observation = mgr.weather_at_coords(48.8566, 2.3522)  # Paris coordinates

                # On successful validation, save API key to settings and restart weather fetching
                self.save_api_key_to_settings(api_key.strip())

            except Exception as e:
                error_msg = str(e).lower()
                if 'unauthorized' in error_msg or 'invalid api key' in error_msg:
                    raise HTTPException(status_code=400, detail="Invalid API Key")
                elif 'timeout' in error_msg or 'connection' in error_msg:
                    raise HTTPException(status_code=400, detail="Connection error: could not validate API key")
                else:
                    raise HTTPException(status_code=400, detail=f"API Key validation failed: {str(e)}")
            return {"valid": True}
            

        @self.router.get("/geocode_address")
        async def geocode_address(address: str):
            """Geocode an address using Nominatim (OpenStreetMap)"""
            if not address or not address.strip():
                raise HTTPException(status_code=400, detail="Address is required for geocoding")

            try:
                # Use Nominatim (OpenStreetMap) for geocoding - no API key required
                url = "https://nominatim.openstreetmap.org/search"
                params = {
                    "q": address.strip(),
                    "format": "json",
                    "limit": 1,
                    "addressdetails": 1
                }
                headers = {
                    "User-Agent": "IGOOR/1.0",
                    "Referer": "https://igoor.local"
                }

                response = requests.get(url, params=params, headers=headers, timeout=8)
                response.raise_for_status()
                data = response.json()

                if data and len(data) > 0:
                    # Take the first (best) match
                    result = data[0]
                    return {
                        "lat": float(result["lat"]),
                        "lon": float(result["lon"]),
                        "name": result.get("display_name", ""),
                        "country": result.get("address", {}).get("country", "")
                    }
                else:
                    raise HTTPException(status_code=404, detail="Address not found")

            except requests.exceptions.Timeout:
                raise HTTPException(status_code=400, detail="Could not connect to geocoding service (timeout)")
            except requests.exceptions.ConnectionError:
                raise HTTPException(status_code=400, detail="Could not connect to geocoding service")
            except requests.exceptions.HTTPError as e:
                raise HTTPException(status_code=400, detail=f"Geocoding failed: HTTP error {str(e)}")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Geocoding failed: {str(e)}")

    @hookimpl
    def startup(self):
        print("METEO IS STARTING UP")
        self._ensure_router()
        # Register router with the main FastAPI app if available
        if hasattr(self, 'pm') and hasattr(self.pm, 'fastapi_app'):
            self.pm.fastapi_app.include_router(self.router)

        self.settings = self.get_my_settings()
        print("METEO settings", self.settings)
        self.geoloc = self.get_geoloc()
        print(f"GEOLOC", self.geoloc)

        # Check if the user has a non-empty api_key, lat_home, and lng_home
        api_key = self.settings.get("api_key")
        lat_home = self.settings.get("lat_home")
        lng_home = self.settings.get("lng_home")

        if not api_key or not lat_home or not lng_home:
            print("Missing required METEO settings: api_key, lat_home, or lng_home.")
            return
        self.schedule_meteo_updates()
        
        # Use a separate thread to handle the sleep and async call
        def delayed_meteo():
            time.sleep(30)  # Sleep for 30 seconds without blocking the main thread
            try:
                asyncio.run(self.get_meteo())
            except Exception as e:
                # Protect the delayed starter from bubbling exceptions
                print("METEO delayed initial fetch failed:", e)

        threading.Thread(target=delayed_meteo, daemon=True).start()
        self.weather_fetching_initialized = True  # Mark that weather fetching has been initialized
        # Plugin-specific initialization logic

        
    def schedule_meteo_updates(self):
        # Use a daemon thread to periodically call get_meteo
        def meteo_updater():
            while True:
                try:
                    asyncio.run(self.get_meteo())
                    time.sleep(600)  # 600 seconds = 10 minutes
                except Exception as e:
                    # Log and keep the updater alive. On error, wait a bit and retry.
                    print("METEO updater exception (will retry):", e)
                    time.sleep(60)
        
        updater_thread = threading.Thread(target=meteo_updater,daemon=True)
        updater_thread.daemon = True  # This allows the program to exit even if the thread is running
        self.updater_thread = updater_thread  # Save reference to updater thread
        self.updater_thread.start()

    def restart_weather_fetching(self):
        """Restart weather fetching when API key is added or changed"""
        print("METEO: Restarting weather fetching")
        # Stop existing updater thread if running
        if self.updater_thread and self.updater_thread.is_alive():
            print("METEO: Stopping existing updater thread")
            # Daemon threads will stop automatically when main thread exits,
            # but we need to wait for the next iteration
            # We'll just start a new one and let the old one die naturally
            # The daemon property handles cleanup

        # Reload settings to get the new API key
        self.settings = self.get_my_settings()
        print("METEO settings (reloaded):", self.settings)
        # Don't fetch geolocation from network
        # User will provide lat/lng via UI geocoding or manual entry
        # Build geolocation dict from settings
        
        self.get_geoloc()
        
        print(f"GEOLOC (built from settings):", self.geoloc)

        # Check if required settings are now available
        api_key = self.settings.get("api_key")
        lat_home = self.settings.get("lat_home")
        lng_home = self.settings.get("lng_home")

        if api_key:
            # Required settings are available, start weather fetching
            self.schedule_meteo_updates()
        else:
            print("METEO: Still missing required settings, not starting weather fetching")
            print(f"  api_key present: {bool(api_key)}")


    def save_api_key_to_settings(self, api_key: str):
        """Save API key to settings file"""
        print("METEO: Saving API key to settings file")

        # Save API key using the correct update_my_settings signature
        self.update_my_settings('api_key', api_key)

        # Update local settings cache
        self.settings['api_key'] = api_key
        print(f"METEO: API key saved to settings: {api_key}")

    def update_my_settings(self, key: str, value: any):
        """Override base update to restart weather fetching when settings are saved"""
        # Call parent update to save to disk
        super().update_my_settings(key, value)

        # Update local settings cache
        self.settings[key] = value
        print(f"METEO: Setting {key} updated to: {value}")

        # When settings are saved, check if we should start weather fetching
        # Only requirement is API key - lat_home and lng_home are optional (for "at home" detection)
        api_key = self.settings.get("api_key")

        if api_key:
            print("METEO: API key present, starting weather fetching")
            self.restart_weather_fetching()
        else:
            print(f"METEO: API key missing, not starting weather fetching")

    async def get_meteo(self):
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
        config_dict['language'] = self.lang

        # Initialize the OWM object with your API key
        api_key = self.settings.get("api_key")  # Ensure your API key is set in the environment variable
        owm = OWM(api_key, config_dict)
        mgr = owm.weather_manager()
        
        lat = self.geoloc.get('lat')
        lng = self.geoloc.get('lon')

        lat_home_val = self.geoloc.get('latHome')
        lng_home_val = self.geoloc.get('lngHome')
        lat_home = float(lat_home_val) if lat_home_val else None
        lng_home = float(lng_home_val) if lng_home_val else None

        is_home = self.is_home(lat,lng,lat_home,lng_home) if lat_home and lng_home else False
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
            # Simple retry loop with exponential backoff using only existing imports
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    observation = mgr.weather_at_coords(lat, lng)
                    weather = observation.weather
                    temp = weather.temperature('celsius')
                    synthesized = {
                        'status': weather.detailed_status,
                        'temperature': {
                            'temp': round(temp.get('temp', 0), 1),
                            'feels_like': round(temp.get('feels_like', 0), 1)
                        },
                        'humidity': weather.humidity,
                        'wind': self.synthesize_wind(weather.wind()),
                        'rain': weather.rain if weather.rain else {},
                        'snow': weather.snow if weather.snow else {},
                    }
                    context_manager.update_context("meteo", synthesized)
                    self.send_message_to_frontend(synthesized)
                    return True
                except Exception as error:
                    msg = str(error).lower()
                    # Consider it transient if it mentions timeout/handshake/read timed out
                    is_timeout_like = 'timeout' in msg or 'handshake' in msg or 'read timed out' in msg
                    print(f"METEO fetch attempt {attempt} failed:", error)
                    if is_timeout_like and attempt < max_retries:
                        # exponential backoff: 1, 2, 4 seconds
                        wait = 2 ** (attempt - 1)
                        print(f"METEO transient error detected, retrying in {wait}s...")
                        time.sleep(wait)
                        continue
                    else:
                        # On persistent timeout or any non-retryable error, update context and notify frontend
                        error_type = 'timeout' if is_timeout_like else 'failed'
                        context_manager.update_context("meteo", {'error': error_type})
                        try:
                            self.send_message_to_frontend({'error': error_type})
                        except Exception:
                            pass
                        # Do not raise here — caller (the updater thread) should stay alive
                        return False

    def synthesize_wind(self, wind_dict):
        speed = wind_dict.get('speed', 0)
        if speed > 8:
            strength = 'strong'
        elif speed > 3:
            strength = 'moderate'
        else:
            strength = 'light'
        return {'strength': strength}
    
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
        if ip_geo is not None and ip_geo.get('status') == 'success':
            # Only set latHome and lngHome if they have actual values
            # Don't use empty strings - will cause float conversion errors
            lat_home = self.settings.get("lat_home")
            lng_home = self.settings.get("lng_home")
            if lat_home and lng_home:  # Check they're not empty
                ip_geo['latHome'] = lat_home
                ip_geo['lngHome'] = lng_home
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
        
    '''
    def get_lat_lng(address):
        geolocator = Nominatim(user_agent="igoor")
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
        else:
            return None, None

        address = "76, rue Beaubourg 75003 Paris"
        lat, lng = get_lat_lng(address)
        print(f"Latitude: {lat}, Longitude: {lng}")

    '''