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
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "")

LANG, WEIGHT, TARGET, HEIGHT, AGE, PAST, NOW, FRIDGE, WORKOUT = range(9)

LANG_BUTTONS = {"ქართული": "ka", "Русский": "ru", "English": "en"}
LANG_NAMES = {"ka": "Georgian", "ru": "Russian", "en": "English"}
YES = {"ka": "დიახ", "ru": "Да", "en": "Yes"}
NO = {"ka": "არა", "ru": "Нет", "en": "No"}

T = {
    "ka": {
        "weight": "რამდენ კილოგრამს იწონი დღეს? (მაგალითად: 82)",
        "target": "რა წონამდე გინდა მისვლა 1 წლის განმავლობაში? (მაგალითად: 72)",
        "height": "რა სიმაღლე გაქვს სანტიმეტრებში? (მაგალითად: 170)",
        "age": "რამდენი წლის ხარ?",
        "past": "მომიყევი შენს წარსულ ცხოვრების წესზე: როგორ ცხოვრობდი, გქონდა თუ არა სტრესი, რა რეჟიმი და გრაფიკი გქონდა, მუშაობდი თუ არა, რა ემოციებს განიცდიდი. დაწერე თავისუფლად, როგორც გინდა.",
        "now": "ახლა მოკლედ მომიყევი, როგორია შენი დღევანდელი ცხოვრება?",
        "fridge": "შენი მაცივარი: რა პროდუქტები გაქვს ხელმისაწვდომი და რა თანხა (ლარებში) შეგიძლია დღეში ან თვეში კვებას დაუთმო?",
        "workout": "შეგიძლია დღეში 3 წუთი ვარჯიში? 💪",
        "bad_number": "გთხოვ, ჩაწერე რიცხვი, მაგალითად: 82",
        "bad_target": "სამიზნე წონა დღევანდელ წონაზე ნაკლები უნდა იყოს. სცადე ისევ.",
        "minor": "ჯერ მხოლოდ 18 წლიდან შემიძლია დახმარება. ახალგაზრდებისთვის კვების გეგმა ექიმთან ერთად უნდა შედგეს. ახლიდან დასაწყებად: /start",
        "wait": "ვფიქრობ და შენთვის გეგმას ვაწყობ... ეს 20-60 წამს გასტანს ⏳",
        "error": "ვაი, ახლა ვერ გავუმკლავდი. სცადე ცოტა ხანში: /start",
        "cancel": "კარგი, გავჩერდით. ახლიდან დასაწყებად: /start",
        "workout_msg": "💪 შენი 3-წუთიანი ვარჯიში: მარტივი ვარჯიშების ვიდეოები ამ ბმულზე:\n{link}\n\nრეკომენდაცია: 2 კვირის შემდეგ ვარჯიში გაზარდე 1 წუთით (4 წუთი), შემდეგ ყოველ 2 კვირაში კიდევ 1 წუთით, სანამ 10 წუთამდე არ მიხვალ.",
        "disclaimer": "ℹ️ ეს ზოგადი რჩევებია და არა სამედიცინო დანიშნულება. თუ ჯანმრთელობის პრობლემები გაქვს, გაიარე კონსულტაცია ექიმთან.\n\nახალი გეგმისთვის: /start",
        "video_query": "easy 3 minute beginner workout at home",
    },
    "ru": {
        "weight": "Сколько килограммов ты весишь сегодня? (например: 82)",
        "target": "Какого веса ты хочешь достичь за 1 год? (например: 72)",
        "height": "Какой у тебя рост в сантиметрах? (например: 170)",
        "age": "Сколько тебе лет?",
        "past": "Расскажи о своём прошлом образе жизни: как ты жил(а), был(а) ли стресс, какой был режим и график, работал(а) ли ты, какие эмоции переживал(а). Пиши свободно, как хочешь.",
        "now": "Теперь коротко: какова твоя жизнь сегодня?",
        "fridge": "Твой холодильник: какие продукты у тебя есть и какую сумму (в лари) ты можешь тратить на питание в день или в месяц?",
        "workout": "Можешь ли ты уделять зарядке 3 минуты в день? 💪",
        "bad_number": "Пожалуйста, напиши число, например: 82",
        "bad_target": "Желаемый вес должен быть меньше текущего. Попробуй ещё раз.",
        "minor": "Пока я могу помогать только с 18 лет. Для молодых людей план питания должен составляться вместе с врачом. Чтобы начать заново: /start",
        "wait": "Думаю и собираю для тебя план... Это займёт 20-60 секунд ⏳",
        "error": "Ой, сейчас не получилось. Попробуй чуть позже: /start",
        "cancel": "Хорошо, остановились. Чтобы начать заново: /start",
        "workout_msg": "💪 Твоя 3-минутная зарядка: простые видео для начинающих по ссылке:\n{link}\n\nРекомендация: через 2 недели увеличь зарядку на 1 минуту (до 4 минут), затем каждые 2 недели ещё на 1 минуту, пока не дойдёшь до 10 минут.",
        "disclaimer": "ℹ️ Это общие советы, а не медицинское назначение. Если у тебя есть проблемы со здоровьем, проконсультируйся с врачом.\n\nДля нового плана: /start",
        "video_query": "лёгкая зарядка 3 минуты для начинающих дома",
    },
    "en": {
        "weight": "How many kilograms do you weigh today? (for example: 82)",
        "target": "What weight would you like to reach within 1 year? (for example: 72)",
        "height": "What is your height in centimeters? (for example: 170)",
        "age": "How old are you?",
        "past": "Tell me about your past lifestyle: how you lived, whether you had stress, what routine and schedule you had, whether you worked, what emotions you went through. Write freely, however you like.",
        "now": "Now briefly: what is your life like today?",
        "fridge": "Your fridge: what foods do you have available, and how much money (in GEL) can you spend on food per day or per month?",
        "workout": "Can you do a 3-minute workout each day? 💪",
        "bad_number": "Please type a number, for example: 82",
        "bad_target": "The target weight must be lower than your current weight. Please try again.",
        "minor": "For now I can only help from age 18. For younger people, a nutrition plan should be made together with a doctor. To start over: /start",
        "wait": "Thinking and building your plan... This takes 20-60 seconds ⏳",
        "error": "Oops, I could not manage that right now. Please try again a bit later: /start",
        "cancel": "Okay, stopped. To start over: /start",
        "workout_msg": "💪 Your 3-minute workout: easy beginner videos at this link:\n{link}\n\nRecommendation: after 2 weeks, add 1 minute (4 minutes total), then add 1 more minute every 2 weeks until you reach 10 minutes.",
        "disclaimer": "ℹ️ This is general advice, not medical treatment. If you have health problems, please consult a doctor.\n\nFor a new plan: /start",
        "video_query": "easy 3 minute beginner workout at home",
    },
}


