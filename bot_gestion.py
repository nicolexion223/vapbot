"""
BOT DE GESTIÓN - VAP SOLO SESEÑA
Solo para Nico, Alex y Edu. Gestión de stock, ventas y pedidos.
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from database import (
    SABORES, VENDEDORES, calcular_precio,
    get_stock_total, get_stock_vendedor, get_todo_stock,
    descontar_stock, registrar_venta_manual, get_pedidos_pendientes,
    confirmar_pedido, get_pedido, confirmar_pedido_mayorista,
    ventas_hoy, ventas_periodo, stats_por_vendedor,
    get_config, set_config, init_db,
    aprobar_cliente, bloquear_cliente, get_clientes_aprobados,
    get_solicitud, eliminar_solicitud,
    registrar_venta_mayorista_manual,
    rechazar_pedido, añadir_stock
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN_GESTION   = os.getenv("TOKEN_BOT_GESTION")
TOKEN_CLIENTES  = os.getenv("TOKEN_BOT_CLIENTES")
bot_clientes    = Bot(token=TOKEN_CLIENTES)

TELEGRAM_NICO = int(os.getenv("TELEGRAM_ID_NICO", "0"))
TELEGRAM_ALEX = int(os.getenv("TELEGRAM_ID_ALEX", "0"))
TELEGRAM_EDU  = int(os.getenv("TELEGRAM_ID_EDU",  "0"))

VENDEDORES_PERMITIDOS = {
    TELEGRAM_NICO: "nico",
    TELEGRAM_ALEX: "alex",
    TELEGRAM_EDU:  "edu",
}

# Estados
(
    MENU_GESTION,
    VENTA_SABOR,
    VENTA_CANTIDAD,
    STOCK_MENU,
    PEDIDOS_MENU,
    STATS_MENU,
    MAYORISTA_SABORES,
    CONFIRMAR_UBICACION,
    VENTA_MAYOR_MANUAL,
    STOCK_AÑADIR_SABOR,
    STOCK_AÑADIR_CANT,
) = range(11)


def get_vendedor(update: Update) -> str | None:
    uid = update.effective_user.id
    return VENDEDORES_PERMITIDOS.get(uid)


def solo_vendedores(func):
    """Decorador que bloquea acceso a no vendedores"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not get_vendedor(update):
            await update.effective_message.reply_text("⛔ No tienes acceso a este bot.")
            return ConversationHandler.END
        return await func(update, context)
    return wrapper


# ─── MENÚ PRINCIPAL ───────────────────────────────────────────────────────────

def _teclado_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Registrar venta",           callback_data="registrar_venta")],
        [InlineKeyboardButton("📦 Venta mayorista (caja)",    callback_data="venta_mayorista")],
        [InlineKeyboardButton("📥 Añadir stock",               callback_data="añadir_stock")],
        [InlineKeyboardButton("📦 Ver mi stock",              callback_data="mi_stock")],
        [InlineKeyboardButton("📊 Stock total",               callback_data="stock_total")],
        [InlineKeyboardButton("📋 Pedidos pendientes",        callback_data="pedidos")],
        [InlineKeyboardButton("📈 Ventas de hoy",             callback_data="ventas_hoy")],
        [InlineKeyboardButton("📊 Estadísticas",              callback_data="stats")],
    ])


@solo_vendedores
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vendedor = get_vendedor(update)
    await update.message.reply_text(
        f"👋 Hola *{vendedor.capitalize()}*! ¿Qué quieres hacer?",
        reply_markup=_teclado_menu(),
        parse_mode="Markdown"
    )
    return MENU_GESTION


# ─── REGISTRAR VENTA ──────────────────────────────────────────────────────────

