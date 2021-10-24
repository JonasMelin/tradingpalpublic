
from flask import Flask, request, Response
import MainStockWatcher
import threading
import json
import FileHandler
import random
import math
import copy

REFRESH_DELAY_SEC = 30

app = Flask(__name__)
globalLock = threading.Lock()
fileHandler = FileHandler.FileHandler()
stockWatcher = MainStockWatcher.MainStockWatcher(fileHandler)

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

        file = fileHandler.readFileFromDisk()
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
        fileHandler.writeFileToDisk(file)
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

        file = fileHandler.readFileFromDisk()
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
        fileHandler.writeFileToDisk(file)
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

        file = fileHandler.readFileFromDisk()
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
        fileHandler.writeFileToDisk(file)
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

        file = fileHandler.readFileFromDisk()
        inputTickerName = inputData["ticker"]

        if inputTickerName not in file:
            file[inputTickerName] = {}

        fileTicker = file[inputTickerName]
        copyOfFileTicker = copy.deepcopy(fileTicker)

        if "lockKey" in fileTicker and fileTicker["lockKey"] == 0:
            return Response("This ticker is not locked and can hence not be updated. Please lock it first", status=400)

        if "lockKey" in inputData:
            newValue = inputData["lockKey"]
            if not isinstance(newValue, (int)):
                return Response("lockKey must be int", status=400)
            if "lockKey" in fileTicker and fileTicker["lockKey"] != newValue:
                return Response("lockKey does not match!", status=403)
            fileTicker["lockKey"] = 0
            fileTicker["lockCounter"] = 0
        else:
            return Response("You need lockKey in order to update data", status=403)

        if "boughtAt" in inputData:
            newValue = inputData["boughtAt"]
            if not isinstance(newValue, (int, float)) and newValue is not None:
                return Response("boughtAt must be float, int or null", status=400)
            fileTicker["boughtAt"] = newValue
        if "soldAt" in inputData:
            newValue = inputData["soldAt"]
            if not isinstance(newValue, (int, float)) and newValue is not None:
                return Response("soldAt must be float, int or null", status=400)
            fileTicker["soldAt"] = newValue
        if "count" in inputData:
            newValue = inputData["count"]
            if not isinstance(newValue, (int)):
                return Response("count must be int", status=400)
            fileTicker["count"] = newValue
        if "name" in inputData:
            newValue = inputData["name"]
            if not isinstance(newValue, (str)):
                return Response("name must be string", status=400)
            fileTicker["name"] = newValue
        if "totalInvestedSek" in inputData:
            newValue = inputData["totalInvestedSek"]
            if not isinstance(newValue, (int)):
                return Response("totalInvestedSek must be int", status=400)
            fileTicker["totalInvestedSek"] = newValue

        if "boughtAt" not in fileTicker: return Response("You did not provide a value for boughtAt", status=400)
        if "count" not in fileTicker: return Response("You did not provide a value for count", status=400)
        if "lockKey" not in fileTicker: return Response("You did not provide a value for lockKey", status=400)
        if "name" not in fileTicker: return Response("You did not provide a value for name", status=400)
        if "soldAt" not in fileTicker: return Response("You did not provide a value for soldAt", status=400)
        if "totalInvestedSek" not in fileTicker: return Response("You did not provide a value for totalInvestedSek", status=400)

        if fileTicker['boughtAt'] is not None and fileTicker['soldAt'] is not None:
            return Response("At least one of soldAt or boughtAt must be null ")

        fileHandler.writeFileToDisk(file)
        fileHandler.writeStockChangeLog(copyOfFileTicker, fileTicker, tradedByBot)
        stockWatcher.forceRefresh()
        return Response(status=200)

@app.route("/tradingpal/getFirstChangeLogItem", methods = ['GET'])
def getChangeLog():
    return json.dumps(fileHandler.takeFirstChangeLogItem(), indent=4)

if __name__ == "__main__":

    app.run(host='0.0.0.0', port=5000)