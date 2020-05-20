import html
from io import BytesIO
from typing import Optional, List

from telegram import Message, Update, Bot, User, Chat
from telegram.error import BadRequest, TelegramError
from telegram.ext import run_async, CommandHandler, MessageHandler, Filters
from telegram.utils.helpers import mention_html

import tg_bot.modules.sql.global_mutes_sql as sql
from tg_bot import dispatcher, OWNER_ID, SUDO_USERS, SUPPORT_USERS, STRICT_GMUTE
from tg_bot.modules.helper_funcs.chat_status import user_admin, is_user_admin
from tg_bot.modules.helper_funcs.extraction import extract_user, extract_user_and_text
from tg_bot.modules.helper_funcs.filters import CustomFilters
from tg_bot.modules.helper_funcs.misc import send_to_list
from tg_bot.modules.sql.users_sql import get_all_chats

GMUTE_ENFORCE_GROUP = 6


@run_async
def gmute(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Parece que no te refieres a un usuario".)
        return

    if int(user_id) in SUDO_USERS:
        message.reply_text("Espío, con mi pequeño ojo ... ¡una guerra de usuarios de sudo! ¿Por qué se están volviendo unos a otros?")
        return

    if int(user_id) in SUPPORT_USERS:
        message.reply_text("¡OOOH alguien está tratando de silenciar a un usuario de soporte! * Agarra palomitas de maíz *")
        return

    if user_id == bot.id:
        message.reply_text("-_- Muy gracioso, vamos a silenciarme, ¿por qué no? Buen intento".)
        return

    try:
        user_chat = bot.get_chat(user_id)
    except BadRequest as excp:
        message.reply_text(excp.message)
        return

    if user_chat.type != 'private':
        message.reply_text("¡Eso no es un usuario!")
        return

    if sql.is_user_gmuted(user_id):
        if not reason:
            message.reply_text("Este usuario ya está silenciado; cambiaría el motivo, pero no me has dado uno ...")
            return

        success = sql.update_gmute_reason(user_id, user_chat.username or user_chat.first_name, reason)
        if success:
            message.reply_text("Este usuario ya está silenciado; sin embargo, he ido y actualizado la razón de gmute".)
        else:
            message.reply_text("¿Te importaría intentarlo de nuevo? Pensé que esta persona estaba muda, pero entonces no lo estaban"
                               "Estoy muy confundido")

        return

    message.reply_text("*Prepara la cinta adhesiva* 😉")

    muter = update.effective_user  # type: Optional[User]
    send_to_list(bot, SUDO_USERS + SUPPORT_USERS,
                 "{} is gmuting user {} "
                 "because:\n{}".format(mention_html(muter.id, muter.first_name),
                                       mention_html(user_chat.id, user_chat.first_name), reason or "No reason given"),
                 html=True)

    sql.gmute_user(user_id, user_chat.username or user_chat.first_name, reason)

    chats = get_all_chats()
    for chat in chats:
        chat_id = chat.chat_id

        # Check if this group has disabled gmutes
        if not sql.does_chat_gmute(chat_id):
            continue

        try:
            bot.restrict_chat_member(chat_id, user_id, can_send_messages=False)
        except BadRequest as excp:
            if excp.message == "El usuario es administrador del chat":
                pass
            elif excp.message == "Chat no encontrado":
                pass
            elif excp.message == "No hay suficientes derechos para restrict/unrestrict miembro de chat":
                pass
            elif excp.message == "User_not_participant":
                pass
            elif excp.message == "Peer_id_invalid":  # Suspect this happens when a group is suspended by telegram.
                pass
            elif excp.message == "El chat grupal fue desactivado":
                pass
            elif excp.message == "Necesito ser un invitador de un usuario para expulsarlo de un grupo básico":
                pass
            elif excp.message == "Chat_admin_required":
                pass
            elif excp.message == "Solo el creador de un grupo básico puede expulsar a los administradores del grupo":
                pass
            elif excp.message == "El método está disponible solo para supergrupos":
                pass
            elif excp.message == "No se puede degradar al creador del chat":
                pass
            else:
                message.reply_text("Could not gmute due to: {}".format(excp.message))
                send_to_list(bot, SUDO_USERS + SUPPORT_USERS, "Could not gmute due to: {}".format(excp.message))
                sql.ungmute_user(user_id)
                return
        except TelegramError:
            pass

    send_to_list(bot, SUDO_USERS + SUPPORT_USERS, "gmute complete!")
    message.reply_text("La persona ha sido mudada.")


@run_async
def ungmute(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message  # type: Optional[Message]

    user_id = extract_user(message, args)
    if not user_id:
        message.reply_text("Parece que no te refieres a un usuario")
        return

    user_chat = bot.get_chat(user_id)
    if user_chat.type != 'private':
        message.reply_text("¡Eso no es un usuario!")
        return

    if not sql.is_user_gmuted(user_id):
        message.reply_text("¡Este usuario no está silenciado!")
        return

    muter = update.effective_user  # type: Optional[User]

    message.reply_text("Dejaré que {} hable nuevamente, globalmente".format(user_chat.first_name))

    send_to_list(bot, SUDO_USERS + SUPPORT_USERS,
                 "{} has ungmuted user {}".format(mention_html(muter.id, muter.first_name),
                                                   mention_html(user_chat.id, user_chat.first_name)),
                 html=True)

    chats = get_all_chats()
    for chat in chats:
        chat_id = chat.chat_id

        # Check if this group has disabled gmutes
        if not sql.does_chat_gmute(chat_id):
            continue

        try:
            member = bot.get_chat_member(chat_id, user_id)
            if member.status == 'restricted':
                bot.restrict_chat_member(chat_id, int(user_id),
                                     can_send_messages=True,
                                     can_send_media_messages=True,
                                     can_send_other_messages=True,
                                     can_add_web_page_previews=True)

        except BadRequest as excp:
            if excp.message == "El usuario es administrador del chat":
                pass
            elif excp.message == "Chat no encontrado":
                pass
            elif excp.message == "No hay suficientes derechos para restringir / no restringir al miembro de chat":
                pass
            elif excp.message == "User_not_participant":
                pass
            elif excp.message == "El método solo está disponible para chats de supergrupos y canales":
                pass
            elif excp.message == "No en el chat":
                pass
            elif excp.message == "Channel_private":
                pass
            elif excp.message == "Chat_admin_required":
                pass
            else:
                message.reply_text("No se pudo anular el silenciamiento debido a: {}".format(excp.message))
                bot.send_message(OWNER_ID, "No se pudo anular el silenciamiento debido a: {}".format(excp.message))
                return
        except TelegramError:
            pass

    sql.ungmute_user(user_id)

    send_to_list(bot, SUDO_USERS + SUPPORT_USERS, "un-gmute complete!")

    message.reply_text("Person has been un-gmuted.")


@run_async
def gmutelist(bot: Bot, update: Update):
    muted_users = sql.get_gmute_list()

    if not muted_users:
        update.effective_message.reply_text("¡No hay usuarios silenciados! Eres más amable de lo que esperaba ... ")
        return

    mutefile = 'Screw these guys.\n'
    for user in muted_users:
        mutefile += "[x] {} - {}\n".format(user["name"], user["user_id"])
        if user["reason"]:
            mutefile += "Reason: {}\n".format(user["reason"])

    with BytesIO(str.encode(mutefile)) as output:
        output.name = "gmutelist.txt"
        update.effective_message.reply_document(document=output, filename="gmutelist.txt",
                                                caption="Here is the list of currently gmuted users.")


def check_and_mute(bot, update, user_id, should_message=True):
    if sql.is_user_gmuted(user_id):
        bot.restrict_chat_member(update.effective_chat.id, user_id, can_send_messages=False)
        if should_message:
            update.effective_message.reply_text("Esta es una mala persona, ¡los silenciaré por ti! ")


@run_async
def enforce_gmute(bot: Bot, update: Update):
    # Not using @restrict handler to avoid spamming - just ignore if cant gmute.
    if sql.does_chat_gmute(update.effective_chat.id) and update.effective_chat.get_member(bot.id).can_restrict_members:
        user = update.effective_user  # type: Optional[User]
        chat = update.effective_chat  # type: Optional[Chat]
        msg = update.effective_message  # type: Optional[Message]

        if user and not is_user_admin(chat, user.id):
            check_and_mute(bot, update, user.id, should_message=True)
        if msg.new_chat_members:
            new_members = update.effective_message.new_chat_members
            for mem in new_members:
                check_and_mute(bot, update, mem.id, should_message=True)
        if msg.reply_to_message:
            user = msg.reply_to_message.from_user  # type: Optional[User]
            if user and not is_user_admin(chat, user.id):
                check_and_mute(bot, update, user.id, should_message=True)

@run_async
@user_admin
def gmutestat(bot: Bot, update: Update, args: List[str]):
    if len(args) > 0:
        if args[0].lower() in ["on", "yes"]:
            sql.enable_gmutes(update.effective_chat.id)
            update.effective_message.reply_text("He habilitado gmutes en este grupo. Esto te ayudará a protegerte "
                                                "de spammers, personajes desagradables y Anirudh ")
        elif args[0].lower() in ["off", "no"]:
            sql.disable_gmutes(update.effective_chat.id)
            update.effective_message.reply_text("He desactivado gmutes en este grupo. GMutes no afectará a sus usuarios "
                                                "nunca más. ¡Sin embargo, estarás menos protegido de Anirudh! ")
    else:
        update.effective_message.reply_text("Dame algunos argumentos para elegir una configuración! on/off, yes/no!\n\n"
                                            "Su configuración actual es: {}\n"
                                            "Cuando es cierto, cualquier cambio que ocurra también ocurrirá en su grupo. "
                                            "Cuando es falso, no lo harán, dejándote a merced de "
                                            "spammers".format(sql.does_chat_gmute(update.effective_chat.id)))


def __stats__():
    return "{} gmuted users.".format(sql.num_gmuted_users())


def __user_info__(user_id):
    is_gmuted = sql.is_user_gmuted(user_id)

    text = "Globally muted: <b>{}</b>"
    if is_gmuted:
        text = text.format("Yes")
        user = sql.get_gmuted_user(user_id)
        if user.reason:
            text += "\nRazon: {}".format(html.escape(user.reason))
    else:
        text = text.format("No")
    return text


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    return "This chat is enforcing *gmutes*: `{}`.".format(sql.does_chat_gmute(chat_id))


__help__ = """
*Admin only:*
 - /gmutestat <on/off/yes/no>: Deshabilitará el efecto de silenciamiento global en su grupo o devolverá su configuración actual.
Los propietarios de bot utilizan Gmutes, también conocidos como silenciadores globales, para silenciar a los spammers de todos los grupos. Esto ayuda a proteger \
usted y sus grupos eliminando los creadores de spam lo más rápido posible. Se pueden deshabilitar para su grupo llamando \
/gmutestat
"""

__mod_name__ = "Global Mute"

GMUTE_HANDLER = CommandHandler("gmute", gmute, pass_args=True,
                              filters=CustomFilters.sudo_filter | CustomFilters.support_filter)
UNGMUTE_HANDLER = CommandHandler("ungmute", ungmute, pass_args=True,
                                filters=CustomFilters.sudo_filter | CustomFilters.support_filter)
GMUTE_LIST = CommandHandler("gmutelist", gmutelist,
                           filters=CustomFilters.sudo_filter | CustomFilters.support_filter)

GMUTE_STATUS = CommandHandler("gmutestat", gmutestat, pass_args=True, filters=Filters.group)

GMUTE_ENFORCER = MessageHandler(Filters.all & Filters.group, enforce_gmute)

dispatcher.add_handler(GMUTE_HANDLER)
dispatcher.add_handler(UNGMUTE_HANDLER)
dispatcher.add_handler(GMUTE_LIST)
dispatcher.add_handler(GMUTE_STATUS)

if STRICT_GMUTE:
    dispatcher.add_handler(GMUTE_ENFORCER, GMUTE_ENFORCE_GROUP)