async def menu_gestion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    vendedor = get_vendedor(update)

    if query.data == "añadir_stock":
        keyboard = [[InlineKeyboardButton(s, callback_data=f"astk_sabor_{s}")] for s in SABORES]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")])
        await query.edit_message_text(
            "📥 *¿De qué sabor quieres añadir stock?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return STOCK_AÑADIR_SABOR

    elif query.data == "venta_mayorista":
        context.user_data["mvm_sabores"] = []
        return await _mostrar_selector_mayorista_manual(query, vendedor, [])

    elif query.data == "registrar_venta":
        context.user_data["carrito"] = []
        keyboard = []
        for sabor in SABORES:
            stock = get_stock_vendedor(sabor, vendedor)
            if stock > 0:
                keyboard.append([InlineKeyboardButton(
                    f"✅ {sabor} ({stock} uds)",
                    callback_data=f"venta_sabor_{sabor}"
                )])
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")])
        await query.edit_message_text(
            "💰 *¿Qué sabor has vendido?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return VENTA_SABOR

    elif query.data == "mi_stock":
        texto = f"📦 *Tu stock, {vendedor.capitalize()}:*\n\n"
        total = 0
        for sabor in SABORES:
            stock = get_stock_vendedor(sabor, vendedor)
            if stock > 0:
                texto += f"• {sabor}: *{stock} uds*\n"
                total += stock
        texto += f"\n📊 *Total: {total} unidades*"
        await query.edit_message_text(
            texto,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")
            ]])
        )
        return MENU_GESTION

    elif query.data == "stock_total":
        rows = get_todo_stock()
        total_global = sum(t for _, _, _, _, t in rows)
        texto = "📊 *Stock total VAP SOLO SESEÑA:*\n\n"
        for sabor, sn, sa, se, total in rows:
            if total == 0:
                continue
            pn = round(sn / total * 100) if total else 0
            pa = round(sa / total * 100) if total else 0
            pe = round(se / total * 100) if total else 0
            texto += f"*{sabor}* — {total} uds\n"
            texto += f"  Nico: {sn} ({pn}%) | Alex: {sa} ({pa}%) | Edu: {se} ({pe}%)\n\n"
        texto += f"📦 *Total global: {total_global} uds*"
        await query.edit_message_text(
            texto,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")
            ]])
        )
        return MENU_GESTION

    elif query.data == "pedidos":
        pedidos = get_pedidos_pendientes()
        if not pedidos:
            await query.edit_message_text(
                "📋 No hay pedidos pendientes.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")
                ]])
            )
            return MENU_GESTION

        texto = "📋 *Pedidos pendientes:*\n\n"
        keyboard = []
        for p in pedidos:
            pid, cliente, vend, sabores_json, cant, tipo, precio, pago, fecha, hora, estado = p
            import json
            sabores = json.loads(sabores_json)
            texto += (
                f"*#{pid}* - {cliente}\n"
                f"  🌿 {', '.join(sabores)}\n"
                f"  🔢 {cant} uds | 💰 {precio}€ | 💳 {pago}\n"
                f"  👤 Vendedor: {vend} | 📅 {fecha} {hora}\n\n"
            )
            keyboard.append([
                InlineKeyboardButton(f"✅ Confirmar #{pid}", callback_data=f"confirmar_{pid}"),
            ])
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")])
        await query.edit_message_text(
            texto,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PEDIDOS_MENU

    elif query.data == "ventas_hoy":
        vendedor = get_vendedor(update)
        ventas = ventas_hoy(vendedor)
        if not ventas:
            texto = f"📈 *Tus ventas hoy, {vendedor.capitalize()}:*\n\nNinguna venta registrada aún."
        else:
            texto = f"📈 *Tus ventas hoy, {vendedor.capitalize()}:*\n\n"
            total_uds = 0
            total_euros = 0
            for sabor, cant, precio in ventas:
                texto += f"• {sabor}: {cant} uds → {precio}€\n"
                total_uds += cant or 0
                total_euros += precio or 0
            texto += f"\n📊 Total: *{total_uds} uds* | *{total_euros}€*"
        await query.edit_message_text(
            texto,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")
            ]])
        )
        return MENU_GESTION

    elif query.data == "stats":
        keyboard = [
            [InlineKeyboardButton("📅 Hoy", callback_data="stats_hoy")],
            [InlineKeyboardButton("📆 Esta semana", callback_data="stats_semana")],
            [InlineKeyboardButton("🗓️ Este mes", callback_data="stats_mes")],
            [InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")],
        ]
        await query.edit_message_text(
            "📊 *Estadísticas — ¿Qué período?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return STATS_MENU

    elif query.data == "volver_menu":
        vendedor = get_vendedor(update)
        await query.edit_message_text(
            f"👋 Hola *{vendedor.capitalize()}*! ¿Qué quieres hacer?",
            reply_markup=_teclado_menu(),
            parse_mode="Markdown"
        )
        return MENU_GESTION


# ─── VENTA: ELEGIR SABOR ──────────────────────────────────────────────────────

async def venta_sabor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "volver_menu":
        return await menu_gestion(update, context)

    sabor = query.data.replace("venta_sabor_", "")
    context.user_data["venta_sabor"] = sabor
    vendedor = get_vendedor(update)
    stock = get_stock_vendedor(sabor, vendedor)

    max_uds = min(stock, 9)
    keyboard = [[InlineKeyboardButton(str(i), callback_data=f"venta_cant_{i}")]
                for i in range(1, max_uds + 1)]
    keyboard.append([InlineKeyboardButton("🔙 Cambiar sabor", callback_data="cambiar_sabor_venta")])

    await query.edit_message_text(
        f"💰 *{sabor}*\n📦 Tu stock: {stock} uds\n\n¿Cuántas unidades has vendido?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return VENTA_CANTIDAD


async def venta_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    vendedor = get_vendedor(update)

    if query.data == "cambiar_sabor_venta" or query.data == "anadir_otro":
        keyboard = []
        for sabor in SABORES:
            stock = get_stock_vendedor(sabor, vendedor)
            if stock > 0:
                keyboard.append([InlineKeyboardButton(
                    f"✅ {sabor} ({stock} uds)",
                    callback_data=f"venta_sabor_{sabor}"
                )])
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")])
        await query.edit_message_text(
            "💰 *¿Qué sabor quieres añadir?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return VENTA_SABOR

    if query.data == "confirmar_venta":
        carrito = context.user_data.get("carrito", [])
        if not carrito:
            await query.answer("El carrito está vacío", show_alert=True)
            return VENTA_CANTIDAD

        total_uds = sum(cant for _, cant in carrito)
        precio_total = calcular_precio(total_uds)

        try:
            ok, resultado = registrar_venta_manual(vendedor, carrito)
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error al registrar la venta:\n`{e}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")
                ]])
            )
            return MENU_GESTION

        if not ok:
            await query.edit_message_text(
                f"❌ Stock insuficiente para *{resultado}*.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")
                ]])
            )
            return MENU_GESTION

        alertas = resultado
        context.user_data["carrito"] = []

        texto = "✅ *Venta registrada:*\n\n"
        for sabor, cant in carrito:
            texto += f"  • {sabor}: {cant} uds\n"
        texto += f"\n🔢 Total esta venta: {total_uds} uds → *{precio_total}€*"
        ventas_de_hoy = ventas_hoy(vendedor)
        euros_hoy = sum(r[2] or 0 for r in ventas_de_hoy)
        uds_hoy = sum(r[1] or 0 for r in ventas_de_hoy)
        texto += f"\n📊 Acumulado hoy: {uds_hoy} uds → *{euros_hoy}€*"
        if alertas:
            texto += "\n\n" + "\n".join(alertas)

        await query.edit_message_text(
            texto,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")
            ]])
        )
        return MENU_GESTION

    if query.data == "volver_menu":
        context.user_data["carrito"] = []
        return await menu_gestion(update, context)

    # Selección de cantidad
    cantidad = int(query.data.replace("venta_cant_", ""))
    sabor = context.user_data["venta_sabor"]

    carrito = context.user_data.get("carrito", [])
    carrito.append((sabor, cantidad))
    context.user_data["carrito"] = carrito

    total_uds = sum(cant for _, cant in carrito)
    precio_total = calcular_precio(total_uds)

    resumen = "🛒 *Venta actual:*\n"
    for s, c in carrito:
        resumen += f"  • {s}: {c} uds\n"
    resumen += f"\n🔢 Total: {total_uds} uds → *{precio_total}€*"

    keyboard = [
        [InlineKeyboardButton("➕ Añadir otro sabor", callback_data="anadir_otro")],
        [InlineKeyboardButton(f"✅ Confirmar ({precio_total}€)", callback_data="confirmar_venta")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="volver_menu")],
    ]
    await query.edit_message_text(
        resumen,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return VENTA_CANTIDAD


# ─── CONFIRMAR PEDIDO ─────────────────────────────────────────────────────────

async def pedidos_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import json as _json
    query = update.callback_query
    await query.answer()
    vendedor = get_vendedor(update)

    if query.data.startswith("confirmar_"):
        pedido_id = int(query.data.replace("confirmar_", ""))
        pedido_info = get_pedido(pedido_id)
        if not pedido_info:
            await query.edit_message_text("❌ Pedido no encontrado.")
            return MENU_GESTION

        sabores = _json.loads(pedido_info["sabores"]) if isinstance(pedido_info["sabores"], str) else pedido_info["sabores"]
        resumen = (
            f"📋 *Pedido #{pedido_id}*\n\n"
            f"👤 Cliente: {pedido_info['cliente_nombre']}\n"
            f"🌿 {', '.join(sabores)}\n"
            f"🔢 {pedido_info['cantidad']} uds | 💰 {pedido_info['precio']}€ | 💳 {pedido_info['pago']}\n"
            f"📅 {pedido_info['fecha']} {pedido_info['hora']}\n\n"
            f"¿Qué quieres hacer con este pedido?"
        )
        await query.edit_message_text(
            resumen,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Confirmar", callback_data=f"conf_{pedido_id}"),
                    InlineKeyboardButton("❌ Rechazar",  callback_data=f"rech_{pedido_id}"),
                ],
                [InlineKeyboardButton("🔙 Volver",     callback_data="volver_menu")],
            ])
        )
        return PEDIDOS_MENU

    elif query.data.startswith("conf_"):
        pedido_id = int(query.data.replace("conf_", ""))
        pedido_info = get_pedido(pedido_id)

        if pedido_info and pedido_info["tipo"] == "mayorista":
            context.user_data["mayorista_pedido_id"] = pedido_id
            context.user_data["mayorista_sabores"] = []
            return await _mostrar_mayorista_selector(query, vendedor, [], pedido_id)

        context.user_data["pedido_ubicacion_id"]  = pedido_id
        context.user_data["pedido_ubicacion_tipo"] = "normal"
        await query.edit_message_text(
            f"📍 *Pedido #{pedido_id}*\n\nEscribe el punto de encuentro para este pedido:",
            parse_mode="Markdown"
        )
        return CONFIRMAR_UBICACION

    elif query.data.startswith("rech_"):
        pedido_id = int(query.data.replace("rech_", ""))
        pedido_info = get_pedido(pedido_id)
        rechazar_pedido(pedido_id)
        if pedido_info and pedido_info["cliente_id"]:
            try:
                await bot_clientes.send_message(
                    chat_id=pedido_info["cliente_id"],
                    text=(
                        f"❌ *Tu pedido #{pedido_id} ha sido rechazado.*\n\n"
                        f"Si tienes dudas, contacta directamente con el vendedor."
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error notificando al cliente: {e}")
        await query.edit_message_text(
            f"🚫 *Pedido #{pedido_id} rechazado.* El cliente ha sido notificado.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")
            ]])
        )
        return MENU_GESTION

    elif query.data == "volver_menu":
        return await menu_gestion(update, context)


async def stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    vendedor = get_vendedor(update)

    if query.data == "volver_menu":
        await query.edit_message_text(
            f"👋 Hola *{vendedor.capitalize()}*! ¿Qué quieres hacer?",
            reply_markup=_teclado_menu(),
            parse_mode="Markdown"
        )
        return MENU_GESTION

    periodo = query.data.replace("stats_", "")  # 'hoy', 'semana', 'mes'
    titulos = {'hoy': 'Hoy', 'semana': 'Esta semana', 'mes': 'Este mes'}
    titulo = titulos.get(periodo, periodo)

    mis_ventas = ventas_periodo(vendedor, periodo)
    top_sabores = ventas_periodo(None, periodo)[:5]
    por_vendedor = stats_por_vendedor(periodo)

    texto = f"📊 *Estadísticas — {titulo}*\n\n"

    texto += f"👤 *Mis ventas ({vendedor.capitalize()}):*\n"
    if mis_ventas:
        for sabor, cant, precio in mis_ventas:
            texto += f"  • {sabor}: {cant} uds → {precio}€\n"
        mis_uds = sum(r[1] or 0 for r in mis_ventas)
        mis_euros = sum(r[2] or 0 for r in mis_ventas)
        texto += f"  📦 *{mis_uds} uds | {mis_euros}€*\n\n"
    else:
        texto += "  Sin ventas en este período\n\n"

    if top_sabores:
        texto += "🏆 *Top sabores (tienda):*\n"
        for i, (sabor, cant, _) in enumerate(top_sabores, 1):
            texto += f"  {i}. {sabor} — {cant} uds\n"
        texto += "\n"

    if por_vendedor:
        texto += "💼 *Ingresos por vendedor:*\n"
        total_uds = total_euros = 0
        for vend, cant, precio in por_vendedor:
            texto += f"  • {vend.capitalize()}: {cant} uds → {precio}€\n"
            total_uds += cant or 0
            total_euros += precio or 0
        texto += f"  💰 *Total tienda: {total_uds} uds → {total_euros}€*"
    else:
        texto += "Sin ventas registradas en la tienda."

    keyboard = [
        [
            InlineKeyboardButton("📅 Hoy", callback_data="stats_hoy"),
            InlineKeyboardButton("📆 Semana", callback_data="stats_semana"),
            InlineKeyboardButton("🗓️ Mes", callback_data="stats_mes"),
        ],
        [InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")],
    ]
    await query.edit_message_text(
        texto,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATS_MENU


async def stock_añadir_sabor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "volver_menu":
        return await menu_gestion(update, context)

    sabor = query.data.replace("astk_sabor_", "")
    context.user_data["astk_sabor"] = sabor
    vendedor = get_vendedor(update)
    stock_actual = get_stock_vendedor(sabor, vendedor)

    keyboard = [
        [InlineKeyboardButton(str(c), callback_data=f"astk_cant_{c}") for c in range(1, 6)],
        [InlineKeyboardButton(str(c), callback_data=f"astk_cant_{c}") for c in range(6, 11)],
        [InlineKeyboardButton("🔙 Cambiar sabor", callback_data="astk_volver_sabores")],
    ]
    await query.edit_message_text(
        f"📥 *{sabor}*\n\nTu stock actual: *{stock_actual} uds*\n\n¿Cuántas unidades añades?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return STOCK_AÑADIR_CANT


async def stock_añadir_cant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    vendedor = get_vendedor(update)

    if query.data == "astk_volver_sabores":
        keyboard = [[InlineKeyboardButton(s, callback_data=f"astk_sabor_{s}")] for s in SABORES]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")])
        await query.edit_message_text(
            "📥 *¿De qué sabor quieres añadir stock?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return STOCK_AÑADIR_SABOR

    if query.data == "volver_menu":
        return await menu_gestion(update, context)

    cantidad = int(query.data.replace("astk_cant_", ""))
    sabor = context.user_data.get("astk_sabor")
    nuevo_stock = añadir_stock(sabor, vendedor, cantidad)

    await query.edit_message_text(
        f"✅ *Stock actualizado*\n\n"
        f"📦 {sabor}\n"
        f"➕ Añadidas: *{cantidad} uds*\n"
        f"📊 Tu nuevo stock: *{nuevo_stock} uds*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Añadir más stock", callback_data="añadir_stock")],
            [InlineKeyboardButton("🔙 Volver al menú",   callback_data="volver_menu")],
        ])
    )
    return MENU_GESTION


async def _mostrar_selector_mayorista_manual(query, vendedor: str, sabores: list):
    from collections import Counter
    restantes = 10 - len(sabores)
    keyboard = []

    if restantes > 0:
        for sabor in SABORES:
            stock = get_stock_vendedor(sabor, vendedor)
            if stock > 0:
                keyboard.append([InlineKeyboardButton(
                    f"✅ {sabor} ({stock} uds)",
                    callback_data=f"mvm_{sabor}"
                )])

    if sabores:
        keyboard.append([InlineKeyboardButton("🗑️ Quitar último", callback_data="mvm_quitar")])
    if len(sabores) == 10:
        keyboard.append([InlineKeyboardButton("✅ Confirmar caja (80€)", callback_data="mvm_confirmar")])
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="volver_menu")])

    counts = Counter(sabores)
    resumen = "\n".join(
        f"  • {s}" + (f" ×{c}" if c > 1 else "")
        for s, c in counts.items()
    ) if sabores else "  _(ninguno aún)_"

    texto = (
        f"📦 *Venta mayorista — elige los 10 sabores*\n\n"
        f"Seleccionados ({len(sabores)}/10):\n{resumen}\n\n"
    )
    texto += f"➕ Elige {restantes} más:" if restantes > 0 else "✅ ¡Completo! Confirma la caja."

    await query.edit_message_text(
        texto,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return VENTA_MAYOR_MANUAL


async def venta_mayorista_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from collections import Counter
    query = update.callback_query
    await query.answer()
    vendedor = get_vendedor(update)
    sabores = context.user_data.get("mvm_sabores", [])

    if query.data == "mvm_quitar":
        if sabores:
            sabores.pop()
            context.user_data["mvm_sabores"] = sabores
        return await _mostrar_selector_mayorista_manual(query, vendedor, sabores)

    if query.data == "mvm_confirmar":
        if len(sabores) != 10:
            await query.answer("Necesitas exactamente 10 sabores", show_alert=True)
            return VENTA_MAYOR_MANUAL

        try:
            ok, resultado = registrar_venta_mayorista_manual(vendedor, sabores)
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error al registrar: `{e}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")
                ]])
            )
            return MENU_GESTION

        if not ok:
            await query.edit_message_text(
                f"❌ Stock insuficiente para *{resultado}*.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")
                ]])
            )
            return MENU_GESTION

        alertas = resultado
        counts = Counter(sabores)
        resumen = "\n".join(
            f"  • {s}" + (f" ×{c}" if c > 1 else "")
            for s, c in counts.items()
        )
        texto = f"✅ *Caja mayorista registrada (80€):*\n\n{resumen}"
        ventas_de_hoy = ventas_hoy(vendedor)
        euros_hoy = sum(r[2] or 0 for r in ventas_de_hoy)
        uds_hoy = sum(r[1] or 0 for r in ventas_de_hoy)
        texto += f"\n\n📊 Acumulado hoy: {uds_hoy} uds → *{euros_hoy}€*"
        if alertas:
            texto += "\n\n" + "\n".join(alertas)

        context.user_data["mvm_sabores"] = []
        await query.edit_message_text(
            texto,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")
            ]])
        )
        return MENU_GESTION

    if query.data == "volver_menu":
        context.user_data["mvm_sabores"] = []
        return await menu_gestion(update, context)

    # Selección de sabor
    sabor = query.data.replace("mvm_", "")
    sabores.append(sabor)
    context.user_data["mvm_sabores"] = sabores
    return await _mostrar_selector_mayorista_manual(query, vendedor, sabores)


