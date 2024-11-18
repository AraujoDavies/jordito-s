from nosql import redis_conn

from api_betfair import callAping, dados_mercado

import json

from datetime import datetime, timedelta
from helper_telegram import enviar_no_telegram
from time import sleep

import logging
import os
import platform

# variaveis de ambiente
# ANALISE_TEMPO_ANTES_DO_JOGO -> vai considerar analisar o jogo quantos minutos antes de iniciar ? 
# MO_LIQUIDEZ -> Qual liquidez minima para considerar o sinal ?
# ODD_MIN_OVER_LIMIT_HT -> ODD do over 
# ODD_MIN_DO_FAVORITO -> odd do favorito
# TELEGRAM_CHAT_ID -> onde enviar mensagens
# VERIFICAR_A_CADA_X_TEMPO -> faz a verificação e espera alguns minutos para verificar de novo

# MO - Fav abaixo de 1.60
# Odd 0.5HT - abaixo de 1.39 
# CS - Lay 1x0 do Fav pré Live

# Critérios de saída: HT
diahr = datetime.now().strftime("%d%m%Y")
logname = f'jordito{diahr}.log' if platform.system() == 'Windows' else f'/app/jordito{diahr}.log'
logging.basicConfig(
    filename=logname,
    level=logging.WARNING,
    encoding='utf-8',
    format='%(asctime)s - %(levelname)s: %(message)s',
)

sinais_enviados = []
ignore_events = []


