"""
Author: Vitor Emanuel Ferreira Vital
Email: vitoremanuelg147@gmail.com
Date: 01/2024
"""

import grpc
from concurrent import futures
import sys
import threading

import loja_pb2, loja_pb2_grpc
import banco_pb2, banco_pb2_grpc

# definições
MIN_ARGS = 5

SUCCESS = 0
NON_EXISTENT = -1
INVALID_BALANCE = -2
INVALID_WALLET = -3

INADDR_ANY = '0.0.0.0' # IP que permite conexão com todo IP associado a máquina no qual está executando

# classe de servidor gRPC no qual as operações da loja estão implementadas
class Loja(loja_pb2_grpc.LojaServicer):
    
    def __init__(self, price, seller_account, bank_add) -> None:
        """
        Inicializa uma instância da classe `Loja`.

        Este construtor configura a loja com o preço dos produtos, a conta do vendedor e o endereço do servidor bancário.
        Também estabelece a comunicação com o servidor bancário e inicializa o saldo do vendedor.

        Args:
            price (int): O preço dos produtos ou serviços oferecidos pela loja.
            seller_account (str): A conta do vendedor usada para identificar a loja no servidor bancário.
            bank_add (str): O endereço do servidor bancário para comunicação.

        Atributos:
            price (int): O preço dos produtos ou serviços oferecidos pela loja.
            seller_account (str): A conta do vendedor associada à loja.
            bank_add (str): O endereço do servidor bancário.
            seller_balance (int): O saldo da conta do vendedor, inicializado em 0.
            bank_channel (grpc.Channel): Canal de comunicação com o servidor bancário.
            bank_stub (banco_pb2_grpc.BancoStub): Stub para chamadas RPC ao servidor bancário.
            stop_event (threading.Event): Evento usado para sinalizar o término da execução.
        """
        self.price = price
        self.seller_account = seller_account
        self.bank_add = bank_add
        
        self.seller_balance = 0
        
        self.bank_channel = grpc.insecure_channel(bank_add)
        self.bank_stub = banco_pb2_grpc.BancoStub(self.bank_channel)
        
        self._init_balance()
        self.stop_event = threading.Event()
    
    def get_price(self, request, context):
        """
        Retorna o preço dos produtos ou serviços oferecidos pela loja.

        Este método é chamado para obter o preço atual definido para a loja.

        Args:
            request (loja_pb2.PriceRequest): Solicitação contendo informações sobre o pedido.
            context (grpc.ServicerContext): Contexto da solicitação RPC.

        Returns:
            loja_pb2.PriceResponse: Resposta contendo o preço atual da loja.
        """
        return loja_pb2.PriceResponse(price=self.price)
    
    def sale(self, request, context):
        """
        Processa uma venda na loja, realizando uma transferência do valor da venda para a conta do vendedor.

        O método tenta transferir o valor da venda para a conta do vendedor através do banco. Se a transferência for bem-sucedida, 
        o saldo do vendedor é atualizado e a resposta indica sucesso. Caso contrário, a resposta reflete o status de falha.

        Args:
            request (loja_pb2.SaleRequest): Solicitação contendo o ID do pedido a ser processado.
            context (grpc.ServicerContext): Contexto da solicitação RPC.

        Returns:
            loja_pb2.SaleResponse: Resposta contendo o status da operação e o valor recebido. Se a transferência falhar, o valor recebido será 0.
        """
        order_id = request.order_id
        
        transfer_request = banco_pb2.TransferRequest(
            order_id=order_id,
            confirmation_amount=self.price,
            wallet_id=self.seller_account
        )
        
        try:
            response = self.bank_stub.transfer(transfer_request)
            if response.status == SUCCESS:
                self.seller_balance += self.price
                return loja_pb2.SaleResponse(status=SUCCESS, amount_received=self.price)
            else:
                return loja_pb2.SaleResponse(status=response.status, amount_received=0)
        except grpc.RpcError as e:
            return loja_pb2.SaleResponse(status=-9, amount_received=0)

    def end_execution(self, request, context):
        """
        Finaliza a execução da loja e solicita o status final dos pedidos pendentes ao servidor bancário.

        O método envia uma solicitação de finalização ao servidor bancário para obter o número de pedidos pendentes. Em seguida, 
        atualiza o estado de parada da loja e retorna o saldo do vendedor e o status do servidor bancário.

        Args:
            request (loja_pb2.EndExecutionRequest): Solicitação RPC para finalizar a execução, sem parâmetros adicionais necessários.
            context (grpc.ServicerContext): Contexto da solicitação RPC.

        Returns:
            loja_pb2.EndExecutionResponse: Resposta RPC contendo o saldo do vendedor e o status final do servidor bancário. 
                                           Se ocorrer um erro ao comunicar com o servidor bancário, o status será -1.
        """
        end_request = banco_pb2.EndExecutionRequest()
        try:
            end_response = self.bank_stub.end_execution(end_request)
            bank_status = end_response.pending_orders
        except grpc.RpcError as e:
            bank_status = -1
            
        self.stop_event.set()
            
        return loja_pb2.EndExecutionResponse(
            seller_balance=self.seller_balance,
            bank_server_status=bank_status
        )
        
    def _init_balance(self):
        """
        Inicializa o saldo do vendedor a partir do servidor bancário.

        Este método envia uma solicitação ao servidor bancário para obter o saldo do vendedor associado à conta. Se a resposta indicar que o saldo não existe, 
        o método não altera o saldo. Caso contrário, o saldo obtido é armazenado na variável `self.balance`.

        O método termina o programa caso dê erro ao comunicar com o servidor bancário.
        """
        request = banco_pb2.BalanceRequest(wallet_id=self.seller_account)
        try:
            response = self.bank_stub.get_balance(request)
            if response.balance is not NON_EXISTENT:
                self.balance = response.balance
        except grpc.RpcError as e:
            sys.exit()
    
    def serve(self, port, ip=INADDR_ANY, max_workers=10):
        """
        Inicia o servidor gRPC da loja e aguarda a finalização da execução.

        Este método configura e inicia o servidor gRPC para a loja, adiciona o serviço da loja ao servidor e o faz escutar na porta e IP especificados. 
        O servidor será executado com um número máximo de threads especificado. O método aguarda um evento de parada (`self.stop_event`) para parar o servidor graciosamente 
        após a conclusão das operações.

        Args:
            port (int): Porta na qual o servidor gRPC deve escutar.
            ip (str, opcional): Endereço IP no qual o servidor deve escutar. O padrão é `INADDR_ANY`, que permite escutar em todos os IPs disponíveis.
            max_workers (int, opcional): Número máximo de threads no pool do servidor. O padrão é 10.
        """
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
        loja_pb2_grpc.add_LojaServicer_to_server(self, server)
        server.add_insecure_port(f'{ip}:{str(port)}')
        server.start()
        
        self.stop_event.wait()
        server.stop(grace=5)
        

