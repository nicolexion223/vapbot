"""
Arranca los dos bots a la vez en hilos separados.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

import asyncio

import threading
import bot_clientes
import bot_gestion

def run_clientes():
    asyncio.set_event_loop(asyncio.new_event_loop())
    bot_clientes.main()

def run_gestion():
    asyncio.set_event_loop(asyncio.new_event_loop())
    bot_gestion.main()

if __name__ == "__main__":
    t1 = threading.Thread(target=run_clientes)
    t2 = threading.Thread(target=run_gestion)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
