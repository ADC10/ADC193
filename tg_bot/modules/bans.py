import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import run_async, CommandHandler, Filters
from telegram.utils.helpers import mention_html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, User, CallbackQuery

from tg_bot import dispatcher, BAN_STICKER, LOGGER
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.chat_status import bot_admin, user_admin, is_user_ban_protected, can_restrict, \
    is_user_admin, is_user_in_chat, is_bot_admin
from tg_bot.modules.helper_funcs.extraction import extract_user_and_text
from tg_bot.modules.helper_funcs.string_handling import extract_time
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.helper_funcs.filters import CustomFilters

RBAN_ERRORS = {
    "El usuario es un administrador del chat",
    "Chat not found",
    "No hay suficientes derechos para restringir /unrestrict al miembro de chat",
    "User_not_participant",
    "Peer_id_invalid",
    "El chat grupal fue desactivado",
    "Necesito ser un invitador de un usuario para expulsarlo de un grupo básico",
    "Chat_admin_required",
    "Solo el creador de un grupo básico puede expulsar a los administradores del grupo",
    "Channel_private",
    "Not in the chat"
}

RUNBAN_ERRORS = {
    "El usuario es un administrador del chat",
    "Chat not found",
    "No hay suficientes derechos para restringir /unrestrict al miembro de chat",
    "User_not_participant",
    "Peer_id_invalid",
    "El chat grupal fue desactivado",
    "Necesito ser un invitador de un usuario para expulsarlo de un grupo básico",
    "Chat_admin_required",
    "Solo el creador de un grupo básico puede expulsar a los administradores del grupo",
    "Channel_private",
    "Not in the chat"
}



