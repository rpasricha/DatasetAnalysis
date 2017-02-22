# Download hourly weather data for the desired dates from Weather Underground

import datetime
import subprocess
import time

start_date = datetime.date(2016, 12, 26)
end_date = datetime.date(2017, 1, 25)

data_dir = 'data/google_traffic/weather_data/'

while start_date <= end_date:
    date_str = start_date.strftime("%Y%m%d")
    filename = data_dir + date_str + '.csv'
    print date_str

    # Get CSV of hourly weather data for this day
    url = "'https://www.wunderground.com/history/airport/KSAN/%d/%d/%d/DailyHistory.html?format=1'" % (start_date.year, start_date.month, start_date.day)
    subprocess.call('wget ' + url + ' -O ' + filename, shell=True)

    # Remove first blank line of response
    subprocess.call('tail -n +2 ' + filename + ' | sponge ' + filename, shell=True)

    # Remove last 6 characters (<br />) from each line
    subprocess.call("sed 's/......$//' " + filename + ' | sponge ' + filename, shell=True)

    start_date += datetime.timedelta(days=1)
    time.sleep(20)
