import asyncio

import tweepy
import telebot
from telebot.async_telebot import AsyncTeleBot
import ast
import json
import time

keys = open("twitter_keys.txt").readlines()
keys = [key.rstrip("\n") for key in keys]

api_key = keys[0]
api_secret = keys[1]
bearer_token = keys[2]
access_key = keys[3]
access_secret = keys[4]

client = tweepy.Client(bearer_token, api_key, api_secret, access_key, access_secret)

auth = tweepy.OAuthHandler(api_key, api_secret)
auth.set_access_token(access_key, access_secret)
api = tweepy.API(auth)

with open("tg_token.txt") as file:
    tg_token = file.readlines()[0].rstrip("\n")
tgbot = AsyncTeleBot(tg_token)

# @tgbot.channel_post_handler(content_types=['text'])
# def handle_chat(message):
#     global chat_id
#     if message.text == "/get":
#         tgbot.send_message(chat_id, "Понял")


# @tgbot.message_handler(content_types=['text'])
# def get_text_messages(message):
#     global user_id
#     user_id = message.forward_from_chat.id
#     if message.text == "/start":
#         user_id = message.from_user.id
#         tgbot.send_message(user_id, "Понял! Начинаю работу")
#     if message.text != "/get":
#         i = int(message.text)
#         # tgbot.send_photo(message.from_user.id,
#         #                  tweets[i].entities["media"][0]["media_url"],
#         #                  caption=tweets[i].full_text)
#         media = {}
#         if "media" in tweets[i].entities \
#                 and "media" in tweets[i].extended_entities:
#             media = tweets[i].extended_entities["media"]
#             photos = [telebot.types.InputMediaPhoto(photo["media_url"]) for photo in media]
#             photos[0].caption = tweets[i].full_text
#             tgbot.send_media_group(message.from_user.id, photos)
#         else:
#             tgbot.send_message(message.from_user.id, tweets[i].full_text)
#         # if tweets[2].retweeted:
#         #     tgbot.send_message(message.from_user.id, tweets[2].retweeted_status.full_text)

bot_json = {"users": [],
            "chats": [],
            "user_ids": [],
            "chat_ids": [],
            "update_offset": 0,
            "since_id": 0}
print(bot_json)


async def resolve_json(file_name: str):
    global bot_json
    with open(file_name, "r") as file:
        lines = file.readlines()
        length = len(lines)
    if length == 0:
        await update_json(file_name, bot_json)
    else:
        bot_json = json.loads(lines[0])


@tgbot.message_handler(commands=["sign"])
async def sign_user(message):
    user = message.from_user
    # noinspection PyTypeChecker
    user_dict = ast.literal_eval(str(user))
    print(user_dict)

    if user.id not in bot_json["user_ids"]:
        bot_json["users"].append(user_dict)
        bot_json["user_ids"].append(user.id)
        await tgbot.send_message(user.id, "Теперь я буду отправлять тебе твиты в личные сообщения!")
        await update_json("bot_json.json", bot_json)
    else:
        await tgbot.send_message(user.id, "Ты уже подписан на уведомления!")
    print(bot_json)


@tgbot.message_handler(content_types=["text"])
async def sign_chat(message):
    chat = message.forward_from_chat
    if chat is None:
        return

    chat_dict = ast.literal_eval(str(chat))

    if chat_dict["id"] not in bot_json["chat_ids"]:
        bot_json["chats"].append(chat_dict)
        bot_json["chat_ids"].append(chat_dict["id"])
        await update_json("bot_json.json", bot_json)

        await tgbot.send_message(chat_dict["id"], "Приятно познакомиться! Теперь я буду высылать твиты в этот канал")


@tgbot.message_handler(commands=["start"])
async def handle_start(message):
    user = message.from_user
    await tgbot.send_message(user.id,
                             "Привет, " + user.first_name + "! Перешли сообщение из канала, в который нужно будет "
                                                            "отправлять твиты. Так я пойму куда мне это нужно "
                                                            "делать.\n"
                                                            "Либо напиши команду /sign, чтобы я отправлял обновления "
                                                            "с канала тебя напрямую \n"
                                                            "Но сначала не забудь добавить меня в админы канала!!!")


# TODO Считывание твитов и запоминание последнего

async def handle_tweets(offset: int, ids: list):
    if offset == 0:
        tweets = api.user_timeline(user_id="xeldery", tweet_mode="extended", count=1)
    else:
        tweets = api.user_timeline(user_id="xeldery", tweet_mode="extended", since_id=offset)
    for tweet in reversed(tweets):
        for id in ids:
            await send_tweet(id, tweet)
        bot_json["since_id"] = tweet.id
        await update_json("bot_json.json", bot_json)


async def send_tweet(id, tweet):
    if "media" in tweet.entities \
            and "media" in tweet.extended_entities:
        media = tweet.extended_entities["media"]
        photos = [telebot.types.InputMediaPhoto(photo["media_url"]) for photo in media]
        photos[0].caption = tweet.full_text
        await tgbot.send_media_group(id, photos)
    else:
        await tgbot.send_message(id, tweet.full_text)


async def handle_chats(since_id):
    # await handle_updates(bot_json["chats"])
    await handle_tweets(since_id, bot_json["chat_ids"])


async def handle_users(since_id):
    # await handle_updates(bot_json["users"])
    await handle_tweets(since_id, bot_json["user_ids"])


# async def handle_updates(users: list):
#     for user_info in users:
#         updates = await tgbot.get_updates(offset=user_info["update_offset"], allowed_updates=["message"], timeout=10)
#         if len(updates) > 0:
#             user_info["update_offset"] = updates[len(updates) - 1].update_id + 1
#             await update_json("bot_json.json", bot_json)
#
#         await tgbot.process_new_updates(updates)


async def work():
    while True:
        print(bot_json["update_offset"])
        print(bot_json)
        # TODO обработка Update_offset для каждого пользователя
        updates = await tgbot.get_updates(offset=bot_json["update_offset"], allowed_updates=["message"], timeout=10)
        if len(updates) > 0:
            bot_json["update_offset"] = updates[len(updates) - 1].update_id + 1
            await update_json("bot_json.json", bot_json)
        for update in updates:
            print(update)
        await tgbot.process_new_updates(updates)

        since_id = bot_json["since_id"]
        await handle_chats(since_id)
        await handle_users(since_id)
        # await asyncio.sleep(5)


@tgbot.message_handler(commands=["post"])
async def post(message):
    api.update_status("How are u today?")


async def update_json(file_name: str, json_dict: dict):
    with open(file_name, "w") as file:
        json.dump(json_dict, file)


# TODO добавить счетчик последнего твита в json как и последнего сообщения в телеге.


async def main():
    await resolve_json("bot_json.json")
    await work()


asyncio.run(main())
