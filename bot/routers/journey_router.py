from datetime import date
import os
from pprint import pprint
from typing import Dict, List, Tuple

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, FSInputFile
from aiogram.utils.markdown import hitalic
import openmeteo_requests
import pandas as pd
import requests
import requests_cache
from retry_requests import retry
from staticmap import Line, StaticMap, CircleMarker

from data.crud import (
    create_journey,
    create_location,
    get_all_user_journeys,
    get_journey_by_title,
    get_location_by_journey_place_datestart_dateend,
    get_user_by_telegram_userid,
    delete_journey,
    delete_location_from_journey,
    update_journey,
    update_location,
)
from data.models import Location, User
from data.validators import validate_location, validate_date
from ux.keyboards import (
    DEFAULT_KEYBOARD,
    EDIT_JOURNEY_PARAMS_KEYBOARD,
    EDIT_LOCATION_PARAMS_KEYBOARD,
    JOURNEY_INFO_KEYBOARD,
    journey_list_keyboard,
    journey_location_list_keyboard,
)
from ux.typical_answers import DATE_CONFLICTS_WITH_ANOTHER_DATE
from settings import ROOT, session

cache_session = requests_cache.CachedSession('temp_files/.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

user_agent_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36'
}

def datestr_to_date(datestr: str) -> date:
    year, month, day = map(int, datestr.split('-'))
    return date(year=year, month=month, day=day)


async def fetch_single_route(
    start_coords: Tuple[float, float],
    end_coords: Tuple[float, float],
) -> List[Tuple[float]]:
    start_longitude, start_latitude = start_coords
    end_longitude, end_latitude = end_coords
    url = f'https://router.project-osrm.org/route/v1/driving/{start_longitude},{start_latitude};{end_longitude},{end_latitude}?steps=true'
    response = requests.get(url, headers=user_agent_headers)
    data = response.json()

    if data['code'] != 'Ok':
        return [start_coords, end_coords]
    
    mid_coords = []
    for step in data['routes'][0]['legs'][0]['steps']:
        coords = tuple(step['maneuver']['location'])
        mid_coords.append(coords)
    
    return [start_coords] + mid_coords + [end_coords]


async def fetch_route(coords: List[Tuple[float]]) -> List[Tuple[float]]:
    points = []
    point_A = coords[0]
    for point_B in coords:
        newpts = await fetch_single_route(start_coords=point_A, end_coords=point_B)
        points += newpts
        point_A = point_B
    return points


async def save_map_to_png(
    user: User,
    locations: List[Location],
) -> None:
    coords = [(user.lon, user.lat)] + [(location.lon, location.lat) for location in locations]

    m = StaticMap(1000, 1000, 10)
    for lon, lat in coords:
        m.add_marker(CircleMarker((lon, lat), 'blue', 12))

    route = await fetch_route(coords=coords)

    point_A = route[0]
    for coord in route:
        point_B = coord
        m.add_line(Line([point_A, point_B], 'black', 3))
        point_A = point_B
    
    image = m.render()
    image.save(f'{ROOT}/bot/temp_files/map.png')


async def delete_map() -> None:
    os.remove(path=f'{ROOT}/bot/temp_files/map.png')


async def fetch_restaurants_near_location(
    location: Location,
    radius_meters: int = 5_000,
    language: str = 'en',
) -> List[str] | None:
    overpass_url = 'http://overpass-api.de/api/interpreter'

    latitude, longitude = location.lat, location.lon

    overpass_query = f'''
        [out:json][timeout:25];
        (
            node["amenity"="restaurant"](around:{radius_meters},{latitude},{longitude});
            way["amenity"="restaurant"](around:{radius_meters},{latitude},{longitude});
            relation["amenity"="restaurant"](around:{radius_meters},{latitude},{longitude});
        );
        out tags;
    '''
    response = requests.post(overpass_url, data=overpass_query, headers=user_agent_headers)
    if response.status_code == 200:
        json = response.json()
        restaurants = []
        for restaurant in json['elements']:
            if 'tags' in restaurant and 'name' in restaurant['tags']:
                name = restaurant['tags'].get(f'name:{language}', restaurant['tags']['name'])
                restaurants.append(name)
        return sorted(restaurants)[:5]
    else:
        return None


