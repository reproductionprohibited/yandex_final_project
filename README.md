
# Travel agent 3.0 2024 pro max

Telegram username: ``` @travelagenttprodbot ```

This is a project for the individual stage of PROD olympiad.

## Setup project

1. Clone

2.1. If you use Docker:

* Launch Docker (e.g. Open Docker for Desktop application). Don't use Github CI/CD tools to start the bot

* Enter ```docker compose up -d``` into the terminal

2.2. If you want to run the project locally, run these commands from the root directory:

    python3 -m venv venv 
    source venv/bin/activate 
    python3 -m pip install requirements 
    cd bot
    python3 bot.py 



## External API usage

[Nominatim](https://nominatim.org/release-docs/develop/api/Overview/) for:
* City Search & Validaton
* Tourist Attraction Places Search
* Hotels Search
* Restaurant Search

[OpenMeteo API](https://open-meteo.com) for:
* Weather Forecast Data

[Open Source Routing Machine](https://project-osrm.org) for:
* Drawing routes on map


## Work Demonstration ( Screenshots of telegram bot )
![example_1_journey_list](/readme_images/example_1.png)

![example_2_command_list](/readme_images/example_2.png)

![example_3_map_list](/readme_images/example_3.png)

## Database Schema
![Database schema](/readme_images/database_schema.png)