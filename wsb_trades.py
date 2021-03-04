import os
import alpaca_trade_api as tradeapi
import praw
import time
import math

import trade_models

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
stockPoints = {}

# holds the share amounts to be calculated
shareAmounts = {}


# define all the functions needed
def add_points(stockTicker, pointValue):
    if stockTicker in stockPoints.keys():
        stockPoints[stockTicker] += pointValue
    else:
        stockPoints[stockTicker] = pointValue


def process_comment(comment):
    # loop over all the assets cause im a terrible programmer and dont know how to do this elsewise
    assetList = api.list_assets(status='active')

    # see if there's some points to get
    for pointStringList in trade_models.positive_points:
        if pointStringList[0] in comment.body and pointStringList[1] in comment.body:
            for asset in assetList:
                # if the comment has the symbol, lets give that stock ticker some points
                symbolString = " " + asset.symbol + " "
                if symbolString in comment.body:
                    add_points(asset.symbol, pointStringList[2] * (comment.score - 4) * comment.body.count(pointStringList[0]))
                    print(asset.symbol, stockPoints[asset.symbol])


def update_wsb_valuations():
    for submission in reddit.subreddit("wallstreetbets").hot(limit=10):
        print("new post")
        submission.comments.replace_more(0)
        for comment in submission.comments:
            if comment.score < 5:
                continue
            process_comment(comment)


while True:
    # clear the stockPoints so we can get our new values
    stockPoints.clear()

    # check if market is open for the next 10 minutes, else don't do anything
    if not api.get_clock().is_open:
        print('Market is not open.')
        time.sleep(60 * 5)
        continue

    # Check if our account is restricted from trading for some oppressive reason
    if api.get_account().trading_blocked:
        print('Account is currently restricted from trading.')
        time.sleep(60 * 10)
        continue

    # check rolling comments on wsb new for our new values
    print("Begin updating...")
    update_wsb_valuations()

    # find out our total value through stocks and buying power
    account = api.get_account()
    accountValue = float(account.buying_power)
    for position in api.list_positions():
        accountValue = accountValue + (float(api.get_last_trade(position.symbol).price) * float(position.qty))

    # get our stock amounts that we should be holding
    totalPoints = 0
    for ticker in stockPoints.keys():
        totalPoints += stockPoints[ticker]
    for ticker in stockPoints.keys():
        # calculate percentage of total points this stock accounts for
        percentage = (stockPoints[ticker] / totalPoints)
        # how much money should we have of this stock? multiply by .9 to have a 10% error threshold
        moneyAmount = math.floor(percentage * accountValue * .9)
        # how many shares does that equate to?  if it's not a full share than we don't buy!
        shareAmount = math.floor(moneyAmount / float(api.get_last_trade(ticker).price))
        print(totalPoints, ticker, stockPoints[ticker], moneyAmount, api.get_last_trade(ticker).price, shareAmount, percentage, accountValue)
        if shareAmount > 0:
            shareAmounts[ticker] = shareAmount

    # sell anything we have too much of
    for position in api.list_positions():
        if position.symbol not in shareAmounts:
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
        elif shareAmounts[position.symbol] < int(position.qty):
            # sell the difference
            try:
                api.submit_order(
                    symbol=position.symbol,
                    qty=(int(position.qty) - int(shareAmounts[position.symbol])),
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
    for ticker in shareAmounts.keys():
        # if I already have some of this, see if i need to buy more
        found = False
        for position in api.list_positions():
            if ticker == position.symbol:
                if shareAmounts[ticker] > int(position.qty):
                    found = True
                    # buy more shares!
                    try:
                        api.submit_order(
                            symbol=ticker,
                            qty=(int(shareAmounts[ticker]) - int(position.qty)),
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
                    qty=int(shareAmounts[ticker]),
                    side='buy',
                    type='market',
                    time_in_force='day'
                )
            except:
                pass
            time.sleep(2)