async def fetch_sights_near_location(
    location: Location,
    radius_meters: int = 15_000
) -> List[str] | None:
    overpass_url = 'http://overpass-api.de/api/interpreter'

    latitude, longitude = location.lat, location.lon

    overpass_query = f'''
        [out:json];
        node["tourism"="attraction"](around:{radius_meters},{latitude},{longitude});
        way["tourism"="attraction"](around:{radius_meters},{latitude},{longitude});
        relation["tourism"="attraction"](around:{radius_meters},{latitude},{longitude});
        out;
    '''
    response = requests.post(overpass_url, data=overpass_query, headers=user_agent_headers)
    if response.status_code == 200:
        sights = []
        json = response.json()
        for place in json['elements']:
            if 'tags' in place and 'name' in place['tags']:
                sights.append(place['tags']['name'])
        if len(sights) == 0:
            return None
        return sorted(sights)[:5]
    else:
        return None


async def fetch_hotels_near_location(
    location: Location,
    radius_meters: int = 1000,
) -> List[str] | None:
    overpass_url = 'http://overpass-api.de/api/interpreter'
    
    latitude = location.lat
    longitude = location.lon

    overpass_query = f'''
        [out:json];
        node["tourism"="hotel"](around:{radius_meters},{latitude},{longitude});
        out;
    '''
    response = requests.post(overpass_url, data=overpass_query, headers=user_agent_headers)
    if response.status_code == 200:
        pprint(response.json(), stream=open('debug.txt', mode='w'))
        hotel_names = []
        for hotel in response.json()['elements']:
            if 'tags' in hotel and 'name' in hotel['tags']:
                hotel_names.append(hotel['tags']['name'])
        if len(hotel_names) == 0:
            return None
        return sorted(hotel_names)[:5]
    else:
        return None


async def fetch_weather_data(location: Location) -> List[Dict[str, float]]:
    start_date = location.date_start
    end_date = location.date_end
    lat = location.lat
    lon = location.lon

    url = 'https://api.open-meteo.com/v1/forecast'
    params = {
        'latitude': lat,
        'longitude': lon,
        'hourly': 'temperature_2m',
        'start_date': str(start_date),
        'end_date': str(end_date),
    }
    try:
        responses = openmeteo.weather_api(url, params=params)

        response = responses[0]

        hourly = response.Hourly()
        hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()

        hourly_data = {'date': pd.date_range(
            start = pd.to_datetime(hourly.Time(), unit = 's', utc = True),
            end = pd.to_datetime(hourly.TimeEnd(), unit = 's', utc = True),
            freq = pd.Timedelta(seconds = hourly.Interval()),
            inclusive = 'left',
        )}
        hourly_data['temperature_2m'] = hourly_temperature_2m

        hourly_dataframe = pd.DataFrame(data = hourly_data)
        hourly_dataframe['date'] = hourly_dataframe['date'].apply(lambda x: str(x).split()[0])
        grouped = hourly_dataframe.groupby('date').mean().reset_index()

        weathers = []
        for i in range(len(grouped)):
            weathers.append({
                'date': grouped.iloc[i, 0],
                'temperature_2m': f'{round(float(grouped.iloc[i, 1]), 1)} ºC',
            })
        return weathers
    except Exception:
        return None


journey_router = Router()


class JourneyCreateForm(StatesGroup):
    title = State()
    description = State()


class JourneyInfoForm(StatesGroup):
    to_title = State()
    to_info = State()


class LocationCreateForm(StatesGroup):
    journey = State()
    location = State()
    date_start = State()
    date_end = State()


class LocationRemoveForm(StatesGroup):
    to_journey = State()
    to_remove = State()


class JourneyEditForm(StatesGroup):
    to_select_journey = State()
    to_choose_parameter_edit = State()
    to_start_edit = State()
    to_edit = State()

    to_edit_location = State()
    to_input_edit_info_location = State()


class JourneyRemoveForm(StatesGroup):
    to_select_journey = State()
    to_remove = State()


