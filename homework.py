import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

MOUNT_IN_SECONDS = 1500000

load_dotenv()

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s, %(levelname)s, %(message)s',
        filemode='w',
        encoding='utf-8'
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
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


def check_tokens():
    """Проверка наличия всех переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID}
    tokens_error = [None, '', ' ']
    token_faild = []
    for token in tokens:
        if tokens[token] in tokens_error:
            token_faild.append(token)
    return ", ".join(token_faild)


def send_message(bot, message):
    """Функция для отправки сообщений в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение отправлено: {message}')
    except telegram.error.TelegramError as telegram_error:
        logger.error(f'Сообщение не отправлено: {telegram_error}')


def get_api_answer(timestamp):
    """Отправка запроса API сервесу."""
    payload = {'from_date': timestamp}
    try:
        if type(timestamp) != int:
            raise TypeError
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.exceptions.RequestException as error:
        raise KeyError(f'запрос недоступен: {error}')
    if response.status_code != HTTPStatus.OK:
        raise requests.RequestException(
            f'API код отличный от 200. Был получен код {response.status_code}')
    return response.json()


def check_response(response):
    """Проверка ответа от API сервеса."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не словарь')
    if 'homeworks' not in response:
        raise TypeError('В ответе API нет ключа — список домашних работ')
    if not isinstance(response['homeworks'], list):
        raise TypeError('В ответе API домашние работы не список')
    return response['homeworks']


def parse_status(homework):
    """Проверка статуса домашней работы."""
    anticipated_keys = ['homework_name', 'status']
    for key in anticipated_keys:
        if key not in homework:
            raise KeyError(
                f'В ответе API отсутствует {key}')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(homework_status)

    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS.get(homework_status)
    else:
        raise ValueError(
            f'Недокументированный '
            f'статус домашней работы - {homework_status}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(bot, 'Start')
    timestamp = int(time.time()) - MOUNT_IN_SECONDS
    fail_tokens = check_tokens()
    if fail_tokens:
        logging.critical(
            f'Отсутвует(ют) переменная(ые) окружения {fail_tokens}')
        raise KeyError(
            f'Отсутвует(ют) переменная(ые) окружения {fail_tokens}')
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                first, *_ = homeworks
                message = parse_status(first)
                send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.error(message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
