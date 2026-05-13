import logging
from datetime import datetime, timedelta, date
import pandas as pd
from dateutil.relativedelta import relativedelta
from prices import Client
import sys

logging.basicConfig(level=logging.DEBUG)


def process_data(data, mode, field, date_range_df):

    data = pd.DataFrame(data)

    # Select relevant columns
    data = data[["date", f"bid_{field}", f"ask_{field}", "symbol"]]

    # Convert 'date' column to datetime
    data['date'] = pd.to_datetime(data['date'])

    # Calculate midpoiunt between bid and ask
    data["price"] = (data[f"bid_{field}"] + data[f"ask_{field}"])/2.0

    # Pivot the data
    dups = data.groupby(['date', 'symbol']).size()
    dups = dups[dups>1]
    print(dups)
    data = data.drop_duplicates(keep = 'last')
    data = data.pivot(index='date', columns='symbol', values='price')

    # Define a dictionary map for overlapping instruments
    column_mapping = {
        'NAS100F': 'NAS100',
        'SPX500F': 'SPX500',
        'US30F': 'US30',
        'US2000F': 'US2000'
    }
    
    # Aplly the column mapping to create new columns
    for new_col, orig_col in column_mapping.items():
        if orig_col in data.columns:
            data[new_col] = data[orig_col]


    # Handle UK shares denominated in pence
    columns_to_divide = [col for col in data.columns if '.uk' in col]

    existing_columns = [col for col in columns_to_divide if col in data.columns]

    data[existing_columns] /= 100



    # If daily mode, reduce date column to just date
    if mode == 'D':
        data = process_daily_data(data, date_range_df)
        period = 'TwoYears'

    # Add miussing dates
    else:
        data = process_hourly_data(data, date_range_df)
        period = '30D'
    
    # Save output csv
    save_csv(data, mode, field, period)
    
def process_daily_data(data, date_range_df):
    data = data.reset_index()
    data['date'] = data['date'].dt.date
    data['date'] = pd.to_datetime(data['date'])

    date_range_df['date'] = date_range_df['date'].dt.date
    date_range_df['date'] = pd.to_datetime(date_range_df['date'])

    data = date_range_df.merge(data, on='date',  how='left')
    data['date'] = data['date'] + pd.DateOffset(days=1)

    # Fill missing values
    data = fill_missing_data(data)

    return data

def process_hourly_data(data, date_range_df):
    date_range_df['date'] = pd.to_datetime(date_range_df['date'])

    data = date_range_df.merge(data, on='date',  how='left')
    data['date'] = pd.to_datetime(data['date'])

    # Fill missing values
    data = fill_missing_data(data)

    return data

def fill_missing_data(data):
    data = data.fillna(method='ffill')
    data = data.fillna(method="bfill")
    return data

def save_csv(data, mode, field, period):
    data.to_csv(f"{mode}1-{field}-{period}-4Y-fc.csv", index=False)

def check_mode_validity(mode):
    valid_modes = ['D', 'H']
    if mode not in valid_modes:
        print('Incorrect mode! Exiting!')
        sys.exit()

def load_symbols():
    symbols = pd.read_csv("symbols.csv", squeeze=True)
    return symbols.tolist()

def setup_date_range(mode):
    today = pd.to_datetime(datetime.today().date() -
                           timedelta(days=1)).replace(hour=21)
    if mode == 'D':
        yesterday = today - timedelta(days=729)
    else:
        #yesterday = today - timedelta(days=90)
        yesterday = datetime(2025, 6,10)

    date_range = pd.date_range(yesterday, today, freq=mode)
    date_range_df = pd.DataFrame({'date': date_range})
    date_range_df['date'] = pd.to_datetime(date_range_df['date'])
    return today, yesterday, date_range_df


def main():
    modes = ['H']
    missing_symbols = []
    for mode in modes:
        check_mode_validity(mode)
        symbols = ['USD/JPY', 'EUR/USD', 'XAU/USD', 'WHEATF', 'XAG/USD', 'GBP/USD']
        today, yesterday, date_range_df = setup_date_range(mode)

        print(today, yesterday)
        fields = ['high', 'low', 'close', 'open']
        client = Client()
        # set connection="demo" for demo accounts
        client.connect("1206026841", "1206026841", connection="real")

        for field in fields:
            data = []
            for symbol in symbols:
                try:
                    prices = client.price_history(
                        symbol, f"{mode}1", yesterday, today)
                    for p in prices:
                        p["symbol"] = symbol
                    data += prices
                except Exception as err:
                    print(f"{type(err).__name__} for {symbol}: {err}")
                    missing_symbols.append(symbol)

            # Call a function to prepare and save CSV data
            process_data(data, mode, field, date_range_df)

        client.close()

    missing_symbols = set(missing_symbols)

    with open('missing_symbols.txt', 'w') as f:
        for line in missing_symbols:
            f.write(f"{line}\n")


if __name__ == "__main__":
    main()
