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
    tokens = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID]
    for token in tokens:
        if token is None:
            note = f'Отсутвует(ют) переменная(ые) окружения {token}'
            logging.critical(note)
            raise SystemExit(-1)
    return all(tokens)


def send_message(bot, message):
    """Функция для отправки сообщений в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение отправлено: {message}')
    except telegram.error.TelegramError as telegram_error:
        logging.error(f'Сообщение не отправлено: {telegram_error}')


def get_api_answer(timestamp):
    """Отправка запроса API сервесу."""
    payload = {'from_date': timestamp}
    try:
        if type(timestamp) != int:
            raise TypeError
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        status_code = response.status_code
    except requests.exceptions.RequestException as error:
        logging.error(f'запрос недоступен: {error}')
    if response.status_code != HTTPStatus.OK:
        note = f'API код отличный от 200. Был получен код {status_code}'
        raise requests.RequestException(f'{note}')
    return response.json()


def check_response(response):
    """Проверка ответа от API сервеса."""
    if not response:
        note = 'Нет ответа от сервера'
        raise note

    if not isinstance(response, dict):
        note = 'Ответ API не словарь'
        raise note

    if 'homeworks' not in response:
        note = 'В ответе API нет ключа — список домашних работ'
        raise note
    if not isinstance(response['homeworks'], list):
        note = 'В ответе API домашние работы не список'
        raise note
    return response['homeworks']


def parse_status(homework):
    """Проверка статуса домашней работы."""
    if homework:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
        if not homework_name:
            raise KeyError('В ответе API отсутствует имя работы')
        if not homework_status:
            raise KeyError('В ответе API отсутствует имя статус')
        verdict = HOMEWORK_VERDICTS.get(homework_status)
        if not verdict:
            raise ValueError(
                f'Недокументированный '
                f'статус домашней работы - {homework_status}')
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(bot, 'Start')
    timestamp = int(time.time()) - MOUNT_IN_SECONDS
    check_tokens()

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
            logging.error(message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
