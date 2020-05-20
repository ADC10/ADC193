import json
from io import BytesIO
from typing import Optional

from telegram import Message, Chat, Update, Bot
from telegram.error import BadRequest
from telegram.ext import CommandHandler, run_async

from tg_bot import dispatcher, LOGGER
from tg_bot.__main__ import DATA_IMPORT
from tg_bot.modules.helper_funcs.chat_status import user_admin


@run_async
@user_admin
def import_data(bot: Bot, update):
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    # TODO: allow uploading doc with command, not just as reply
    # only work with a doc
    if msg.reply_to_message and msg.reply_to_message.document:
        try:
            file_info = bot.get_file(msg.reply_to_message.document.file_id)
        except BadRequest:
            msg.reply_text("Intente descargar y volver a cargar el archivo como usted mismo antes de importar, este parece"
                           "ser dudoso!")
            return

        with BytesIO() as file:
            file_info.download(out=file)
            file.seek(0)
            data = json.load(file)

        # only import one group
        if len(data) > 1 and str(chat.id) not in data:
            msg.reply_text("Hay más de un grupo aquí en este archivo, y ninguno tiene la misma identificación de chat que este grupo"
                           "- ¿Cómo elijo qué importar?")
            return

        # Select data source
        if str(chat.id) in data:
            data = data[str(chat.id)]['hashes']
        else:
            data = data[list(data.keys())[0]]['hashes']

        try:
            for mod in DATA_IMPORT:
                mod.__import_data__(str(chat.id), data)
        except Exception:
            msg.reply_text("Se produjo una excepción al restaurar sus datos. El proceso puede no estar completo. Si"
                           "tiene problemas con esto, envíe un mensaje a @kingpipo18 con su archivo de copia de seguridad para que el"
                           "El problema puede ser depurado. Mis propietarios estarán encantados de ayudar, y cada error"
                           "¡El informe me hace mejor! ¡Gracias! :)")
            LOGGER.exception("Falló la importación para chatid %s con el nombre %s"., str(chat.id), str(chat.title))
            return

        # TODO: some of that link logic
        # NOTE: consider default permissions stuff?
        msg.reply_text("Copia de seguridad totalmente importada. ¡Dar una buena acogida! :RE")


@run_async
@user_admin
def export_data(bot: Bot, update: Update):
    msg = update.effective_message  # type: Optional[Message]
    msg.reply_text("Exportado con éxito :-)")


__mod_name__ = "Backups"

__help__ = """
* Solo administrador: *
  - /import: responde a un archivo de copia de seguridad de mayordomo grupal para importar lo más posible, haciendo que la transferencia sea súper simple. Nota \
que los archivos / fotos no pueden importarse debido a restricciones de telegramas.
  - /exportar: !!! Esto aún no es un comando, ¡pero debería llegar pronto!
"" "
IMPORT_HANDLER = CommandHandler("import", import_data)
EXPORT_HANDLER = CommandHandler("export", export_data)

dispatcher.add_handler(IMPORT_HANDLER)
dispatcher.add_handler(EXPORT_HANDLER)