def parse_number(text):
    match = re.search(r"\d+(?:[.,]\d+)?", text or "")
    if not match:
        return None
    return float(match.group().replace(",", "."))


def max_loss_kg(weight):
    # 95 kg -> about 9.5 kg, 150 kg -> about 25 kg
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
    await update.message.reply_text(T[lang]["now"])
    return NOW


async def get_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    context.user_data["now"] = (update.message.text or "")[:2000]
    await update.message.reply_text(T[lang]["fridge"])
    return FRIDGE


async def get_fridge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    context.user_data["fridge"] = (update.message.text or "")[:2000]
    keyboard = ReplyKeyboardMarkup(
        [[YES[lang], NO[lang]]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(T[lang]["workout"], reply_markup=keyboard)
    return WORKOUT


def build_prompt(d, lang, can_workout):
    weight, target, height = d["weight"], d["target"], d["height"]
    wanted = round(weight - target, 1)
    recommended = min(wanted, max_loss_kg(weight))
    bmi_now = round(weight / ((height / 100) ** 2), 1)
    bmi_after = round((weight - recommended) / ((height / 100) ** 2), 1)
    return f"""You are Easy Balance, a warm, funny, non-judgmental nutrition coach and dietitian.
Write the whole answer in {LANG_NAMES[lang]}.

User data:
- Current weight: {weight} kg
- Wished target weight within 1 year: {target} kg (wants to lose {wanted} kg)
- Height: {height} cm
- Age: {d['age']}
- BMI now: {bmi_now}
- Recommended realistic loss over 12 months: about {recommended} kg (BMI would be about {bmi_after})
- Past lifestyle (stress, routine, work, emotions): {d['past']}
- Life today: {d['now']}
- Fridge, available foods and food budget: {d['fridge']}
- Can do a 3 minute daily workout: {'yes' if can_workout else 'no'}

Your task: do a professional but simple analysis and create a balanced eating plan that is financially, morally and emotionally balanced.

Rules:
1. Weight loss must be healthy and low-stress. Use the recommended loss above as the yearly goal, and explain in one or two friendly sentences why it is a good, safe goal. If the user's wish is bigger than that, gently say so. Never recommend a BMI below 20. If the user is already at a healthy BMI, focus on healthy habits instead of losing weight.
2. Base everything on the user's real possibilities: foods they have, their budget, their schedule and their emotional situation. Use cheap, local, easy-to-find foods and simple cooking.
3. The plan MUST include tasty foods and sweets that are usually seen as unhealthy (for example dessert, pizza, khachapuri, chocolate, ice cream), but in a balanced, planned way. No forbidden foods, no guilt.
4. Give: (a) a short analysis of the user's situation (3-5 lines), (b) a rough daily calorie range and a simple plate rule, (c) a simple 7-day menu with breakfast, lunch, snack, dinner, (d) a weekly treats plan, (e) a cheap shopping list that fits the budget, (f) 3-5 tips for stress and emotional eating based on the user's story, (g) milestones for 3, 6, 9 and 12 months, (h) what to do if the user slips or skips a day.
5. The menu must be very easy to understand and should not raise extra questions. Think ahead about possible situations (eating out, guests, holidays, no time to cook, low budget days) and give a short answer for each.
6. Do NOT use markdown symbols such as *, #, or backticks. Use plain text, emojis, short lines and line breaks.
7. Keep it clear and compact, at most about 6000 characters. A light touch of humor is welcome.
"""


def model_rank(name):
    m = re.match(r"^gemini-(\d+(?:\.\d+)?)-flash(-lite)?$", name)
    if m:
        return (0, -float(m.group(1)), 1 if m.group(2) else 0, name)
    return (1, 0, 0, name)


async def pick_models(client):
    """Ask Google which Flash models are available right now."""
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
    # stable models first, then previews; full Flash before Flash-Lite
    names.sort(key=lambda n: ("preview" in n, "lite" in n))
    logging.info("Available Flash models: %s", names)
    return names[:8], ""


async def ask_gemini(prompt):
    errors = []
    async with httpx.AsyncClient(timeout=60) as client:
        discovered, list_error = await pick_models(client)
        if list_error:
            errors.append(list_error)
        models = []
        for m in [GEMINI_MODEL] + discovered + ["gemini-2.5-flash", "gemini-2.5-flash-lite"]:
            if m and m not in models:
                models.append(m)
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                r = await client.post(
                    url,
                    headers={"x-goog-api-key": GEMINI_API_KEY},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.7},
                    },
                )
            except Exception as e:
                logging.warning("Gemini %s request failed: %r", model, e)
                errors.append(f"{model}: {type(e).__name__}")
                continue
            if r.status_code == 200:
                try:
                    parts = r.json()["candidates"][0]["content"]["parts"]
                    text = "".join(p.get("text", "") for p in parts).strip()
                    if text:
                        logging.info("Answer created with model %s", model)
                        return text, ""
                    errors.append(f"{model}: empty answer")
                except Exception as e:
                    logging.warning("Gemini %s parse failed: %r", model, e)
                    errors.append(f"{model}: unreadable answer")
                continue
            status = ""
            try:
                status = r.json().get("error", {}).get("status", "")
            except Exception:
                pass
            errors.append(f"{model}: HTTP {r.status_code} {status}".strip())
            logging.warning("Gemini %s status %s: %s", model, r.status_code, r.text[:300])
            if r.status_code in (400, 401, 403) and "API key" in r.text:
                break  # the key itself is wrong, other models will not help
    return None, " | ".join(errors)[:600]


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


