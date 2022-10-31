from telebot.async_telebot import AsyncTeleBot
import asyncio
import tweepy
import telebot
import json

keys = open("twitter_keys.txt").readlines()
keys = [key.rstrip("\n") for key in keys]

api_key = keys[0]
api_secret = keys[1]
bearer_token = keys[2]
access_key = keys[3]
access_secret = keys[4]

# auth = tweepy.OAuthHandler(api_key, api_secret)
# auth.set_access_token(access_key, access_secret)
auth = tweepy.OAuth2BearerHandler(bearer_token)
api = tweepy.API(auth)

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
    if length == 0:
        await update_json(file_name, bot_json)
    else:
        bot_json = json.loads(lines[0])


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
    twitter_id = str(message.text).strip("/add ")
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
        await tgbot.send_message(user.id, f"Не могу найти пользователя с id *{twitter_id}*")
        return

    if len(tweets) > 0:
        await add_sign(user.id, twitter_id, tweets[0].id)
    else:
        await add_sign(user.id, twitter_id, 0)


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

    twitt_ids = [follower["signs"][sign]["twitter_id"] for sign in range(len(follower["signs"]))]
    if twitter_id in twitt_ids:
        await tgbot.send_message(tg_id, f"Вы уже подписаны на уведомления от *{twitter_id}*!")
    else:
        follower["signs"].append(sign)
        await tgbot.send_message(tg_id, f"Теперь я буду отправлять сюда твиты от *{twitter_id}*!")

    await update_json("bot_json.json", bot_json)


async def handle_tweets():
    for follower in bot_json["followers"]:
        for sign in follower["signs"]:
            twitter_id = sign["twitter_id"]
            since_id = sign["since_id"]
            print(f"Проверка пользователя {twitter_id} для уведомления канала {follower['tg_id']}")

            if since_id == 0:
                tweets = api.user_timeline(screen_name=twitter_id, tweet_mode="extended", count=1)
            else:
                tweets = api.user_timeline(screen_name=twitter_id, tweet_mode="extended", since_id=since_id)
            for tweet in reversed(tweets):
                await send_tweet(follower["tg_id"], tweet)
                sign["since_id"] = tweet.id

    await update_json("bot_json.json", bot_json)


async def send_tweet(id, tweet):
    about_message = f"Новый твит от @{tweet._json['user']['screen_name']}\nURL:https://twitter.com/twitter/statuses/{tweet.id}\n__________\n\n"
    if "media" in tweet.entities \
            and "media" in tweet.extended_entities:
        media = tweet.extended_entities["media"]
        photos = [telebot.types.InputMediaPhoto(photo["media_url"]) for photo in media]
        photos[0].caption = about_message + tweet.full_text
        await tgbot.send_media_group(id, photos)
    else:
        await tgbot.send_message(id, about_message + tweet.full_text)


async def handle_updates():
    try:
        updates = await tgbot.get_updates(offset=bot_json["update_offset"], allowed_updates=["message"], timeout=3)
    except:
        await asyncio.sleep(5)
        return
    if len(updates) > 0:
        bot_json["update_offset"] = updates[len(updates) - 1].update_id + 1
        await update_json("bot_json.json", bot_json)

    await tgbot.process_new_updates(updates)


async def work():
    while True:
        print(bot_json)
        await handle_updates()
        await handle_tweets()


async def update_json(file_name: str, json_dict: dict):
    with open(file_name, "w") as file:
        json.dump(json_dict, file)


async def main():
    await resolve_json("bot_json.json")
    await work()


asyncio.run(main())

# TODO Полный текст ретввита и возможность удаления канала добавить возможность админского оповещения и автоматический перезапуск
# подумать про количество твитов
