import os
import json
import threading
import copy
import datetime, pytz

AUTO_RELEASE_LOCKS_AFTER = 4

TICKERS_FILE_ALTERNATIVE2 = './tickers.json'
TICKERS_FILE_ALTERNATIVE1 = '/tickers/tickers.json'
ACTIVE_FILE_PATH = None

if os.path.isfile(TICKERS_FILE_ALTERNATIVE1):
    ACTIVE_FILE_PATH = TICKERS_FILE_ALTERNATIVE1
if os.path.isfile(TICKERS_FILE_ALTERNATIVE2):
    ACTIVE_FILE_PATH = TICKERS_FILE_ALTERNATIVE2

if ACTIVE_FILE_PATH is None:
    print("Please provide a path you your tickers.json file...")
    exit(37)

print(f"Reading tickers from {ACTIVE_FILE_PATH}")

globalFileLock = threading.RLock()

class FileHandler:

    def __init__(self):
        self.lastFileHash = 0
        self.changeLog = []

    def readFileFromDisk(self):
        with globalFileLock:
            with open(ACTIVE_FILE_PATH, "r") as jsonFile:
                jsonLoaded = json.load(jsonFile)
                if self.incrementLockCounter(jsonLoaded):
                    self.writeFileToDisk(jsonLoaded)
                self.lastFileHash = hash(str(jsonLoaded))
                return jsonLoaded

    def writeFileToDisk(self, file):

        print("Saving data to disk... ")

        with globalFileLock:
            with open(ACTIVE_FILE_PATH, "w") as jsonFile:
                jsonFile.write(json.dumps(file, indent=4, sort_keys=True))

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
    fileFromDisk = f.readFileFromDisk()
    f.writeFileToDisk(fileFromDisk)