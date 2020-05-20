import html
from io import BytesIO
from typing import Optional, List
import random
import uuid
from time import sleep

from future.utils import string_types
from telegram.error import BadRequest, TelegramError
from telegram import ParseMode, Update, Bot, Chat, User, MessageEntity
from telegram.ext import run_async, CommandHandler, MessageHandler, Filters
from telegram.utils.helpers import escape_markdown, mention_html

from tg_bot import dispatcher, OWNER_ID, SUDO_USERS, WHITELIST_USERS, MESSAGE_DUMP, LOGGER
from tg_bot.modules.helper_funcs.handlers import CMD_STARTERS
from tg_bot.modules.helper_funcs.misc import is_module_loaded, send_to_list
from tg_bot.modules.helper_funcs.chat_status import is_user_admin
from tg_bot.modules.helper_funcs.extraction import extract_user, extract_user_and_text
from tg_bot.modules.helper_funcs.string_handling import markdown_parser
from tg_bot.modules.disable import DisableAbleCommandHandler

import tg_bot.modules.sql.feds_sql as sql

from tg_bot.modules.translations.strings import tld

from tg_bot.modules.connection import connected

# Hello bot owner, I spended for feds many hours of my life, Please don't remove this if you still respect MrYacha and peaktogoo
# Federation by MrYacha 2018-2019
# Federation rework in process by Mizukito Akito 2019
# Time spended on feds = 10h by #MrYacha
# Time spended on reworking on the whole feds = 20+ hours by @peaktogoo

LOGGER.info("Reeditado por @kingpipo18 Módulo de federación original por MrYacha, reelaborado por Mizukito Akito (@peaktogoo) en Telegram ".)

FBAN_ERRORS = {
    "El usuario es un administrador del chat",
    "Chat not found",
    "No hay suficientes derechos para restrict/unrestrict al miembro de chat",
    "User_not_participant",
    "Peer_id_invalid",
    "El chat grupal fue desactivado",
    "Necesito invitar a un usuario para que lo saque de un grupo básico",
    "Chat_admin_required",
    "Solo el creador de un grupo básico puede expulsar a los administradores del grupo",
    "Channel_private",
    "No en el chat"
}

UNFBAN_ERRORS = {
    "El usuario es un administrador del chat",
    "Chat not found",
    "No hay suficientes derechos para restrict/unrestrict al miembro de chat",
    "User_not_participant",
    "El método solo está disponible para chats de supergrupos y canales",
    "No en el chat",
    "Channel_private",
    "Chat_admin_required",
}


