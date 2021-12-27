import pytz
from datetime import datetime

class MarketOpenHours:
    MARKET_OPEN_HOURS = {
        # "in": True means if key occurs in ticker name.
        # "in": False means if key does not occur in ticker name.
        # tuples mean: (hour, min)
        #                                                                               Delay: Avanza / Yahoo finance
        ".OL": {"in": True, "open": (9, 17), "close": (16, 22), "timezone": "Europe/Stockholm"}, # 15 / 15
        ".ST": {"in": True, "open": (9, 2), "close": (17, 27), "timezone": "Europe/Stockholm"},  # RT / RT
        ".DE": {"in": True, "open": (9, 17), "close": (17, 27), "timezone": "Europe/Stockholm"}, # RT / 15
        ".HE": {"in": True, "open": (9, 2), "close": (17, 27), "timezone": "Europe/Stockholm"},  # RT / RT
        ".CO": {"in": True, "open": (9, 2), "close": (16, 57), "timezone": "Europe/Stockholm"},  # RT / RT
        ".TO": {"in": True, "open": (9, 45), "close": (15, 57), "timezone": "US/Eastern"},       # 15 / RT
        ".": {"in": False, "open": (9, 45), "close": (15, 57), "timezone": "US/Eastern"}         # 15 / RT
    }

    def __init__(self):
        self.marketOpenHash = 0

    def isTimeWithin(self, openTime, closeTime, timezone):

        currentDate = datetime.now(pytz.timezone(timezone))
        currentHour = currentDate.hour
        currentMinute = currentDate.minute

        if (((currentHour > openTime[0]) or (currentHour == openTime[0] and currentMinute >= openTime[1])) and \
                ((currentHour < closeTime[0]) or (currentHour == closeTime[0] and currentMinute < closeTime[1]))):
            return True
        else:
            return False

    def marketsOpenedOrClosed(self):

        stringValue = ""

        for key, value in self.MARKET_OPEN_HOURS.items():
            stringValue += f"{self.isTimeWithin(value['open'], value['close'], value['timezone'])}"

        newHash = hash(stringValue)

        if self.marketOpenHash != newHash:
            self.marketOpenHash = newHash
            print(f"{str(datetime.now(pytz.timezone('Europe/Stockholm')))} Market open hours changed!!")
            return True
        else:
            return False

    def isMarketOpen(self, ticker):

        if not self.isWeekday():
            return False

        for key, value in self.MARKET_OPEN_HOURS.items():
            if value["in"]:
                if key in ticker:
                    return self.isTimeWithin(value["open"], value["close"], value["timezone"])
            else:
                if key not in ticker:
                    return self.isTimeWithin(value["open"], value["close"], value["timezone"])

        print(f"Open hours for ticker {ticker} not found")
        return True

    def isWeekday(self):
        return datetime.now(pytz.timezone('Europe/Stockholm')).weekday() <= 4


if __name__ == "__main__":
    m = MarketOpenHours()
    print(f"AKSO.L open {m.isMarketOpen('AKSO.OL')}")
    print(f"T open {m.isMarketOpen('T')}")
    print(f"opened or closed {m.marketsOpenedOrClosed()}")
    print(f"opened or closed {m.marketsOpenedOrClosed()}")
    print(f"is weekday {m.isWeekday()}")