import logging
import os
import sys
import time
import requests
import telegram
from dotenv import load_dotenv

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

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщения в Telegram чат."""
    bot.send_message(TELEGRAM_CHAT_ID, message)


def get_api_answer(current_timestamp):
    """
    Делает запрос к единственному эндпоинту API-сервиса.
    Возвращает ответ API.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        logger.info('Отправлен запрос к API')
    except Exception as error:
        logger.error(f'Ошибка при запросе к основному API: {error}')

    if response.status_code != 200:
        logger.error(f'Response status cod error: {response.status_code}')
        raise Exception('API не ответил')
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('response не список')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('homeworks не список')
    if homeworks is None:
        raise KeyError('Ключ homeworks отсутствует в словаре')
    return homeworks


def parse_status(homework):
    """
    Извлекает из информации о конкретной домашней работе статус этой работы.

    """
    if not homework:
        raise Exception('Домашняя работа не найдена')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None:
        raise KeyError('Отсутствует homework_name')
    if homework_status is None:
        raise Exception('Отсутствует homework_status')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if verdict is None:
        raise Exception('Статус домашней работы неизвестен')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if PRACTICUM_TOKEN is None:
        logger.critical("Отсутствует обязательная переменная окружения:"
                        " 'PRACTICUM_TOKEN'")
    if TELEGRAM_TOKEN is None:
        logger.critical("Отсутствует обязательная переменная окружения:"
                        " 'TELEGRAM_TOKEN'")
    if TELEGRAM_CHAT_ID is None:
        logger.critical("Отсутствует обязательная переменная окружения:"
                        " 'TELEGRAM_CHAT_ID'")
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    prev_report = {}
    check_tokens()
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response['current_date']
            homeworks = check_response(response)
            try:
                message = parse_status(homeworks[0])
            except Exception:
                logger.error('Cбой при формировании сообщения в Telegram')
            finally:
                current_report = {
                    'name': homeworks[0].get('homework_name'),
                    'message': homeworks[0].get('status'),
                }
            if current_report != prev_report:
                try:
                    send_message(bot, message)
                except Exception:
                    logging.error('Cбой при отправке сообщения в Telegram')
                finally:
                    prev_report = current_report.copy()
            else:
                logger.info('Нет новых статусов')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            ...
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
