import copy
import datetime, pytz
from pymongo import ASCENDING, MongoClient
import os

PRODUCTION = os.getenv('TP_PROD')

if PRODUCTION is not None and PRODUCTION == "true":
    print("RUNNING IN PRODUCTION MODE!!")
else:
    print("Running in dev mode cause environment variable \"TP_PROD=true\" was not set...")
    PRODUCTION = None

AUTO_RELEASE_LOCKS_AFTER = 3

mongoPort = 27018
mongoHost = "192.168.1.50"
databaseName = "TP"
collectionNameStockAssets = f"stockAssets"

class FileHandler:

    def __init__(self):
        self.lastFileHash = 0
        self.changeLog = []

    def init(self):
        self.DB, self.COLLECTION, self.MONGO_CLIENT = self._connectDb(mongoHost, mongoPort, databaseName, collectionNameStockAssets)
        self._testMongoConnection(self.MONGO_CLIENT)
        self._fixIndex()

    def _connectDb(self, mongoHost, mongoPort, databaseName, collectionName):

        dbConnection = MongoClient(host=mongoHost, port=mongoPort)
        db = dbConnection[databaseName]
        collection = db[collectionName]
        return db, collection, dbConnection

    def _testMongoConnection(self, dbConnection):

        try:
            print(f"{datetime.datetime.now(pytz.timezone('Europe/Stockholm'))} Mongo connection OK! Version: {dbConnection.server_info()['version']}")
        except Exception as ex:
            raise ValueError(f"{datetime.datetime.utcnow()} Mongo connection FAILED! (B)  {ex}")

    def _fixIndex(self):
        self.DB[collectionNameStockAssets].create_index([('ticker', ASCENDING)], unique=True)

    def readAssetsFromMongo(self):

        data = self.COLLECTION.find()
        retData = {}

        for entry in data:
            ticker = entry['ticker']
            del(entry['ticker'])
            del(entry['_id'])
            retData[ticker] = entry

        return retData

    def writeAssetsToMongo(self, file):

        for ticker, entry in file.items():
            newEntry = copy.deepcopy(entry)
            newEntry['ticker'] = ticker

            if PRODUCTION:
                self.COLLECTION.update_one(
                    {"ticker": ticker},
                    {"$set":
                         newEntry
                    },
                    upsert=True)

    def incrementLockCounter(self, file):

        changes = False

        for stock, stockData in file.items():
            if "lockCounter" not in stockData:
                changes = True
                stockData["lockCounter"] = 0

            if "lockKey" not in stockData:
                changes = True
                stockData["lockKey"] = 0

            if stockData["lockKey"] == 0:
                stockData["lockCounter"] = 0
                continue

            stockData["lockCounter"] += 1
            changes = True

            if stockData["lockCounter"] > AUTO_RELEASE_LOCKS_AFTER:
                print("Releasing lock due to inactivity")
                changes = True
                stockData["lockCounter"] = 0
                stockData["lockKey"] = 0

        return changes

    def writeStockChangeLog(self, oldStock, newStock, tradedByBot):

        entry = copy.deepcopy(newStock)

        entry["purchasedStocks"] = newStock['count'] - oldStock['count']
        entry["purchaseValueSek"] = newStock['totalInvestedSek'] - oldStock['totalInvestedSek']
        entry["date"] = str(datetime.datetime.now(pytz.timezone('Europe/Stockholm')))
        entry["tradedByBot"] = tradedByBot
        del(entry["lockCounter"])
        del (entry["lockKey"])
        print(f"Added to stock changelog: {entry}")
        self.changeLog.append(entry)

    def takeFirstChangeLogItem(self):
        if len(self.changeLog) > 0:
            retData = self.changeLog[0]
            del(self.changeLog[0])
            return retData

        return {}

if __name__ == "__main__":
    f = FileHandler()
    f.init()
    fileFromDisk = f.readAssetsFromMongo()
