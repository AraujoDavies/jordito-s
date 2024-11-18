import os
from time import sleep
from api_betfair import dados_mercado
from nosql import redis_conn
import logging
from helper_telegram import enviar_no_telegram
import platform

if platform.system() == 'Windows':
  from dotenv import load_dotenv
  load_dotenv()


logging.basicConfig(
    level=logging.WARNING,
    encoding='utf-8',
    format='%(asctime)s - %(levelname)s: %(message)s',
)

# {'id': '33761138',
#  'nome': 'France v Israel',
#  'mo_market_id': '1.235689324',
#  'mo_odd_home': '1.15',
#  'mo_odd_away': '24.0',
#  'mo_liquidez': '5253092.350000001',
#  'cs_market_id': '1.235689333',
#  'cs_liquidez': '135509.39025000003',
#  'cs_oddback_1x0': '12.0',
#  'cs_oddback_0x1': '70.0',
#  'cs_oddlay_1x0': '12.5',
#  'cs_oddlay_0x1': '85.0',
#  'moht_market_id': '1.235689305',
#  'moht_odd_home': '1.46',
#  'moht_odd_away': '16.5',
#  'overltht_odd': '1.21',
#  'status_ht': 'EM_ANDAMENTO',
#  'favorito': 'home'}


while True:
     for jordito_id in redis_conn.scan_iter("jordito:*"):
          evento = redis_conn.hgetall(jordito_id)
          
          if evento['status_ht'] == 'FINALIZADO': 
               logging.warning('%s já finalizado', jordito_id)
               continue               

          dados = dados_mercado(evento['moht_market_id'])

          enviar_sinal = False
          if dados['result'][0]['status'].upper() == 'CLOSED':
               if evento['favorito'] == 'home': # fav mandante perdendo ou empatando
                    if dados['result'][0]['runners'][0]['status'].upper() == 'LOSER':
                         enviar_sinal = True

               if evento['favorito'] == 'away': # fav visitante perdendo ou empatando
                    if dados['result'][0]['runners'][1]['status'].upper() == 'LOSER':
                         enviar_sinal = True

               evento['status_ht'] = 'FINALIZADO'
               redis_conn.hset(
                    jordito_id,
                    mapping=evento,
               )

          if enviar_sinal == True:
               msg = """
⭐️ Back Favorito 2°T ⭐️

⚽️ {nome} ⚽️

🎯 Empatado = 1un

🦓 1x0 = 0,5un 
🦓 2x0 = 0,25un 
🦓 3x0 = 0,1un 

LINK: https://www.betfair.com/exchange/plus/football/market/{market_id}
"""

               msg = msg.replace('{nome}', evento['nome']).replace('{market_id}', evento['mo_market_id'])
               tele = enviar_no_telegram(os.getenv('TELEGRAM_CHAT_ID_BACKFAV'), msg)

               if tele > 0:
                    logging.warning('Sinal enviado %s', jordito_id)
               else:
                    logging.critical('Sinal não enviado %s', jordito_id)

     x = 500
     logging.warning(f'Proxima rotina em {x} segundos')
     sleep(x)