''' Create New Journey Func Group '''
@journey_router.message(Command(commands=['create_journey']))
async def start_create_journey(message: Message, state: FSMContext) -> None:
    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    if user is None:
        await state.clear()
        await message.answer('🤓 You are not signed up!. Use /start', reply_markup=DEFAULT_KEYBOARD)
    else:
        await state.set_state(JourneyCreateForm.title)
        await state.update_data(user=user)
        await message.answer(
            '✍️ Provide some information about your trip. What would you call it?',
            reply_markup=DEFAULT_KEYBOARD,
        )


@journey_router.message(JourneyCreateForm.title)
async def set_title_journey(message: Message, state: FSMContext) -> None:
    title = message.text

    data = await state.get_data()
    user = data['user']

    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)
    
    if len(title) > 50:
        await message.answer(
            '🫨 That is too long for a title! Maybe we could try something shorter?',
            reply_markup=DEFAULT_KEYBOARD,
        )
    elif title in [journey.title for journey in journeys]:
        await message.answer(
            '🫨 You already have such a journey. Please try another title',
            reply_markup=DEFAULT_KEYBOARD,
        )
    else:
        await state.set_state(JourneyCreateForm.description)
        await state.update_data(title=title)
        await message.answer(
            '✍️ Nice title! Now tell me more about it',
            reply_markup=DEFAULT_KEYBOARD,
        )


@journey_router.message(JourneyCreateForm.description)
async def set_description_journey(message: Message, state: FSMContext) -> None:
    description = message.text
    if len(description) > 100:
        await message.answer(
            '🫨 That is too long for a description! Maybe we could try something shorter?',
            reply_markup=DEFAULT_KEYBOARD,
        )
    else:
        data = await state.update_data(description=description)
        user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
        await create_journey(
            db_session=session,
            owner_id=user.id,
            title=data['title'],
            description=data['description'],
        )
        await end_create_journey(message=message, state=state)


async def end_create_journey(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        '✅ New journey created! If you want to add locations, try /add_location',
        reply_markup=DEFAULT_KEYBOARD,
    )


''' Get All User Journeys '''
@journey_router.message(Command(commands=['journey_list']))
async def get_journeys(message: Message) -> None:
    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)
    text = ''
    if len(journeys) == 0:
        await message.answer(
            '⚠️ You do not have any journeys planned yet. To create one, use /create_journey',
            reply_markup=DEFAULT_KEYBOARD,
        )
    else:
        for journey in journeys:
            text += f'{journey.title}\n{journey.description}\n\nLocations:\n'
            if len(journey.locations) == 0:
                text += '🫨 No locations added for now\n'
            else:
                for location in journey.locations:
                    text += (
                        f'{location.place}\n{location.date_start} - {location.date_end}\n'
                    )

            text += '-----\n'
        await message.answer(f'🗒️ Your journeys:\n\n{text}', reply_markup=DEFAULT_KEYBOARD)


''' Get a Particular Journey Info Func Group '''
@journey_router.message(Command(commands=['journey_info']))
async def start_get_journey(message: Message, state: FSMContext) -> None:
    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)

    if len(journeys) > 0:
        keyboard = journey_list_keyboard(journey_list=journeys)
        await state.set_state(JourneyInfoForm.to_title)
        await message.answer('🧐 Which journey do you want to know about?', reply_markup=keyboard)
    else:
        await state.clear()
        await message.answer(
            '🤓 First, you should create a journey. Use /create_journey',
            reply_markup=DEFAULT_KEYBOARD,
        )


@journey_router.message(JourneyInfoForm.to_title)
async def get_journey_info(message: Message, state: FSMContext) -> None:
    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journey = await get_journey_by_title(db_session=session, journey_title=message.text, owner_id=user.id)
    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)

    if journey is None or journey not in journeys:
        keyboard = journey_list_keyboard(journey_list=journeys)
        await message.answer(
            '⚠️ You do not have such journey. Use the buttons', reply_markup=keyboard
        )
    elif len(journey.locations) > 0:
        await state.set_state(JourneyInfoForm.to_info)
        await state.update_data(journey=journey, user=user)
        await message.answer(
            '🧐 What exactly do you want to know?',
            reply_markup=JOURNEY_INFO_KEYBOARD,
        )
    else:
        await state.clear()
        await message.answer(
            '⚠️ There are no locations added to this journey. Use /add_location',
            reply_markup=DEFAULT_KEYBOARD,
        )


