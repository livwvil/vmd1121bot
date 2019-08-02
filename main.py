import itertools

import requests
import configparser
import telebot
import vk_api
from vk_api.audio import VkAudio
import logging


# TODO очистка данных пользователя по таймеру
# TODO обработчики старых кнопок надо подчищать

def run_bot(token, vk_session):
    users_data = {}
    bot = telebot.TeleBot(token)
    vk_audio = VkAudio(vk_session)

    @bot.message_handler(commands=['search', 'get'])
    def start_message(message):
        users_data[message.chat.id] = {}
        command = message.text.split()[0][1:]
        if command == 'search':
            users_data[message.chat.id]['mode'] = 'search'
            bot.send_message(message.chat.id, "Что будем искать?")
        elif command == 'get':
            users_data[message.chat.id]['mode'] = 'get'
            try:
                users_data[message.chat.id]['user_id'] = message.text.split()[1]
                users_data[message.chat.id]['page'] = 0
                get(message)
            except:
                bot.send_message(message.chat.id, "Вы не ввели id (попробуйте - /get id)")

    @bot.message_handler(content_types=['text'])
    def send_text(message):
        if users_data[message.chat.id]['mode'] == 'search':
            search(message)

    @bot.callback_query_handler(func=lambda call: True)
    def callback_worker(call):
        if users_data[call.message.chat.id]['mode'] == 'search':
            download(call)
        elif users_data[call.message.chat.id]['mode'] == 'get':
            if call.data == 'back':
                users_data[call.message.chat.id]['page'] -= 5
                get(call.message, call.message.message_id)
            elif call.data == 'forward':
                users_data[call.message.chat.id]['page'] += 5
                get(call.message, call.message.message_id)
            else:
                download(call)

    def download(call):
        data = users_data[call.message.chat.id][call.data]
        try:
            print("Загрузка")
            bot.send_message(call.message.chat.id, "Загрузка")
            open('tmp.mp3', 'wb').write(requests.get(data['url'], allow_redirects=True, verify=False).content)
            audio = open('tmp.mp3', "rb")
            bot.send_message(call.message.chat.id, "Отправка")
            print("Отправка")
            bot.send_audio(call.message.chat.id, audio, performer=data['artist'], title=data['title'])
        except Exception as exc:
            print("Ошибка")
            bot.send_message(call.message.chat.id, exc)

    def get_audio_name(audio):
        m, s = divmod(audio["duration"], 60)
        track_name = "{} - {} ({}:{:0<2})".format(audio["artist"], audio["title"], m, s)
        return track_name

    def search(message):
        print("Принято сообщение:", message.text)
        items = [it for it in vk_audio.search(message.text, 5)]
        if len(items) != 0:
            print("По запросу найдено", len(items))
            keyboard = telebot.types.InlineKeyboardMarkup()
            for item in items:
                users_data[message.chat.id][str(items.index(item))] = {'artist': item["artist"], 'title': item["title"],
                                                                       'url': item["url"]}
                key = telebot.types.InlineKeyboardButton(text=get_audio_name(item),
                                                         callback_data=str(items.index(item)))
                keyboard.add(key)
            bot.send_message(message.chat.id, text="Что будем качать?", reply_markup=keyboard)
        else:
            print("По запросу ничего не найдено")
            bot.send_message(message.chat.id, "По запросу ничего не найдено")
        print("Конец")

    def get(message, id_msg_to_edit=None):
        try:
            it = vk_audio.get_iter(users_data[message.chat.id]['user_id'])
            itt = itertools.islice(it, users_data[message.chat.id]['page'], users_data[message.chat.id]['page'] + 5)
            keyboard = telebot.types.InlineKeyboardMarkup()
            costil = 0
            for i in itt:
                users_data[message.chat.id][str(costil)] = i
                keyboard.add(telebot.types.InlineKeyboardButton(text=get_audio_name(i), callback_data=str(costil)))
                costil += 1
            if users_data[message.chat.id]['page'] != 0:
                keyboard.add(telebot.types.InlineKeyboardButton(text="Назад", callback_data="back"))
            if costil != 4:
                keyboard.add(telebot.types.InlineKeyboardButton(text="Вперед", callback_data="forward"))
            if id_msg_to_edit is None:
                bot.send_message(message.chat.id, text='Что будем качать?', reply_markup=keyboard)
            else:
                bot.edit_message_reply_markup(message.chat.id, id_msg_to_edit, reply_markup=keyboard)
        except Exception as exc:
            bot.send_message(message.chat.id, text=exc)

    bot.polling()


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('conf.ini')
    if 'socks5proxy' in config:
        proxy = config['socks5proxy']
        telebot.apihelper.proxy = {
            'https': 'socks5://{login}:{password}@{address}:{port}'.format(login=proxy['login'],
                                                                           password=proxy['password'],
                                                                           address=proxy['address'],
                                                                           port=proxy['port'])}
    if 'debug' in config:
        debug = config['debug']
        if debug['debug_mode'] == 'true':
            logger = telebot.logger
            telebot.logger.setLevel(logging.DEBUG)
    if 'auth' in config:
        auth = config['auth']
        try:
            vk_session = vk_api.VkApi(auth['vk_login'], auth['vk_password'])
            vk_session.auth()
            run_bot(auth['bot_token'], vk_session)
        except vk_api.AuthError as error_msg:
            print(error_msg)
