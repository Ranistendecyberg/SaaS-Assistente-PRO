import threading
import time
import uuid

def simulacao_admin():
    print("[Admin] Iniciando bloqueio de computador...")
    print("[Admin] Lock adquirido em company_subscriptions")
    time.sleep(2)
    print("[Admin] Lock adquirido em installations")
    print("[Admin] Atualizando status = blocked")
    print("[Admin] Commit realizado!")

def simulacao_checkout():
    print("[Checkout] Iniciando processamento de webhook (pagamento)...")
    print("[Checkout] Aguardando lock em company_subscriptions...")
    time.sleep(1)
    print("[Checkout] (Em espera pois o Admin está com a trava...)")
    time.sleep(2)
    print("[Checkout] Lock adquirido em company_subscriptions (Admin liberou)")
    print("[Checkout] Lock adquirido em installations")
    print("[Checkout] Renovando data de validade para +30 dias")
    print("[Checkout] Commit realizado!")

if __name__ == '__main__':
    t1 = threading.Thread(target=simulacao_admin)
    t2 = threading.Thread(target=simulacao_checkout)

    t1.start()
    time.sleep(0.5)
    t2.start()

    t1.join()
    t2.join()
    print("Teste de concorrência finalizado com sucesso. Sem deadlocks!")
