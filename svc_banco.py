"""
Author: Vitor Emanuel Ferreira Vital
Email: vitoremanuelg147@gmail.com
Date: 01/2024
"""

import grpc
from concurrent import futures
import sys
import os
import threading

import banco_pb2
import banco_pb2_grpc

# definições
MIN_ARGS = 2

SUCCESS = 0
NON_EXISTENT = -1
INVALID_BALANCE = -2
INVALID_WALLET = -3

INADDR_ANY = '0.0.0.0' # IP que permite conexão com todo IP associado a máquina no qual está executando

# classe de servidor gRPC no qual as operações do banco estão implementadas
class Banco(banco_pb2_grpc.BancoServicer):
    
    def __init__(self) -> None:
        """
        Inicializa uma instância da classe Banco.

        Atributos:
            wallets (dict[str, int]): Um dicionário que mapeia identificadores de carteiras (strings) para seus saldos (inteiros).
            pay_orders (dict[int, int]): Um dicionário que mapeia IDs de ordens de pagamento (inteiros) para valores de pagamento (inteiros).
            order_id (int): Um contador para gerar IDs únicos para novas ordens de pagamento, começando em 1.
            stop_event (threading.Event): Um evento de sincronização utilizado para controlar o término do servidor.
        """
        self.wallets: dict[str, int] = dict()
        self.pay_orders: dict[int, int] = dict()
        self.order_id: int = 1
        self.stop_event = threading.Event()
        pass
    
    def get_balance(self, request, context):
        """
        Retorna o saldo de uma carteira específica.

        Args:
            request: O objeto de solicitação gRPC que contém o identificador da carteira (wallet_id).
            context: O contexto de chamada gRPC (não utilizado diretamente na função).

        Returns:
            banco_pb2.BalanceResponse: Um objeto de resposta gRPC que contém o saldo da carteira especificada.
                                       Se a carteira não existir, retorna um valor indicativo de 'NON_EXISTENT'(-1).
        """
        id = request.wallet_id
        balance = self.wallets.get(id, NON_EXISTENT)
        return banco_pb2.BalanceResponse(balance=balance)
    
    def create_payment_order(self,  request, context):
        """
        Cria uma ordem de pagamento para uma carteira específica.

        Args:
            request: O objeto de solicitação gRPC que contém o identificador da carteira (wallet_id) e o valor (amount) a ser pago.
            context: O contexto de chamada gRPC (não utilizado diretamente na função).

        Returns:
            banco_pb2.OrderResponse: Um objeto de resposta gRPC que contém o status da criação da ordem de pagamento.
                                     - Se a carteira não existir, retorna 'NON_EXISTENT'(-1).
                                     - Se o saldo for insuficiente, retorna 'INVALID_BALANCE'(-2).
                                     - Caso contrário, retorna o 'order_id' da nova ordem de pagamento.
        """
        wallet_id = request.wallet_id
        amount = request.amount
        
        balance = self.wallets.get(wallet_id, NON_EXISTENT)
        
        if balance is NON_EXISTENT:
            return banco_pb2.OrderResponse(status=NON_EXISTENT)
        if amount > balance:
            return banco_pb2.OrderResponse(status=INVALID_BALANCE)
        
        order_id = self._get_order_id()
        self.pay_orders[order_id] = amount
        self.wallets[wallet_id] -= amount
        
        return banco_pb2.OrderResponse(status=order_id)
    
    def transfer(self, request, context):
        """
        Realiza a transferência de um valor confirmado para uma carteira específica, associada a uma ordem de pagamento.

        Args:
            request: O objeto de solicitação gRPC que contém:
                - order_id: O identificador da ordem de pagamento.
                - confirmation_amount: O valor que deve ser transferido.
                - wallet_id: O identificador da carteira de destino.
            context: O contexto de chamada gRPC (não utilizado diretamente na função).

        Returns:
            banco_pb2.TransferResponse: Um objeto de resposta gRPC que contém o status da transferência.
                - Se a ordem não existir, retorna 'NON_EXISTENT'(-1).
                - Se o valor da ordem não corresponder ao valor de confirmação, retorna 'INVALID_BALANCE'(-2).
                - Se a carteira de destino não existir, retorna 'INVALID_WALLET'(-3).
                - Se a transferência for bem-sucedida, retorna 'SUCCESS'(0).
        """
        order_id = request.order_id
        confirmation_amount = request.confirmation_amount
        wallet_id = request.wallet_id
        
        value_order = self.pay_orders.get(order_id, NON_EXISTENT)
        
        if value_order is NON_EXISTENT:
            return banco_pb2.TransferResponse(status=NON_EXISTENT)
        
        if value_order != confirmation_amount:
            return banco_pb2.TransferResponse(status=INVALID_BALANCE)
        
        if wallet_id not in self.wallets:
            return banco_pb2.TransferResponse(status=INVALID_WALLET)
        
        self.wallets[wallet_id] += confirmation_amount
        del self.pay_orders[order_id]
        
        return banco_pb2.TransferResponse(status=SUCCESS)

    def end_execution(self, request, context):
        """
        Finaliza a execução do servidor, imprimindo os saldos das carteiras e sinalizando o evento de parada.
    
        Args:
            request: O objeto de solicitação gRPC (não utilizado diretamente na função).
            context: O contexto de chamada gRPC (não utilizado diretamente na função).
    
        Returns:
            banco_pb2.EndExecutionResponse: Um objeto de resposta gRPC contendo o número de ordens de pagamento pendentes (`pending_orders`).
        """
        for wallet_id, balance in self.wallets.items():
            print(f"{wallet_id} {balance}")
            
        self.stop_event.set()
        
        pending_orders = len(self.pay_orders)
        return banco_pb2.EndExecutionResponse(pending_orders=pending_orders)
    
    def _get_order_id(self):
        """
        Gera um novo ID de ordem de pagamento de forma incremental.

        Returns:
            int: O próximo ID de ordem de pagamento disponível.
        """
        self.order_id += 1
        return self.order_id - 1
    
    def read_wallets(self, input_stream):
        """
        Lê dados de carteiras a partir de um fluxo de entrada e os armazena no dicionário de carteiras.

        Args:
            input_stream: Um iterável de linhas de texto (por exemplo, um arquivo ou lista de strings), 
                          onde cada linha contém um ID de carteira e um saldo inicial separados por espaço.
        """
        for line in input_stream:
            wallet_data = line.strip().split()
            
            if len(wallet_data) != MIN_ARGS:
                continue
            
            wallet_id, balance = wallet_data[0], int(wallet_data[1])
            self.wallets[wallet_id] = balance
        
    
    def serve(self, port, ip=INADDR_ANY, max_workers=10):
        """
        Inicia o servidor gRPC e aguarda a sua parada.

        Args:
            port (int): A porta na qual o servidor deve escutar.
            ip (str): O endereço IP no qual o servidor deve escutar. O padrão é `INADDR_ANY`, 
                      que permite que o servidor escute em todos os endereços IP disponíveis.
            max_workers (int): O número máximo de threads trabalhadoras no pool de threads. O padrão é 10.
        """
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
        banco_pb2_grpc.add_BancoServicer_to_server(self, server)
        server.add_insecure_port(f'{ip}:{str(port)}')
        server.start()
        
        self.stop_event.wait()
        server.stop(grace=5)

def use():
    print(f"Usage: python3 {sys.argv[0]} <port>")
    print("Port must be between 2048 and 65535.")


def parse_args(args: list[str]):
    """
    Analisa a lista de argumentos para verificar a validade e extrair a porta do servidor.

    Args:
        args (list[str]): Uma lista de strings representando os argumentos fornecidos ao script. 
                          O segundo argumento deve ser a porta na qual o servidor irá escutar.

    Returns:
        int: A porta extraída dos argumentos, se for válida.
    """
    if len(args) != MIN_ARGS:
        use(); exit(1)
        
    port = int(args[1])

    if port < 2048 or port > 65535:
        use(); exit(1)
    
    return port


def main():
    port = parse_args(sys.argv)
    banco_svc = Banco()
    banco_svc.read_wallets(sys.stdin)
    banco_svc.serve(port=port)

if __name__ == "__main__":
    main()