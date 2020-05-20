from functools import wraps
from typing import Optional

from tg_bot.modules.helper_funcs.misc import is_module_loaded

FILENAME = __name__.rsplit(".", 1)[-1]

if is_module_loaded(FILENAME):
    from telegram import Bot, Update, ParseMode, Message, Chat
    from telegram.error import BadRequest, Unauthorized
    from telegram.ext import CommandHandler, run_async
    from telegram.utils.helpers import escape_markdown

    from tg_bot import dispatcher, LOGGER
    from tg_bot.modules.helper_funcs.chat_status import user_admin
    from tg_bot.modules.sql import log_channel_sql as sql


    def loggable(func):
        @wraps(func)
        def log_action(bot: Bot, update: Update, *args, **kwargs):
            result = func(bot, update, *args, **kwargs)
            chat = update.effective_chat  # type: Optional[Chat]
            message = update.effective_message  # type: Optional[Message]
            if result:
                if chat.type == chat.SUPERGROUP and chat.username:
                    result += "\n<b>Link:</b> " \
                              "<a href=\"http://telegram.me/{}/{}\">click here</a>".format(chat.username,
                                                                                           message.message_id)
                log_chat = sql.get_chat_log_channel(chat.id)
                if log_chat:
                    send_log(bot, log_chat, chat.id, result)
            elif result == "":
                pass
            else:
                LOGGER.warning("%s se estableció como registrable, pero no tenía declaración de devolución ", func)

            return result

        return log_action


    def send_log(bot: Bot, log_chat_id: str, orig_chat_id: str, result: str):
        try:
            bot.send_message(log_chat_id, result, parse_mode=ParseMode.HTML)
        except BadRequest as excp:
            if excp.message == "Chat no encontrado":
                bot.send_message(orig_chat_id, "Este canal de registro ha sido eliminado - desarmando ".)
                sql.stop_chat_logging(orig_chat_id)
            else:
                LOGGER.warning(excp.message)
                LOGGER.warning(result)
                LOGGER.exception("No se pudo analizar")

                bot.send_message(log_chat_id, result + "\n\nEl formateo se ha deshabilitado debido a un error inesperado ")


    @run_async
    @user_admin
    def logging(bot: Bot, update: Update):
        message = update.effective_message  # type: Optional[Message]
        chat = update.effective_chat  # type: Optional[Chat]

        log_channel = sql.get_chat_log_channel(chat.id)
        if log_channel:
            log_channel_info = bot.get_chat(log_channel)
            message.reply_text(
                "Este grupo tiene todos sus registros enviados a: {} (`{}`)".format(escape_markdown(log_channel_info.title),
                                                                         log_channel),
                parse_mode=ParseMode.MARKDOWN)

        else:
            message.reply_text("¡No se ha establecido ningún canal de registro para este grupo!")


    @run_async
    @user_admin
    def setlog(bot: Bot, update: Update):
        message = update.effective_message  # type: Optional[Message]
        chat = update.effective_chat  # type: Optional[Chat]
        if chat.type == chat.CHANNEL:
            message.reply_text("¡Ahora, reenvíe el /setlog al grupo al que desea vincular este canal!")

        elif message.forward_from_chat:
            sql.set_chat_log_channel(chat.id, message.forward_from_chat.id)
            try:
                message.delete()
            except BadRequest as excp:
                if excp.message == "Mensaje para borrar no encontrado":
                    pass
                else:
                    LOGGER.exception("Error al eliminar el mensaje en el canal de registro. Sin embargo, debería funcionar de todos modos")

            try:
                bot.send_message(message.forward_from_chat.id,
                                 "Este canal se ha establecido como el canal de registro para {}".format(
                                     chat.title or chat.first_name))
            except Unauthorized as excp:
                if excp.message == "Prohibido: el bot no es miembro del chat del canal":
                    bot.send_message(chat.id, "¡Establecer correctamente el canal de registro!")
                else:
                    LOGGER.exception("ERROR al configurar el canal de registro")

            bot.send_message(chat.id, "¡Establecer correctamente el canal de registro!")

        else:
            message.reply_text("Los pasos para configurar un canal de registro son:\n"
                               " - agregue bot al canal deseado\n"
                               " - Enviar /setlog al canal\n"
                               " - forward the /setlog en el grupo\n")


    @run_async
    @user_admin
    def unsetlog(bot: Bot, update: Update):
        message = update.effective_message  # type: Optional[Message]
        chat = update.effective_chat  # type: Optional[Chat]

        log_channel = sql.stop_chat_logging(chat.id)
        if log_channel:
            bot.send_message(log_channel, "El canal ha sido desvinculado de {}".format(chat.title))
            message.reply_text("El canal de registro ha sido desarmado.")

        else:
            message.reply_text("¡Aún no se ha establecido un canal de registro!")


    def __stats__():
        return "{} log channels set.".format(sql.num_logchannels())


    def __migrate__(old_chat_id, new_chat_id):
        sql.migrate_chat(old_chat_id, new_chat_id)


    def __chat_settings__(chat_id, user_id):
        log_channel = sql.get_chat_log_channel(chat_id)
        if log_channel:
            log_channel_info = dispatcher.bot.get_chat(log_channel)
            return "Este grupo tiene todos sus registros enviados a: {} (`{}`)".format(escape_markdown(log_channel_info.title),
                                                                            log_channel)
        return "¡No se ha establecido ningún canal de registro para este grupo!"


    __help__ = """
*Admin only:*
- /logchannel: obtener información del canal de registro
- /setlog: establecer el canal de registro.
- /unsetlog: desarmar el canal de registro.

La configuración del canal de registro se realiza mediante:
- Agregar el bot al canal deseado (¡como administrador!)
- envío /setlog en el canal
- reenviar el /setlog al grupo
"" "

    __mod_name__ = "Log Channels"

    LOG_HANDLER = CommandHandler("logchannel", logging)
    SET_LOG_HANDLER = CommandHandler("setlog", setlog)
    UNSET_LOG_HANDLER = CommandHandler("unsetlog", unsetlog)

    dispatcher.add_handler(LOG_HANDLER)
    dispatcher.add_handler(SET_LOG_HANDLER)
    dispatcher.add_handler(UNSET_LOG_HANDLER)

else:
    # run anyway if module not loaded
    def loggable(func):
        return func
