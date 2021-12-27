
from flask import Flask, request, Response
import MainStockWatcher
import threading
import json
import FileHandler
import StocksFetcher
import random
import math
import copy
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

REFRESH_DELAY_SEC = 30

app = Flask(__name__)
globalLock = threading.Lock()
fileHandler = FileHandler.FileHandler()
stocksFetcher = StocksFetcher.StocksFetcher()
fileHandler.init()
stockWatcher = MainStockWatcher.MainStockWatcher(fileHandler, stocksFetcher)

@app.route("/tradingpal")
def index():
    return "hello..."

@app.route("/tradingpal/getStocksToBuy", methods = ['GET'])
def getStocksToBuy():
    return json.dumps(stockWatcher.getStocksToBuyAsList(), indent=4)

@app.route("/tradingpal/getStocksToSell", methods = ['GET'])
def getStocksToSell():
    return json.dumps(stockWatcher.getStocksToSellAsList(), indent=4)

@app.route("/tradingpal/getAllStocks", methods = ['GET'])
def getAllStocks():
    return json.dumps(stockWatcher.getAllStocks(), indent=4)

@app.route("/tradingpal/refresh", methods = ['PUT'])
def refresh():
    print("Force refresh!")
    stockWatcher.forceRefresh()
    return Response(status=200)

@app.route("/tradingpal/lock", methods = ['POST'])
def lockTicker():
    with globalLock:

        if request.data is None:
            return Response("missing body", status=400)

        inputData = json.loads(request.data)

        if "ticker" not in inputData:
            return Response("please provide ticker to lock", status=400)

        file = fileHandler.readAssetsFromMongo()
        inputTickerName = inputData["ticker"]

        if inputTickerName not in file:
            print(f"Ticker not found: {inputTickerName}")
            return Response("Ticker not found", status=400)

        fileTicker = file[inputTickerName]
        if fileTicker["lockKey"] != 0:
            print(f"Ticker already locked: {inputTickerName}")
            return Response("Ticker already locked!", status=403)

        lockKey = math.floor(math.fabs(random.randint(1000000, 1000000000)))
        fileTicker["lockKey"] = lockKey
        fileTicker["lockCounter"] = 0
        fileHandler.writeAssetsToMongo(file)
        stockWatcher.forceRefresh(QUICK_REFRESH=True)
        return json.dumps({"lockKey": lockKey})

@app.route("/tradingpal/unlock", methods = ['POST'])
def unlockTicker():
    with globalLock:
        if request.data is None:
            return Response("missing body", status=400)

        inputData = json.loads(request.data)

        if "ticker" not in inputData:
            return Response("please provide ticker to unlock", status=400)
        if "lockKey" not in inputData:
            return Response("please provide lockKey", status=403)

        file = fileHandler.readAssetsFromMongo()
        inputTickerName = inputData["ticker"]
        inputLockKey = inputData["lockKey"]

        if not isinstance(inputLockKey, (int)):
            return Response("lockKey must be an integer", status=400)

        if inputTickerName not in file:
            return Response("Ticker not found", status=400)

        fileTicker = file[inputTickerName]
        if fileTicker["lockKey"] == 0:
            return Response(status=200)
        if fileTicker["lockKey"] != inputLockKey:
            return Response("Wrong lockKey. Cannot unlock it!", status=403)

        fileTicker["lockKey"] = 0
        fileTicker["lockCounter"] = 0
        fileHandler.writeAssetsToMongo(file)
        stockWatcher.forceRefresh()
        return Response(status=200)

@app.route("/tradingpal", methods = ['DELETE'])
def deleteTicker():
    with globalLock:
        if request.data is None:
            return Response("missing body", status=400)

        inputData = json.loads(request.data)

        if "ticker" not in inputData:
            return Response("please provide ticker to delete", status=400)
        if "lockKey" not in inputData:
            return Response("please provide lockKey", status=403)

        file = fileHandler.readAssetsFromMongo()
        inputTickerName = inputData["ticker"]
        inputLockKey = inputData["lockKey"]

        if not isinstance(inputLockKey, (int)):
            return Response("lockKey must be an integer", status=400)

        if inputTickerName not in file:
            return Response("Ticker not found", status=400)

        fileTicker = file[inputTickerName]
        if fileTicker["lockKey"] != inputLockKey:
            return Response("Wrong lockKey. Cannot delete ticker!", status=403)

        del(file[inputTickerName])
        fileHandler.writeAssetsToMongo(file)
        stockWatcher.forceRefresh()
        return Response(status=200)