@journey_router.message(JourneyInfoForm.to_info)
async def display_journey_info(message: Message, state: FSMContext) -> None:
    info_request = message.text
    if info_request == 'Location List':
        data = await state.get_data()
        journey = data['journey']
        
        lines = [f'ℹ️ Journey {journey.title}\n{journey.description}\n---']
        
        locations: List[Location] = list(journey.locations)
        locations.sort(key=lambda location: location.date_start)

        for location in locations:
            lines += [
                f'{location.place}',
                f'{location.date_start} -- {location.date_end}',
                '---',
            ]
        
        await message.answer('\n'.join(lines), reply_markup=DEFAULT_KEYBOARD)
        await state.clear()
    elif info_request == 'Weather':
        data = await state.get_data()
        journey = data['journey']

        lines = [f'ℹ️ Journey {journey.title}\n{journey.description}\n---']
        
        locations = journey.locations
        locations.sort(key=lambda location: location.date_start)

        for location in locations:
            lines.append(hitalic(location.place))
            weathers = await fetch_weather_data(location=location)

            if weathers is None:
                lines.append('Something went wrong. Come back later\n')
            else:
                lines.append('Average daily temperatures:')
                for weather in weathers:
                    lines.append(f'{weather["date"]} : {weather["temperature_2m"]}')
            lines.append('\n')
        
        await message.answer('\n'.join(lines), reply_markup=DEFAULT_KEYBOARD)
        await state.clear()
    elif info_request == 'Sightseeing':
        data = await state.get_data()
        journey = data['journey']

        lines = [f'ℹ️ Journey {journey.title}\n{journey.description}\n---']

        locations = journey.locations
        locations.sort(key=lambda location: location.date_start)

        for location in locations:
            lines.append(hitalic(location.place))
            sights = await fetch_sights_near_location(
                location=location,
            )
            if sights is None:
                lines.append('No sightseeing places found nearby')
            else:
                lines.append('Sights nearby:')
                for sight in sights:
                    lines.append(sight)
            lines.append('\n')
        
        await message.answer('\n'.join(lines), reply_markup=DEFAULT_KEYBOARD)
        await state.clear()
    elif info_request == 'Hotels':
        data = await state.get_data()
        journey = data['journey']

        lines = [f'ℹ️ Journey {journey.title}\n{journey.description}\n---']

        locations = journey.locations
        locations.sort(key=lambda location: location.date_start)

        for location in locations:
            lines.append(hitalic(location.place))
            hotel_names = await fetch_hotels_near_location(
                location=location,
                radius_meters=7_000,
            )
            if hotel_names is None:
                lines.append('No hotels found nearby')
            else:
                lines.append('Hotels nearby:')
                for hotel_name in hotel_names:
                    lines.append(hotel_name)
            lines.append('\n')
        
        await message.answer('\n'.join(lines), reply_markup=DEFAULT_KEYBOARD)
        await state.clear()
    elif info_request == 'Restaurants':
        data = await state.get_data()
        journey = data['journey']

        lines = [f'ℹ️ Journey {journey.title}\n{journey.description}\n---']

        locations = journey.locations
        locations.sort(key=lambda location: location.date_start)
        
        for location in locations:
            lines.append(hitalic(location.place))
            restaurants = await fetch_restaurants_near_location(
                location=location,
            )
            if restaurants is None:
                lines.append('No restaurants found nearby')
            else:
                lines.append('Restaurants nearby:')
                for restaurant in restaurants:
                    lines.append(restaurant)
            lines.append('\n')
        await message.answer('\n'.join(lines), reply_markup=DEFAULT_KEYBOARD)
        await state.clear()
    elif info_request == 'Map Route':
        data = await state.get_data()
        journey = data['journey']
        user = data['user']

        locations = list(journey.locations)
        locations.sort(key=lambda location: location.date_start)

        await message.answer('Loading... Please, wait a second')
        await save_map_to_png(locations=journey.locations, user=user)
        photo = FSInputFile(f'{ROOT}/bot/temp_files/map.png')
        await message.answer_photo(photo)
        await delete_map()
        await state.clear()
    else:
        await message.answer('🤓 Use the buttons, please', reply_markup=JOURNEY_INFO_KEYBOARD)


