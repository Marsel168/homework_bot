import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from telegram.error import TelegramError
from dotenv import load_dotenv
from exceptions import GetAPIError, WrongAPIResponseCodeError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщения в Telegram чат."""
    try:
        logging.info('Начата отправка сообщения')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info('Сообщения успешно отправлено')
    except TelegramError:
        raise TelegramError('Cбой при отправке сообщения в Telegram')


def get_api_answer(current_timestamp):
    """
    Делает запрос к единственному эндпоинту API-сервиса.
    Возвращает ответ API.
    """
    timestamp = current_timestamp or int(time.time())
    request_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    try:
        logging.info('Запрос к API')
        response = requests.get(**request_params)
        logging.info('Отправлен запрос к API')
        if response.status_code != HTTPStatus.OK:
            raise WrongAPIResponseCodeError(
                f'Ответ сервера не является успешным: {response.status_code}'
            )
        return response.json()
    except GetAPIError as error:
        raise GetAPIError(f'Ошибка при запросе к основному API: {error}')


def check_response(response):
    """Проверяет ответ API на корректность."""
    logging.info('Начата проверка ответа сервера')
    if not isinstance(response, dict):
        raise TypeError('response не словарь')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(
            f'В ответе от API под ключом "homeworks" пришел не список. '
            f'homeworks = {homeworks}.'
        )
    if 'homeworks' not in response:
        raise KeyError('Ключ homeworks отсутствует в словаре')
    if 'current_date' not in response:
        raise KeyError('Ключ current_date отсутствует в словаре')
    return homeworks


def parse_status(homework):
    """Получает статус домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Ключ homework_name отсутствует в словаре')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(
            f'Отсутствует статус {homework_name} в словаре HOMEWORK_VERDICTS.'
        )
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if not verdict:
        raise ValueError('Статус домашней работы неизвестен')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствуют токены')
        sys.exit('Отсутствуют токены')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    current_report = {'name': '', 'message': ''}
    prev_report = current_report.copy()
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response['current_date']
            new_homeworks = check_response(response)
            if not new_homeworks:
                message = 'Нет домашней работы на проверке'
                current_report['message'] = message
            else:
                message = parse_status(new_homeworks[0])
                current_report['name'] = new_homeworks[0]['homework_name']
                current_report['message'] = message
            if current_report != prev_report:
                send_message(bot, message)
                prev_report = current_report.copy()
            else:
                logging.info('Нет новых статусов')
        except KeyError as error:
            logging.error(error)
        except ValueError as error:
            logging.critical(error)
        except TypeError as error:
            logging.error(error)
        except GetAPIError as error:
            logging.error(error)
        except TelegramError as error:
            logging.error(error)
        except WrongAPIResponseCodeError as error:
            logging.error(error)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            current_report['message'] = message
            logging.error(message, exc_info=True)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        filename='homework.log',
        filemode='a',
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )
    main()
