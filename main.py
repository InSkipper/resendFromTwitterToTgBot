import asyncio
import json

import telebot
import tweepy
from telebot.async_telebot import AsyncTeleBot

twitter_update_time = 3

keys = open("twitter_keys.txt").readlines()
keys = [key.rstrip("\n") for key in keys]

api_key = keys[0]
api_secret = keys[1]
bearer_token = keys[2]
access_key = keys[3]
access_secret = keys[4]

auth = tweepy.OAuth2BearerHandler(bearer_token)
api = tweepy.API(auth, timeout=2)

with open("tg_token.txt") as file:
    tg_token = file.readlines()[0].rstrip("\n")
tgbot = AsyncTeleBot(tg_token)

bot_json = {"followers": [],
            "update_offset": 0}


async def resolve_json(file_name: str):
    global bot_json
    with open(file_name, "r") as file:
        lines = file.readlines()
        length = len(lines)
    if length == 1:
        bot_json = json.loads(lines[0])
    else:
        await update_json()


@tgbot.message_handler(commands=["start"])
async def handle_user_start(message):
    user = message.from_user
    await tgbot.send_message(user.id,
                             "Привет, " + user.first_name
                             + "!\nЧтобы начать отслеживание пользователя воспользуйся "
                               "коммандой '/add *id твиттера*'.\n"
                               "Возможно добавление множества пользователей\n"
                               "Для того, чтобы пользоваться ботом в канале,"
                               " нужно добавить его в админы канала.")


@tgbot.channel_post_handler(commands=["start"])
async def handle_chat_start(message):
    chat = message.chat
    await tgbot.send_message(chat.id,
                             "Приветствую всех на канале " + chat.title
                             + "!\nЧтобы начать отслеживание пользователя воспользуйтесь "
                               "коммандой '/add *id твиттера*'.\n"
                               "Возможно добавление множества пользователей!")


@tgbot.channel_post_handler(commands=["add"])
@tgbot.message_handler(commands=["add"])
async def add_to_signs(message):
    twitter_id = message.text.replace("/add", "").strip()
    if message.from_user is None:
        user = message.chat
    else:
        user = message.from_user
    if len(twitter_id) == 0:
        await tgbot.send_message(user.id,
                                 f'После /add нужно написать id пользователя в твиттер. Этот id можно посмотреть по '
                                 f'ссылке на его профиль в твиттере')
        return

    try:
        tweets = api.user_timeline(screen_name=twitter_id, count=1)
    except:
        await tgbot.send_message(user.id, f"Не могу найти пользователя с id *{twitter_id}*."
                                          f"Либо у него ещё нет твитов")
        return

    if len(tweets) > 0:
        await add_sign(user.id, twitter_id, tweets[0].id)
    else:
        await add_sign(user.id, twitter_id, 0)


@tgbot.message_handler(commands=["remove"])
@tgbot.channel_post_handler(commands=["remove"])
async def handle_remove(message):
    twitter_id = message.text.replace("/remove", "").strip()
    if message.from_user is None:
        user = message.chat
    else:
        user = message.from_user
    follower = await find_follower(user.id)
    if follower is None:
        await tgbot.send_message(user.id,
                                 f'Вы не на что не подписаны. Для начала '
                                 f'воспользуйтесь командой /add')
        return

    if len(twitter_id) == 0:
        await tgbot.send_message(user.id,
                                 f'После /remove нужно написать id пользователя в твиттер. '
                                 f'Этот id можно посмотреть по '
                                 f'ссылке на его профиль в твиттере.\n'
                                 f'Вы подписаны на:\n\t'
                                 + '\n\t'.join(await get_twitter_ids(follower)))

        return

    await remove_sign(follower, twitter_id)


async def find_follower(tg_id: int):
    for follower in bot_json["followers"]:
        if follower["tg_id"] == tg_id:
            return follower
    return None


async def get_twitter_ids(follower: dict) -> list:
    return [sign["twitter_id"] for sign in follower["signs"]]


