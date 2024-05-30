from lumibot.brokers import Alpaca
from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies.strategy import Strategy
from datetime import datetime, timedelta
from alpaca_trade_api import REST
from finbert_utils import estimate_sentiment
import numpy as np
import pandas as pd

API_KEY = "PKGOFPNAT6C71GQ3ACSP"
API_SECRET = "YY89yu5wdTvnCia8UdIeXM9B67LI9Hnw4zJR0Fik"
BASE_URL = "https://paper-api.alpaca.markets/v2"

ALPACA_CREDS = {
"API_KEY": API_KEY,
"API_SECRET": API_SECRET,
"PAPER": True
}

class MLTrader(Strategy):
	def initialize(self, symbol:str="SPY", cash_at_risk:float=.5):
		self.symbol = symbol
		self.sleeptime = "24H"
		self.last_trade = None
		self.cash_at_risk = cash_at_risk
		self.api = REST(base_url=BASE_URL, key_id=API_KEY, secret_key=API_SECRET)
		self.close_prices = []  # List to store last 50 closing prices

	def position_sizing(self):
			cash = self.get_cash()
			last_price = self.get_last_price(self.symbol)
			quantity = round(cash * self.cash_at_risk / last_price)
			return cash, last_price, quantity
	def get_dates(self):
		today = self.get_datetime()
		three_days_prior = today - timedelta(days=3)
		return today.strftime('%Y-%m-%d'), three_days_prior.strftime('%Y-%m-%d')

	def get_sentiment(self):
		today, three_days_prior = self.get_dates()
		news = self.api.get_news(symbol=self.symbol, start=three_days_prior, end=today)
		news = [ev.__dict__["_raw"]["headline"] for ev in news]
		probability, sentiment = estimate_sentiment(news)
		return probability, sentiment

	def update_close_prices(self, new_close):
		if len(self.close_prices) == 50:  # If we already have 50 closing prices
			self.close_prices.pop(0)  # Remove the oldest closing price
		self.close_prices.append(new_close)  # Add the new closing price

	def calculate_moving_averages(self):
		short_term_ma = sum(self.close_prices[-20:]) / min(20, len(self.close_prices))
		long_term_ma = sum(self.close_prices[-50:]) / min(50, len(self.close_prices))
		return short_term_ma, long_term_ma

	def on_trading_iteration(self):
		cash, last_price, quantity = self.position_sizing() 
		probability, sentiment = self.get_sentiment()

		if cash > last_price: 
			if sentiment == "positive" and probability > .999: 
				if self.last_trade == "sell": 
					self.sell_all() 
				order = self.create_order(
					self.symbol, 
					quantity, 
					"buy", 
					type="bracket", 
					take_profit_price=last_price*1.20, 
					stop_loss_price=last_price*.95
				)
				self.submit_order(order) 
				self.last_trade = "buy"
			elif sentiment == "negative" and probability > .999: 
				if self.last_trade == "buy":
					self.sell_all() 
				order = self.create_order(
					self.symbol, 
					quantity, 
					"sell", 
					type="bracket", 
					take_profit_price=last_price*.8, 
					stop_loss_price=last_price*1.05
				)
				self.submit_order(order) 
				self.last_trade = "sell"

			# Update close prices and calculate moving averages for next iteration
			self.update_close_prices(last_price)
			short_term_ma, long_term_ma = self.calculate_moving_averages()


start_date = datetime(2020,1,1)
end_date = datetime(2023,12,31)

broker = Alpaca(ALPACA_CREDS)

strategy = MLTrader(name='mlstrat', broker=broker, parameters={"symbol":"SPY", "cash_at_risk":.5, "min_prob":0.7})
strategy.backtest(
YahooDataBacktesting, 
start_date,
end_date,
parameters={"symbol":"SPY", "cash_at_risk":.5, "min_prob":0.7}
)

# trader = Trader()
# trader.add_strategy(strategy)
# trader.run_all()
