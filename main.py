import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

import multiprocessing
import bot_clientes
import bot_gestion

def run_clientes():
    bot_clientes.main()

def run_gestion():
    bot_gestion.main()

if __name__ == "__main__":
    p1 = multiprocessing.Process(target=run_clientes)
    p2 = multiprocessing.Process(target=run_gestion)
    p1.start()
    p2.start()
    p1.join()
    p2.join()