@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def ban(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Parece que no te refieres a un usuario".)
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "Usuario no encontrado":
            message.reply_text("Parece que no puedo encontrar a este usuario")
            return ""
        else:
            raise

    if is_user_ban_protected(chat, user_id, member):
        message.reply_text("Realmente desearía poder prohibir a los administradores ...")
        return ""

    if user_id == bot.id:
        message.reply_text("No me voy a PROHIBIR, ¿estás loco?")
        return ""

    log = "<b>{}:</b>" \
          "\n#BANNED" \
          "\n<b>Admin:</b> {}" \
          "\n<b>User:</b> {}".format(html.escape(chat.title), mention_html(user.id, user.first_name),
                                     mention_html(member.user.id, member.user.first_name))
    if reason:
        log += "\n<b>Reason:</b> {}".format(reason)

    try:
        chat.kick_member(user_id)
        bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        keyboard = []
        reply = "{} Banned!".format(mention_html(member.user.id, member.user.first_name))
        message.reply_text(reply, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return log

    except BadRequest as excp:
        if excp.message == "Mensaje de respuesta no encontrado":
            # Do not reply
            message.reply_text('Banned!', quote=False)
            return log
        else:
            LOGGER.warning(update)
            LOGGER.exception("ERROR al prohibir al usuario %s en el chat %s (%s) debido a %s", user_id, chat.title, chat.id,
                             excp.message)
            message.reply_text("Bueno, maldición, no puedo prohibir a ese usuario")

    return ""


@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def temp_ban(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Parece que no te refieres a un usuario".)
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "Usuario no encontrado":
            message.reply_text("Parece que no puedo encontrar a este usuario")
            return ""
        else:
            raise

    if is_user_ban_protected(chat, user_id, member):
        message.reply_text("Realmente desearía poder prohibir a los administradores ...")
        return ""

    if user_id == bot.id:
        message.reply_text("No me voy a PROHIBIR, ¿estás loco?")
        return ""

    if not reason:
        message.reply_text("¡No has especificado un momento para prohibir a este usuario!")
        return ""

    split_reason = reason.split(None, 1)

    time_val = split_reason[0].lower()
    if len(split_reason) > 1:
        reason = split_reason[1]
    else:
        reason = ""

    bantime = extract_time(message, time_val)

    if not bantime:
        return ""

    log = "<b>{}:</b>" \
          "\n#TEMP BANNED" \
          "\n<b>Admin:</b> {}" \
          "\n<b>User:</b> {}" \
          "\n<b>Time:</b> {}".format(html.escape(chat.title), mention_html(user.id, user.first_name),
                                     mention_html(member.user.id, member.user.first_name), time_val)
    if reason:
        log += "\n<b>Razon:</b> {}".format(reason)

    try:
        chat.kick_member(user_id, until_date=bantime)
        bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        message.reply_text("¡Prohibido! El usuario será prohibido por {}"..format(time_val))
        return log

    except BadRequest as excp:
        if excp.message == "Mensaje de respuesta no encontrado":
            # Do not reply
            message.reply_text("¡Prohibido! El usuario será prohibido por {}"..format(time_val), quote=False)
            return log
        else:
            LOGGER.warning(update)
            LOGGER.exception("ERROR al prohibir al usuario% s en el chat% s (% s) debido a% s", user_id, chat.title, chat.id,
                             excp.message)
            message.reply_text("Bueno, maldición, no puedo prohibir a ese usuario".)

    return ""


@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def kick(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "Usuario no encontrado":
            message.reply_text("Parece que no puedo encontrar a este usuario")
            return ""
        else:
            raise

    if is_user_ban_protected(chat, user_id):
        message.reply_text("Realmente desearía poder patear a los administradores ...")
        return ""

    if user_id == bot.id:
        message.reply_text("Sí, no voy a hacer eso")
        return ""

    res = chat.unban_member(user_id)  # unban on current user = kick
    if res:
        bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        message.reply_text("Kicked!")
        log = "<b>{}:</b>" \
              "\n#KICKED" \
              "\n<b>Admin:</b> {}" \
              "\n<b>User:</b> {}".format(html.escape(chat.title),
                                         mention_html(user.id, user.first_name),
                                         mention_html(member.user.id, member.user.first_name))
        if reason:
            log += "\n<b>Razon:</b> {}".format(reason)

        return log

    else:
        message.reply_text("Bueno, maldición, no puedo patear a ese usuario".)

    return ""


@run_async
@bot_admin
@can_restrict
def kickme(bot: Bot, update: Update):
    user_id = update.effective_message.from_user.id
    if is_user_admin(update.effective_chat, user_id):
        update.effective_message.reply_text("Desearía poder ... pero eres un administrador".)
        return

    res = update.effective_chat.unban_member(user_id)  # unban on current user = kick
    if res:
        update.effective_message.reply_text("No hay problema.")
    else:
        update.effective_message.reply_text("¿Eh? No puedo :/")


@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def unban(bot: Bot, update: Update, args: List[str]) -> str:
    message = update.effective_message  # type: Optional[Message]
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "Usuario no encontrado":
            message.reply_text("Parece que no puedo encontrar a este usuario")
            return ""
        else:
            raise

    if user_id == bot.id:
        message.reply_text("¿Cómo me libraría si no estuviera aquí ...?")
        return ""

    if is_user_in_chat(chat, user_id):
        message.reply_text("¿Por qué estás tratando de desbancar a alguien que ya está en el chat?")
        return ""

    chat.unban_member(user_id)
    message.reply_text("Sí, este usuario puede unirse!")

    log = "<b>{}:</b>" \
          "\n#UNBANNED" \
          "\n<b>Admin:</b> {}" \
          "\n<b>User:</b> {}".format(html.escape(chat.title),
                                     mention_html(user.id, user.first_name),
                                     mention_html(member.user.id, member.user.first_name))
    if reason:
        log += "\n<b>Razon:</b> {}".format(reason)

    return log


@run_async
@bot_admin
def rban(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message

    if not args:
        message.reply_text("Parece que no te estás refiriendo a un chat /user")
        return

    user_id, chat_id = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Parece que no te refieres a un usuario".)
        return
    elif not chat_id:
        message.reply_text("Parece que no te estás refiriendo a un chat".)
        return

    try:
        chat = bot.get_chat(chat_id.split()[0])
    except BadRequest as excp:
        if excp.message == "Chat no encontrado":
            message.reply_text("¡Chat no encontrado! Asegúrese de haber ingresado una ID de chat válida y yo soy parte de ese chat".)
            return
        else:
            raise

    if chat.type == 'private':
        message.reply_text("Lo siento, ¡pero eso es un chat privado!")
        return

    if not is_bot_admin(chat, bot.id) or not chat.get_member(bot.id).can_restrict_members:
        message.reply_text("¡No puedo restringir a las personas allí! Asegúrate de que soy administrador y puedo prohibir a los usuarios".)
        return

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "Usuario no encontrado":
            message.reply_text("Parece que no puedo encontrar a este usuario")
            return
        else:
            raise

    if is_user_ban_protected(chat, user_id, member):
        message.reply_text("Realmente desearía poder prohibir a los administradores ...")
        return

    if user_id == bot.id:
        message.reply_text("No me voy a PROHIBIR, ¿estás loco?")
        return

    try:
        chat.kick_member(user_id)
        message.reply_text("Banned!")
    except BadRequest as excp:
        if excp.message == "Mensaje de respuesta no encontrado":
            # Do not reply
            message.reply_text('Banned!', quote=False)
        elif excp.message in RBAN_ERRORS:
            message.reply_text(excp.message)
        else:
            LOGGER.warning(update)
            LOGGER.exception("ERROR banning user %s in chat %s (%s) due to %s", user_id, chat.title, chat.id,
                             excp.message)
            message.reply_text("Bueno, maldición, no puedo prohibir a ese usuario".)

@run_async
@bot_admin
def runban(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message

    if not args:
        message.reply_text("Parece que no te estás refiriendo a un chat /user".)
        return

    user_id, chat_id = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Parece que no te refieres a un usuario")
        return
    elif not chat_id:
        message.reply_text("Parece que no te refieres a un usuario")
        return

    try:
        chat = bot.get_chat(chat_id.split()[0])
    except BadRequest as excp:
        if excp.message == "Chat no encontrado":
            message.reply_text("¡Chat no encontrado! Asegúrese de haber ingresado una ID de chat válida y yo soy parte de ese chat".)
            return
        else:
            raise

    if chat.type == 'private':
        message.reply_text("Lo siento, ¡pero eso es un chat privado!")
        return

    if not is_bot_admin(chat, bot.id) or not chat.get_member(bot.id).can_restrict_members:
        message.reply_text("¡No puedo restringir a las personas allí! Asegúrate de que soy administrador y puedo excluir a los usuarios".)
        return

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "Usuario no encontrado":
            message.reply_text("Parece que no puedo encontrar a este usuario allí")
            return
        else:
            raise
            
    if is_user_in_chat(chat, user_id):
        message.reply_text("¿Por qué estás tratando de deshacer remotamente a alguien que ya está en ese chat?")
        return

    if user_id == bot.id:
        message.reply_text("No me voy a ABANDONAR, ¡soy un administrador allí!")
        return

    try:
        chat.unban_member(user_id)
        message.reply_text("Sí, este usuario puede unirse a ese chat!")
    except BadRequest as excp:
        if excp.message == "Mensaje de respuesta no encontrado":
            # Do not reply
            message.reply_text('Unbanned!', quote=False)
        elif excp.message in RUNBAN_ERRORS:
            message.reply_text(excp.message)
        else:
            LOGGER.warning(update)
            LOGGER.exception("ERROR al desbancar al usuario %s en el chat %s (%s) debido a %s", user_id, chat.title, chat.id,
                             excp.message)
            message.reply_text("Bueno maldita sea, no puedo deshacer a ese usuario".)


__help__ = """
- /kickme: patea al usuario que emitió el comando

* Solo administrador: *
  - /ban <userhandle>: prohíbe a un usuario. (a través del identificador o respuesta)
  - /tban <userhandle> x (m / h / d): prohíbe a un usuario x tiempo. (a través del identificador o respuesta). m = minutos, h = horas, d = días.
  - /unban <userhandle>: deshace la prohibición de un usuario. (a través del identificador o respuesta)
  - /kick <userhandle>: patea a un usuario, (a través del identificador o respuesta)
"" "

__mod_name__ = "Bans"

BAN_HANDLER = CommandHandler("ban", ban, pass_args=True, filters=Filters.group)
TEMPBAN_HANDLER = CommandHandler(["tban", "tempban"], temp_ban, pass_args=True, filters=Filters.group)
KICK_HANDLER = CommandHandler("kick", kick, pass_args=True, filters=Filters.group)
UNBAN_HANDLER = CommandHandler("unban", unban, pass_args=True, filters=Filters.group)
KICKME_HANDLER = DisableAbleCommandHandler("kickme", kickme, filters=Filters.group)
RBAN_HANDLER = CommandHandler("rban", rban, pass_args=True, filters=CustomFilters.sudo_filter)
RUNBAN_HANDLER = CommandHandler("runban", runban, pass_args=True, filters=CustomFilters.sudo_filter)

dispatcher.add_handler(BAN_HANDLER)
dispatcher.add_handler(TEMPBAN_HANDLER)
dispatcher.add_handler(KICK_HANDLER)
dispatcher.add_handler(UNBAN_HANDLER)
dispatcher.add_handler(KICKME_HANDLER)
dispatcher.add_handler(RBAN_HANDLER)
dispatcher.add_handler(RUNBAN_HANDLER)