''' Start Adding Locations Func Group '''
@journey_router.message(Command(commands=['add_location']))
async def start_add_location(message: Message, state: FSMContext) -> None:
    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)

    if len(journeys) > 0:
        keyboard = journey_list_keyboard(journey_list=journeys)

        await state.set_state(LocationCreateForm.journey)
        await message.answer(
            '🧐 So, you want to add a new location. To which journey do you want to add location?',
            reply_markup=keyboard,
        )
    else:
        await state.clear()
        await message.answer(
            '🤓 First, you should create a journey. Use /create_journey',
            reply_markup=DEFAULT_KEYBOARD,
        )


@journey_router.message(LocationCreateForm.journey)
async def set_journey_location(message: Message, state: FSMContext) -> None:
    journey_title = message.text
    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)

    if journey_title not in [journey.title for journey in journeys]:
        keyboard = journey_list_keyboard(journey_list=journeys)
        await message.answer('🤓 Invalid journey. Use the buttons', reply_markup=keyboard)
    else:
        await state.set_state(LocationCreateForm.location)
        await state.update_data(journey=journey_title)
        await message.answer(
            f'🧐 A new location to visit! Where is it?',
            reply_markup=DEFAULT_KEYBOARD,
        )


@journey_router.message(LocationCreateForm.location)
async def set_place_location(message: Message, state: FSMContext) -> None:
    place = message.text
    is_valid, _, placename, lat, lon = await validate_location(city=place)

    if is_valid:
        await state.set_state(LocationCreateForm.date_start)
        await state.update_data(place=placename, lat=lat, lon=lon)
        await message.answer(
            'So, when are you going to go there? DD-MM-YYYY format 😉',
            reply_markup=DEFAULT_KEYBOARD,
        )
    else:
        await message.answer(
            '🫨 Invalid location. Are you sure you entered an existing location?',
            reply_markup=DEFAULT_KEYBOARD,
        )


@journey_router.message(LocationCreateForm.date_start)
async def set_date_start_location(message: Message, state: FSMContext) -> None:
    datestr = message.text
    try:
        if not await validate_date(datestr):
            raise ValueError()

        day, month, year = map(int, datestr.split('-'))
        dt = date(year=year, month=month, day=day)
        await state.set_state(LocationCreateForm.date_end)
        await state.update_data(date_start=dt)
        await message.answer(
            'Good! When do you plan to leave the place? DD-MM-YYYY format 😉', reply_markup=DEFAULT_KEYBOARD
        )
    except ValueError as e:
        if str(e) == DATE_CONFLICTS_WITH_ANOTHER_DATE:
            await message.answer(str(e), reply_markup=DEFAULT_KEYBOARD)
            return
        await message.answer('🫨 Invalid date, try again', reply_markup=DEFAULT_KEYBOARD)


@journey_router.message(LocationCreateForm.date_end)
async def set_date_end_location(message: Message, state: FSMContext) -> None:
    datestr = message.text
    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)

    try:
        if not await validate_date(datestr):
            raise ValueError()

        day, month, year = map(int, datestr.split('-'))
        dt = date(year=year, month=month, day=day)
        data = await state.update_data(date_end=dt)
        date_start = data['date_start']

        if date_start > dt:
            raise ValueError(DATE_CONFLICTS_WITH_ANOTHER_DATE)

        await create_location(
            db_session=session,
            place=data['place'],
            date_start=data['date_start'],
            date_end=data['date_end'],
            lat=data['lat'],
            lon=data['lon'],
            journey=await get_journey_by_title(
                db_session=session, journey_title=data['journey'], owner_id=user.id
            ),
        )
        await finish_add_location(message=message, state=state)
    except ValueError as e:
        if str(e) == DATE_CONFLICTS_WITH_ANOTHER_DATE:
            await message.answer(
                DATE_CONFLICTS_WITH_ANOTHER_DATE, reply_markup=DEFAULT_KEYBOARD
            )
            return
        await message.answer('🫨 Invalid date, try again', reply_markup=DEFAULT_KEYBOARD)


