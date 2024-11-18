from os import getenv

import redis

redis_conn = redis.Redis(
    host=getenv('REDIS_HOST'), port=6379, decode_responses=True
)   # se começar dar b.o joga dentro da rota


# evento = {'id': '33761138', 'nome': 'France v Israel', 'mo_market_id': '1.235689324', 'mo_odd_home': 1.15, 'mo_odd_away': 24.0, 'mo_liquidez': 5106018.399375, 'cs_market_id': '1.235689333', 'cs_liquidez': 131796.46850000002, 'cs_oddback_1x0': 12.0, 'cs_oddback_0x1': 75.0, 'cs_oddlay_1x0': 12.5, 'cs_oddlay_0x1': 90.0, 'moht_market_id': '1.235689305', 'moht_odd_home': 1.46, 'moht_odd_away': 16.5, 'overltht_odd': 1.21, 'status': '', 'favorito': 'home'}

if __name__ == '__main__':
    x = 0
    for jordito_id in redis_conn.scan_iter("jordito:*"):
        print(jordito_id)

        x += 1
        evento = redis_conn.hgetall(jordito_id)
        evento['status_ht'] = 'EM_ANDAMENTO'
        redis_conn.hset(
            f'jordito:{x}',
            mapping=evento,
        )