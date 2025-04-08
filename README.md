# Striper Log
#### Video Demo: [Striper Log Link](https://www.youtube.com/watch?v=RFIGDwmrw9o)
#### Description: Welcome to Striper Log. This is a web based app to record surf fishermen's catches.
## Features:
- **Catch Log**: Records catch details of the users form entry and allows the user to optionally capture a photo of their fish directly from their device. This feature also allows user to change the automatic input like tide data, date/time, and moon phase so that they can record the catches when they get home if they prefer that way of logging their catches or just caught so many they forgot to add one!
- **Tide Info**: Uses NOAA to give the user the most accurate tide predictions available based on location. I did not need to use a API for this to work properly
- **Moon Info**: Initially I used an API to track moon phase data but I ran into a ton of issues. I found some algorithms people used to track this before and used their logic. The logic is based off a known new moon date and uses the lunar cycle length to determine the current phase with some basic math.
- **Geolocation**: My web app uses browser geolocation to track the users long/lat.
- **Photo upload**: Allows user to capture and upload photos directly from their device.
- **Calendar**: Give the user a detailed catch log for every catch and stores all their data in the proper order by date. The user can go back years collecting data to determine when would be a great time to target migrating fish this year.
- **Weather Info**: Uses openweathermap API and geolocation to get the user accurate weather data.
## Design:
I chose several pictures from Pixabay.com to add to my web app. I had a lot of trouble creating the logo so I coded a small program to resize pictures which helped in the logo on the login page. I left the calendar page white so the logs are easy to read and stand out to the user. I had many different pictures picked out for background images but none of them had high enough quality to stretch.
## Usage: 
### 1. Register/Login:
- Head to [https://www.striperlog.com](https://striperlog.com/) to register a new account or login if you have already registered.
### 2. Log a catch:
- Click on log a catch or go to /catch then fill out the form and capture a photo with your device
- The web app will save all the user inputted data along with tide and moon data to the calendar
### 3. View your log:
- Head over to the calendar on the navbar or /calendar and check out all your previous logs in a calendar format.
### 4. Log out:
- There is a "Log Out" button in the bottom right corner of all 3 pages (dashboard, catch, calendar)
- Be prepared for steady updates and new features. You can check back here for any information about any updates in the future.
## Contributing
Feedback and contributions are welcome! Submit issues or pull requests on [GitHub](https://github.com/Ryanwilk-pro/surf-fishing-app) or email me at [Ryanwilk.pro@gmail.com](mailto:ryanwilk.pro@gmail.com)
