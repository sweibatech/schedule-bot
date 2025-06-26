from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

from bot_app.handlers import start, participate_handler, choose_day, choose_event, choose_role, cancel, \
    show_cancel_participation_menu, cancel_participation, schedule_handler, admin, admin_manage_event_select, \
    admin_edit_event_choice, admin_set_event_time, user_menu_handler
from config.settings import TOKEN, CHOOSING_DAY, CHOOSING_EVENT, CHOOSING_ROLE, CHOOSING_CANCEL, MANAGE_EVENT_SELECT, \
    EDIT_EVENT_CHOICE, SET_EVENT_TIME
from db.db_structure import init_db


def bot_app():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    participate_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^Участвовать$"), participate_handler)
        ],
        states={
            CHOOSING_DAY: [CallbackQueryHandler(choose_day, pattern=r"^chooseday")],
            CHOOSING_EVENT: [CallbackQueryHandler(choose_event, pattern=r"^chooseevent")],
            CHOOSING_ROLE: [CallbackQueryHandler(choose_role, pattern=r"^chooserole")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(participate_conv)

    cancel_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Отменить участие$"), show_cancel_participation_menu)],
        states={
            CHOOSING_CANCEL: [CallbackQueryHandler(cancel_participation, pattern=r"^(cancelpart\||cancelall$)")],
        },
        fallbacks=[],
    )
    app.add_handler(cancel_conv)

    app.add_handler(MessageHandler(filters.Regex("^Расписание$"), schedule_handler))

    admin_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Редактировать события$"), admin)],
        states={
            MANAGE_EVENT_SELECT: [
                CallbackQueryHandler(admin_manage_event_select, pattern=r"^manageevent\|")
            ],
            EDIT_EVENT_CHOICE: [
                CallbackQueryHandler(admin_edit_event_choice, pattern=r"^(edittime|canceladmin)$")
            ],
            SET_EVENT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_event_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(admin_conv)
    app.add_handler(MessageHandler(
        filters.Regex("^(Участвовать|Расписание|Отменить участие)$"),
        user_menu_handler
    ))

    app.run_polling()
