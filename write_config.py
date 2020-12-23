import pathlib
from configparser import ConfigParser

config = ConfigParser()

config.add_section('main')

config.set('main', 'REGULAR_ACCOUNT', 'ENTER_YOUR_REGULAR_ACCOUNT_HERE')
config.set('main', 'REGULAR_PASSWORD', 'ENTER_YOUR_REGULAR_PASSWORD')
config.set('main', 'REGULAR_USERNAME', 'ENTER_YOUR_REGULAR_USERNAME')

config.set('main', 'PAPER_ACCOUNT', 'ENTER_YOUR_PAPER_ACCOUNT_HERE')
config.set('main', 'PAPER_PASSWORD', 'ENTER_YOUR_PAPER_PASSWORD_HERE')
config.set('main', 'PAPER_USERNAME', 'ENTER_YOUR_PAPER_USERNAME_HERE')

new_directory = pathlib.Path("config/").mkdir(parents=True, exist_ok=True)

with open('config/config.ini', 'w+') as f:
    config.write(f)