def use():
    print(f"Usage: python3 {sys.argv[0]} <price> <port> <id_seller_account> <id_bank_server>")
    print("Port must be between 2048 and 65535.")


def parse_args(args: list[str]):
    """
    Analisa os argumentos da linha de comando para configurar o cliente da loja.

    Este método verifica a validade e a quantidade de argumentos fornecidos, e os analisa para extrair as informações necessárias. 
    Se o número de argumentos não estiver correto ou se o valor da porta estiver fora do intervalo permitido, o método exibe a mensagem de uso e encerra o programa com um código de saída 1.

    Args:
        args (list[str]): Lista de argumentos passados na linha de comando.

    Returns:
        tuple: Uma tupla contendo:
            - price (int): O preço do item.
            - port (int): A porta na qual o servidor deve escutar.
            - seller_account (str): O ID da conta do vendedor.
            - bank_add (str): O endereço do servidor bancário.
    """
    if len(args) != MIN_ARGS:
        use(); exit(1)
    
    price = int(args[1])    
    port = int(args[2])
    seller_account = args[3]
    bank_add = args[4]

    if port < 2048 or port > 65535:
        use(); exit(1)
    
    return price, port, seller_account, bank_add


def main():
    price, port, seller_account, bank_add = parse_args(sys.argv)
    loja_svc = Loja(price, seller_account, bank_add)
    loja_svc.serve(port=port)

if __name__ == "__main__":
    main()