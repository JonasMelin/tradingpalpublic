import requests
from lxml import html
import json
import copy
from bs4 import BeautifulSoup
import urllib3
from datetime import datetime, timedelta

currency_urls = {
    'USD': 'http://www.4-traders.com/US-DOLLAR-SWEDISH-KRONA-2371289/',
    'CAD': 'http://www.4-traders.com/CANADIAN-DOLLAR-SWEDISH-2355617/',
    'EUR': 'http://www.4-traders.com/EURO-SWEDISH-KRONA-EUR-2371239/',
    'GBP': 'http://www.4-traders.com/BRITISH-POUND-SWEDISH-K-2371243/',
    'NOK': 'http://www.4-traders.com/NORWEGIAN-KRONER-SWEDIS-2371209/',
    'DKK': 'http://www.4-traders.com/DANISH-KRONE-SWEDISH-KR-2371195/'
}

class StocksFetcher:

    REFRESH_CURRENCY_DELAY_HOUR = 4
    REFRESH_STATIC_DATA_DELAY_HOUR = 24

    # ################################################################################
    # Construct
    # ################################################################################
    def __init__(self):
        self.currencyConverter = {}
        self.staticTickerData = {}
        self.dynamicTickerData = {}
        self.lastRefreshedCurrencies = datetime.utcnow() - timedelta(days=1000)
        self.lastRefreshedStaticData = datetime.utcnow() - timedelta(days=1000)
        self.http = urllib3.PoolManager()

    # ################################################################################
    # Fetches info for a ticker...
    # ################################################################################
    def fetchTickerInfo(self, ticker, currency, useCacheForDynamics=False):

        self._refreshCurrencyConvertions()
        summary_data = self._fetchDynamicData(ticker, useCacheForDynamics)
        self._getStaticData(summary_data, ticker)
        summary_data['price_in_sek'] = self._convertToSek(summary_data['price'], currency.upper())
        summary_data['convertToSekRatio'] = float(self.currencyConverter[currency.upper()])

        return summary_data

    # ################################################################################
    # Refreshes the currency convertion ratios, if needed... You may call this
    # function as often as you like.
    # ################################################################################
    def _refreshCurrencyConvertions(self):

        timeSinceLastRefresh = datetime.utcnow() - self.lastRefreshedCurrencies

        if timeSinceLastRefresh.total_seconds() > (self.REFRESH_CURRENCY_DELAY_HOUR * 60 * 60):
            self._fetchCurrenciesFromInternet()
            self.lastRefreshedCurrencies = datetime.utcnow()

    # ################################################################################
    # Gets static data, such as currency for a stock, i.e. values that are assumed
    # not to change very often and will hence be cached....
    # ################################################################################
    def _getStaticData(self, summary_data, ticker):

        timeSinceLastRefresh = datetime.utcnow() - self.lastRefreshedStaticData

        if timeSinceLastRefresh.total_seconds() > (self.REFRESH_STATIC_DATA_DELAY_HOUR * 60 * 60):
            print("Refreshing all static data!")
            self.staticTickerData = {}
            self.lastRefreshedStaticData = datetime.utcnow()

        if ticker not in self.staticTickerData:
            self._fetchStaticDataFromInternet(ticker)

        summary_data['trailingPE'] = 0
        summary_data['priceToSalesTrailing12Months'] = 0
        summary_data['trailingAnnualDividendYield'] = 0
        summary_data['enterpriseValue'] = 0

        try:
            soup_data = self.staticTickerData[ticker]['soup_statistics']
            summary_data['trailingPE'] = self.extractStaticValue("trailingPE", soup_data)
            summary_data['priceToSalesTrailing12Months'] = self.extractStaticValue("priceToSalesTrailing12Months",
                                                                               soup_data)
            summary_data['trailingAnnualDividendYield'] = self.extractStaticValue("trailingAnnualDividendYield", soup_data)
            summary_data['enterpriseValue'] = self.extractStaticValue("enterpriseValue", soup_data)
        except Exception:
            if ticker in self.staticTickerData:
                del(self.staticTickerData[ticker])
            print("Could not extract additional static data from web reply. Ignoring.. " + ticker)


    # ################################################################################
    # Fetches constantly updating data for a ticker. This data is not cached, and
    # always refreshed from yahoo
    # ################################################################################
    def _fetchDynamicData(self, ticker, useCache=False):

        summary_data = {}

        if useCache and ticker in self.dynamicTickerData:
            return copy.deepcopy(self.dynamicTickerData[ticker])

        raw_ticker_data_url = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{0}?formatted=true&lang=en-US&region=US&modules=summaryProfile%2CfinancialData%2CrecommendationTrend%2CupgradeDowngradeHistory%2Cearnings%2CdefaultKeyStatistics%2CcalendarEvents&corsDomain=finance.yahoo.com".format(ticker)
        summary_json_response = self.http.request('GET', raw_ticker_data_url)
        json_loaded_summary = json.loads(summary_json_response.data)

        if json_loaded_summary["quoteSummary"]["error"] is not None:
            raise Exception(f"Ticker not found: {ticker}")

        try:
            summary_data['price'] = json_loaded_summary["quoteSummary"]["result"][0]["financialData"]["currentPrice"]['raw']
        except:
            raise Exception(f"Could not get currentPrice for {ticker}")

        try:
            summary_data['industry'] = json_loaded_summary["quoteSummary"]["result"][0]["summaryProfile"]["industry"]
            summary_data['employees'] = int(
                json_loaded_summary["quoteSummary"]["result"][0]["summaryProfile"]["fullTimeEmployees"])
        except:
            summary_data['industry'] = "unknown"
            summary_data['employees'] = 0

        self.dynamicTickerData[ticker] = copy.deepcopy(summary_data)
        return summary_data

    # ################################################################################
    # collects static data for a ticker, such as currency. This data will be cached.
    # ################################################################################
    def _fetchStaticDataFromInternet(self, ticker):

        print(f"Fetching static data for ticker {ticker}")
        url_statistics = f"https://finance.yahoo.com/quote/{ticker}/key-statistics?p={ticker}".lower()
        try:
            html_statistics = self.http.request('GET', url_statistics)

            if html_statistics.status != 200:
                raise RuntimeError(f"FAILED to get key-statistics for ticker: {ticker}, {url_statistics}")

            soup_statistics = BeautifulSoup(html_statistics.data, 'lxml')
            self.staticTickerData[ticker] = {}
            self.staticTickerData[ticker]['soup_statistics'] = soup_statistics

        except Exception:
            raise RuntimeError(f"FAILED to parse currency from message: {ticker}, {url_statistics}")

    # ################################################################################
    # ...
    # ################################################################################
    def extractStaticValue(self, valueToExtract, soup_statistics):

        cutStringAsList = str(soup_statistics).split(valueToExtract)

        for nextSlice in cutStringAsList:
            try:
                startOfString = nextSlice.split('{')[1]
                startOfString = startOfString.split('}')[0]
                valueAsJson = json.loads("{" + startOfString + "}")
                return valueAsJson["raw"]
            except:
                pass

        return None

    # ################################################################################
    # Returns Conversion dictrionary from currencies to SEK
    # ################################################################################
    def _fetchCurrenciesFromInternet(self):

        print("Fetching currency convertion ratios...")

        result = {}
        for currency, url in currency_urls.items():
            page = requests.get(url)
            tree = html.fromstring(page.content)
            cur = str(tree.xpath('//td[@class="fvPrice colorBlack"]/text()'))
            cur_cut = cur[+2:-2]
            result[currency] = cur_cut

        result['SEK'] = "1.0"
        self.currencyConverter = result

    # ################################################################################
    # Adds the value of the stock in SEK to the tickerSummary structure
    # ################################################################################
    def _convertToSek(self, price, currency):

        try:
            return price * \
                float(self.currencyConverter[currency])
        except Exception:
            print(f"Could not convert stock currency to SEK: {price} / {currency}")
            raise

if __name__ == "__main__":
    fetcher = StocksFetcher()
    print(fetcher.fetchTickerInfo("T"))
    print(fetcher.fetchTickerInfo("T"))