async def finish_add_location(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        '✅ New location added. If you want to add another one, call /add_location',
        reply_markup=DEFAULT_KEYBOARD,
    )


''' Remove Locations Func Group '''
@journey_router.message(Command(commands=['remove_location']))
async def start_remove_location(message: Message, state: FSMContext) -> None:
    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)

    if len(journeys) > 0:
        keyboard = journey_list_keyboard(journey_list=journeys)

        await state.set_state(LocationRemoveForm.to_journey)
        await message.answer(
            '🧐 From which journey do you want to remove location?',
            reply_markup=keyboard,
        )
    else:
        await state.clear()
        await message.answer(
            '🤓 First, you should create a journey. Use /create_journey',
            reply_markup=DEFAULT_KEYBOARD,
        )


@journey_router.message(LocationRemoveForm.to_journey)
async def select_remove_location(message: Message, state: FSMContext) -> None:
    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journey = await get_journey_by_title(db_session=session, journey_title=message.text, owner_id=user.id)

    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)

    if journey is None or journey not in journeys:
        keyboard = journey_list_keyboard(journey_list=journeys)
        await message.answer(
            '⚠️ You do not have such journey. Use the buttons', reply_markup=keyboard
        )
    elif len(journey.locations) > 0:
        await state.update_data(journey=journey)
        await state.set_state(LocationRemoveForm.to_remove)
        keyboard = journey_location_list_keyboard(journey=journey)


        await message.answer(
            '🧐 Which location do you want to remove?', reply_markup=keyboard
        )
    else:
        await state.clear()
        await message.answer(
            '⚠️ There are no locations in this journey. Use /add_location',
            reply_markup=DEFAULT_KEYBOARD,
        )


@journey_router.message(LocationRemoveForm.to_remove)
async def remove_location(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    journey = data['journey']

    msg = message.text.replace(' - ', ':')

    place, date_start, date_end = [it.strip() for it in msg.split(':')]
    location = await get_location_by_journey_place_datestart_dateend(
        db_session=session,
        place=place,
        journey=journey,
        date_start=datestr_to_date(date_start),
        date_end=datestr_to_date(date_end),
    )

    if location is None:
        keyboard = journey_location_list_keyboard(journey=journey)
        await message.answer(
            '⚠️ There is no such location associated with this journey. Use the buttons',
            reply_markup=keyboard,
        )
    else:
        await state.clear()
        await delete_location_from_journey(
            db_session=session, journey=journey, location=location
        )
        await message.answer(
            '✅ Location removed successfully',
            reply_markup=DEFAULT_KEYBOARD,
        )


''' Edit Journey [Title & Description & Locations] Func Group '''
@journey_router.message(Command(commands=['edit_journey']))
async def start_edit_journey(message: Message, state: FSMContext) -> None:

    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)

    keyboard = journey_list_keyboard(journey_list=journeys)
    await state.set_state(JourneyEditForm.to_choose_parameter_edit)
    await message.answer(
        '🧐 Which journey do you want to edit?',
        reply_markup=keyboard,
    )


@journey_router.message(JourneyEditForm.to_choose_parameter_edit)
async def select_edit_journey(message: Message, state: FSMContext) -> None:
    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journey = await get_journey_by_title(db_session=session, journey_title=message.text, owner_id=user.id)

    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)

    if journey not in journeys:
        keyboard = journey_list_keyboard(journey_list=journeys)
        await message.answer(
            '⚠️ You do not have such journey. Use the buttons',
            reply_markup=keyboard,
        )
    else:
        await state.set_state(JourneyEditForm.to_start_edit)
        await state.update_data(journey=journey, journeys=journeys)
        await message.answer(
            '🧐 What do you want to change?',
            reply_markup=EDIT_JOURNEY_PARAMS_KEYBOARD,
        )


