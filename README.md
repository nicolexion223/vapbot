# 🤖 VAP SOLO SESEÑA — Bot de Telegram

Sistema completo de pedidos y gestión de stock para VAP SOLO SESEÑA.

## Estructura

```
vapbot/
├── database.py       # Base de datos SQLite + lógica de precios
├── bot_clientes.py   # Bot público para clientes
├── bot_gestion.py    # Bot privado para vendedores
├── main.py           # Arranca los dos bots a la vez
├── requirements.txt
└── .env.example      # Variables de entorno necesarias
```

---

## 🚀 Instalación paso a paso

### 1. Crear los dos bots en Telegram

1. Abre [@BotFather](https://t.me/BotFather) en Telegram
2. Escribe `/newbot` → ponle nombre → ej: `VAP SOLO SESEÑA`
3. Guarda el **token** que te da → es `TOKEN_BOT_CLIENTES`
4. Repite → crea otro bot llamado `VAP SOLO Gestión`
5. Guarda ese token → es `TOKEN_BOT_GESTION`

### 2. Obtener los IDs de Telegram de los vendedores

1. Cada vendedor abre [@userinfobot](https://t.me/userinfobot) en Telegram
2. Escribe `/start` → te dice tu ID numérico
3. Apunta los tres IDs

### 3. Configurar las variables de entorno

```bash
cp .env.example .env
# Edita .env y rellena todos los valores
```

### 4. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 5. Arrancar en local (para probar)

```bash
python main.py
```

---

## ☁️ Despliegue en Railway (gratis, 24/7)

1. Crea cuenta en [railway.app](https://railway.app)
2. Nuevo proyecto → **Deploy from GitHub repo**
3. Sube este código a un repo de GitHub
4. En Railway → **Variables** → añade todas las del `.env`
5. Deploy → listo, funciona 24/7

---

## 📱 Cómo usar

### Bot de clientes
- `/start` → menú principal
- Elegir entre pedido normal o caja mayorista
- Seleccionar sabor → ver foto + stock
- Elegir cantidad, vendedor, método de pago, día y hora
- Confirmar → llega notificación a los 3 vendedores

### Bot de gestión (solo Nico, Alex, Edu)
- `/start` → menú de gestión
- **Registrar venta** → elige sabor y cantidad → descuenta stock automáticamente
- **Ver mi stock** → tu stock personal por sabor
- **Stock total** → stock de los tres
- **Pedidos pendientes** → pedidos de clientes por confirmar
- **Ventas de hoy** → resumen del día

---

## 💰 Tarifas configuradas

| Cantidad | Precio |
|----------|--------|
| 1 unidad | 12€    |
| 2 unidades | 20€  |
| 3 unidades | 32€  |
| 4 unidades | 40€  |
| 5 unidades | 52€  |
| Caja 10u mezcladas | 80€ |

---

## 📦 Stock inicial

| Sabor | Stock por persona |
|-------|------------------|
| Raspberry Watermelon | 20 |
| Strawberry Kiwi | 20 |
| Lemon Lime | 20 |
| Strawberry Vanilla Cola | 20 |  
| Peach Mango Pineapple | 20 |
| Kiwi Passionfruit | 20 |
| Strawberry Banana | 20 |
| Peach Berry | 20 |
| Frambuesa Sandía | 20 |
| Redbull | 10 |
| Love 66 | 10 |
| Black Berry Blueberry Ice | 10 |
| Triple Cherry | 10 |
| Blueberry Ice | 10 |
| Blueberry Cherry Cranberry | 10 |
| Blueberry Blackcurrant Ice | 10 |
| Strawberry Watermelon | 10 |
| Black Ice Dragonfruit Strawberry | 10 |
| Grape Burst | 10 |
| Double Apple | 10 |
