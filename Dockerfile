FROM python:3.7-slim

RUN pip install urllib3==1.25.11
RUN pip install Flask==1.1.1 
RUN pip install requests==2.25.1
RUN pip install lxml==4.6.3
RUN pip install bs4==0.0.1
RUN pip install pytz==2020.5
RUN pip list

ADD Analyze.py MainStockWatcher.py RestServer.py StocksFetcher.py FileHandler.py /

ENTRYPOINT ["python3","/RestServer.py"]


# These versions worked, with python:3.7-slim base image
#Package            Version
#------------------ ---------
#beautifulsoup4     4.9.3
#bs4                0.0.1
#certifi            2021.5.30
#chardet            4.0.0
#click              8.0.1
#Flask              1.1.1
#idna               2.10
#importlib-metadata 4.6.0
#itsdangerous       2.0.1
#Jinja2             3.0.1
#lxml               4.6.3
#MarkupSafe         2.0.1
#pip                21.1.3
#requests           2.25.1
#setuptools         57.0.0
#soupsieve          2.2.1
#typing-extensions  3.10.0.0
#urllib3            1.25.11
#Werkzeug           2.0.1
#wheel              0.36.2
#zipp               3.4.1