async def _mostrar_mayorista_selector(query, vendedor: str, sabores_elegidos: list, pedido_id: int):
    from collections import Counter
    restantes = 10 - len(sabores_elegidos)
    keyboard = []

    if restantes > 0:
        for sabor in SABORES:
            stock = get_stock_vendedor(sabor, vendedor)
            if stock > 0:
                keyboard.append([InlineKeyboardButton(
                    f"✅ {sabor} ({stock} uds)",
                    callback_data=f"mayor_sabor_{sabor}"
                )])

    if sabores_elegidos:
        keyboard.append([InlineKeyboardButton("🗑️ Quitar último", callback_data="mayor_quitar")])
    if len(sabores_elegidos) == 10:
        keyboard.append([InlineKeyboardButton("✅ Confirmar caja", callback_data="mayor_confirmar")])
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="volver_menu")])

    counts = Counter(sabores_elegidos)
    resumen = "\n".join(
        f"  • {s}" + (f" ×{c}" if c > 1 else "")
        for s, c in counts.items()
    ) if sabores_elegidos else "  _(ninguno aún)_"

    texto = (
        f"📦 *Elige los sabores para el pedido #{pedido_id}*\n\n"
        f"Seleccionados ({len(sabores_elegidos)}/10):\n{resumen}\n\n"
    )
    texto += f"➕ Elige {restantes} más:" if restantes > 0 else "✅ ¡Completo! Confirma la caja."

    await query.edit_message_text(
        texto,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MAYORISTA_SABORES


async def mayorista_sabores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from collections import Counter
    query = update.callback_query
    await query.answer()
    vendedor = get_vendedor(update)
    sabores_elegidos = context.user_data.get("mayorista_sabores", [])
    pedido_id = context.user_data.get("mayorista_pedido_id")

    if query.data == "mayor_quitar":
        if sabores_elegidos:
            sabores_elegidos.pop()
            context.user_data["mayorista_sabores"] = sabores_elegidos

    elif query.data == "mayor_confirmar":
        if len(sabores_elegidos) != 10:
            await query.answer("Necesitas exactamente 10 sabores", show_alert=True)
            return MAYORISTA_SABORES

        pedido_info = get_pedido(pedido_id)
        try:
            ok, resultado = confirmar_pedido_mayorista(pedido_id, vendedor, sabores_elegidos)
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error al confirmar: `{e}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")
                ]])
            )
            return MENU_GESTION

        if not ok:
            await query.edit_message_text(
                f"❌ Stock insuficiente para *{resultado}*. Elige otro sabor.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")
                ]])
            )
            return MENU_GESTION

        alertas = resultado
        context.user_data.pop("mayorista_pedido_id", None)
        context.user_data.pop("mayorista_sabores", None)

        # Notificar al cliente con los sabores elegidos
        if pedido_info and pedido_info["cliente_id"]:
            counts = Counter(sabores_elegidos)
            lista = "\n".join(
                f"  • {s}" + (f" ×{c}" if c > 1 else "")
                for s, c in counts.items()
            )
            try:
                await bot_clientes.send_message(
                    chat_id=pedido_info["cliente_id"],
                    text=(
                        f"✅ *¡Tu pedido #{pedido_id} ha sido confirmado!*\n\n"
                        f"📦 *Sabores de tu caja (10 unidades):*\n{lista}\n\n"
                        f"💰 Total: *80€*\n"
                        f"👤 Vendedor: *{pedido_info['vendedor'].capitalize()}*\n\n"
                        f"📍 *Punto de encuentro:*\n{get_config('ubicacion', 'A convenir con el vendedor')}\n\n"
                        f"¡Hasta pronto! 💨"
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error notificando al cliente: {e}")

        texto = f"✅ *Pedido mayorista #{pedido_id} confirmado.*\n\n📦 *Sabores elegidos:*\n"
        counts = Counter(sabores_elegidos)
        for s, c in counts.items():
            texto += f"  • {s}" + (f" ×{c}" if c > 1 else "") + "\n"
        if alertas:
            texto += "\n" + "\n".join(alertas)

        await query.edit_message_text(
            texto,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")
            ]])
        )
        return MENU_GESTION

    elif query.data == "volver_menu":
        context.user_data.pop("mayorista_pedido_id", None)
        context.user_data.pop("mayorista_sabores", None)
        return await menu_gestion(update, context)

    elif query.data.startswith("mayor_sabor_"):
        sabor = query.data.replace("mayor_sabor_", "")
        if len(sabores_elegidos) < 10:
            sabores_elegidos.append(sabor)
            context.user_data["mayorista_sabores"] = sabores_elegidos

    return await _mostrar_mayorista_selector(query, vendedor, sabores_elegidos, pedido_id)


async def editar_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nueva = update.message.text.strip()
    pedido_id = context.user_data.pop("pedido_ubicacion_id", None)

    if pedido_id:
        pedido_info = get_pedido(pedido_id)
        ok = confirmar_pedido(pedido_id)
        if ok and pedido_info and pedido_info["cliente_id"]:
            import json
            sabores = json.loads(pedido_info["sabores"]) if isinstance(pedido_info["sabores"], str) else pedido_info["sabores"]
            try:
                await bot_clientes.send_message(
                    chat_id=pedido_info["cliente_id"],
                    text=(
                        f"✅ *¡Tu pedido #{pedido_id} ha sido confirmado!*\n\n"
                        f"🌿 Sabor(es): {', '.join(sabores)}\n"
                        f"💰 Total: *{pedido_info['precio']}€*\n"
                        f"👤 Vendedor: *{pedido_info['vendedor'].capitalize()}*\n\n"
                        f"📍 *Punto de encuentro:*\n{nueva}\n\n"
                        f"¡Hasta pronto! 💨"
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error notificando al cliente: {e}")

    await update.message.reply_text(
        f"✅ *Pedido #{pedido_id} confirmado.*\n📍 Punto de encuentro:\n_{nueva}_\n\n"
        f"Escribe vapers para volver al menú.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelado. Escribe vapers para volver.")
    context.user_data.clear()
    return ConversationHandler.END


# ─── APROBACIÓN DE CLIENTES DESDE EL BOT ─────────────────────────────────────

async def callback_aprobacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    accion, telegram_id_str = query.data.split("_", 1)
    telegram_id = int(telegram_id_str)

    solicitud = get_solicitud(telegram_id)
    if not solicitud:
        await query.edit_message_text("ℹ️ Esta solicitud ya fue procesada.")
        return

    _, nombre, username, _ = solicitud
    vendedor = get_vendedor(update)

    if accion == "aprc":
        aprobar_cliente(telegram_id, nombre, username, vendedor)
        eliminar_solicitud(telegram_id)
        await query.edit_message_text(
            f"✅ *{nombre}* (ID: `{telegram_id}`) aprobado por {vendedor}.",
            parse_mode="Markdown"
        )
        try:
            await bot_clientes.send_message(
                chat_id=telegram_id,
                text="✅ ¡Tu acceso ha sido aprobado! Escribe *vapers* para empezar a comprar.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error notificando al cliente: {e}")

    elif accion == "rchz":
        eliminar_solicitud(telegram_id)
        await query.edit_message_text(
            f"🚫 Solicitud de *{nombre}* (ID: `{telegram_id}`) rechazada.",
            parse_mode="Markdown"
        )
        try:
            await bot_clientes.send_message(
                chat_id=telegram_id,
                text="❌ Tu solicitud de acceso ha sido rechazada."
            )
        except Exception as e:
            logger.error(f"Error notificando al cliente: {e}")


# ─── GESTIÓN DE LISTA BLANCA ──────────────────────────────────────────────────

@solo_vendedores
async def cmd_aprobar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Uso: /aprobar <telegram_id> <nombre>"""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Uso: /aprobar <telegram_id> <nombre>\nEjemplo: /aprobar 123456789 Juan"
        )
        return
    try:
        telegram_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ El ID debe ser un número.")
        return
    nombre = " ".join(args[1:])
    vendedor = get_vendedor(update)
    ok = aprobar_cliente(telegram_id, nombre, "", vendedor)
    if ok:
        await update.message.reply_text(f"✅ *{nombre}* (ID: {telegram_id}) añadido a la lista.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"ℹ️ {nombre} ya estaba en la lista.")


@solo_vendedores
async def cmd_bloquear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Uso: /bloquear <telegram_id>"""
    args = context.args
    if not args:
        await update.message.reply_text("❌ Uso: /bloquear <telegram_id>\nEjemplo: /bloquear 123456789")
        return
    try:
        telegram_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ El ID debe ser un número.")
        return
    ok = bloquear_cliente(telegram_id)
    if ok:
        await update.message.reply_text(f"🚫 ID {telegram_id} eliminado de la lista.")
    else:
        await update.message.reply_text(f"ℹ️ Ese ID no estaba en la lista.")


@solo_vendedores
async def cmd_clientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista todos los clientes aprobados"""
    clientes = get_clientes_aprobados()
    if not clientes:
        await update.message.reply_text("📋 No hay clientes aprobados aún.")
        return
    texto = "📋 *Clientes aprobados:*\n\n"
    for tid, nombre, username, aprobado_por, fecha in clientes:
        user_str = f"@{username}" if username else "sin username"
        texto += f"• *{nombre}* ({user_str})\n  ID: `{tid}` | Añadido por: {aprobado_por}\n\n"
    await update.message.reply_text(texto, parse_mode="Markdown")


def main():
    init_db()
    app = Application.builder().token(TOKEN_GESTION).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'(?i)^vapers$'), start)],
        states={
            MENU_GESTION:      [CallbackQueryHandler(menu_gestion)],
            VENTA_SABOR:       [CallbackQueryHandler(venta_sabor)],
            VENTA_CANTIDAD:    [CallbackQueryHandler(venta_cantidad)],
            PEDIDOS_MENU:      [CallbackQueryHandler(pedidos_menu)],
            STATS_MENU:        [CallbackQueryHandler(stats_menu)],
            MAYORISTA_SABORES:  [CallbackQueryHandler(mayorista_sabores)],
            CONFIRMAR_UBICACION: [MessageHandler(filters.TEXT & ~filters.COMMAND, editar_ubicacion)],
            VENTA_MAYOR_MANUAL:  [CallbackQueryHandler(venta_mayorista_manual)],
            STOCK_AÑADIR_SABOR:  [CallbackQueryHandler(stock_añadir_sabor)],
            STOCK_AÑADIR_CANT:   [CallbackQueryHandler(stock_añadir_cant)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(callback_aprobacion, pattern=r"^(aprc|rchz)_\d+$"))
    app.add_handler(CommandHandler("aprobar",  cmd_aprobar))
    app.add_handler(CommandHandler("bloquear", cmd_bloquear))
    app.add_handler(CommandHandler("clientes", cmd_clientes))
    print("🤖 Bot de gestión arrancado...")
    app.run_polling()


if __name__ == "__main__":
    main()