while True:
    logging.warning('------------------------')
    odd_fav = float(os.getenv('ODD_MIN_DO_FAVORITO'))
    dt = datetime.now()
    dt2 = dt + timedelta(days=1)
    from_date, to_date = dt.strftime("%Y-%m-%dT00:00:00"), dt2.strftime("%Y-%m-%dT23:59:00")

    rpc = """
    {
        "jsonrpc": "2.0",
        "method": "SportsAPING/v1.0/listEvents",
        "params": {
            "filter": {
                "eventTypeIds": [
                    "1"
                ],
                "marketStartTime": {
                    "from": "{from_date}",
                    "to": "{to_date}"
                }
            }
        },
    "id": 1}
    """.replace('{from_date}', from_date).replace('{to_date}', to_date)

    jogos_48h = callAping(rpc)
    jogos_48h = json.loads(jogos_48h)


    analise_jogos = []


    for jogo in jogos_48h['result']:
        # converter open_date em datetime com GMT-3 e verificar se falta menos de 1h para o evento
        open_date = jogo['event']['openDate']

        datetime_event_start = datetime.strptime(open_date, '%Y-%m-%dT%H:%M:%S.000Z') - timedelta(hours=3)
        
        if datetime_event_start.day == datetime.now().day:
            if datetime_event_start > datetime.now(): # Se jogo ainda nao começou
                datetime_diff = datetime_event_start - datetime.now()
                tempo_antes = 60 * int(os.getenv('ANALISE_TEMPO_ANTES_DO_JOGO'))
                if datetime_diff.seconds < tempo_antes: # 2700 sec = 45 min
                    event_id = jogo['event']['id']
                    if event_id not in ignore_events:
                        minutos = datetime_diff.seconds / 60
                        logging.warning('Analisando: %s - %s', jogo['event']['name'], minutos)
                        analise_jogos.append(event_id) # guarda o ID para consultar posteriormente


    analise_events = []

    for event_id in analise_jogos:
        if event_id in ignore_events:
            continue

        rpc = """
        {
            "jsonrpc": "2.0",
            "method": "SportsAPING/v1.0/listMarketCatalogue",
            "params": {
                "filter": {
                    "eventIds": [
                        "{event_id}"
                    ]
                },
                "maxResults": "200",
                "marketProjection": [
                    "COMPETITION",
                    "EVENT",
                    "EVENT_TYPE",
                    "RUNNER_DESCRIPTION",
                    "RUNNER_METADATA",
                    "MARKET_START_TIME"
                ]
            },
            "id": 1
        }
        """.replace('{event_id}', event_id)

        informacoes = callAping(rpc)

        informacoes = json.loads(informacoes)

        evento = {
        'id': '',
        'nome': '' , 

        'mo_market_id': '',
        'mo_odd_home': '', 
        'mo_odd_away': '', 
        'mo_liquidez': '',

        'cs_market_id': '',
        'cs_liquidez': '',
        'cs_oddback_1x0': '',
        'cs_oddback_0x1': '',
        'cs_oddlay_1x0': '',
        'cs_oddlay_0x1': '',
        
        'moht_market_id': '',
        'moht_odd_home': '',
        'moht_odd_away': '',

        'overltht_odd': '',

        'status_ht': '',
        }

        evento['id'] = event_id
        mo = 'Match Odds'
        moht = 'Half Time'
        over_ht = 'First Half Goals 0.5'
        cs = 'Correct Score'
        favorito = ''
        consulta_erro = False # variavel de controle para o caso de não coletar dados

        # MO - Fav abaixo de 1.60
        # Odd 0.5HT - abaixo de 1.39 
        # CS - Lay 1x0 do Fav pré Live

        # Critérios de saída: HT

        for info in informacoes['result']:
            evento['nome'] = info['event']['name']

            if info['marketName'] == moht:
                evento['moht_market_id'] = info['marketId']

            if info['marketName'] == mo:
                try:
                    evento['mo_market_id'] = info['marketId']
                    evento['mo_liquidez'] = info['totalMatched'] # Liquidez em real

                    mo_liquidez_config = float(os.getenv("MO_LIQUIDEZ"))
                    if evento['mo_liquidez'] < mo_liquidez_config:
                        logging.warning('Pouca liquidez para o evento - %s', evento['nome'])
                        ignore_events.append(event_id)
                        break
                    
                    detalhes_mo = dados_mercado(evento['mo_market_id'])
                    
                    evento['mo_odd_home'] = detalhes_mo['result'][0]['runners'][0]['ex']['availableToBack'][0]['price'],
                    evento['mo_odd_away'] = detalhes_mo['result'][0]['runners'][1]['ex']['availableToBack'][0]['price'],

                    if type(evento['mo_odd_home']) == tuple:
                        evento['mo_odd_home'] = evento['mo_odd_home'][0]
                        evento['mo_odd_away'] = evento['mo_odd_away'][0]

                    if evento['mo_odd_home'] <= odd_fav:
                        favorito = 'home'
                    elif evento['mo_odd_away'] <= odd_fav:
                        favorito = 'away'
                    else:
                        logging.warning('Sem favoritos para o evento - %s', evento['nome'])
                        ignore_events.append(event_id)
                        break
                except:
                    logging.error('MO - Não encontrou dados para o evento %s', evento['nome'])
                    consulta_erro = True
                    break

        for info in informacoes['result']:
            if event_id in ignore_events or consulta_erro: # id não está valido para consultas na API
                break # pula

            if info['marketName'] == over_ht:
                try:
                    detalhes_overht = dados_mercado(info['marketId'])
                    evento['overltht_odd'] = detalhes_overht['result'][0]['runners'][1]['ex']['availableToBack'][0]['price']
                    odd_over_ht = float(os.getenv("ODD_MIN_OVER_LIMIT_HT"))
                    if evento['overltht_odd'] > odd_over_ht:
                        logging.warning('ODD do over limite muito alta - %s', evento['nome'])
                        ignore_events.append(event_id)
                        break
                except:
                    logging.error('OVER HT - Não encontrou dados para o evento %s', evento['nome'])
                    consulta_erro = True
                    break


        for info in informacoes['result']:
            if event_id in ignore_events or consulta_erro: # id não está valido para consultas na API
                break # pula

            if info['marketName'] == cs:
                try:
                    evento['cs_market_id'] = info['marketId']
                    evento['cs_liquidez'] = info['totalMatched'] # Liquidez em real
                    detalhes_cs = dados_mercado(evento['cs_market_id'])
                    evento['cs_oddlay_0x1'] = detalhes_cs['result'][0]['runners'][1]['ex']['availableToLay'][0]['price']
                    evento['cs_oddlay_1x0'] = detalhes_cs['result'][0]['runners'][4]['ex']['availableToLay'][0]['price']
                    evento['cs_oddback_0x1'] = detalhes_cs['result'][0]['runners'][1]['ex']['availableToBack'][0]['price']
                    evento['cs_oddback_1x0'] = detalhes_cs['result'][0]['runners'][4]['ex']['availableToBack'][0]['price']
                    # Talvez acrescente uma tratativa de liquidez aqui futuramente
                except:
                    logging.error('CS - Não encontrou dados para o evento %s', evento['nome'])
                    consulta_erro = True
                    break


            if info['marketName'] == moht:
                try:
                    detalhes_moht = dados_mercado(info['marketId'])
                    evento['moht_odd_home'] = detalhes_moht['result'][0]['runners'][0]['ex']['availableToBack'][0]['price']
                    evento['moht_odd_away'] = detalhes_moht['result'][0]['runners'][1]['ex']['availableToBack'][0]['price']
                except:
                    logging.error('MO HT - Não encontrou dados para o evento %s', evento['nome'])
                    consulta_erro = True
                    break

        if event_id not in ignore_events and consulta_erro == False:
            # logging.critical(evento)
            analise_events.append(evento)


    # enviar sinal
    for evento in analise_events:
        # identificar o favorito
        try:
            if evento['mo_odd_home'] <= odd_fav:
                favorito = 'home'
                evento['favorito'] = favorito
            elif evento['mo_odd_away'] <= odd_fav:
                favorito = 'away'
                evento['favorito'] = favorito
            else:
                logging.critical('ERRO DE FAVORITO %s', evento)
                continue
        except:
            logging.critical(f'ERRO DE TIPO NO EVENTO: {evento}')
            continue

        cs_gap = int(os.getenv('GAP_MAXIMO_NO_CS'))
        msg = """
🎸 Jordito's Encontrado! 🎸

⚽️ {nome} ⚽️

🎯 Lay {placar}: @{cs_odd} 🎯

🦓 Back Zebra HT: @{moht_odd} 🦓
"""
        odd_max_cs = float(os.getenv('ODD_MAX_CS'))
        if favorito == 'home':
            odd_diff = evento['cs_oddlay_1x0'] - evento['cs_oddback_1x0'] 
            if evento['cs_oddlay_1x0'] > odd_max_cs:
                logging.warning(f"ODD do Evento {evento['nome']} ({evento['cs_oddlay_1x0']}) excede odd máx {odd_max_cs}")
                continue
            msg = msg.replace('{nome}', evento['nome']).replace('{cs_odd}', str(evento['cs_oddlay_1x0'])).replace('{moht_odd}', str(evento['moht_odd_away'])).replace('{placar}', '1x0')

        elif favorito == 'away':
            odd_diff = evento['cs_oddlay_0x1'] - evento['cs_oddback_0x1'] 
            if evento['cs_oddlay_0x1'] > float(os.getenv('ODD_MAX_CS')):
                logging.warning(f"ODD do Evento {evento['nome']} ({evento['cs_oddlay_0x1']}) excede odd máx {odd_max_cs}")
                continue
            msg = msg.replace('{nome}', evento['nome']).replace('{cs_odd}', str(evento['cs_oddlay_0x1'])).replace('{moht_odd}', str(evento['moht_odd_home'])).replace('{placar}', '0x1')

        if odd_diff > cs_gap: 
            continue
        telegram_chat = os.getenv('TELEGRAM_CHAT_ID')
        tele = enviar_no_telegram(telegram_chat, msg)
        # print(tele)
        # print(type(tele))
        # print(msg)
        if tele > 0:
            logging.warning('enviou sinal: %s', evento)
            evento['status_ht'] = 'EM_ANDAMENTO'
            ignore_events.append(evento['id'])
            sinais_enviados.append(evento)
            jordito_id = str(datetime.now().timestamp()).split('.')[0]
            jordito_id = f"jordito:{jordito_id}"
            redis_conn.hset(
                jordito_id,
                mapping=evento,
            )
            logging.warning('Salvou no redis: %s', jordito_id)
            sleep(1)

    tempo_verificacao = int(os.getenv('VERIFICAR_A_CADA_X_TEMPO')) * 60
    logging.warning('Aguardando %s minutos para próxima verificação', os.getenv('VERIFICAR_A_CADA_X_TEMPO'))
    sleep(tempo_verificacao)