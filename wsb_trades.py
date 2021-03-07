import alpaca_trade_api as tradeapi
from trade_models import positive_points

import os
import praw
import time
import math


os.environ['APCA_API_BASE_URL'] = "https://paper-api.alpaca.markets"
os.environ['APCA_API_KEY_ID'] = ""
os.environ['APCA_API_SECRET_KEY'] = ""

api = tradeapi.REST()

reddit = praw.Reddit(client_id="",
                     client_secret="",
                     password="",
                     user_agent="",
                     username=""
                     )

# holds the values for each cycle
stock_points = {}

share_amounts = {}


def add_points(stock_ticker, point_value):
    if stock_ticker in stock_points:
        stock_points[stock_ticker] += point_value
    else:
        stock_points[stock_ticker] = point_value


def process_comment(comment):
    asset_list = api.list_assets(status='active')

    for point_string_list in positive_points:
        if point_string_list[0] in comment.body and point_string_list[1] in comment.body:
            for asset in asset_list:
                symbol_string = f" {asset.symbol} "
                if symbol_string in comment.body:
                    comment_score = comment.score - 4
                    point_value = point_string_list[2] * comment_score * comment.body.count(point_string_list[0])
                    add_points(asset.symbol, point_value)
                    print(asset.symbol, stock_points[asset.symbol])


def update_wsb_valuations():
    """check rolling comments on wsb new for our new values"""
    hot_posts = reddit.subreddit('wallstreetbets').hot(limit=10)

    for submission in hot_posts:
        print("new post")
        sub_comments = submission.comments
        sub_comments.replace_more(0)

        for comment in sub_comments:
            if comment.score > 5:
                process_comment(comment)
            continue


def get_account_value(account_value):
    for position in api.list_positions():
        price = api.get_last_trade(position.symbol).price
        account_value += float(price) * float(position.qty)
    return account_value


while True:
    stock_points.clear()

    if not api.get_clock().is_open:
        print('Market is not open.')
        time.sleep(300)
        continue

    if api.get_account().trading_blocked:
        print('Account is currently restricted from trading.')
        time.sleep(600)
        continue

    print("Begin updating...")
    update_wsb_valuations()

    account = api.get_account()
    account_value = float(account.buying_power)
    account_value = get_account_value(account_value)

    # get our stock amounts that we should be holding
    totalPoints = 0
    for ticker in stock_points.keys():
        totalPoints += stock_points[ticker]
    for ticker in stock_points.keys():
        # calculate percentage of total points this stock accounts for
        percentage = (stock_points[ticker] / totalPoints)
        # how much money should we have of this stock? multiply by .9 to have a 10% error threshold
        moneyAmount = math.floor(percentage * account_value * .9)
        # how many shares does that equate to?  if it's not a full share than we don't buy!
        shareAmount = math.floor(moneyAmount / float(api.get_last_trade(ticker).price))
        print(totalPoints, ticker, stock_points[ticker], moneyAmount, api.get_last_trade(ticker).price, shareAmount, percentage, account_value)
        if shareAmount > 0:
            share_amounts[ticker] = shareAmount

    # sell anything we have too much of
    for position in api.list_positions():
        if position.symbol not in share_amounts:
            # sell it all we don't want it
            try:
                api.submit_order(
                    symbol=position.symbol,
                    qty=int(position.qty),
                    side='sell',
                    type='market',
                    time_in_force='day'
                )
            except:
                pass

            time.sleep(2)
        elif share_amounts[position.symbol] < int(position.qty):
            # sell the difference
            try:
                api.submit_order(
                    symbol=position.symbol,
                    qty=(int(position.qty) - int(share_amounts[position.symbol])),
                    side='sell',
                    type='market',
                    time_in_force='day'
                )
            except:
                pass
            time.sleep(2)
    # wait and hopefully the orders goes through
    time.sleep(60)
    # buy the ones that I do need
    for ticker in share_amounts.keys():
        # if I already have some of this, see if i need to buy more
        found = False
        for position in api.list_positions():
            if ticker == position.symbol:
                if share_amounts[ticker] > int(position.qty):
                    found = True
                    # buy more shares!
                    try:
                        api.submit_order(
                            symbol=ticker,
                            qty=(int(share_amounts[ticker]) - int(position.qty)),
                            side='buy',
                            type='market',
                            time_in_force='day'
                        )
                    except:
                        pass
                    time.sleep(2)
        if not found:
            # if we don't already own it, let's buy some
            # buy more shares!
            try:
                api.submit_order(
                    symbol=ticker,
                    qty=int(share_amounts[ticker]),
                    side='buy',
                    type='market',
                    time_in_force='day'
                )
            except:
                pass
            time.sleep(2)
