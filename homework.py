import json
import logging
import os
import sys
import time
from http import HTTPStatus
from logging import StreamHandler

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(message)s',
    filemode='w',
    encoding='utf-8',
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN_SECRET')
TELEGRAM_TOKEN = os.getenv('TOKEN_CHAT_SECRET')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID_SECRET')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


def check_tokens():
    """Проверка наличия всех переменных окружения."""
    note = 'Отсутвует переменная окружения'
    tokens = {
        PRACTICUM_TOKEN: 'PRACTICUM_TOKEN',
        TELEGRAM_TOKEN: 'TELEGRAM_TOKEN',
        TELEGRAM_CHAT_ID: 'TELEGRAM_CHAT_ID'}
    for token in tokens.keys():
        if token is None:
            note = f'Отсутвует переменная окружения {tokens[token]}'
            raise ValueError(note)


def send_message(bot, message):
    """Функция для отправки сообщений в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение отправлено: {message}')
    except telegram.error.TelegramError as telegram_error:
        logging.error(f'Сообщение не отправлено: {telegram_error}')


def get_api_answer(timestamp):
    """Отправка запроса API сервесу."""
    try:
        if type(timestamp) != int:
            raise TypeError
        payload = {'from_date': timestamp}
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            logging.error('API код отличный от 200')
            raise requests.exceptions.HTTPError
        return response.json()
    except json.JSONDecodeError as error:
        logging.error(f'Не удалось обработать JSON {error}')
        return None
    except requests.exceptions.RequestException as error:
        logging.error(f'запрос недоступен: {error}')
        raise KeyError
    except Exception:
        raise TypeError


def check_response(response):
    """Проверка ответа от API сервеса."""
    if not response:
        logging.error('Нет ответа от сервера')
        raise Exception

    if not isinstance(response, dict):
        logging.error('Ответ API не словарь')
        raise TypeError

    if 'homeworks' not in response:
        logging.error('В ответе API нет ключа — список домашних работ')
        raise KeyError
    if not isinstance(response['homeworks'], list):
        logging.error('В ответе API домашние работы не список')
        raise TypeError
    return response['homeworks']


def parse_status(homework):
    """Проверка статуса домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if all([homework_name, homework_status]):
        verdict = HOMEWORK_VERDICTS.get(homework_status)
        if not verdict:
            raise ValueError(
                f'Недокументированный '
                f'статус домашней работы - {homework_status}')
    else:
        raise KeyError('В ответе API отсутствует имя работы или статус')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    MOUNT_IN_SECONDS = 1500000
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        send_message(bot, 'Start')
        timestamp = int(time.time()) - MOUNT_IN_SECONDS
        check_tokens()
    except ValueError:
        note = 'Переменная(ые) окружения отсутствует(ют).'
        logging.critical(note)
        raise ValueError(note)

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logging.error(message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
