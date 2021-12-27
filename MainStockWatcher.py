import StocksFetcher
import Analyze
import time
import sys
import copy
import random
import math
import threading
import pytz
import MarketOpenHours
from datetime import datetime

class MainStockWatcher:

    TIMER_DELAY_SEC = 3
    MIN_REFRESH_INTERVAL_SEC = 240
    MAX_REFRESH_INTERVAL_SEC = 600


    def __init__(self, fileHandler, stocksFetcher):
        self.NEXT_REFRESH_INTERVAL_SEC = self.MIN_REFRESH_INTERVAL_SEC
        self.timer = None
        self.FORCE_REFRESH = False
        self.QUICK_REFRESH = False
        self.globalLock = threading.Lock()
        self.fileHandler = fileHandler
        self.marketOpenHours = MarketOpenHours.MarketOpenHours()
        self.fetcher = stocksFetcher
        self.cachedAllStocks = {}
        self.cachedStocksToBuy = {}
        self.cachedStocksToSell = {}
        self.lastRefreshedTime = 0
        self.timerCallback()

    def forceRefresh(self, QUICK_REFRESH=False):
        self.FORCE_REFRESH = True
        self.QUICK_REFRESH = QUICK_REFRESH

    def reinitializeAllVariables(self):
        self.FORCE_REFRESH = False
        self.industries = {}
        self.totalInvested = 0
        self.totalEmployees = 0
        self.successCounter = 0
        self.skippedCounter = 0
        self.sellModeStocks = 0
        self.buyModeStocks = 0
        self.neutralModeStocks = 0
        self.totalGlobalValue = 0
        self.allStocks = {}
        self.allStocks["list"] = []
        self.stocksToSell = {}
        self.stocksToSell["list"] = []
        self.stocksToBuy = {}
        self.stocksToBuy["list"] = []
        self.failedToLookup = []

    def industryConverter(self, industry):
        if "bank" in industry.lower():
            return "banking"
        if "oil" in industry.lower():
            return "oil industry"
        if "drug" in industry.lower():
            return "drug industry"

        return industry

    def timerCallback(self):
        self.timer = None
        try:
            if self._shallStocksBeUpdated():
                self.updateAllStocks()
        finally:
            self.timer = threading.Timer(self.TIMER_DELAY_SEC, self.timerCallback)
            self.timer.start()
            sys.stdout.flush()

    def _shallStocksBeUpdated(self):

        if self.marketOpenHours.marketsOpenedOrClosed() or self.FORCE_REFRESH or (self.lastRefreshedTime < (int(time.time()) - (self.NEXT_REFRESH_INTERVAL_SEC))):
            return True
        else:
            return False

    def updateAllStocks(self):

        startTime = datetime.now(pytz.timezone('Europe/Stockholm'))
        print(f"\n{startTime} - Updating all stocks")
        self.reinitializeAllVariables()
        myStocks = self.fileHandler.readAssetsFromMongo()
        self.lastRefreshedTime = int(time.time())

        for nextStock, stockData in myStocks.items():
            try:
                if not self.marketOpenHours.isMarketOpen(nextStock):
                    self.skippedCounter = self.skippedCounter + 1 if stockData['count'] > 0 else self.skippedCounter
                    continue

                stockDetails = self.fetcher.fetchTickerInfo(nextStock, stockData['currency'],
                                                            useCacheForDynamics=((stockData['lockKey'] > 0) or self.QUICK_REFRESH),
                                                            getStaticData=False)
                stockOwnName = stockData['name']
                valueSek = int(stockDetails['price_in_sek'] * stockData['count'])
                stockData['tickerIsLocked'] = True if stockData['lockKey'] > 0 else False
                stockData['lockKey'] = -1

                soldAt = 10000000
                boughtAt = 0
                switchedAt = 0
                transactionMode = Analyze.TransactionMode.Neutral

                if 'soldAt' in stockData and stockData['soldAt']:
                    soldAt = stockData['soldAt']
                    switchedAt = soldAt
                if 'boughtAt' in stockData and stockData['boughtAt']:
                    boughtAt = stockData['boughtAt']
                    switchedAt = boughtAt

                if stockData['count'] > 0 and stockData['boughtAt'] is None and stockData['soldAt'] is not None:
                    self.sellModeStocks += 1
                    transactionMode = Analyze.TransactionMode.Sell
                if stockData['count'] > 0 and stockData['boughtAt'] is not None and stockData['soldAt'] is None:
                    self.buyModeStocks += 1
                    transactionMode = Analyze.TransactionMode.Buy
                if stockData['count'] > 0 and stockData['boughtAt'] is None and stockData['soldAt'] is None:
                    self.neutralModeStocks += 1
                    transactionMode = Analyze.TransactionMode.Neutral
                if "switchedAt" in stockData:
                    switchedAt = stockData["switchedAt"]

                stockCountToSell = Analyze.howManyToSell(nextStock, valueSek, stockDetails['price_in_sek'], stockDetails['price'], boughtAt, soldAt, switchedAt, transactionMode)

                if stockData['count'] > 0 and stockCountToSell > 0:
                    self.stocksToSell['list'].append({"tickerName": nextStock, "currentStock": stockData, "numberToSell": stockCountToSell,
                                              "singleStockPriceSek": stockDetails['price_in_sek'],
                                              "priceOrigCurrancy": stockDetails['price'], "currancy": stockData['currency']})

                numberStocksToBuy = Analyze.howManyToBuy(nextStock, valueSek, stockDetails['price_in_sek'], stockDetails['price'], boughtAt, soldAt, switchedAt, transactionMode)
                if stockData['count'] > 0 and numberStocksToBuy > 0:
                    buyIndication = Analyze.getBuyIndication(valueSek, stockData["totalInvestedSek"])
                    self.stocksToBuy['list'].append({"tickerName": nextStock, "currentStock": stockData, "buyIndication": buyIndication,
                                             "numberToBuy": numberStocksToBuy, "singleStockPriceSek": stockDetails['price_in_sek'],
                                             "priceOrigCurrancy": stockDetails['price'], "currancy": stockData['currency']})

                self.totalEmployees += stockDetails["employees"]

                industry = self.industryConverter(stockDetails["industry"])

                if industry not in self.industries:
                    self.industries[industry] = \
                        {
                            "totValue (SEK)": 0,
                            "companies": []
                        }

                self.industries[industry]["totValue (SEK)"] += valueSek
                self.industries[industry]["companies"].append(stockOwnName)

                self.totalGlobalValue += valueSek
                self.totalInvested += stockData["totalInvestedSek"]

                self.allStocks["list"].append({"tickerName": nextStock, "currentStock": stockData,
                                               "singleStockPriceSek": stockDetails['price_in_sek'],
                                               "priceOrigCurrancy": stockDetails['price'], "currancy": stockData['currency'],
                                               })

                if stockData['count'] > 0:
                    self.successCounter += 1

                if "manualOverridePriceSek" in stockData:
                    print(f"Warning: You have a manual override price for a stock that is available online! {stockOwnName}")

            except Exception as ex:

                if "manualOverridePriceSek" in stockData:
                    print(f"Using manual override price for {stockData['name']}")
                    self.totalGlobalValue += int(stockData["manualOverridePriceSek"] * stockData['count'])
                else:
                    print(f"Could not get stock data: {stockData['name']}  ({ex})")

                self.failedToLookup.append(stockData["name"])

            finally:
                sys.stdout.flush()

        self.QUICK_REFRESH = False
        topData = {}
        topData['updatedUtc'] = str(datetime.now(pytz.timezone('Europe/Stockholm')))
        topData['sellModeStocks'] = self.sellModeStocks
        topData['buyModeStocks'] = self.buyModeStocks
        topData['neutralModeStocks'] = self.neutralModeStocks
        topData['failCounter'] = len(self.failedToLookup)
        topData['successCounter'] = self.successCounter
        topData['skippedCounter'] = self.skippedCounter
        topData['totalInvestedSek'] = self.totalInvested
        topData['totalGlobalValueSek'] = self.totalGlobalValue
        topData['updateVersion'] = math.floor(math.fabs(random.randint(1000000, 1000000000)))

        self.stocksToBuy = {**self.stocksToBuy, **topData}
        self.stocksToSell = {**self.stocksToSell, **topData}

        self.stocksToBuy['list'] = sorted(self.stocksToBuy['list'], key=lambda i: i['buyIndication'], reverse=True)
        self.industries = {k: v for k, v in sorted(self.industries.items(), key=lambda item: item[1]["totValue (SEK)"])}

        self.allStocks = {**self.allStocks, **topData}
        self.allStocks["industries"] = self.industries

        with self.globalLock:
            self.cachedStocksToBuy = copy.deepcopy(self.stocksToBuy)
            self.cachedStocksToSell = copy.deepcopy(self.stocksToSell)
            self.cachedAllStocks = copy.deepcopy(self.allStocks)

        self.NEXT_REFRESH_INTERVAL_SEC = random.randint(self.MIN_REFRESH_INTERVAL_SEC, self.MAX_REFRESH_INTERVAL_SEC)

        print(f"{datetime.now(pytz.timezone('Europe/Stockholm'))} - Done! updating all stocks   (Took: {(datetime.now(pytz.timezone('Europe/Stockholm')) - startTime).total_seconds():.2f}s)\n")

    def getStocksToBuyAsList(self):
        with self.globalLock:
            return copy.deepcopy(self.cachedStocksToBuy)

    def getStocksToSellAsList(self):
        with self.globalLock:
            return copy.deepcopy(self.cachedStocksToSell)

    def getAllStocks(self):
        with self.globalLock:
            return copy.deepcopy(self.cachedAllStocks)