@journey_router.message(JourneyEditForm.to_start_edit)
async def select_parameter_edit_journey(message: Message, state: FSMContext) -> None:
    if message.text not in ['Title', 'Description', 'Locations']:
        await message.answer(
            '⚠️ Invalid parameter. Use the buttons',
            reply_markup=EDIT_JOURNEY_PARAMS_KEYBOARD,
        )
    elif message.text == 'Title':
        await state.set_state(JourneyEditForm.to_edit)
        await state.update_data(edit='title')
        await message.answer(
            '🧐 What do you want to change the title to?', reply_markup=DEFAULT_KEYBOARD
        )
    elif message.text == 'Description':
        await state.set_state(JourneyEditForm.to_edit)
        await state.update_data(edit='description')
        await message.answer(
            '🧐 What do you want to change the description to?',
            reply_markup=DEFAULT_KEYBOARD,
        )
    elif message.text == 'Locations':
        await state.set_state(JourneyEditForm.to_edit)
        data = await state.update_data(edit='locations')
        journey = data['journey']
        keyboard = journey_location_list_keyboard(journey=journey)
        if len(journey.locations) == 0:
            await state.clear()
            await message.answer(
                '⚠️ There are no locations associated with this journey. Use /add_location',
                reply_markup=DEFAULT_KEYBOARD,
            )
        else:
            await message.answer(
                '🧐 Which location do you want to change?',
                reply_markup=keyboard,
            )


