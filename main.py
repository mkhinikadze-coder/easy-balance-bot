import asyncio
import logging
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import quote_plus

import httpx
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "")
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "minde5a")

(
    LANG, PATH, ED_SCREEN, WEIGHT, TARGET, HEIGHT, AGE,
    PAST, EMOTION, NOW, FRIDGE, WORKOUT,
) = range(12)

LANG_BUTTONS = {"ქართული": "ka", "Русский": "ru", "English": "en"}
LANG_NAMES = {"ka": "Georgian", "ru": "Russian", "en": "English"}
YES = {"ka": "დიახ", "ru": "Да", "en": "Yes"}
NO = {"ka": "არა", "ru": "Нет", "en": "No"}

PATH_BUTTONS = {
    "ka": {"🍽 მშვიდი კალორია": "calm", "⏳ მსუბუქი დეფიციტი": "window"},
    "ru": {"🍽 Спокойные калории": "calm", "⏳ Лёгкий дефицит": "window"},
    "en": {"🍽 Calm Calories": "calm", "⏳ Light Deficit": "window"},
}

T = {
    "ka": {
        "choose_path": "ორი გზა გაქვს არჩევანში — ორივე მიდის იმავე მიზნისკენ, სხვადასხვა გზით:\n\n🍽 მშვიდი კალორია — კვების რაოდენობის მსუბუქი, მინიმალურად დამძაბავი კორექტირება.\n⏳ მსუბუქი დეფიციტი — კვების საათების თანდათანობითი, ნელი დავიწროება 18-საათიან ინტერვალურ კვებამდე, რაოდენობის შეზღუდვის გარეშე.\n\nრომელი გინდა?",
        "ed_screen": "სანამ გავაგრძელებთ — გქონია თუ არა ოდესმე სერიოზული ბრძოლა კვების დარღვევებთან (მაგალითად ანორექსია, ბულიმია), ან ხარ თუ არა ამჟამად ამის მკურნალობის პროცესში?",
        "ed_screen_yes_note": "მადლობა გულწრფელობისთვის. ეს ნამდვილად მნიშვნელოვანია — კარგი იქნება, თუ ამ გზაზე სპეციალისტთან ერთად იაროთ, განსაკუთრებით კვების საათებთან დაკავშირებულ ნაწილში. მე მაინც შემიძლია დაგეხმარო მსუბუქი, ზრუნვაზე დაფუძნებული მიმართულებით, თუ გსურს გავაგრძელოთ.",
        "weight": "რამდენ კილოგრამს იწონი დღეს? (მაგალითად: 82)",
        "target": "რა წონამდე გინდა მისვლა 1 წლის განმავლობაში? (მაგალითად: 72)",
        "height": "რა სიმაღლე გაქვს სანტიმეტრებში? (მაგალითად: 170)",
        "age": "რამდენი წლის ხარ?",
        "past": "მომიყევი შენს წარსულ ცხოვრების წესზე: როგორ ცხოვრობდი, გქონდა თუ არა სტრესი, რა რეჟიმი და გრაფიკი გქონდა, მუშაობდი თუ არა, რა ემოციებს განიცდიდი. დაწერე თავისუფლად, როგორც გინდა.",
        "emotion": "როცა ცუდად ხარ ან ცუდი ემოცია გაქვს, რას მიმართავ ყველაზე ხშირად — საკვებს, სხვა რამეს, თუ არაფერს?",
        "now": "ახლა მოკლედ მომიყევი, როგორია შენი დღევანდელი ცხოვრება?",
        "fridge": "შენი მაცივარი: რა პროდუქტები გაქვს ხელმისაწვდომი და რა თანხა (ლარებში) შეგიძლია დღეში ან თვეში კვებას დაუთმო?",
        "workout": "შეგიძლია დღეში 3 წუთი ვარჯიში? 💪",
        "bad_number": "გთხოვ, ჩაწერე რიცხვი, მაგალითად: 82",
        "bad_target": "სამიზნე წონა დღევანდელ წონაზე ნაკლები უნდა იყოს. სცადე ისევ.",
        "minor": "ჯერ მხოლოდ 18 წლიდან შემიძლია დახმარება. ახალგაზრდებისთვის კვების გეგმა ექიმთან ერთად უნდა შედგეს. ახლიდან დასაწყებად: /start",
        "wait": "ვფიქრობ და შენთვის გეგმას ვაწყობ... ეს 20-60 წამს გასტანს ⏳",
        "error": "ვაი, ახლა ვერ გავუმკლავდი. სცადე ცოტა ხანში: /start",
        "cancel": "კარგი, გავჩერდით. ახლიდან დასაწყებად: /start",
        "disclaimer": "ℹ️ ეს ზოგადი რჩევებია და არა სამედიცინო დანიშნულება. თუ ჯანმრთელობის პრობლემები გაქვს, გაიარე კონსულტაცია ექიმთან.\n\nახალი გეგმისთვის: /start",
        "contact": "კითხვა გაქვს, ტექნიკური პრობლემა შეგექმნა, ან გადახდის ქვითარი გინდა გამოაგზავნო? მომწერე პირდაპირ: https://t.me/{owner}",
        "help": "დახმარებისთვის ან ნებისმიერი კითხვისთვის მომწერე: https://t.me/{owner}\n\nახალი ანალიზის დასაწყებად: /start",
    },
    "ru": {
        "choose_path": "У тебя есть два пути — оба ведут к одной цели, разными способами:\n\n🍽 Спокойные калории — мягкая, минимально напряжная корректировка количества еды.\n⏳ Лёгкий дефицит — постепенное сужение часов питания до 18-часового интервального питания, без ограничения количества.\n\nКакой выбираешь?",
        "ed_screen": "Прежде чем продолжить — был ли у тебя когда-нибудь серьёзный опыт расстройства пищевого поведения (например, анорексия, булимия), или проходишь ли ты сейчас лечение от этого?",
        "ed_screen_yes_note": "Спасибо за честность. Это действительно важно — будет хорошо, если этот путь ты будешь проходить вместе со специалистом, особенно в части, связанной с часами питания. Я всё равно могу помочь мягким, заботливым направлением, если хочешь продолжить.",
        "weight": "Сколько килограммов ты весишь сегодня? (например: 82)",
        "target": "Какого веса ты хочешь достичь за 1 год? (например: 72)",
        "height": "Какой у тебя рост в сантиметрах? (например: 170)",
        "age": "Сколько тебе лет?",
        "past": "Расскажи о своём прошлом образе жизни: как ты жил(а), был(а) ли стресс, какой был режим и график, работал(а) ли ты, какие эмоции переживал(а). Пиши свободно, как хочешь.",
        "emotion": "Когда тебе плохо или возникает тяжёлая эмоция, к чему ты чаще всего обращаешься — к еде, к чему-то другому, или ни к чему?",
        "now": "Теперь коротко: какова твоя жизнь сегодня?",
        "fridge": "Твой холодильник: какие продукты у тебя есть и какую сумму (в лари) ты можешь тратить на питание в день или в месяц?",
        "workout": "Можешь ли ты уделять зарядке 3 минуты в день? 💪",
        "bad_number": "Пожалуйста, напиши число, например: 82",
        "bad_target": "Желаемый вес должен быть меньше текущего. Попробуй ещё раз.",
        "minor": "Пока я могу помогать только с 18 лет. Для молодых людей план питания должен составляться вместе с врачом. Чтобы начать заново: /start",
        "wait": "Думаю и собираю для тебя план... Это займёт 20-60 секунд ⏳",
        "error": "Ой, сейчас не получилось. Попробуй чуть позже: /start",
        "cancel": "Хорошо, остановились. Чтобы начать заново: /start",
        "disclaimer": "ℹ️ Это общие советы, а не медицинское назначение. Если у тебя есть проблемы со здоровьем, проконсультируйся с врачом.\n\nДля нового плана: /start",
        "contact": "Есть вопрос, техническая проблема, или хочешь отправить квитанцию об оплате? Пиши напрямую: https://t.me/{owner}",
        "help": "Для помощи или любого вопроса пиши: https://t.me/{owner}\n\nЧтобы начать новый анализ: /start",
    },
    "en": {
        "choose_path": "You have two paths — both lead to the same goal, in different ways:\n\n🍽 Calm Calories — a gentle, low-stress adjustment of how much you eat.\n⏳ Light Deficit — a slow, gradual narrowing of your eating hours toward 18-hour intermittent eating, with no limit on quantity.\n\nWhich one do you want?",
        "ed_screen": "Before we continue — have you ever seriously struggled with an eating disorder (for example anorexia, bulimia), or are you currently being treated for one?",
        "ed_screen_yes_note": "Thank you for your honesty. That really matters — it would be good to go through this path together with a specialist, especially the eating-hours part. I can still help with a gentle, caring direction if you'd like to continue.",
        "weight": "How many kilograms do you weigh today? (for example: 82)",
        "target": "What weight would you like to reach within 1 year? (for example: 72)",
        "height": "What is your height in centimeters? (for example: 170)",
        "age": "How old are you?",
        "past": "Tell me about your past lifestyle: how you lived, whether you had stress, what routine and schedule you had, whether you worked, what emotions you went through. Write freely, however you like.",
        "emotion": "When you feel bad or have a hard emotion, what do you usually turn to most — food, something else, or nothing?",
        "now": "Now briefly: what is your life like today?",
        "fridge": "Your fridge: what foods do you have available, and how much money (in GEL) can you spend on food per day or per month?",
        "workout": "Can you do a 3-minute workout each day? 💪",
        "bad_number": "Please type a number, for example: 82",
        "bad_target": "The target weight must be lower than your current weight. Please try again.",
        "minor": "For now I can only help from age 18. For younger people, a nutrition plan should be made together with a doctor. To start over: /start",
        "wait": "Thinking and building your plan... This takes 20-60 seconds ⏳",
        "error": "Oops, I could not manage that right now. Please try again a bit later: /start",
        "cancel": "Okay, stopped. To start over: /start",
        "disclaimer": "ℹ️ This is general advice, not medical treatment. If you have health problems, please consult a doctor.\n\nFor a new plan: /start",
        "contact": "Have a question, a technical problem, or want to send a payment receipt? Message directly: https://t.me/{owner}",
        "help": "For help or any question, message: https://t.me/{owner}\n\nTo start a new analysis: /start",
    },
}