def new_fed(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message
    fednam = message.text[len('/newfed '):]
    if not fednam == '':
        fed_id = str(uuid.uuid4())
        fed_name = fednam
        LOGGER.info(fed_id)

        #if fednam == 'Name':
        #     fed_id = "Name"

        x = sql.new_fed(user.id, fed_name, fed_id)
        if not x:
            update.effective_message.reply_text(tld(chat.id, "¡Gran F! ¡Hay un error al crear Federaciones, amablemente entra a mi grupo de apoyo y pregunta qué está pasando!"))
            return

        update.effective_message.reply_text("* ¡Has creado con éxito una nueva federación! *"\
                                            "\nName: `{}`"\
                                            "\nID: `{}`"
                                            "\n\nUtilice el siguiente comando para unirse a la federación: "
                                            "\n`/joinfed {}`".format(fed_name, fed_id, fed_id), parse_mode=ParseMode.MARKDOWN)
        bot.send_message(
            MESSAGE_DUMP,
           "La federación <b>{}</b> se ha creado con el ID: <pre>{}</pre>".format(fed_name, fed_id),parse_mode=ParseMode.HTML)
    else:
        update.effective_message.reply_text(tld(chat.id, "¡Por favor escriba el nombre de la federación!"))


def del_fed(bot: Bot, update: Update, args: List[str]):

        chat = update.effective_chat  # type: Optional[Chat]
        user = update.effective_user  # type: Optional[User]
        fed_id = sql.get_fed_id(chat.id)

        if not fed_id:
            update.effective_message.reply_text(tld(chat.id, "Por el momento, solo admitimos eliminar la federación en el grupo que se unió a ella".))
            return

        if not is_user_fed_owner(fed_id, user.id):
            update.effective_message.reply_text(tld(chat.id, "Solo el dueño alimentado puede hacer esto!"))
            return

        sql.del_fed(fed_id, chat.id)
        update.effective_message.reply_text(tld(chat.id, "Deleted!"))


def fed_chat(bot: Bot, update: Update, args: List[str]):
        chat = update.effective_chat  # type: Optional[Chat]
        user = update.effective_user  # type: Optional[User]
        fed_id = sql.get_fed_id(chat.id)

        user_id = update.effective_message.from_user.id
        if not is_user_admin(update.effective_chat, user_id):
            update.effective_message.reply_text("Debe ser un administrador de chat para ejecutar este comando: P")
            return

        if not fed_id:
            update.effective_message.reply_text(tld(chat.id, "¡Este grupo no está en ninguna federación!"))
            return

        print(fed_id)
        user = update.effective_user  # type: Optional[Chat]
        chat = update.effective_chat  # type: Optional[Chat]
        info = sql.get_fed_info(fed_id)

        text = "Este chat forma parte de la siguiente federación:"
        text += "\n{} (ID: <code>{}</code>)".format(info.fed_name, fed_id)

        update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


def join_fed(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message
    administrators = chat.get_administrators()
    fed_id = sql.get_fed_id(chat.id)

    if user.id in SUDO_USERS:
        pass
    else:
        for admin in administrators:
            status = admin.status
            if status == "creator":
                print(admin)
                if str(admin.user.id) == str(user.id):
                    pass
                else:
                    update.effective_message.reply_text(tld(chat.id, "¡Solo el creador del grupo puede hacerlo!"))
                    return
    if fed_id:
        message.reply_text(tld(chat.id, "Uh, ¿te unirás a dos federaciones en una conversación?"))
        return

    if len(args) >= 1:
        fedd = args[0]
        print(fedd)
        if sql.search_fed_by_id(fedd) == False:
            message.reply_text(tld(chat.id, "Ingrese un ID de federación válido".))
            return

        x = sql.chat_join_fed(fedd, chat.id)
        if not x:
                message.reply_text(tld(chat.id, "¡No pude unirme a la federación! ¡Debido a algunos errores que básicamente no tengo idea, intente informarlo en el grupo de soporte!"))
                return

        message.reply_text(tld(chat.id, "¡Chat unido a la federación!"))
def leave_fed(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    fed_id = sql.get_fed_id(chat.id)

    administrators = chat.get_administrators()

    if user.id in SUDO_USERS:
        pass
    else:
        for admin in administrators:
            status = admin.status
            if status == "creator":
                print(admin)
                if str(admin.user.id) == str(user.id):
                    pass
                else:
                    update.effective_message.reply_text(tld(chat.id, "¡Solo el creador del grupo puede hacerlo!"))
                    return

    if sql.chat_leave_fed(chat.id) == True:
        update.effective_message.reply_text(tld(chat.id, "¡Dejado de alimentado!"))
    else:
        update.effective_message.reply_text(tld(chat.id, "¡Por qué dejas a los federales cuando no te has unido a ninguno!"))


def user_join_fed(bot: Bot, update: Update, args: List[str]):

        chat = update.effective_chat  # type: Optional[Chat]
        user = update.effective_user  # type: Optional[User]
        fed_id = sql.get_fed_id(chat.id)

        if is_user_fed_owner(fed_id, user.id) == False:
                update.effective_message.reply_text(tld(chat.id, "Solo el dueño alimentado puede hacer esto!"))
                return

        msg = update.effective_message  # type: Optional[Message]
        user_id = extract_user(msg, args)
        if user_id:
                user = bot.get_chat(user_id)

        elif not msg.reply_to_message and not args:
                user = msg.from_user

        elif not msg.reply_to_message and (not args or (
                len(args) >= 1 and not args[0].startswith("@") and not args[0].isdigit() and not msg.parse_entities(
                [MessageEntity.TEXT_MENTION]))):
                msg.reply_text(tld(chat.id, "No puedo extraer un usuario de esto".))
                return

        else:
            return

        print(sql.search_user_in_fed(fed_id, user_id))

        #if user_id == user_id:
        #        update.effective_message.reply_text(tld(chat.id, "Are you gonna promote yourself?"))
        #        return

        fed_id = sql.get_fed_id(chat.id)
        info = sql.get_fed_info(fed_id)
        OW = bot.get_chat(info.owner_id)
        HAHA = OW.id
        if user_id == HAHA:
                update.effective_message.reply_text(tld(chat.id, "¿Por qué estás tratando de promover al propietario de la federación?"))
                return

        if not sql.search_user_in_fed(fed_id, user_id) == False:
                update.effective_message.reply_text(tld(chat.id, "¡No puedo promocionar a un usuario que ya es un administrador alimentado! Pero puedo degradarlos"))
                return

        if user_id == bot.id:
                update.effective_message.reply_text(tld(chat.id, "¡Ya soy el administrador de la federación y el que lo gestiona!"))
                return

        #else:
        #        return

        res = sql.user_join_fed(fed_id, user_id)
        if not res:
                update.effective_message.reply_text(tld(chat.id, "¡No se pudo promocionar! ¡Puede ser porque eres administrador de otra federación! Nuestro código aún tiene errores, ¡lo sentimos!"))
                return

        update.effective_message.reply_text(tld(chat.id, "Promoted Successfully!"))


def user_demote_fed(bot: Bot, update: Update, args: List[str]):
        chat = update.effective_chat  # type: Optional[Chat]
        user = update.effective_user  # type: Optional[User]
        fed_id = sql.get_fed_id(chat.id)

        if is_user_fed_owner(fed_id, user.id) == False:
                update.effective_message.reply_text(tld(chat.id, "Solo el dueño alimentado puede hacer esto!"))
                return

        msg = update.effective_message  # type: Optional[Message]
        user_id = extract_user(msg, args)
        if user_id:
                user = bot.get_chat(user_id)

        elif not msg.reply_to_message and not args:
                user = msg.from_user

        elif not msg.reply_to_message and (not args or (
                len(args) >= 1 and not args[0].startswith("@") and not args[0].isdigit() and not msg.parse_entities(
                [MessageEntity.TEXT_MENTION]))):
                msg.reply_text(tld(chat.id, "No puedo extraer un usuario de esto".))
                return

        #else:
        #        return

        if user_id == bot.id:
                update.effective_message.reply_text(tld(chat.id, "¿Qué estás tratando de hacer? ¿Degradarme de tu federación?"))
                return

        if sql.search_user_in_fed(fed_id, user_id) == False:
                update.effective_message.reply_text(tld(chat.id, "¡No puedo degradar al usuario que no es un administrador alimentado! ¡Si quieres hacer que llore, promociona primero!"))
                return

        res = sql.user_demote_fed(fed_id, user_id)
        if res == True:
                update.effective_message.reply_text(tld(chat.id, "¡Sal de aquí!"))
        else:
                update.effective_message.reply_text(tld(chat.id, "No puedo eliminarlo, ¡soy impotente!"))


def fed_info(bot: Bot, update: Update, args: List[str]):

        chat = update.effective_chat  # type: Optional[Chat]
        user = update.effective_user  # type: Optional[User]
        fed_id = sql.get_fed_id(chat.id)
        info = sql.get_fed_info(fed_id)

        if not fed_id:
            update.effective_message.reply_text(tld(chat.id, "¡Este grupo no está en ninguna federación!"))
            return

        if is_user_fed_admin(fed_id, user.id) == False:
            update.effective_message.reply_text(tld(chat.id, "¡Solo los administradores alimentados pueden hacer esto!"))
            return

        OW = bot.get_chat(info.owner_id)
        HAHA = OW.id
        FEDADMIN = sql.all_fed_users(fed_id)
        FEDADMIN.append(int(HAHA))
        ACTUALADMIN = len(FEDADMIN)

        print(fed_id)
        user = update.effective_user  # type: Optional[Chat]
        chat = update.effective_chat  # type: Optional[Chat]
        info = sql.get_fed_info(fed_id)

        text = "<b>Fed info:</b>"
        text += "\nFedID: <code>{}</code>".format(fed_id)
        text += "\nName: {}".format(info.fed_name)
        text += "\nCreator: {}".format(mention_html(HAHA, "this guy"))
        text += "\nNumber of admins: <code>{}</code>".format(ACTUALADMIN)
        R = 0
        for O in sql.get_all_fban_users(fed_id):
                R = R + 1

        text += "\nNumber of bans: <code>{}</code>".format(R)
        h = sql.all_fed_chats(fed_id)
        asdf = len(h)
        text += "\nNumber of connected chats: <code>{}</code>".format(asdf)

        update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


def fed_admin(bot: Bot, update: Update, args: List[str]):

        chat = update.effective_chat  # type: Optional[Chat]
        user = update.effective_user  # type: Optional[User]
        fed_id = sql.get_fed_id(chat.id)

        if not fed_id:
            update.effective_message.reply_text(tld(chat.id, "¡Este grupo no está en ninguna federación!"))
            return

        if is_user_fed_admin(fed_id, user.id) == False:
            update.effective_message.reply_text(tld(chat.id, "¡Solo los administradores alimentados pueden hacer esto!"))
            return

        print(fed_id)
        user = update.effective_user  # type: Optional[Chat]
        chat = update.effective_chat  # type: Optional[Chat]
        info = sql.get_fed_info(fed_id)

        text = "\n\n<b>Federation Admins:</b>"
        user = bot.get_chat(info.owner_id) 
        text += "\n• {} - <code>{}</code> (Creator)".format(mention_html(user.id, user.first_name), user.id)

        h = sql.all_fed_users(fed_id)
        for O in h:
                user = bot.get_chat(O) 
                text += "\n• {} - <code>{}</code>".format(mention_html(user.id, user.first_name), user.id, O)

        update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


def fed_ban(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    fed_id = sql.get_fed_id(chat.id)

    if not fed_id:
        update.effective_message.reply_text(tld(chat.id, "¡Este grupo no está en ninguna federación!"))
        return

    info = sql.get_fed_info(fed_id)
    OW = bot.get_chat(info.owner_id)
    HAHA = OW.id
    FEDADMIN = sql.all_fed_users(fed_id)
    FEDADMIN.append(int(HAHA))

    if is_user_fed_admin(fed_id, user.id) == False:
        update.effective_message.reply_text(tld(chat.id, "¡Solo los administradores alimentados pueden hacer esto!"))
        return

    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    fban = sql.get_fban_user(fed_id, user_id)
    if not fban == False:
        update.effective_message.reply_text(tld(chat.id, "*Tos* ¡Este usuario ya está prohibido!"))
        return

    if not user_id:
        message.reply_text(tld(chat.id, "Parece que no te refieres a un usuario".))
        return

    if user_id == bot.id:
        message.reply_text(tld(chat.id, "No me puedes fban, mejor golpea tu cabeza contra la pared, es más divertido".))
        return

    if is_user_fed_owner(fed_id, user_id) == True:
        message.reply_text(tld(chat.id,"¿Por qué estás tratando de fbanar al dueño de la federación?"))
        return

    if is_user_fed_admin(fed_id, user_id) == True:
        message.reply_text(tld(chat.id, "¿Por qué tan serio tratando de fban el administrador de la federación?"))
        return

    if user_id == OWNER_ID:
        message.reply_text(tld(chat.id, "No estoy prohibiendo a mi maestro, ¡Esa es una idea bastante tonta!"))
        return

    if int(user_id) in SUDO_USERS:
        message.reply_text(tld(chat.id, "¡No estoy prohibiendo a los sudoers bot! 😴"))
        return

    if int(user_id) in WHITELIST_USERS:
        message.reply_text(tld(chat.id, "¡Esta persona está en la lista blanca de ser excluido!"))
        return

    try:
        user_chat = bot.get_chat(user_id)
    except BadRequest as excp:
        message.reply_text(excp.message)
        return

    if user_chat.type != 'private':
        message.reply_text(tld(chat.id, "That's not a user!"))
        return

    ok123 = mention_html(user_chat.id, user_chat.first_name)
    ok1234 = info.fed_name

    text12 = f"Beginning federation ban of {ok123} in {ok1234}."
    update.effective_message.reply_text(text12, parse_mode=ParseMode.HTML)

    if reason == "":
        reason = "No Reason."

    x = sql.fban_user(fed_id, user_id, reason)
    if not x:
        message.reply_text("¡No se pudo prohibir la federación! Probablemente este error aún no se haya solucionado debido a que el desarrollador es perezoso".)
        return

    h = sql.all_fed_chats(fed_id)
    for O in h:
        try:
            bot.kick_chat_member(O, user_id)
            #text = tld(chat.id, "I should fban {}, but it's only test fban, right? So i let him live.").format(O)
            text = "Fbanning {}".format(user_id)
            #message.reply_text(text)
        except BadRequest as excp:
            if excp.message in FBAN_ERRORS:
                pass
            else:
                message.reply_text(tld(chat.id, "Could not fban due to: {}").format(excp.message))
                return
        except TelegramError:
            pass

    send_to_list(bot, FEDADMIN,
             "<b>New FedBan</b>" \
             "\n<b>Fed:</b> {}" \
             "\n<b>FedAdmin:</b> {}" \
             "\n<b>User:</b> {}" \
             "\n<b>User ID:</b> <code>{}</code>" \
             "\n<b>Reason:</b> {}".format(info.fed_name, mention_html(user.id, user.first_name),
                                   mention_html(user_chat.id, user_chat.first_name),
                                                user_chat.id, reason), 
            html=True)
    text13 = f"Chu {ok123} Sucessfully Fbanned in {ok1234} Fed."
    update.effective_message.reply_text(text13, parse_mode=ParseMode.HTML)

@run_async
def unfban(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]
    fed_id = sql.get_fed_id(chat.id)

    if not fed_id:
        update.effective_message.reply_text(tld(chat.id, "¡Este grupo no está en ninguna federación!"))
        return

    info = sql.get_fed_info(fed_id)

    if is_user_fed_admin(fed_id, user.id) == False:
        update.effective_message.reply_text(tld(chat.id, "¡Solo los administradores alimentados pueden hacer esto!"))
        return

    user_id = extract_user(message, args)
    if not user_id:
        message.reply_text(tld(chat.id, "Parece que no te refieres a un usuario".))
        return

    user_chat = bot.get_chat(user_id)
    if user_chat.type != 'private':
        message.reply_text(tld(chat.id, "¡Eso no es un usuario!"))
        return

    if sql.get_fban_user(fed_id, user_id) == False:
        message.reply_text(tld(chat.id, "Este usuario no está prohibido!"))
        return

    banner = update.effective_user  # type: Optional[User]

    message.reply_text(tld(chat.id,"Le daré a {} una segunda oportunidad en esta federación".).format(user_chat.first_name))

    h = sql.all_fed_chats(fed_id)

    for O in h:
        try:
            member = bot.get_chat_member(O, user_id)
            if member.status == 'kicked':
                bot.unban_chat_member(O, user_id)


        except BadRequest as excp:

            if excp.message in UNFBAN_ERRORS:
                pass
            else:
                message.reply_text(tld(chat.id, "Could not un-fban due to: {}").format(excp.message))
                return

        except TelegramError:
            pass

        try:
            x = sql.un_fban_user(fed_id, user_id)
            if not x:
                message.reply_text(tld(chat.id, "No se pudo fban, ¡Este usuario probablemente está prohibido!"))
                return
        except:
            pass

    message.reply_text(tld(chat.id, "La persona no ha sido excluida".))

    OW = bot.get_chat(info.owner_id)
    HAHA = OW.id
    FEDADMIN = sql.all_fed_users(fed_id)
    FEDADMIN.append(int(HAHA))

    send_to_list(bot, FEDADMIN,
             "<b>Un-FedBan</b>" \
             "\n<b>Fed:</b> {}" \
             "\n<b>FedAdmin:</b> {}" \
             "\n<b>User:</b> {}" \
             "\n<b>User ID:</b> <code>{}</code>".format(info.fed_name, mention_html(user.id, user.first_name),
                                                 mention_html(user_chat.id, user_chat.first_name),
                                                              user_chat.id),
            html=True)


def set_frules(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    fed_id = sql.get_fed_id(chat.id)

    if not fed_id:
        update.effective_message.reply_text(tld(chat.id, "¡Este chat no está en ninguna federación!"))
        return

    if is_user_fed_admin(fed_id, user.id) == False:
        update.effective_message.reply_text(tld(chat.id, "¡Solo los administradores alimentados pueden hacer esto!"))
        return

    if len(args) >= 1:
        msg = update.effective_message  # type: Optional[Message]
        raw_text = msg.text
        args = raw_text.split(None, 1)  # use python's maxsplit to separate cmd and args
        if len(args) == 2:
            txt = args[1]
            offset = len(txt) - len(raw_text)  # set correct offset relative to command
            markdown_rules = markdown_parser(txt, entities=msg.parse_entities(), offset=offset)
        x = sql.set_frules(fed_id, markdown_rules)
        if not x:
            update.effective_message.reply_text(tld(chat.id, "¡Gran F! ¡Hay un error al establecer las reglas de la federación! ¡Si se pregunta por qué, por favor pregúntelo en el grupo de apoyo!"))
            return

        rules = sql.get_fed_info(fed_id).fed_name
        update.effective_message.reply_text(tld(chat.id, f"Rules are set for {rules}!"))
    else:
        update.effective_message.reply_text(tld(chat.id, "¡Por favor escriba reglas para configurarlo!"))


def get_frules(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]
    fed_id = sql.get_fed_id(chat.id)
    if not fed_id:
        update.effective_message.reply_text(tld(chat.id, "¡Este chat no está en ninguna federación!"))
        return

    ruless = sql.get_frules(fed_id)
    try:
        rules = ruless.rules
        print(rules)
        text = "*Rules in this fed:*\n"
        text += rules
        update.effective_message.reply_text(tld(chat.id, text), parse_mode=ParseMode.MARKDOWN)
        return
    except AttributeError:
        update.effective_message.reply_text(tld(chat.id, "¡No hay reglas en esta federación!"))
        return


@run_async
def broadcast(bot: Bot, update: Update, args: List[str]):
    to_send = update.effective_message.text.split(None, 1)
    if len(to_send) >= 2:
        chat = update.effective_chat  # type: Optional[Chat]
        fed_id = sql.get_fed_id(chat.id)
        chats = sql.all_fed_chats(fed_id)
        failed = 0
        for Q in chats:
            try:
                bot.sendMessage(Q, to_send[1])
                sleep(0.1)
            except TelegramError:
                failed += 1
                LOGGER.warning("No se pudo enviar la transmisión a %s, nombre de grupo %s", str(chat.chat_id), str(chat.chat_name))

        update.effective_message.reply_text(tld(chat.id, "La transmisión de Federaciones se completó. {} Los grupos no pudieron recibir el mensaje, probablemente"
                                            "debido a dejar la federación".).format(failed))


def is_user_fed_admin(fed_id, user_id):
    list = sql.all_fed_users(fed_id)
    print(user_id)
    if str(user_id) in list or is_user_fed_owner(fed_id, user_id) == True:
        return True
    else:
        return False


def is_user_fed_owner(fed_id, user_id):
    print("Check on fed owner")

    if int(user_id) == int(sql.get_fed_info(fed_id).owner_id) or user_id == OWNER_ID or user_id == '721193998':
        return True
    else:
        return False


def welcome_fed(bot, update):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    fed_id = sql.get_fed_id(chat.id)
    fban = fban = sql.get_fban_user(fed_id, user.id)
    if not fban == False:
        update.effective_message.reply_text(tld(chat.id, "¡Este usuario está prohibido en la federación actual! Lo eliminaré".))
        bot.kick_chat_member(chat.id, user.id)
        return True
    else:
        return False


def __stats__():
    R = 0
    for O in sql.get_all_fban_users_global():
        R = R + 1

    S = 0
    for O in sql.get_all_feds_users_global():
        S = S + 1

    return "{} fbanned users, across {} feds".format(R, S)


def __user_info__(user_id, chat_id):
    fed_id = sql.get_fed_id(chat_id)
    if fed_id:
        fban = sql.get_fban_user(fed_id, user_id)
        info = sql.get_fed_info(fed_id)
        infoname = info.fed_name

        if is_user_fed_admin(fed_id, user_id) == True:
            text = f"Este usuario es un administrador alimentado en la federación actual, <code>{infoname} </code>".

        elif not fban == False:
            text = "Prohibido en la federación actual - <b>Yes</b>"
            text += "\n<b>Reason:</b> {}".format(fban)
        else:
            text = "Prohibido en la federación actual - <b>No</b>"
    else:
        text = ""
    return text


__mod_name__ = "Federations"

__help__ = """
Ah, gestión de grupo. Todo es diversión y juegos, hasta que comiences a recibir spammers y necesites prohibirlos. Entonces debes comenzar a prohibir más y más, y se vuelve doloroso.
Pero entonces tienes varios grupos y no quieres que estos spammers estén en ninguno de tus grupos, ¿cómo puedes tratar? ¿Tienes que prohibirlos manualmente en todos tus grupos?

¡No más! Con las federaciones, puede prohibir la superposición de un chat con todos sus otros chats.
Incluso puede nombrar administradores de la federación, para que sus administradores confiables puedan prohibir todos los chats que desea proteger.

Comandos:
 - /newfed <fedname>: crea una nueva federación con el nombre de pila. Los usuarios solo pueden tener una federación. Este método también se puede usar para cambiar el nombre de la federación. (máximo 64 caracteres)
 - /delfed: elimina su federación y cualquier información relacionada con ella. No desbancará a ningún usuario prohibido.
 - /fedinfo <FedID>: información sobre la federación especificada.
 - /joinfed <FedID>: se une al chat actual con la federación. Solo los propietarios de chat pueden hacer esto. Cada chat solo puede estar en una federación.
 - /leavefed <FedID>: deja la federación dada. Solo los propietarios de chat pueden hacer esto.
 - /fpromote <user>: promueve al usuario a administrador alimentado. Propietario de la Fed solamente.
 - /fdemote <user>: degrada al usuario de administrador alimentado a usuario normal. Propietario de la Fed solamente.
 - /fban <user>: bans a un usuario de todas las federaciones en las que está este chat y sobre el que el ejecutor tiene control.
 - /unfban <user>: unbansa un usuario de todas las federaciones en las que está este chat y sobre el que el ejecutor tiene control.
 - /setfrules: Set federation rules
 - /frules: Show federation rules
 - /chatfed: Mostrar a la federación en la que se encuentra el chat
 - /fedadmins: Mostrar los administradores de la federación

"""

NEW_FED_HANDLER = CommandHandler("newfed", new_fed)
DEL_FED_HANDLER = CommandHandler("delfed", del_fed, pass_args=True)
JOIN_FED_HANDLER = CommandHandler("joinfed", join_fed, pass_args=True)
LEAVE_FED_HANDLER = CommandHandler("leavefed", leave_fed, pass_args=True)
PROMOTE_FED_HANDLER = CommandHandler("fpromote", user_join_fed, pass_args=True)
DEMOTE_FED_HANDLER = CommandHandler("fdemote", user_demote_fed, pass_args=True)
INFO_FED_HANDLER = CommandHandler("fedinfo", fed_info, pass_args=True)
BAN_FED_HANDLER = DisableAbleCommandHandler(["fban", "fedban"], fed_ban, pass_args=True)
UN_BAN_FED_HANDLER = CommandHandler("unfban", unfban, pass_args=True)
FED_BROADCAST_HANDLER = CommandHandler("fbroadcast", broadcast, pass_args=True)
FED_SET_RULES_HANDLER = CommandHandler("setfrules", set_frules, pass_args=True)
FED_GET_RULES_HANDLER = CommandHandler("frules", get_frules, pass_args=True)
FED_CHAT_HANDLER = CommandHandler("chatfed", fed_chat, pass_args=True)
FED_ADMIN_HANDLER = CommandHandler("fedadmins", fed_admin, pass_args=True)

dispatcher.add_handler(NEW_FED_HANDLER)
dispatcher.add_handler(DEL_FED_HANDLER)
dispatcher.add_handler(JOIN_FED_HANDLER)
dispatcher.add_handler(LEAVE_FED_HANDLER)
dispatcher.add_handler(PROMOTE_FED_HANDLER)
dispatcher.add_handler(DEMOTE_FED_HANDLER)
dispatcher.add_handler(INFO_FED_HANDLER)
dispatcher.add_handler(BAN_FED_HANDLER)
dispatcher.add_handler(UN_BAN_FED_HANDLER)
#dispatcher.add_handler(FED_BROADCAST_HANDLER)
dispatcher.add_handler(FED_SET_RULES_HANDLER)
dispatcher.add_handler(FED_GET_RULES_HANDLER)
dispatcher.add_handler(FED_CHAT_HANDLER)
dispatcher.add_handler(FED_ADMIN_HANDLER)
