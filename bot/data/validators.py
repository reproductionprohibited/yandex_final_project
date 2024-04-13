from datetime import date
import requests
from typing import Tuple


async def validate_location(
    city: str,
) -> Tuple[bool, int, str | None, int | None, int | None]:
    city = city.capitalize()

    base_url = 'https://nominatim.openstreetmap.org/search'
    params = {
        'q': city,
        'format': 'json',
    }

    headers = {
        'accept-language': 'en-US',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36'
    }

    response = requests.get(base_url, params=params, headers=headers)

    if response.status_code != 200:
        return False, response.status_code, None

    # locations = [it for it in response.json() if it['addresstype'] == 'city']
    locations = response.json()
    if len(locations) == 0:
        return False, response.status_code, None
    return (
        True,
        response.status_code,
        locations[0]['display_name'],
        float(locations[0]['lat']),
        float(locations[0]['lon']),
    )


async def validate_date(dtstr: str) -> bool:
    try:
        day, month, year = map(int, dtstr.split('-'))
        dt = date(year=year, month=month, day=day)
        if dt < date.today():
            raise ValueError()
        return True
    except ValueError:
        return False
