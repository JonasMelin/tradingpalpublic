# Trading pal
## Introduction
Simple helper program that crawls stocks tickers and applies some rules to suggest
when and how many stocks to sell from your current posessions, and what you should
buy more of from your current posessions. Detailed data printed to standard out, 
the buy and sell instructions are presented via a simple web endpoint. Add your 
tickers in the tickers.json and fire it up by launching Restserver.py

## Tickers.json
The tickers are provided in tickers.json either in a file in your current directory, but when running
a container you shall put the ticker file ~/tickers/tickers.json . Go ahead and configure
for your needs. 

## Launching from command line
 * Install dependencies according to Dockerfile
 * \>\> python3 RestServer.py
 * info is dumped to standard out
 * In your web browser, surf to http://localhost:5000 

## Build and launch program as a docker container
\>\> docker build . -t tradingpal <p>
\>\> docker run --rm -v ~/tickers:/tickers --network host tradingpal <p>
 


