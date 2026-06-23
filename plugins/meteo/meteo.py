from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager
import os
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

# WMO weather interpretation codes -> localized descriptions.
# Replaces pyowm's server-side detailed_status localization.
# Keys match the locale folder names (en_EN / fr_FR / it_IT).
WMO_DESCRIPTIONS = {
    0:  {"en_EN": "Clear sky",                   "fr_FR": "Ciel dégagé",                "it_IT": "Cielo sereno"},
    1:  {"en_EN": "Mainly clear",                "fr_FR": "Plutôt dégagé",              "it_IT": "Prevalentemente sereno"},
    2:  {"en_EN": "Partly cloudy",               "fr_FR": "Partiellement nuageux",      "it_IT": "Parzialmente nuvoloso"},
    3:  {"en_EN": "Overcast",                    "fr_FR": "Couvert",                    "it_IT": "Cielo coperto"},
    45: {"en_EN": "Fog",                         "fr_FR": "Brouillard",                 "it_IT": "Nebbia"},
    48: {"en_EN": "Depositing rime fog",         "fr_FR": "Brouillard givrant",         "it_IT": "Nebbia con brina"},
    51: {"en_EN": "Light drizzle",               "fr_FR": "Bruine légère",              "it_IT": "Pioviggine leggera"},
    53: {"en_EN": "Moderate drizzle",            "fr_FR": "Bruine modérée",             "it_IT": "Pioviggine moderata"},
    55: {"en_EN": "Dense drizzle",               "fr_FR": "Bruine dense",               "it_IT": "Pioviggine fitta"},
    56: {"en_EN": "Light freezing drizzle",      "fr_FR": "Bruine verglaçante légère",  "it_IT": "Pioviggine gelata leggera"},
    57: {"en_EN": "Dense freezing drizzle",      "fr_FR": "Bruine verglaçante dense",   "it_IT": "Pioviggine gelata fitta"},
    61: {"en_EN": "Slight rain",                 "fr_FR": "Pluie légère",               "it_IT": "Pioggia debole"},
    63: {"en_EN": "Moderate rain",               "fr_FR": "Pluie modérée",              "it_IT": "Pioggia moderata"},
    65: {"en_EN": "Heavy rain",                  "fr_FR": "Forte pluie",                "it_IT": "Pioggia forte"},
    66: {"en_EN": "Light freezing rain",         "fr_FR": "Pluie verglaçante légère",   "it_IT": "Pioggia gelata leggera"},
    67: {"en_EN": "Heavy freezing rain",         "fr_FR": "Forte pluie verglaçante",    "it_IT": "Pioggia gelata forte"},
    71: {"en_EN": "Slight snow fall",            "fr_FR": "Légères chutes de neige",    "it_IT": "Debole nevicata"},
    73: {"en_EN": "Moderate snow fall",          "fr_FR": "Chutes de neige modérées",   "it_IT": "Nevicata moderata"},
    75: {"en_EN": "Heavy snow fall",             "fr_FR": "Fortes chutes de neige",     "it_IT": "Forte nevicata"},
    77: {"en_EN": "Snow grains",                 "fr_FR": "Grains de neige",            "it_IT": "Granelli di neve"},
    80: {"en_EN": "Slight rain showers",         "fr_FR": "Averses légères",            "it_IT": "Rovesci deboli"},
    81: {"en_EN": "Moderate rain showers",       "fr_FR": "Averses modérées",           "it_IT": "Rovesci moderati"},
    82: {"en_EN": "Violent rain showers",        "fr_FR": "Averses violentes",          "it_IT": "Rovesci violenti"},
    85: {"en_EN": "Slight snow showers",         "fr_FR": "Averses de neige légères",   "it_IT": "Rovesci di neve deboli"},
    86: {"en_EN": "Heavy snow showers",          "fr_FR": "Averses de neige fortes",    "it_IT": "Rovesci di neve forti"},
    95: {"en_EN": "Thunderstorm",                "fr_FR": "Orage",                      "it_IT": "Temporale"},
    96: {"en_EN": "Thunderstorm with slight hail","fr_FR": "Orage avec légère grêle",   "it_IT": "Temporale con leggera grandine"},
    99: {"en_EN": "Thunderstorm with heavy hail","fr_FR": "Orage avec forte grêle",     "it_IT": "Temporale con forte grandine"},
}

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
        self._ensure_router()
        # Register router with the main FastAPI app if available
        if hasattr(self, 'pm') and hasattr(self.pm, 'fastapi_app'):
            self.pm.fastapi_app.include_router(self.router)
        self.settings = self.get_my_settings()
        print("METEO settings", self.settings)
        self.geoloc = self.get_geoloc()
        print(f"GEOLOC", self.geoloc)

        # Open-Meteo requires no API key. Start fetching as long as we have a
        # location: current coords (IP geolocation) or home coords (settings).
        has_current = self.geoloc.get('lat') and self.geoloc.get('lon')
        lat_home = self.settings.get("lat_home")
        lng_home = self.settings.get("lng_home")
        if not (has_current or (lat_home and lng_home)):
            print("Missing location for METEO weather (no IP geolocation and no home coordinates).")
            return
        self.schedule_meteo_updates()
        self.mark_ready()

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
        """Restart weather fetching when location settings change"""
        print("METEO: Restarting weather fetching")
        # Stop existing updater thread if running
        if self.updater_thread and self.updater_thread.is_alive():
            print("METEO: Stopping existing updater thread")
            # Daemon threads will stop automatically when main thread exits,
            # but we need to wait for the next iteration
            # We'll just start a new one and let the old one die naturally
            # The daemon property handles cleanup

        # Reload settings to get the new location
        self.settings = self.get_my_settings()
        print("METEO settings (reloaded):", self.settings)
        # Don't fetch geolocation from network
        # User will provide lat/lng via UI geocoding or manual entry
        # Build geolocation dict from settings

        self.get_geoloc()

        print(f"GEOLOC (built from settings):", self.geoloc)

        # Open-Meteo needs no API key; fetching only requires a location
        self.schedule_meteo_updates()


    def update_my_settings(self, key: str, value: any):
        """Override base update to restart weather fetching when settings are saved"""
        # Call parent update to save to disk
        super().update_my_settings(key, value)

        # Update local settings cache
        self.settings[key] = value
        print(f"METEO: Setting {key} updated to: {value}")

        # Restart weather fetching on any settings change (e.g. a new home address)
        print("METEO: Settings changed, restarting weather fetching")
        self.restart_weather_fetching()

    async def get_meteo(self):
        """
        Retrieve current weather information from Open-Meteo (no API key required)
        based on the given geolocation data.

        Parameters:
        geoloc (dict): A dictionary containing geolocation data with keys:
            - lat: Latitude of the location.
            - lng: Longitude of the location.
            - latHome: Latitude of the home location.
            - lngHome: Longitude of the home location.
            - city: Name of the city.

        Returns:
        dict: Weather information from Open-Meteo, written to context_manager and
              pushed to the frontend.
        """

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
                    url = "https://api.open-meteo.com/v1/forecast"
                    params = {
                        "latitude": lat,
                        "longitude": lng,
                        "current": (
                            "temperature_2m,apparent_temperature,relative_humidity_2m,"
                            "wind_speed_10m,rain,snowfall,weather_code"
                        ),
                        "temperature_unit": "celsius",
                        # keep m/s so synthesize_wind thresholds (>3 / >8) stay valid
                        "wind_speed_unit": "ms",
                    }
                    response = requests.get(url, params=params, timeout=10)
                    response.raise_for_status()
                    current = response.json()["current"]

                    # Open-Meteo returns snowfall in cm; convert to mm to match rain
                    rain_mm = current.get("rain") or 0.0
                    snow_cm = current.get("snowfall") or 0.0

                    synthesized = {
                        'status': self._describe_weather_code(current.get("weather_code")),
                        'temperature': {
                            'temp': round(current.get("temperature_2m", 0), 1),
                            'feels_like': round(current.get("apparent_temperature", 0), 1)
                        },
                        'humidity': current.get("relative_humidity_2m", 0),
                        'wind': self.synthesize_wind({'speed': current.get("wind_speed_10m", 0)}),
                        'rain': {'1h': rain_mm} if rain_mm else {},
                        'snow': {'1h': round(snow_cm * 10, 1)} if snow_cm else {},
                    }
                    context_manager.update_context("meteo", synthesized)
                    self.send_message_to_frontend(synthesized)
                    return True
                except Exception as error:
                    msg = str(error).lower()
                    # Consider it transient if it mentions timeout/handshake/connection
                    is_timeout_like = ('timeout' in msg or 'handshake' in msg
                                       or 'read timed out' in msg or 'connection' in msg)
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

    def _describe_weather_code(self, code):
        """Map a WMO weather code to a localized description (falls back to English)."""
        if code is None:
            return "Unknown"
        entry = WMO_DESCRIPTIONS.get(int(code))
        if not entry:
            return "Unknown"
        return entry.get(self.lang) or entry.get("en_EN") or "Unknown"

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
