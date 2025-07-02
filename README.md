# Telegram Event Manager

A modular, maintainable Telegram bot for managing weekly event schedules, built with Python, SQLAlchemy, and python-telegram-bot.

## Setup

1. **Clone the repository**
2. **Install dependencies**:
    ```
    pip install -r requirements.txt
    ```
3. **Copy `.env.example` to `.env` and set your environment variables**:
    ```
    TELEGRAM_BOT_TOKEN=YOUR_TOKEN
    ADMIN_IDS=123456789,987654321
    ```
4. **Run the bot**:
    ```
    python bot.py
    ```

## Features

- View and participate in scheduled events for a week from current day
- Admin interface for editing events

## License

MIT