@journey_router.message(JourneyEditForm.to_edit)
async def input_edit_journey(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data['edit'] == 'title':
        title = message.text
        journeys = data['journeys']
        if len(title) > 50:
            await message.answer(
                '⚠️ New title is too long. Think of something shorter',
                reply_markup=DEFAULT_KEYBOARD,
            )
        elif title in [journey.title for journey in journeys] and title != data['journey'].title:
            await message.answer(
                '⚠️ You already have such a journey. Please try another one',
                reply_markup=DEFAULT_KEYBOARD,
            )
        else:
            journey = data['journey']
            await update_journey(
                db_session=session,
                journey=journey,
                new_title=title,
            )
            await finish_edit_journey(message=message, state=state)
    elif data['edit'] == 'description':
        description = message.text
        if len(description) > 100:
            await message.answer(
                '⚠️ New description is too long. Think of something shorter',
                reply_markup=DEFAULT_KEYBOARD,
            )
        else:
            journey = data['journey']
            await update_journey(
                db_session=session, journey=journey, new_description=description
            )
            await finish_edit_journey(message=message, state=state)
    elif data['edit'] == 'locations':
        msg = message.text.replace(' - ', ':')

        place, date_start, date_end = [it.strip() for it in msg.split(':')]
        await state.set_state(JourneyEditForm.to_edit_location)
        await state.update_data(
            locplace=place, datestart_str=date_start, dateend_str=date_end
        )

        await message.answer(
            '🧐 What do you want to change?',
            reply_markup=EDIT_LOCATION_PARAMS_KEYBOARD,
        )


@journey_router.message(JourneyEditForm.to_edit_location)
async def edit_location_choose_parameter_journey(
    message: Message, state: FSMContext
) -> None:
    if message.text not in ['Place', 'Date start', 'Date end']:
        await message.answer(
            '⚠️ Invalid parameter. Use the buttons',
            reply_markup=EDIT_LOCATION_PARAMS_KEYBOARD,
        )
    elif message.text == 'Place':
        await state.set_state(JourneyEditForm.to_input_edit_info_location)
        await state.update_data(location_edit='place')
        await message.answer(
            f'🧐 To what did you change your destination to?',
            reply_markup=DEFAULT_KEYBOARD,
        )
    elif message.text == 'Date start':
        await state.set_state(JourneyEditForm.to_input_edit_info_location)
        data = await state.update_data(location_edit='date_start')
        await message.answer(
            f'🧐 When do you plan to arrive at {data["locplace"]}? DD-MM-YYYY format 😉',
            reply_markup=DEFAULT_KEYBOARD,
        )
    elif message.text == 'Date end':
        await state.set_state(JourneyEditForm.to_input_edit_info_location)
        data = await state.update_data(location_edit='date_end')
        await message.answer(
            f'🧐 When do you plan to leave {data["locplace"]}? DD-MM-YYYY format 😉',
            reply_markup=DEFAULT_KEYBOARD,
        )


@journey_router.message(JourneyEditForm.to_input_edit_info_location)
async def edit_location_parameter_journey(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    location = await get_location_by_journey_place_datestart_dateend(
        db_session=session,
        place=data['locplace'],
        journey=data['journey'],
        date_start=datestr_to_date(data['datestart_str']),
        date_end=datestr_to_date(data['dateend_str']),
    )
    if data['location_edit'] == 'place':
        place = message.text
        is_valid, _, placename, lat, lon = await validate_location(city=place)
        if is_valid:
            await update_location(
                db_session=session,
                location=location,
                new_place=placename,
                new_lat=lat,
                new_lon=lon,
            )
            await finish_edit_journey(message=message, state=state)
        else:
            await message.answer(
                '⚠️ Invalid place. Please try again', reply_markup=DEFAULT_KEYBOARD
            )
    elif data['location_edit'] == 'date_start':
        datestr = message.text
        try:
            if not await validate_date(datestr):
                raise ValueError()

            day, month, year = map(int, datestr.split('-'))
            dt = date(year=year, month=month, day=day)

            if location.date_end < dt:
                raise ValueError(DATE_CONFLICTS_WITH_ANOTHER_DATE)

            await update_location(
                db_session=session,
                location=location,
                new_date_start=dt,
            )
            await finish_edit_journey(message=message, state=state)
        except ValueError as e:
            if str(e) == DATE_CONFLICTS_WITH_ANOTHER_DATE:
                await message.answer(
                    str(e),
                    reply_markup=DEFAULT_KEYBOARD,
                )
                return
            await message.answer(
                '⚠️ Invalid date, try again', reply_markup=DEFAULT_KEYBOARD
            )
    elif data['location_edit'] == 'date_end':
        datestr = message.text
        try:
            if not await validate_date(datestr):
                raise ValueError()

            day, month, year = map(int, datestr.split('-'))
            dt = date(year=year, month=month, day=day)

            if location.date_start > dt:
                raise ValueError(DATE_CONFLICTS_WITH_ANOTHER_DATE)

            await update_location(
                db_session=session,
                location=location,
                new_date_end=dt,
            )

            await finish_edit_journey(message=message, state=state)
        except ValueError:
            await message.answer(
                '⚠️ Invalid date, try again', reply_markup=DEFAULT_KEYBOARD
            )


async def finish_edit_journey(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        '✅ Journey successfully edited. Anything else?',
        reply_markup=DEFAULT_KEYBOARD,
    )


''' Journey Remove Func Group '''
@journey_router.message(Command(commands=['remove_journey']))
async def start_remove_journey(message: Message, state: FSMContext) -> None:
    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)

    if len(journeys) > 0:
        keyboard = journey_list_keyboard(journey_list=journeys)
        await state.set_state(JourneyRemoveForm.to_remove)
        await state.update_data(journeys=journeys)
        await message.answer('🧐 What is your journey called?', reply_markup=keyboard)
    else:
        await state.clear()
        await message.answer(
            '⚠️ You do not have any journeys planned. Use /create_journey',
            reply_markup=DEFAULT_KEYBOARD,
        )


@journey_router.message(JourneyRemoveForm.to_remove)
async def remove_journey(message: Message, state: FSMContext) -> None:
    title = message.text
    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journey = await get_journey_by_title(db_session=session, journey_title=title, owner_id=user.id)
    data = await state.get_data()
    journeys = data['journeys']

    if journey is None or journey not in journeys:
        keyboard = journey_list_keyboard(journey_list=journeys)
        await message.answer(
            '⚠️ You do not have such journey. Use the buttons',
            reply_markup=keyboard,
        )
    else:
        await delete_journey(db_session=session, journey=journey)
        await finish_remove_journey(message=message, state=state)


async def finish_remove_journey(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        '✅ The journey has been deleted. Anything else?',
        reply_markup=DEFAULT_KEYBOARD,
    )
