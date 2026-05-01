"""
BOT DE CLIENTES - VAP SOLO SESEÑA
Los clientes pueden ver el catálogo, elegir sabor, vendedor,
día/hora y hacer su pedido.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove, Bot
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from database import (
    SABORES, VENDEDORES, calcular_precio,
    get_stock_total, crear_pedido, init_db,
    cliente_aprobado, registrar_solicitud, get_solicitud
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Token del bot de clientes (configurar en .env)
TOKEN_CLIENTES = os.getenv("TOKEN_BOT_CLIENTES")

# IDs de Telegram de los vendedores (configurar en .env)
TELEGRAM_NICO = int(os.getenv("TELEGRAM_ID_NICO", "0"))
TELEGRAM_ALEX = int(os.getenv("TELEGRAM_ID_ALEX", "0"))
TELEGRAM_EDU  = int(os.getenv("TELEGRAM_ID_EDU",  "0"))

VENDEDORES_IDS = {
    "nico": TELEGRAM_NICO,
    "alex": TELEGRAM_ALEX,
    "edu":  TELEGRAM_EDU,
}

TELEFONOS = {
    "nico": os.getenv("TELEFONO_NICO", ""),
    "alex": os.getenv("TELEFONO_ALEX", ""),
    "edu":  os.getenv("TELEFONO_EDU",  ""),
}

USERNAMES_TELEGRAM = {
    "nico": os.getenv("TELEGRAM_USERNAME_NICO", ""),
    "alex": os.getenv("TELEGRAM_USERNAME_ALEX", ""),
    "edu":  os.getenv("TELEGRAM_USERNAME_EDU",  ""),
}

# Bot de gestión usado para notificar a vendedores
TOKEN_GESTION = os.getenv("TOKEN_BOT_GESTION")
bot_gestion = Bot(token=TOKEN_GESTION)

# Estados de conversación
(
    MENU_PRINCIPAL,
    ELEGIR_TIPO,
    ELEGIR_SABOR,
    ELEGIR_CANTIDAD,
    ELEGIR_SABORES_MAYOR,
    ELEGIR_VENDEDOR,
    ELEGIR_PAGO,
    ELEGIR_FECHA,
    ELEGIR_HORA,
    CONFIRMAR_PEDIDO,
    CARRITO,
    ELEGIR_CANTIDAD_CARRITO,
    PEDIR_TELEFONO,
) = range(13)


# ─── FOTOS POR SABOR (URLs de imágenes reales del VAP SOLO 15K) ───────────────
FOTOS_SABORES = {
    "Raspberry Watermelon":            "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Strawberry Kiwi":                 "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Lemon Lime":                      "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Redbull":                         "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Love 66":                         "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Strawberry Vanilla Cola":         "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Peach Mango Pineapple":           "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Black Berry Blueberry Ice":       "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Triple Cherry":                   "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Pink Lemonade":                   "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Strawberry Banana":               "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Blueberry Ice":                   "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Kiwi Passionfruit":               "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Blueberry Cherry Cranberry":      "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Blueberry Blackcurrant Ice":      "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Strawberry Watermelon":           "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Black Ice Dragonfruit Strawberry":"https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Peach Berry":                     "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Grape Burst":                     "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
    "Double Apple":                    "https://m.media-amazon.com/images/I/61Z5S6xkJpL.jpg",
}

EMOJIS_SABORES = {
    "Raspberry Watermelon":            "🍓🍉",
    "Strawberry Kiwi":                 "🍓🥝",
    "Lemon Lime":                      "🍋🟢",
    "Redbull":                         "🐂⚡",
    "Love 66":                         "❤️",
    "Strawberry Vanilla Cola":         "🍓🥤",
    "Peach Mango Pineapple":           "🍑🥭🍍",
    "Black Berry Blueberry Ice":       "🫐❄️",
    "Triple Cherry":                   "🍒🍒🍒",
    "Pink Lemonade":                   "🌸🍋",
    "Strawberry Banana":               "🍓🍌",
    "Blueberry Ice":                   "🫐❄️",
    "Kiwi Passionfruit":               "🥝💛",
    "Blueberry Cherry Cranberry":      "🫐🍒",
    "Blueberry Blackcurrant Ice":      "🫐🖤❄️",
    "Strawberry Watermelon":           "🍓🍉",
    "Black Ice Dragonfruit Strawberry":"🐉🍓❄️",
    "Peach Berry":                     "🍑🍓",
    "Grape Burst":                     "🍇💥",
    "Double Apple":                    "🍎🍎",
}


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def teclado_sabores(volver_carrito: bool = False):
    sabores_disponibles = [(s, get_stock_total(s)) for s in SABORES]
    keyboard = []
    for sabor, stock in sabores_disponibles:
        emoji = EMOJIS_SABORES.get(sabor, "🌿")
        disponible = "✅" if stock > 0 else "❌"
        btn = InlineKeyboardButton(
            f"{disponible} {emoji} {sabor}",
            callback_data=f"sabor_{sabor}" if stock > 0 else "sin_stock"
        )
        keyboard.append([btn])
    if volver_carrito:
        keyboard.append([InlineKeyboardButton("🔙 Volver al carrito", callback_data="volver_carrito")])
    else:
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")])
    return InlineKeyboardMarkup(keyboard)


def teclado_vendedores():
    keyboard = [
        [InlineKeyboardButton("👤 Nico", callback_data="vendedor_nico")],
        [InlineKeyboardButton("👤 Alex", callback_data="vendedor_alex")],
        [InlineKeyboardButton("👤 Edu",  callback_data="vendedor_edu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def proximas_fechas():
    """Genera los próximos 7 días como botones"""
    keyboard = []
    hoy = datetime.now()
    dias_es = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    for i in range(1, 8):
        dia = hoy + timedelta(days=i)
        nombre = dias_es[dia.weekday()]
        label = f"{nombre} {dia.strftime('%d/%m')}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"fecha_{dia.strftime('%Y-%m-%d')}")])
    return InlineKeyboardMarkup(keyboard)


def teclado_horas():
    horas = ["10:00", "11:00", "12:00", "13:00", "16:00",
             "17:00", "18:00", "19:00", "20:00", "21:00"]
    keyboard = []
    row = []
    for i, hora in enumerate(horas):
        row.append(InlineKeyboardButton(hora, callback_data=f"hora_{hora}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)


def texto_carrito(carrito: list) -> str:
    if not carrito:
        return "🛒 Tu carrito está vacío."
    total_uds = sum(item["cantidad"] for item in carrito)
    precio = calcular_precio(total_uds)
    lineas = "\n".join(
        f"  {EMOJIS_SABORES.get(item['sabor'], '🌿')} {item['sabor']} × {item['cantidad']}"
        for item in carrito
    )
    return (
        f"🛒 *Carrito ({total_uds} unidades):*\n\n"
        f"{lineas}\n\n"
        f"💰 Total: *{precio}€*"
    )


def resumen_pedido(data: dict) -> str:
    tipo = data.get("tipo")
    carrito = data.get("carrito", [])
    cantidad = data.get("cantidad", 0)
    vendedor = data.get("vendedor", "").capitalize()
    precio = data.get("precio", 0)
    pago = data.get("pago", "")
    fecha = data.get("fecha", "")
    hora = data.get("hora", "")

    if tipo == "mayorista":
        return (
            f"📦 *Resumen de tu pedido*\n\n"
            f"🏷️ Tipo: Caja mayorista (10 unidades mezcladas)\n"
            f"👤 Vendedor: {vendedor}\n"
            f"💰 Precio total: *{precio}€*\n"
            f"💳 Pago: {pago.capitalize()}\n"
            f"📅 Fecha: {fecha}\n"
            f"⏰ Hora: {hora}"
        )
    else:
        lineas = "\n".join(
            f"  {EMOJIS_SABORES.get(item['sabor'], '🌿')} {item['sabor']} × {item['cantidad']}"
            for item in carrito
        )
        return (
            f"📦 *Resumen de tu pedido*\n\n"
            f"🛒 *{cantidad} unidades:*\n{lineas}\n\n"
            f"👤 Vendedor: {vendedor}\n"
            f"💰 Precio total: *{precio}€*\n"
            f"💳 Pago: {pago.capitalize()}\n"
            f"📅 Fecha: {fecha}\n"
            f"⏰ Hora: {hora}"
        )


# ─── HANDLERS ─────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data.clear()

    if not cliente_aprobado(user.id):
        solicitud_existente = get_solicitud(user.id)
        if solicitud_existente:
            await update.message.reply_text(
                "⏳ Tu solicitud ya está en revisión. Te avisaremos cuando un vendedor te apruebe."
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                "👋 ¡Hola! Para acceder al bot necesitas ser aprobado por un vendedor.\n\n"
                "📱 *Escribe tu número de teléfono móvil* para enviar la solicitud:",
                parse_mode="Markdown"
            )
            return PEDIR_TELEFONO

    keyboard = [
        [InlineKeyboardButton("🛒 Hacer un pedido", callback_data="pedir")],
        [InlineKeyboardButton("📦 Ver catálogo y stock", callback_data="catalogo")],
        [InlineKeyboardButton("💼 Compra al por mayor", callback_data="mayorista")],
    ]
    await update.message.reply_text(
        "👋 ¡Bienvenido a *VAP SOLO SESEÑA*! 💨\n\n"
        "Somos distribuidores del *VAP SOLO 15K*.\n"
        "¿Qué quieres hacer?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return MENU_PRINCIPAL


async def pedir_telefono(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telefono = update.message.text.strip()

    digitos = ''.join(c for c in telefono if c.isdigit())
    if len(digitos) < 9:
        await update.message.reply_text(
            "❌ Número no válido. Por favor escribe tu número de móvil (mínimo 9 dígitos):"
        )
        return PEDIR_TELEFONO

    registrar_solicitud(user.id, user.full_name, user.username or "", telefono)
    await update.message.reply_text(
        "⏳ Tu solicitud ha sido enviada. Te avisaremos en cuanto un vendedor te apruebe."
    )

    nombre_display = user.full_name + (f" (@{user.username})" if user.username else "")
    mensaje = (
        f"🔔 *Nueva solicitud de acceso*\n\n"
        f"👤 *{nombre_display}*\n"
        f"📱 Teléfono: *{telefono}*\n"
        f"🆔 ID Telegram: `{user.id}`\n\n"
        f"¿Apruebas o rechazas el acceso?"
    )
    teclado_aprobacion = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Aprobar", callback_data=f"aprc_{user.id}"),
        InlineKeyboardButton("❌ Rechazar", callback_data=f"rchz_{user.id}"),
    ]])
    for nombre_v, tid_v in VENDEDORES_IDS.items():
        if tid_v:
            try:
                await bot_gestion.send_message(
                    chat_id=tid_v,
                    text=mensaje,
                    parse_mode="Markdown",
                    reply_markup=teclado_aprobacion
                )
            except Exception as e:
                logger.error(f"Error notificando a {nombre_v}: {e}")

    return ConversationHandler.END


async def menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "pedir":
        await query.edit_message_text(
            "🛒 *¿Qué tipo de compra quieres hacer?*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("1️⃣ Unidades sueltas (1-9 unid.)", callback_data="tipo_normal")],
                [InlineKeyboardButton("📦 Caja mayorista (10 unid. = 80€)", callback_data="tipo_mayorista")],
                [InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")],
            ]),
            parse_mode="Markdown"
        )
        return ELEGIR_TIPO

    elif query.data == "catalogo":
        stock_texto = "📋 *Catálogo VAP SOLO 15K*\n\n"
        for sabor in SABORES:
            stock = get_stock_total(sabor)
            emoji = EMOJIS_SABORES.get(sabor, "🌿")
            estado = "✅ Disponible" if stock > 0 else "❌ Agotado"
            stock_texto += f"{emoji} *{sabor}*\n   {estado} ({stock} uds)\n\n"
        stock_texto += "\n💰 *Precios:*\n1u = 12€ | 2u = 20€ | 3u = 32€ | 4u = 40€\n📦 Caja 10u mezcladas = 80€"
        await query.edit_message_text(
            stock_texto,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Hacer pedido", callback_data="pedir")],
                [InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")],
            ])
        )
        return MENU_PRINCIPAL

    elif query.data == "mayorista":
        context.user_data["tipo"] = "mayorista"
        context.user_data["sabores"] = ["Caja mezclada"]
        context.user_data["cantidad"] = 10
        context.user_data["precio"] = 80
        await query.edit_message_text(
            "📦 *Caja mayorista - 10 unidades mezcladas = 80€*\n\n"
            "Los sabores los elige el vendedor según stock disponible.\n\n"
            "👤 *¿Con qué vendedor quieres tratar?*",
            reply_markup=teclado_vendedores(),
            parse_mode="Markdown"
        )
        return ELEGIR_VENDEDOR

    elif query.data == "volver_menu":
        keyboard = [
            [InlineKeyboardButton("🛒 Hacer un pedido", callback_data="pedir")],
            [InlineKeyboardButton("📦 Ver catálogo y stock", callback_data="catalogo")],
            [InlineKeyboardButton("💼 Compra al por mayor", callback_data="mayorista")],
        ]
        await query.edit_message_text(
            "👋 ¡Bienvenido a *VAP SOLO SESEÑA*! 💨\n\n¿Qué quieres hacer?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return MENU_PRINCIPAL


async def elegir_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "tipo_normal":
        context.user_data["tipo"] = "normal"
        context.user_data["carrito"] = []
        await query.edit_message_text(
            "🛒 *Carrito vacío — elige el primer sabor:*",
            reply_markup=teclado_sabores(),
            parse_mode="Markdown"
        )
        return ELEGIR_SABOR

    elif query.data == "tipo_mayorista":
        context.user_data["tipo"] = "mayorista"
        context.user_data["sabores"] = ["Caja mezclada"]
        context.user_data["cantidad"] = 10
        context.user_data["precio"] = 80
        await query.edit_message_text(
            "📦 *Caja mayorista - 10 unidades mezcladas = 80€*\n\n"
            "Los sabores los elige el vendedor según stock disponible.\n\n"
            "👤 *¿Con qué vendedor quieres tratar?*",
            reply_markup=teclado_vendedores(),
            parse_mode="Markdown"
        )
        return ELEGIR_VENDEDOR

    elif query.data == "volver_menu":
        return await menu_principal(update, context)


async def elegir_sabor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "sin_stock":
        await query.answer("❌ Este sabor está agotado", show_alert=True)
        return ELEGIR_SABOR

    if query.data == "volver_menu":
        return await menu_principal(update, context)

    if query.data == "volver_carrito":
        carrito = context.user_data.get("carrito", [])
        await _mostrar_carrito(query, carrito)
        return CARRITO

    sabor = query.data.replace("sabor_", "")
    context.user_data["sabor_actual"] = sabor
    stock = get_stock_total(sabor)
    emoji = EMOJIS_SABORES.get(sabor, "🌿")

    max_uds = min(stock, 9)
    keyboard = [[InlineKeyboardButton(str(i), callback_data=f"cantcarrito_{i}")]
                for i in range(1, max_uds + 1)]
    keyboard.append([InlineKeyboardButton("🔙 Cambiar sabor", callback_data="cambiar_sabor_carrito")])

    await query.edit_message_text(
        f"{emoji} *{sabor}*\n📦 Stock: {stock} uds\n\n"
        f"¿Cuántas unidades quieres añadir al carrito?\n\n"
        f"💰 1u=12€ | 2u=20€ | 3u=32€ | 4u=40€",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ELEGIR_CANTIDAD_CARRITO


async def elegir_cantidad_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cambiar_sabor_carrito":
        carrito = context.user_data.get("carrito", [])
        markup = teclado_sabores(volver_carrito=bool(carrito))
        await query.edit_message_text(
            "🌿 *Elige el sabor:*",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return ELEGIR_SABOR

    cantidad = int(query.data.replace("cantcarrito_", ""))
    sabor = context.user_data.get("sabor_actual")
    carrito = context.user_data.get("carrito", [])

    for item in carrito:
        if item["sabor"] == sabor:
            item["cantidad"] += cantidad
            break
    else:
        carrito.append({"sabor": sabor, "cantidad": cantidad})

    context.user_data["carrito"] = carrito
    await _mostrar_carrito(query, carrito)
    return CARRITO


async def _mostrar_carrito(query, carrito: list):
    keyboard = [
        [InlineKeyboardButton("➕ Añadir otro sabor", callback_data="carrito_añadir")],
        [InlineKeyboardButton("🗑️ Quitar último", callback_data="carrito_quitar")],
        [InlineKeyboardButton("✅ Confirmar y continuar", callback_data="carrito_confirmar")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="volver_menu")],
    ]
    await query.edit_message_text(
        texto_carrito(carrito),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def ver_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    carrito = context.user_data.get("carrito", [])

    if query.data == "carrito_añadir":
        markup = teclado_sabores(volver_carrito=True)
        await query.edit_message_text(
            "🌿 *Elige el sabor que quieres añadir:*",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return ELEGIR_SABOR

    elif query.data == "carrito_quitar":
        if carrito:
            eliminado = carrito.pop()
            context.user_data["carrito"] = carrito
            await query.answer(f"Eliminado: {eliminado['sabor']}", show_alert=False)
        if not carrito:
            markup = teclado_sabores(volver_carrito=False)
            await query.edit_message_text(
                "🛒 Carrito vacío. Elige el primer sabor:",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            return ELEGIR_SABOR
        await _mostrar_carrito(query, carrito)
        return CARRITO

    elif query.data == "carrito_confirmar":
        if not carrito:
            await query.answer("El carrito está vacío", show_alert=True)
            return CARRITO
        total_uds = sum(item["cantidad"] for item in carrito)
        precio = calcular_precio(total_uds)
        context.user_data["cantidad"] = total_uds
        context.user_data["precio"] = precio
        context.user_data["tipo"] = "normal"
        sabores_expandidos = []
        for item in carrito:
            sabores_expandidos.extend([item["sabor"]] * item["cantidad"])
        context.user_data["sabores"] = sabores_expandidos

        await query.edit_message_text(
            f"{texto_carrito(carrito)}\n\n👤 *¿Con qué vendedor quieres tratar?*",
            reply_markup=teclado_vendedores(),
            parse_mode="Markdown"
        )
        return ELEGIR_VENDEDOR

    elif query.data == "volver_menu":
        return await menu_principal(update, context)

    return CARRITO


async def elegir_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return CARRITO


async def elegir_sabores_mayorista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "sin_stock":
        await query.answer("❌ Este sabor está agotado", show_alert=True)
        return ELEGIR_SABORES_MAYOR

    if query.data == "confirmar_mayor":
        sabores = context.user_data.get("sabores", [])
        if len(sabores) < 10:
            await query.answer(f"Aún te faltan {10 - len(sabores)} sabores", show_alert=True)
            return ELEGIR_SABORES_MAYOR
        context.user_data["cantidad"] = 10
        context.user_data["precio"] = 80
        await query.edit_message_text(
            f"✅ *10 sabores seleccionados:*\n"
            + "\n".join(f"  {EMOJIS_SABORES.get(s,'🌿')} {s}" for s in sabores)
            + f"\n\n💰 Precio: *80€*\n\n"
            f"👤 *¿Con qué vendedor quieres tratar?*",
            reply_markup=teclado_vendedores(),
            parse_mode="Markdown"
        )
        return ELEGIR_VENDEDOR

    sabor = query.data.replace("sabor_", "")
    sabores = context.user_data.get("sabores", [])
    sabores.append(sabor)
    context.user_data["sabores"] = sabores
    restantes = 10 - len(sabores)

    if restantes == 0:
        keyboard = [[InlineKeyboardButton("✅ Confirmar caja", callback_data="confirmar_mayor")]]
    else:
        keyboard = list(teclado_sabores().inline_keyboard)
        keyboard.insert(0, [InlineKeyboardButton(
            f"✅ Confirmar ({len(sabores)}/10)", callback_data="confirmar_mayor"
        )])

    await query.edit_message_text(
        f"📦 *Caja mayorista ({len(sabores)}/10)*\n\n"
        + "\n".join(f"  {EMOJIS_SABORES.get(s,'🌿')} {s}" for s in sabores)
        + (f"\n\n➕ Elige {restantes} más:" if restantes > 0 else "\n\n✅ ¡Completa! Confirma la caja."),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ELEGIR_SABORES_MAYOR


async def elegir_vendedor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    vendedor = query.data.replace("vendedor_", "")
    context.user_data["vendedor"] = vendedor

    await query.edit_message_text(
        f"👤 Vendedor: *{vendedor.capitalize()}*\n\n"
        f"💳 *¿Cómo vas a pagar?*",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Bizum", callback_data="pago_bizum")],
            [InlineKeyboardButton("💵 Efectivo", callback_data="pago_efectivo")],
        ]),
        parse_mode="Markdown"
    )
    return ELEGIR_PAGO


async def elegir_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pago = query.data.replace("pago_", "")
    context.user_data["pago"] = pago

    await query.edit_message_text(
        f"💳 Pago: *{pago.capitalize()}*\n\n"
        f"📅 *¿Qué día lo quieres?*",
        reply_markup=proximas_fechas(),
        parse_mode="Markdown"
    )
    return ELEGIR_FECHA


async def elegir_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    fecha = query.data.replace("fecha_", "")
    context.user_data["fecha"] = fecha

    await query.edit_message_text(
        f"📅 Fecha: *{fecha}*\n\n"
        f"⏰ *¿A qué hora?*",
        reply_markup=teclado_horas(),
        parse_mode="Markdown"
    )
    return ELEGIR_HORA


async def elegir_hora(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    hora = query.data.replace("hora_", "")
    context.user_data["hora"] = hora

    resumen = resumen_pedido(context.user_data)
    await query.edit_message_text(
        resumen + "\n\n¿Confirmas el pedido?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirmar pedido", callback_data="confirmar_si")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="confirmar_no")],
        ]),
        parse_mode="Markdown"
    )
    return CONFIRMAR_PEDIDO


async def confirmar_pedido_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirmar_no":
        await query.edit_message_text("❌ Pedido cancelado. Escribe vapers para volver.")
        return ConversationHandler.END

    # Guardar pedido en BD
    user = query.from_user
    data = context.user_data
    pedido_id = crear_pedido(
        cliente_id=user.id,
        cliente_nombre=user.full_name,
        cliente_username=user.username or "",
        vendedor=data["vendedor"],
        sabores_lista=data["sabores"],
        cantidad=data["cantidad"],
        tipo=data["tipo"],
        precio=data["precio"],
        pago=data["pago"],
        fecha=data["fecha"],
        hora=data["hora"],
    )

    vendedor_elegido = data["vendedor"]
    telefono = TELEFONOS.get(vendedor_elegido, "")
    username = USERNAMES_TELEGRAM.get(vendedor_elegido, "")
    contacto = f"\n📞 Teléfono: *{telefono}*" if telefono else ""

    botones_contacto = []
    if username:
        botones_contacto.append(
            InlineKeyboardButton(f"💬 Hablar con {vendedor_elegido.capitalize()}", url=f"https://t.me/{username}")
        )

    keyboard_confirmacion = [botones_contacto] if botones_contacto else []

    await query.edit_message_text(
        f"⏳ *Pedido #{pedido_id} enviado — pendiente de confirmación*\n\n"
        f"{resumen_pedido(data)}\n\n"
        f"👤 Vendedor: *{vendedor_elegido.capitalize()}*{contacto}\n\n"
        f"Te avisaremos en cuanto el vendedor confirme tu pedido. 🔔",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard_confirmacion) if keyboard_confirmacion else None
    )

    # Notificar a TODOS los vendedores pidiendo confirmación
    mensaje_vendedores = (
        f"⚠️ *PEDIDO #{pedido_id} — NECESITA CONFIRMACIÓN*\n\n"
        f"{resumen_pedido(data)}\n\n"
        f"👤 Cliente: {user.full_name}"
        + (f" (@{user.username})" if user.username else "")
        + f"\n📞 ID Telegram cliente: `{user.id}`\n\n"
        f"_(Vendedor elegido: {vendedor_elegido.capitalize()})_\n\n"
        f"👉 Confirma o rechaza el pedido en el bot de gestión."
    )

    for nombre, telegram_id in VENDEDORES_IDS.items():
        if telegram_id:
            try:
                await bot_gestion.send_message(
                    chat_id=telegram_id,
                    text=mensaje_vendedores,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error notificando a {nombre}: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada. Escribe vapers para empezar de nuevo.")
    context.user_data.clear()
    return ConversationHandler.END


def main():
    init_db()
    app = Application.builder().token(TOKEN_CLIENTES).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'(?i)^vapers$'), start)],
        states={
            MENU_PRINCIPAL:          [CallbackQueryHandler(menu_principal)],
            ELEGIR_TIPO:             [CallbackQueryHandler(elegir_tipo)],
            ELEGIR_SABOR:            [CallbackQueryHandler(elegir_sabor)],
            ELEGIR_CANTIDAD:         [CallbackQueryHandler(elegir_cantidad)],
            ELEGIR_CANTIDAD_CARRITO: [CallbackQueryHandler(elegir_cantidad_carrito)],
            CARRITO:                 [CallbackQueryHandler(ver_carrito)],
            ELEGIR_SABORES_MAYOR:    [CallbackQueryHandler(elegir_sabores_mayorista)],
            ELEGIR_VENDEDOR:         [CallbackQueryHandler(elegir_vendedor)],
            ELEGIR_PAGO:             [CallbackQueryHandler(elegir_pago)],
            ELEGIR_FECHA:            [CallbackQueryHandler(elegir_fecha)],
            ELEGIR_HORA:             [CallbackQueryHandler(elegir_hora)],
            CONFIRMAR_PEDIDO:        [CallbackQueryHandler(confirmar_pedido_handler)],
            PEDIR_TELEFONO:          [MessageHandler(filters.TEXT & ~filters.COMMAND, pedir_telefono)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    print("🤖 Bot de clientes arrancado...")
    app.run_polling()


if __name__ == "__main__":
    main()