@app.route("/tradingpal/updateStock", methods = ['POST'])
def updateStock():

    with globalLock:

        if request.data is None:
            return Response("missing body", status=400)

        inputData = json.loads(request.data)

        tradedByBot = False
        if "tradedByBot" in inputData:
            tradedByBot = True

        if "ticker" not in inputData:
            return Response("please provide ticker", status=400)

        fullMongoData = fileHandler.readAssetsFromMongo()
        inputTickerName = inputData["ticker"]

        if inputTickerName not in fullMongoData:
            fullMongoData[inputTickerName] = {}

        tickerInfoFromMongo = fullMongoData[inputTickerName]
        copyOfTickerInfoFromMongo = copy.deepcopy(tickerInfoFromMongo)

        if "lockKey" in tickerInfoFromMongo and tickerInfoFromMongo["lockKey"] == 0:
            return Response("This ticker is not locked and can hence not be updated. Please lock it first", status=400)

        if "lockKey" in inputData:
            newValue = inputData["lockKey"]
            if not isinstance(newValue, (int)):
                return Response("lockKey must be int", status=400)
            if "lockKey" in tickerInfoFromMongo and tickerInfoFromMongo["lockKey"] != newValue:
                return Response("lockKey does not match!", status=403)
            tickerInfoFromMongo["lockKey"] = 0
            tickerInfoFromMongo["lockCounter"] = 0
        else:
            return Response("You need lockKey in order to update data", status=403)

        if "boughtAt" in inputData:
            newBoughtAtValue = inputData["boughtAt"]
            if not isinstance(newBoughtAtValue, (int, float)) and newBoughtAtValue is not None:
                return Response("boughtAt must be float, int or null", status=400)

            if "switchedAt" in tickerInfoFromMongo:
                newSwitchValue = tickerInfoFromMongo["switchedAt"]
            else:
                newSwitchValue = None

            if "boughtAt" in tickerInfoFromMongo:
                newSwitchValue = checkMadeTheSwitch(tickerInfoFromMongo["boughtAt"], newBoughtAtValue, newSwitchValue)

            tickerInfoFromMongo["switchedAt"] = newSwitchValue
            tickerInfoFromMongo["boughtAt"] = newBoughtAtValue
        if "soldAt" in inputData:
            newSoldAtValue = inputData["soldAt"]
            if not isinstance(newSoldAtValue, (int, float)) and newSoldAtValue is not None:
                return Response("soldAt must be float, int or null", status=400)

            if "switchedAt" in tickerInfoFromMongo:
                newSwitchValue = tickerInfoFromMongo["switchedAt"]
            else:
                newSwitchValue = None

            if "soldAt" in tickerInfoFromMongo:
                newSwitchValue = checkMadeTheSwitch(tickerInfoFromMongo["soldAt"], newSoldAtValue, newSwitchValue)

            tickerInfoFromMongo["switchedAt"] = newSwitchValue
            tickerInfoFromMongo["soldAt"] = newSoldAtValue
        if "count" in inputData:
            newValue = inputData["count"]
            if not isinstance(newValue, (int)):
                return Response("count must be int", status=400)
            tickerInfoFromMongo["count"] = newValue
        if "name" in inputData:
            newValue = inputData["name"]
            if not isinstance(newValue, (str)):
                return Response("name must be string", status=400)
            tickerInfoFromMongo["name"] = newValue
        if "totalInvestedSek" in inputData:
            newValue = inputData["totalInvestedSek"]
            if not isinstance(newValue, (int)):
                return Response("totalInvestedSek must be int", status=400)
            tickerInfoFromMongo["totalInvestedSek"] = newValue

        if "boughtAt" not in tickerInfoFromMongo: return Response("You did not provide a value for boughtAt", status=400)
        if "count" not in tickerInfoFromMongo: return Response("You did not provide a value for count", status=400)
        if "lockKey" not in tickerInfoFromMongo: return Response("You did not provide a value for lockKey", status=400)
        if "name" not in tickerInfoFromMongo: return Response("You did not provide a value for name", status=400)
        if "soldAt" not in tickerInfoFromMongo: return Response("You did not provide a value for soldAt", status=400)
        if "totalInvestedSek" not in tickerInfoFromMongo: return Response("You did not provide a value for totalInvestedSek", status=400)

        if tickerInfoFromMongo['boughtAt'] is not None and tickerInfoFromMongo['soldAt'] is not None:
            return Response("At least one of soldAt or boughtAt must be null ")

        fileHandler.writeAssetsToMongo(fullMongoData)
        fileHandler.writeStockChangeLog(copyOfTickerInfoFromMongo, tickerInfoFromMongo, tradedByBot)
        stockWatcher.forceRefresh()
        return Response(status=200)

@app.route("/tradingpal/getTickerValue", methods = ['GET'])
def getTickerValue():
    ticker = request.args.get("ticker")
    currency = request.args.get("currency")

    if ticker is None or currency is None:
        return "Missing arg ticker or currency"

    return json.dumps(stocksFetcher.fetchTickerInfo(ticker, currency, useCacheForDynamics=True, getStaticData=False), indent=4)

@app.route("/tradingpal/getFirstChangeLogItem", methods = ['GET'])
def getChangeLog():
    return json.dumps(fileHandler.takeFirstChangeLogItem(), indent=4)


def checkMadeTheSwitch(oldTradeVal, newTradeVal, currentSwitchValue):

    if oldTradeVal == None and newTradeVal is not None:
        return newTradeVal
    else:
        return currentSwitchValue


if __name__ == "__main__":

    app.run(host='0.0.0.0', port=5000)