async def get_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    can_workout = (update.message.text or "").strip() == YES[lang]
    await update.message.reply_text(T[lang]["wait"], reply_markup=ReplyKeyboardRemove())

    answer, error_info = await ask_gemini(build_prompt(context.user_data, lang, can_workout))
    if not answer:
        await update.message.reply_text(T[lang]["error"] + "\n\n(info: " + error_info + ")")
        return ConversationHandler.END

    await send_long(update, answer)

    if can_workout:
        link = "https://www.youtube.com/results?search_query=" + quote_plus(T[lang]["video_query"])
        await update.message.reply_text(T[lang]["workout_msg"].format(link=link))

    await update.message.reply_text(T[lang]["disclaimer"])
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(context)
    await update.message.reply_text(T[lang]["cancel"], reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


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
            WEIGHT: [MessageHandler(text_only, get_weight)],
            TARGET: [MessageHandler(text_only, get_target)],
            HEIGHT: [MessageHandler(text_only, get_height)],
            AGE: [MessageHandler(text_only, get_age)],
            PAST: [MessageHandler(text_only, get_past)],
            NOW: [MessageHandler(text_only, get_now)],
            FRIDGE: [MessageHandler(text_only, get_fridge)],
            WORKOUT: [MessageHandler(text_only, get_workout)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )
    app.add_handler(conv)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