async def remove_sign(follower: dict, twitter_id: str):
    for i in range(len(follower["signs"])):
        if twitter_id == follower["signs"][i]["twitter_id"]:
            del follower["signs"][i]
            await update_json()
            await tgbot.send_message(follower["tg_id"], f"Отписал вас от уведомлений пользователя "
                                                        f"*{twitter_id}*")
            return

    await tgbot.send_message(follower["tg_id"], f"Кажется, вы ошиблись в написании команды. "
                                                f"Не могу найти пользователя *{twitter_id}*")


async def add_sign(tg_id, twitter_id, since_id):
    sign = {"twitter_id": twitter_id,
            "since_id": since_id}

    follower = None
    for foll in bot_json["followers"]:
        if foll["tg_id"] == tg_id:
            follower = foll
    if follower is None:
        follower = {"tg_id": tg_id,
                    "signs": []}
        bot_json["followers"].append(follower)

    twitt_ids = await get_twitter_ids(follower)
    if twitter_id in twitt_ids:
        await tgbot.send_message(tg_id, f"Вы уже подписаны на уведомления от *{twitter_id}*!")
    else:
        follower["signs"].append(sign)
        await tgbot.send_message(tg_id, f"Теперь я буду отправлять сюда твиты от *{twitter_id}*!")

    await update_json()


async def handle_tweets():
    for follower in bot_json["followers"]:
        for sign in follower["signs"]:
            await handle_updates()

            twitter_id = sign["twitter_id"]
            since_id = sign["since_id"]
            print(f"Проверка пользователя {twitter_id} для уведомления канала {follower['tg_id']}")

            try:
                print("\tSTART")
                if since_id == 0:
                    tweets = api.user_timeline(screen_name=twitter_id, tweet_mode="extended", count=1)
                else:
                    tweets = api.user_timeline(screen_name=twitter_id, tweet_mode="extended", since_id=since_id)
                print("\tEND")
            except:
                print("Произошла ОБИБКА поиска пользователя твиттер")
                return
            for tweet in reversed(tweets):
                await send_tweet(follower["tg_id"], tweet)
                sign["since_id"] = tweet.id

    await update_json()


async def send_tweet(id, tweet):
    about_message = f"Новый твит от @{tweet._json['user']['screen_name']}\n" \
                    f"URL:https://twitter.com/twitter/statuses/{tweet.id}\n" \
                    f"__________\n\n"
    if hasattr(tweet, "retweeted_status"):
        status_id = tweet.retweeted_status.id
        retweet = api.get_status(status_id, tweet_mode="extended")
        full_text = f"Retweet from @{retweet._json['user']['screen_name']}\n\n"
        full_text += retweet.full_text
        print("full = " + full_text)
    else:
        full_text = tweet.full_text
    full_text = about_message + full_text
    if "media" in tweet.entities \
            and "media" in tweet.extended_entities:
        media = tweet.extended_entities["media"]
        photos = [telebot.types.InputMediaPhoto(photo["media_url"]) for photo in media]
        photos[0].caption = full_text
        await tgbot.send_media_group(id, photos)
    else:
        await tgbot.send_message(id, full_text)


async def handle_updates():
    try:
        updates = await tgbot.get_updates(offset=bot_json["update_offset"], allowed_updates=["message"],
                                          timeout=1)
    except:
        print("Произошла ОШИБКА поиска новый обновлений от ТГ")
        return
    if len(updates) > 0:
        bot_json["update_offset"] = updates[len(updates) - 1].update_id + 1
        print("Запрос от ТГ")
        await update_json()
        await tgbot.process_new_updates(updates)


async def work():
    while True:
        # asyncio.create_task(handle_updates())
        await handle_tweets()


async def update_json():
    with open("bot_json.json", "w") as file:
        json.dump(bot_json, file)


async def main():
    await resolve_json("bot_json.json")
    await work()


asyncio.run(main())