def parse_number(text):
    match = re.search(r"\d+(?:[.,]\d+)?", text or "")
    if not match:
        return None
    return float(match.group().replace(",", "."))


def max_loss_kg(weight):
    factor = 0.10 + 0.067 * min(max((weight - 100) / 50, 0), 1)
    return round(weight * factor, 1)


def lang_of(context):
    return context.user_data.get("lang", "en")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = ReplyKeyboardMarkup(
        [["ქართული", "Русский", "English"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(
        "Easy Balance 🍰\n\nაირჩიე ენა / Выбери язык / Choose language:",
        reply_markup=keyboard,
    )
    return LANG


async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = LANG_BUTTONS.get((update.message.text or "").strip())
    if not lang:
        return await start(update, context)
    context.user_data["lang"] = lang
    labels = list(PATH_BUTTONS[lang].keys())
    keyboard = ReplyKeyboardMarkup([[labels[0]], [labels[1]]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(T[lang]["choose_path"], reply_markup=keyboard)
    return PATH


async def choose_path(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    path = PATH_BUTTONS[lang].get((update.message.text or "").strip())
    if not path:
        labels = list(PATH_BUTTONS[lang].keys())
        keyboard = ReplyKeyboardMarkup([[labels[0]], [labels[1]]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(T[lang]["choose_path"], reply_markup=keyboard)
        return PATH
    context.user_data["path"] = path
    keyboard = ReplyKeyboardMarkup([[YES[lang], NO[lang]]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(T[lang]["ed_screen"], reply_markup=keyboard)
    return ED_SCREEN


async def ed_screen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    answer = (update.message.text or "").strip()
    said_yes = answer == YES[lang]
    context.user_data["ed_screen"] = "yes" if said_yes else "no"
    if said_yes:
        await update.message.reply_text(T[lang]["ed_screen_yes_note"], reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(T[lang]["weight"], reply_markup=ReplyKeyboardRemove())
    return WEIGHT


async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    n = parse_number(update.message.text)
    if n is None or not 30 <= n <= 300:
        await update.message.reply_text(T[lang]["bad_number"])
        return WEIGHT
    context.user_data["weight"] = n
    await update.message.reply_text(T[lang]["target"])
    return TARGET


async def get_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    n = parse_number(update.message.text)
    if n is None or not 30 <= n <= 300:
        await update.message.reply_text(T[lang]["bad_number"])
        return TARGET
    if n >= context.user_data["weight"]:
        await update.message.reply_text(T[lang]["bad_target"])
        return TARGET
    context.user_data["target"] = n
    await update.message.reply_text(T[lang]["height"])
    return HEIGHT


async def get_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    n = parse_number(update.message.text)
    if n is None or not 120 <= n <= 230:
        await update.message.reply_text(T[lang]["bad_number"])
        return HEIGHT
    context.user_data["height"] = n
    await update.message.reply_text(T[lang]["age"])
    return AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    n = parse_number(update.message.text)
    if n is None or not 8 <= n <= 100:
        await update.message.reply_text(T[lang]["bad_number"])
        return AGE
    if n < 18:
        await update.message.reply_text(T[lang]["minor"])
        return ConversationHandler.END
    context.user_data["age"] = int(n)
    await update.message.reply_text(T[lang]["past"])
    return PAST


async def get_past(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    context.user_data["past"] = (update.message.text or "")[:2000]
    await update.message.reply_text(T[lang]["emotion"])
    return EMOTION


async def get_emotion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    context.user_data["emotion"] = (update.message.text or "")[:500]
    await update.message.reply_text(T[lang]["now"])
    return NOW


async def get_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    context.user_data["now"] = (update.message.text or "")[:2000]
    if context.user_data.get("path") == "window":
        context.user_data["fridge"] = ""
        return await run_analysis(update, context, can_workout=True)
    await update.message.reply_text(T[lang]["fridge"])
    return FRIDGE


async def get_fridge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    context.user_data["fridge"] = (update.message.text or "")[:2000]
    keyboard = ReplyKeyboardMarkup([[YES[lang], NO[lang]]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(T[lang]["workout"], reply_markup=keyboard)
    return WORKOUT


async def get_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    can_workout = (update.message.text or "").strip() == YES[lang]
    return await run_analysis(update, context, can_workout)


PATH1_SCHEDULE = (
    "Meditation/exercise progression (10-day stages, both habits grow together, "
    "never require skipping more than 1 day in a row or more than 2 days a month): "
    "stage1 (day1-10): meditation 1 min; stage2 (day11-20): 2 min; stage3 (21-30): 3 min; "
    "stage4 (31-40): 4 min; stage5 (41-50): 5 min; stage6 (51-60): 6 min; "
    "stage7 (61-90): 7 min (optionally up to 15 min for those who want more). "
    "A short 3-minute beginner workout runs in parallel from day 1, same easy pace."
)

PATH2_SCHEDULE = (
    "Eating-window progression (5 stages of 14 days each = 90 days total; fasting window, "
    "last-meal target time, meditation and exercise minutes all advance together on the same "
    "14-day clock; missing the exact last-meal time is fine, the only real rule is keeping the "
    "gap-since-last-meal principle and never skipping meditation/exercise more than 1 day in a "
    "row or 2 days a month): "
    "stage1 (day1-14): just keep a 12h gap since last meal, aim to stop eating by 22:00; "
    "meditation 1 min, exercise 3 min. "
    "stage2 (day15-28): 14h gap, aim to stop by 21:00; meditation 2 min, exercise 4 min. "
    "stage3 (day29-42): 16h gap, aim to stop by 20:00; meditation 4 min, exercise 5 min. "
    "stage4 (day43-56): 18h gap, aim to stop by 19:00; meditation 6 min, exercise 7 min. "
    "stage5 (day57-90): hold the 18h/19:00 pattern to let it settle; meditation 7 min "
    "(optionally up to 15 min), exercise 8-10 min."
)


def build_prompt(d, lang, can_workout, path):
    weight, target, height = d["weight"], d["target"], d["height"]
    wanted = round(weight - target, 1)
    recommended = min(wanted, max_loss_kg(weight))
    bmi_now = round(weight / ((height / 100) ** 2), 1)
    bmi_after = round((weight - recommended) / ((height / 100) ** 2), 1)
    ed_flag = d.get("ed_screen") == "yes"
    path_name = "Calm Calories (calorie deficit)" if path == "calm" else "Eating Window (gradual eating-hours narrowing)"
    schedule = PATH1_SCHEDULE if path == "calm" else PATH2_SCHEDULE

    voice_rules = """
Voice and tone rules (plain, concrete, brief — never name any book, author, technique, or
religion anywhere in the output):
- Keep all guidance simple, short and balanced. No abstract or preachy language, no repeated
  slogans, no filler encouragement. Say things directly and concretely.
- For habits (meditation, exercise, the eating schedule): the only real rule is never missing
  two days in a row, and no more than 2 missed days in a month. State this plainly whenever
  relevant. A missed day is not a failure, just continue the next day — say this once, briefly,
  not repeatedly.
- For the meditation/emotional part, convey one simple idea in a sentence or two: the urge to
  eat is often really the mind or an emotion asking to be noticed, not actual hunger. Meditation
  here just means noticing that feeling for a minute (or whatever the stage's duration is)
  without judging it, then deciding separately whether to eat.
- Include one small optional extra: a brief contrast shower (alternating a few seconds of hot
  and cold water) at the end of a regular shower, framed as an optional light practice, never
  required.
- End the weekly menu section with one short line: if feeling bad, pause for a few minutes of
  breathing or a short walk before deciding whether to eat.
"""

    ed_note = ""
    if ed_flag:
        ed_note = (
            "\nImportant: this person indicated a past or current struggle with an eating "
            "disorder. Keep all language extra gentle, avoid any restrictive or achievement-"
            "pressuring framing, emphasize flexibility and self-compassion more than usual, and "
            "naturally mention once that a specialist's support alongside this plan is a good idea "
            "(without being repetitive or alarming)."
        )

    return f"""You are Easy Balance, a warm, grounded, non-judgmental nutrition and habits coach.
Write the whole answer in {LANG_NAMES[lang]}.
{voice_rules}
{ed_note}

Chosen path: {path_name}

User data:
- Current weight: {weight} kg
- Wished target weight within 1 year: {target} kg (wants to lose {wanted} kg)
- Height: {height} cm
- Age: {d['age']}
- BMI now: {bmi_now}
- Recommended realistic loss over 12 months: about {recommended} kg (BMI would be about {bmi_after})
- Past lifestyle (stress, routine, work, emotions): {d['past']}
- What they turn to when feeling bad emotionally: {d['emotion']}
- Life today: {d['now']}
{"- Fridge, available foods and food budget: " + d['fridge'] if d.get('fridge') else ""}
- Can do a 3 minute daily workout: {'yes' if can_workout else 'no'}

Your task: do a professional but simple analysis and create a balanced, low-stress 90-day plan
for this first quarter (this quarter's milestone is day 90; later quarters are handled in a
future check-in, so focus this output on the first 90 days).

Rules:
1. Weight loss must be healthy and low-stress. Use the recommended loss above as the yearly
   goal (not all of it needs to happen in 90 days), and explain in one or two sentences, in the
   voice described above, why this pace is a good, safe goal. If the user's wish is bigger
   than that, gently say so. Never recommend a BMI below 20. If already at a healthy BMI, focus
   on healthy habits rather than further loss.
2. Base everything on the user's real possibilities: their schedule and emotional situation,
   and (when fridge/budget info is given above) their foods and budget. Use cheap, local,
   easy-to-find foods and simple cooking; if no fridge/budget info was given, keep suggestions
   generically affordable rather than asking the person anything further.
3. If the path is Calm Calories, give a rough daily calorie range and a simple plate rule.
   If the path is Eating Window, explain the eating-hours concept simply (no calorie counting
   needed) and make clear food choice stays flexible within the eating window.
4. The plan MUST include tasty foods and sweets usually seen as unhealthy (dessert, pizza,
   khachapuri, chocolate, ice cream), in a balanced, planned way. No forbidden foods, no guilt.
5. Give, in this order: (a) a short analysis of the user's situation (3-5 lines, identity-based
   voice), (b) the calorie/plate rule OR eating-window explanation as appropriate, (c) a simple
   7-day sample menu (breakfast, lunch, snack, dinner) that stays reasonable across the whole
   quarter, ending with the emotion-and-food reminder line, (d) the full stage-by-stage habit
   schedule below verbatim in spirit (meditation, exercise, and for Eating Window also the
   fasting window and last-meal time), written in the required voice, (e) a cheap shopping list
   fitting the budget, (f) 3-5 tips for stress/emotional eating based specifically on what this
   person wrote about their past and their emotional trigger, (g) a short note that there will be
   a check-in around day 90 to see how it went and adjust, (h) what to do in common situations
   (eating out, guests, holidays, no time to cook, low-budget days), (i) the optional contrast-
   shower line, (j) one short closing sentence previewing the longer arc: starting around month
   3 sugar gradually decreases, and the last 3 months (month 9-12) the aim is cutting sugary
   items specifically (juice, soda, cake, ice cream and similar — not ingredient-level sugar
   like ketchup, mayo or butter), without going into detail now since that is covered at the
   month-3 and month-9 check-ins.
   Stage schedule to adapt into the required voice: {schedule}
6. Do NOT use markdown symbols such as *, #, or backticks. Use plain text, emojis, short lines
   and line breaks.
7. Keep it clear and compact, at most about 7000 characters.
"""


async def pick_models(client):
    try:
        r = await client.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": GEMINI_API_KEY},
            params={"pageSize": 200},
        )
    except Exception as e:
        logging.warning("Model list failed: %r", e)
        return [], "model list: connection problem"
    if r.status_code != 200:
        logging.warning("Model list status %s: %s", r.status_code, r.text[:300])
        return [], f"model list: HTTP {r.status_code}"
    bad = (
        "image", "tts", "audio", "live", "embedding", "robotics", "computer",
        "customtools", "exp", "learnlm", "omni", "veo", "imagen", "native", "thinking",
    )
    names = []
    for m in r.json().get("models", []):
        name = m.get("name", "").replace("models/", "")
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" in methods and "flash" in name and not any(b in name for b in bad):
            names.append(name)
    names.sort(reverse=True)
    names.sort(key=lambda n: ("preview" in n, "lite" in n))
    return names[:5], ""


PREFERRED_MODELS = ["gemini-3.1-flash-lite", "gemini-3-flash-preview"]


async def ask_gemini(prompt):
    errors = {}
    models = [m for m in [GEMINI_MODEL] + PREFERRED_MODELS if m]
    seen = []
    for m in models:
        if m not in seen:
            seen.append(m)
    models = seen

    async with httpx.AsyncClient(timeout=60) as client:
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            for attempt in range(2):
                try:
                    r = await client.post(
                        url,
                        headers={"x-goog-api-key": GEMINI_API_KEY},
                        json={
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
                        },
                    )
                except Exception as e:
                    logging.warning("Gemini %s request failed: %r", model, e)
                    errors[model] = type(e).__name__
                    await asyncio.sleep(10)
                    continue
                if r.status_code == 200:
                    try:
                        parts = r.json()["candidates"][0]["content"]["parts"]
                        text = "".join(p.get("text", "") for p in parts).strip()
                        if text:
                            logging.info("Answer created with model %s", model)
                            return text, ""
                        errors[model] = "empty answer"
                    except Exception as e:
                        logging.warning("Gemini %s parse failed: %r", model, e)
                        errors[model] = "unreadable answer"
                    break
                status = ""
                try:
                    status = r.json().get("error", {}).get("status", "")
                except Exception:
                    pass
                errors[model] = f"HTTP {r.status_code} {status}".strip()
                logging.warning("Gemini %s status %s: %s", model, r.status_code, r.text[:300])
                if r.status_code in (400, 401, 403) and "API key" in r.text:
                    return None, "API key problem: " + errors[model]
                if r.status_code == 404:
                    break
                if r.status_code in (429, 500, 503) and attempt == 0:
                    await asyncio.sleep(20)
                    continue
                break
    summary = " | ".join(f"{k}: {v}" for k, v in errors.items())
    return None, summary[:600]


async def send_long(update: Update, text: str):
    while text:
        if len(text) <= 3800:
            chunk, text = text, ""
        else:
            cut = text.rfind("\n", 0, 3800)
            if cut < 1000:
                cut = 3800
            chunk, text = text[:cut], text[cut:].lstrip("\n")
        await update.message.reply_text(chunk)


async def run_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, can_workout: bool):
    lang = lang_of(context)
    path = context.user_data.get("path", "calm")
    await update.message.reply_text(T[lang]["wait"], reply_markup=ReplyKeyboardRemove())

    answer, error_info = await ask_gemini(build_prompt(context.user_data, lang, can_workout, path))
    if not answer:
        await update.message.reply_text(T[lang]["error"] + "\n\n(info: " + error_info + ")")
        return ConversationHandler.END

    await send_long(update, answer)
    await update.message.reply_text(T[lang]["disclaimer"])
    await update.message.reply_text(T[lang]["contact"].format(owner=OWNER_USERNAME))
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    await update.message.reply_text(T[lang]["cancel"], reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context) if context.user_data.get("lang") else "en"
    await update.message.reply_text(T[lang]["help"].format(owner=OWNER_USERNAME))


class Ping(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Easy Balance is running")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def run_server():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), Ping).serve_forever()


def main():
    threading.Thread(target=run_server, daemon=True).start()

    app = Application.builder().token(TELEGRAM_TOKEN).concurrent_updates(True).build()
    text_only = filters.TEXT & ~filters.COMMAND
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [MessageHandler(text_only, choose_lang)],
            PATH: [MessageHandler(text_only, choose_path)],
            ED_SCREEN: [MessageHandler(text_only, ed_screen)],
            WEIGHT: [MessageHandler(text_only, get_weight)],
            TARGET: [MessageHandler(text_only, get_target)],
            HEIGHT: [MessageHandler(text_only, get_height)],
            AGE: [MessageHandler(text_only, get_age)],
            PAST: [MessageHandler(text_only, get_past)],
            EMOTION: [MessageHandler(text_only, get_emotion)],
            NOW: [MessageHandler(text_only, get_now)],
            FRIDGE: [MessageHandler(text_only, get_fridge)],
            WORKOUT: [MessageHandler(text_only, get_workout)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("help", help_cmd))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
